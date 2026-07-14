from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
import users_dao, quests_dao, quest_sessions_dao, participations_dao, admin_dao
from models import User
from PIL import Image

# CONSTANTS
SIMULATED_NOW = datetime(2026, 8, 17, 9, 0)  # 17 August 2026, Monday, 09:00, in the fictional week
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LOCATIONS = ["Dragonslair", "Maester's Library", "The Labyrinth"]
QUEST_TYPES = ["combat", "exploration", "puzzle", "stealth", "magic", "survival"]
DIFFICULTIES = ["easy", "medium", "hard", "legendary"]
ROLE_CAPACITIES = {"Warrior": 4, "Mage": 3, "Healer": 2} #i decided to create a dictionary here

# IMAGE HANDLING
QUEST_IMG_HEIGHT = 300

# CREATE THE APPLICATION
app = Flask(__name__)
app.config["SECRET_KEY"] = "Dragonlaria's secret key"
login_manager = LoginManager()
login_manager.init_app(app)

# UNAUTHORIZED ROUTES (accessible to all) ─
# THE HOMEPAGE: will only show quests that match the filters + have at least one available session

@app.route("/")
def homepage(): 

    selected_quest_type = request.args.get("quest_type") or None
    selected_difficulty = request.args.get("difficulty") or None
    selected_day = request.args.get("day") or None
    selected_role = request.args.get("role") or None

    quests_db = quests_dao.get_all_quests(quest_type=selected_quest_type, difficulty=selected_difficulty, day=selected_day)

    if selected_role:
        quests_with_role = [] #this is the list that is going to be returned

        for q in quests_db:
            sessions = quest_sessions_dao.get_sessions_by_quest(q["quest_id"]) #sessions list

            for s in sessions:
                if selected_day and s["day"] != selected_day:
                    continue
                if quest_sessions_dao.get_remaining_places(s["session_id"], selected_role) > 0:
                    quests_with_role.append(q)
                    break 
        quests_db = quests_with_role

    return render_template("public/homepage.html", quests=quests_db, quest_types=QUEST_TYPES,
        difficulties=DIFFICULTIES, days=DAYS, roles=list(ROLE_CAPACITIES.keys()))

# THE CHOSEN QUEST PAGE : full details of the chosen quest and the available sessions
@app.route("/quests/<int:quest_id>")
def quest(quest_id):
    quest_db = quests_dao.get_quest_by_id(quest_id)
    if quest_db is None:
        flash("Quest not found", "danger")
        return redirect(url_for("homepage"))
    sessions = quest_sessions_dao.get_sessions_by_quest(quest_id)
    return render_template("public/quest.html", quest=quest_db, sessions=sessions)

# SESSION DETAIL PAGE: full details of the chosen session
@app.route("/sessions/<int:session_id>")
def session(session_id):
    session_db = quest_sessions_dao.get_session_by_id(session_id)
    if session_db is None:
        flash("Quest session not found", "danger")
        return redirect(url_for("homepage"))
    remaining = quest_sessions_dao.get_all_remaining_places(session_id)
    return render_template("public/session.html", session=session_db, remaining=remaining, roles=list(ROLE_CAPACITIES.keys()))

# THE SIGNUP PAGE
@app.route("/register")
def register():
    return render_template("login_register/register.html")

@app.route("/register", methods=["POST"])
def register_post():
    identifier = request.form.get("identifier", "").strip()
    password = request.form.get("password", "")

    if identifier == "" or password == "":
        flash("Email and password are required", "danger")
        return redirect(url_for("register"))

    if users_dao.identifier_exists(identifier):
        flash("An account already exists", "danger")
        return redirect(url_for("register"))

    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    users_dao.create_user(identifier, password_hash, "adventurer")

    flash("Account created, you can now log in", "success")
    return redirect(url_for("homepage"))

# AUTHORIZED ROUTES: ADVENTURER 
# Redirects GET requests to the session page (Flask-Login sends a GET here after login)
@app.route("/sessions/<int:session_id>/join", methods=["GET"])
@login_required
def join_session_get(session_id):
    return redirect(url_for("session", session_id=session_id))

