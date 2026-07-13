from datetime import datetime, timedelta
import sqlite3
from quest_sessions_dao import time_to_minutes, DAY_ORDER

# CONSTANTS
MAX_ACTIVE_SESSIONS = 3

def get_participations_by_user(user_id):
    query = (
        "SELECT P.participation_id, P.user_id, P.session_id, P.places_reserved, "
        "P.role_is AS role_category, "
        "QS.day, QS.start_time, QS.location, Q.title, Q.dur_mins AS duration_minutes "
        "FROM PARTICIPATIONS P "
        "JOIN QUEST_SESSIONS QS ON P.session_id = QS.session_id "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE P.user_id = ?"
    )
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    db_participations = cursor.fetchall()
    cursor.close()
    conn.close()
    return db_participations


def count_active_sessions_for_user(user_id):
    query = "SELECT COUNT(*) AS n FROM PARTICIPATIONS WHERE user_id = ?"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    db_count = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_count["n"]


def get_user_session_schedules(user_id):
    query = (
        "SELECT QS.day, QS.start_time, Q.dur_mins AS duration_minutes "
        "FROM PARTICIPATIONS P "
        "JOIN QUEST_SESSIONS QS ON P.session_id = QS.session_id "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "WHERE P.user_id = ?"
    )
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    db_sessions = cursor.fetchall()
    cursor.close()
    conn.close()
    return db_sessions


def has_time_conflict(user_id, day, start_time, duration_minutes):
    new_start = time_to_minutes(start_time)
    new_end = new_start + duration_minutes

    for db_session in get_user_session_schedules(user_id):
        if db_session["day"] != day:
            continue
        existing_start = time_to_minutes(db_session["start_time"])
        existing_end = existing_start + db_session["duration_minutes"]
        if new_start < existing_end and existing_start < new_end:
            return True
    return False


def create_participation(user_id, session_id, role_category, places_reserved):
    query = "INSERT INTO PARTICIPATIONS (user_id, session_id, role_is, places_reserved) VALUES (?, ?, ?, ?)"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id, session_id, role_category, places_reserved))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id

# Finds how many days ahead a session is
def is_modifiable(session_day, session_start_time, simulated_now):
    current_day_index = simulated_now.weekday()  # Monday = 0
    target_day_index = DAY_ORDER.index(session_day)
    days_ahead = (target_day_index - current_day_index) % 7

    session_datetime = datetime.combine(
        simulated_now.date() + timedelta(days=days_ahead),
        datetime.strptime(session_start_time, "%H:%M").time(),
    )

    return session_datetime - simulated_now > timedelta(hours=8)


def delete_participation(participation_id):
    query = "DELETE FROM PARTICIPATIONS WHERE participation_id = ?"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (participation_id,))
    conn.commit()
    cursor.close()
    conn.close()