from datetime import datetime
import sqlite3

# CONSTANTS
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

#Used later on for the overlap function
def time_to_minutes(hhmm):
    t = datetime.strptime(hhmm, "%H:%M")
    return t.hour * 60 + t.minute

#Gets the number of how many remaining places are available for a given role
def get_remaining_places(session_id, role_category):
    capacities = {"Warrior": 4, "Mage": 3, "Healer": 2} #capacities dictionary
    query = (
        "SELECT COALESCE(SUM(places_reserved), 0) AS taken " #COALESCE is added bc if no participants = return 0 rather than NULL
        "FROM PARTICIPATIONS P "
        "WHERE session_id = ? AND role_is = ?" )
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (session_id, role_category))
    db_participation = cursor.fetchone()
    cursor.close()
    conn.close()
    return capacities[role_category] - db_participation["taken"] #returns int value of remaining places for role

#Returns remaining places for all roles as a dictionary (key = role, value = remaining places)
def get_all_remaining_places(session_id):
    capacities = {"Warrior": 4, "Mage": 3, "Healer": 2}
    remaining = {}
    for role in capacities:
        remaining[role] = get_remaining_places(session_id, role)
    return remaining

#Checks if a role is available
def role_is_available(session_id, role_category, places_requested=1):
    return get_remaining_places(session_id, role_category) >= places_requested

#Gets the available sessions that have remaining places 
def get_sessions_with_remaining_places(quest_id):
    db_sessions = get_sessions_by_quest(quest_id)
    db_sessions_with_remaining = []
    capacities = {"Warrior": 4, "Mage": 3, "Healer": 2}
    for db_session in db_sessions:
        remaining = {
            role: get_remaining_places(db_session["session_id"], role)
            for role in capacities }
        db_sessions_with_remaining.append({"session": db_session, "remaining": remaining})
    return db_sessions_with_remaining

#Gets all the sessions
def get_all_sessions(day=None, quest_type=None, difficulty=None, role=None):
    query = (
        "SELECT QS.*, Q.title, Q.quest_type, Q.difficulty, Q.dur_mins AS duration_minutes, Q.image_path "
        "FROM QUEST_SESSIONS QS "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE (QS.day = ? OR ? IS NULL) "
        "AND (Q.quest_type = ? OR ? IS NULL) "
        "AND (Q.difficulty = ? OR ? IS NULL)")

    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # i am passing each parameter twice: once for the = check, once for the IS NULL check
    cursor.execute(query, (day, day, quest_type, quest_type, difficulty, difficulty))
    db_sessions = cursor.fetchall()
    cursor.close()
    conn.close()

    def sort_by_day_and_time(session):
        day_index = DAY_ORDER.index(session["day"]) #returns the index of the day, 0 for Monday and 6 for Sunday
        return (day_index, session["start_time"])

    db_sessions = sorted(db_sessions, key=sort_by_day_and_time) #sorts the sessions by day and time, example of a key (0, "10:00:00")

    # if the role is selected during the filtering, show only the sessions that have availability for that role
    if role:
        db_sessions = [s for s in db_sessions if get_remaining_places(s["session_id"], role) > 0]

    return db_sessions

#Gets a specific session
def get_session_by_id(session_id):
    query = (
        "SELECT QS.*, Q.title, Q.quest_type, Q.difficulty, Q.dur_mins AS duration_minutes, "
        "Q.desc AS description, Q.image_path "
        "FROM QUEST_SESSIONS QS "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE QS.session_id = ?" )
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (session_id,))
    db_session = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_session

#Gets all the sessions for a specific quest
def get_sessions_by_quest(quest_id):
    query = "SELECT * FROM QUEST_SESSIONS WHERE quest_id = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (quest_id,))
    db_sessions = cursor.fetchall()
    cursor.close()
    conn.close()
    return db_sessions

#Gets all the sessions created by a specific guild master
def get_sessions_by_creator(user_id):
    query = (
        "SELECT QS.*, Q.title "
        "FROM QUEST_SESSIONS QS "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE Q.created_by = ? "
        "ORDER BY Q.quest_id" )
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    db_sessions = cursor.fetchall()
    cursor.close()
    conn.close()
    return db_sessions

#Checks if a new session overlaps with an existing one
def is_overlapping(day, location, start_time, duration_minutes, exclude_session_id=None):
    query = (
        "SELECT QS.session_id, QS.start_time, Q.dur_mins AS duration_minutes "
        "FROM QUEST_SESSIONS QS "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE QS.day = ? AND QS.location = ? "
        "AND (QS.session_id != ? OR ? IS NULL)" )
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (day, location, exclude_session_id, exclude_session_id))
    db_sessions = cursor.fetchall()
    cursor.close()
    conn.close()

    new_start = time_to_minutes(start_time)
    new_end = new_start + duration_minutes

    for db_session in db_sessions:
        existing_start = time_to_minutes(db_session["start_time"])
        existing_end = existing_start + db_session["duration_minutes"]
        if new_start < existing_end and existing_start < new_end:
            return True #new session that is selected overlaps with the preexisting one

    return False #not overlapping

# Checks if a session has participants
def has_participants(session_id):
    query = "SELECT 1 FROM PARTICIPATIONS WHERE session_id = ? LIMIT 1"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (session_id,))
    db_participation = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_participation is not None

#Creates a new session
def create_session(quest_id, day, start_time, location):
    query = "INSERT INTO QUEST_SESSIONS (quest_id, day, start_time, location) VALUES (?, ?, ?, ?)"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (quest_id, day, start_time, location))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id

# Updates a session
def update_session(session_id, day, start_time, location):
    query = "UPDATE QUEST_SESSIONS SET day = ?, start_time = ?, location = ? WHERE session_id = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (day, start_time, location, session_id))
    conn.commit()
    cursor.close()
    conn.close()

# Deletes a session
def delete_session(session_id):
    query = "DELETE FROM QUEST_SESSIONS WHERE session_id = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (session_id,))
    conn.commit()
    cursor.close()
    conn.close()