# JOIN A QUEST SESSION
@app.route("/sessions/<int:session_id>/join", methods=["POST"])
@login_required
def join_session(session_id):
    session_db = quest_sessions_dao.get_session_by_id(session_id)
    if session_db is None:
        flash("Quest session not found", "danger")
        return redirect(url_for("homepage"))

    role_category = request.form.get("role_category")
    places_reserved = 2 if request.form.get("bring_guest") == "on" else 1

    if role_category not in ROLE_CAPACITIES: 
        flash("Please select a valid role", "danger")
        return redirect(url_for("session", session_id=session_id))

    ## control for if the adventurer has the right to enroll in another session
    if participations_dao.count_active_sessions_for_user(current_user.id) >= participations_dao.MAX_ACTIVE_SESSIONS:
        app.logger.error("Adventurer already has 3 active quest sessions")
        flash("You have already joined the maximum of 3 quest sessions this week", "danger")
        return redirect(url_for("session", session_id=session_id))
    ## control for if sessions have a time conflict
    if participations_dao.has_time_conflict(current_user.id, session_db["day"], session_db["start_time"], session_db["duration_minutes"]):
        app.logger.error("Adventurer has a time conflict with this session")
        flash("This session overlaps with a quest session you already joined", "danger")
        return redirect(url_for("session", session_id=session_id))
    ## control for if that role is available
    if not quest_sessions_dao.role_is_available(session_id, role_category, places_reserved):
        app.logger.error("Not enough places left for this role")
        flash("Not enough places left for this role", "danger")
        return redirect(url_for("session", session_id=session_id))

    success = participations_dao.create_participation(int(current_user.id), session_id, role_category, places_reserved)
    if success:
        app.logger.info("Participation created correctly")
        flash("You have joined the quest session!", "success")
    else:
        app.logger.error("Error while creating your participation, please try again!")
        flash("Something went wrong, please try again", "danger")
    return redirect(url_for("session", session_id=session_id))

# CANCEL A QUEST PARTICIPATION
@app.route("/participations/<int:participation_id>/cancel", methods=["POST"])
@login_required
def cancel_participation(participation_id):
    participations = participations_dao.get_participations_by_user(current_user.id)
    target = None
    for p in participations:
        if p["participation_id"] == participation_id:
            target = p
            break

    if target is None:
        flash("Participation not found", "danger")
        return redirect(url_for("profile"))

    if not participations_dao.is_modifiable(target["day"], target["start_time"], SIMULATED_NOW):
        app.logger.error("Participation can no longer be modified")
        flash("This participation can no longer be modified (there is less than 8 hours before the session)", "danger")
        return redirect(url_for("profile"))

    participations_dao.delete_participation(participation_id)
    flash("Participation cancelled successfully", "success")
    return redirect(url_for("profile"))

# THE ADVENTURER'S OWN PROFILE PAGE
@app.route("/profile")
@login_required
def profile():
    participations_db = participations_dao.get_participations_by_user(current_user.id)
    participations = []
    for p in participations_db:
        modifiable = participations_dao.is_modifiable(p["day"], p["start_time"], SIMULATED_NOW)
        participation = dict(p) # made a copy
        participation["modifiable"] = modifiable #modifiable participations are added (modifiable is a boolean)
        participations.append(participation)
    return render_template("adventurer/profile.html", participations=participations)

# AUTHORIZED ROUTES: GUILD MASTER
# NEW QUEST FORM PAGE
@app.route("/gm/quests/new")
@login_required
def new_quest_form():
    if not current_user.is_guild_master():
        flash("Only the Guild Master can create quests", "danger")
        return redirect(url_for("homepage"))
    return render_template("guildmaster/new_quest.html", quest_types=QUEST_TYPES, difficulties=DIFFICULTIES)

