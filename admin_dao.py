import sqlite3

def get_adventurers_with_participation_count():
    query = (
        "SELECT U.user_id, U.email, COUNT(P.participation_id) AS participation_count "
        "FROM USERS U "
        "LEFT JOIN PARTICIPATIONS P ON U.user_id = P.user_id "
        "WHERE U.role = 'adventurer' "
        "GROUP BY U.user_id "
        "ORDER BY U.email"
    )
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_all_quests_with_sessions():
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    quests = [dict(row) for row in cursor.execute(
        "SELECT quest_id, title, quest_type, difficulty, dur_mins AS duration_minutes, image_path, created_by FROM QUESTS"
    ).fetchall()]
    for q in quests:
        q["sessions"] = cursor.execute(
            "SELECT * FROM QUEST_SESSIONS WHERE quest_id = ?", (q["quest_id"],)
        ).fetchall()

    cursor.close()
    conn.close()
    return quests


def get_statistics():
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS n FROM USERS WHERE role = 'adventurer'")
    total_adventurers = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM QUESTS")
    total_quests = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM QUEST_SESSIONS")
    total_sessions = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM PARTICIPATIONS")
    total_participations = cursor.fetchone()["n"]

    cursor.execute("SELECT role_is, SUM(places_reserved) AS total FROM PARTICIPATIONS GROUP BY role_is")
    places_per_role = {row["role_is"]: row["total"] for row in cursor.fetchall()}

    cursor.execute(
        "SELECT Q.quest_type, COUNT(P.participation_id) AS total "
        "FROM QUESTS Q "
        "JOIN QUEST_SESSIONS QS ON Q.quest_id = QS.quest_id "
        "JOIN PARTICIPATIONS P ON QS.session_id = P.session_id "
        "GROUP BY Q.quest_type ORDER BY total DESC LIMIT 1"
    )
    row = cursor.fetchone()
    most_popular_quest_type = row["quest_type"] if row else "N/A"

    cursor.execute(
        "SELECT QS.session_id, Q.title, QS.day, QS.start_time, "
        "COALESCE(SUM(P.places_reserved), 0) AS total_reserved "
        "FROM QUEST_SESSIONS QS "
        "JOIN QUESTS Q ON QS.quest_id = Q.quest_id "
        "LEFT JOIN PARTICIPATIONS P ON QS.session_id = P.session_id "
        "GROUP BY QS.session_id ORDER BY total_reserved DESC LIMIT 1"
    )
    busiest_session = cursor.fetchone()

    cursor.close()
    conn.close()

    return {
        "total_adventurers": total_adventurers,
        "total_quests": total_quests,
        "total_sessions": total_sessions,
        "total_participations": total_participations,
        "places_per_role": places_per_role,
        "most_popular_quest_type": most_popular_quest_type,
        "busiest_session": busiest_session,
    }