# CREATE A NEW QUEST (POST REQUEST)
@app.route("/gm/quests/new", methods=["POST"])
@login_required
def new_quest():
    if not current_user.is_guild_master():
        flash("Only the Guild Master can create quests", "danger")
        return redirect(url_for("homepage"))

    quest_form = request.form.to_dict()
    duration_minutes = int(quest_form.get("duration_minutes", 0))

    image_path = None
    quest_image = request.files.get("quest_image")
    if quest_image and quest_image.filename:
        img = Image.open(quest_image)
        width, height = img.size
        new_width = QUEST_IMG_HEIGHT * width / height
        size = (new_width, QUEST_IMG_HEIGHT)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        left = new_width / 2 - QUEST_IMG_HEIGHT / 2
        top = 0
        right = new_width / 2 + QUEST_IMG_HEIGHT / 2
        bottom = QUEST_IMG_HEIGHT
        img = img.crop((left, top, right, bottom))
        secs = int(datetime.now().timestamp())
        ext = quest_image.filename.split(".")[-1]
        img_newname = str(secs) + "." + ext
        img.save("static/images/quests/" + img_newname)
        image_path = "images/quests/" + img_newname

    new_id = quests_dao.create_quest(
        title=quest_form["title"],
        duration_minutes=duration_minutes,
        quest_type=quest_form["quest_type"],
        difficulty=quest_form["difficulty"],
        description=quest_form["description"],
        image_path=image_path,
        created_by=int(current_user.id),)

    if new_id:
        flash("Quest created", "success")
    else:
        flash("Something went wrong, please try again", "danger")
        return redirect(url_for("new_quest_form"))
    
    return redirect(url_for("quest", quest_id=new_id))

# NEW SESSION FORM PAGE
@app.route("/gm/quests/<int:quest_id>/sessions/new")
@login_required
def new_session_form(quest_id):
    if not current_user.is_guild_master():
        flash("Only the Guild Master can schedule quest sessions", "danger")
        return redirect(url_for("homepage"))
    
    quest_db = quests_dao.get_quest_by_id(quest_id)
    if quest_db is None:
        flash("Quest not found", "danger")
        return redirect(url_for("gm_profile"))
    if quest_db["created_by"] != int(current_user.id):
        flash("You can only schedule sessions for your own quests", "danger")
        return redirect(url_for("gm_profile"))

    return render_template("guildmaster/new_session.html", quest=quest_db, days=DAYS, locations=LOCATIONS)

# SCHEDULE A NEW SESSION (POST REQUEST, PREVENTS DAY/TIME/LOCATION OVERLAPS)
@app.route("/gm/quests/<int:quest_id>/sessions/new", methods=["POST"])
@login_required
def new_session(quest_id):
    if not current_user.is_guild_master():
        flash("Only the Guild Master can schedule quest sessions", "danger")
        return redirect(url_for("homepage"))

    quest_db = quests_dao.get_quest_by_id(quest_id)
    if quest_db is None:
        flash("Quest not found", "danger")
        return redirect(url_for("gm_profile"))

    if quest_db["created_by"] != int(current_user.id):
        flash("You can only schedule sessions for your own quests", "danger")
        return redirect(url_for("gm_profile"))

    session_form = request.form.to_dict()

    if quest_sessions_dao.is_overlapping(session_form["day"], session_form["location"], session_form["start_time"], quest_db["dur_mins"]):
        flash("This location is already booked at that day and time", "danger")
        return redirect(url_for("new_session_form", quest_id=quest_id))

    new_id = quest_sessions_dao.create_session(quest_id, session_form["day"], session_form["start_time"], session_form["location"])

    if new_id:
        flash("Quest session scheduled", "success")
    else:
        flash("Something went wrong, please try again", "danger")

    return redirect(url_for("quest", quest_id=quest_id))


# EDIT SESSION FORM PAGE (only reachable if nobody has joined yet)
@app.route("/gm/sessions/<int:session_id>/edit")
@login_required
def edit_session_form(session_id):
    if not current_user.is_guild_master():
        flash("Only the Guild Master can edit quest sessions", "danger")
        return redirect(url_for("homepage"))

    session_db = quest_sessions_dao.get_session_by_id(session_id)
    if session_db is None:
        flash("Quest session not found", "danger")
        return redirect(url_for("gm_profile"))

    if quest_sessions_dao.has_participants(session_id):
        flash("This session already has participants and can no longer be edited", "danger")
        return redirect(url_for("gm_profile"))

    return render_template("guildmaster/edit_session.html", session=session_db, days=DAYS, locations=LOCATIONS)


# UPDATE A SESSION (POST REQUEST)
@app.route("/gm/sessions/<int:session_id>/edit", methods=["POST"])
@login_required
def edit_session(session_id):
    if not current_user.is_guild_master():
        flash("Only the Guild Master can edit quest sessions", "danger")
        return redirect(url_for("homepage"))

    session_db = quest_sessions_dao.get_session_by_id(session_id)
    if session_db is None:
        flash("Quest session not found", "danger")
        return redirect(url_for("gm_profile"))

    if quest_sessions_dao.has_participants(session_id):
        flash("This session already has participants and can no longer be edited", "danger")
        return redirect(url_for("gm_profile"))

    session_form = request.form.to_dict()

    if quest_sessions_dao.is_overlapping(session_form["day"], session_form["location"], session_form["start_time"],
                                          session_db["duration_minutes"], exclude_session_id=session_id):
        flash("This location is already booked at that day and time", "danger")
        return redirect(url_for("edit_session_form", session_id=session_id))

    quest_sessions_dao.update_session(session_id, session_form["day"], session_form["start_time"], session_form["location"])
    flash("Quest session updated", "success")

    return redirect(url_for("gm_profile"))


# CANCEL A SESSION (only allowed if nobody has joined yet)
@app.route("/gm/sessions/<int:session_id>/cancel", methods=["POST"])
@login_required
def cancel_session(session_id):
    if not current_user.is_guild_master():
        flash("Only the Guild Master can cancel quest sessions", "danger")
        return redirect(url_for("homepage"))

    session_db = quest_sessions_dao.get_session_by_id(session_id)
    if session_db is None:
        flash("Quest session not found", "danger")
        return redirect(url_for("gm_profile"))

    if quest_sessions_dao.has_participants(session_id):
        flash("This session already has participants and cannot be cancelled", "danger")
        return redirect(url_for("gm_profile"))

    quest_sessions_dao.delete_session(session_id)
    flash("Quest session cancelled", "success")

    return redirect(url_for("gm_profile"))


# THE GUILD MASTER'S PROFILE PAGE: all quests with their sessions grouped
@app.route("/gm/profile")
@login_required
def gm_profile():
    if not current_user.is_guild_master():
        flash("Only the Guild Master has a dashboard", "danger")
        return redirect(url_for("homepage"))

    quests_db = quests_dao.get_quests_by_creator(current_user.id)

    quests_with_sessions = []
    for q in quests_db:
        sessions_db = quest_sessions_dao.get_sessions_by_quest(q["quest_id"])
        sessions_with_stats = []

        for s in sessions_db:
            remaining = quest_sessions_dao.get_all_remaining_places(s["session_id"])
            has_participants = quest_sessions_dao.has_participants(s["session_id"])
            sessions_with_stats.append({"session": s, "remaining": remaining, "has_participants": has_participants})
        quests_with_sessions.append({"quest": q, "sessions": sessions_with_stats})

    return render_template("guildmaster/gm_profile.html", quests=quests_with_sessions)


# AUTH ROUTES (login, logout)
# GUILD COUNCIL ADMIN PAGE
@app.route("/admin")
@login_required
def admin():
    if not current_user.is_guild_council():
        flash("Access denied", "danger")
        return redirect(url_for("homepage"))
    adventurers = admin_dao.get_adventurers_with_participation_count()
    quests = admin_dao.get_all_quests_with_sessions()
    stats = admin_dao.get_statistics()
    return render_template("admin/admin.html", adventurers=adventurers, quests=quests, stats=stats)

# THE LOGIN PAGE
@app.route("/login")
def login():
    return render_template("login_register/login.html")

# THE LOGIN FORM (POST REQUEST) 
@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("txt_email", "")
    password = request.form.get("txt_password", "")
    user_db = users_dao.get_user_by_identifier(email)

    if not user_db or not check_password_hash(user_db["password_hash"], password):
        flash("Invalid credentials, please try again", "danger")
        return redirect(url_for("login"))

    logged_in_user = User(id=user_db["user_id"], email=user_db["email"],password_hash=user_db["password_hash"], role=user_db["role"])
    login_user(logged_in_user, remember=True)
    flash("Welcome back, " + user_db["email"] + "!", "success")

    if logged_in_user.is_guild_council(): #specific case for if the admin is logging in
        return redirect(url_for("admin"))
    return redirect(url_for("homepage"))

@login_manager.user_loader
def load_user(user_id):
    db_user = users_dao.get_user_by_id(user_id)
    if db_user is None:
        return None
    return User(id=db_user["user_id"], email=db_user["email"],
                password_hash=db_user["password_hash"], role=db_user["role"])

# THE LOGOUT 
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("homepage"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)