import sqlite3

# Get a specific quest
def get_quest_by_id(quest_id):
    query = "SELECT * FROM QUESTS WHERE quest_id = ?"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (quest_id,))
    db_quest = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_quest


# Create a new quest
def create_quest(title, duration_minutes, quest_type, difficulty, description, image_path, created_by):
    query = "INSERT INTO QUESTS (title, dur_mins, quest_type, difficulty, desc, image_path, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (title, duration_minutes, quest_type, difficulty, description, image_path, created_by))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id

# Get all quests created by a specific guild master
def get_quests_by_creator(creator_id):
    query = "SELECT * FROM QUESTS WHERE created_by = ? ORDER BY quest_id"
    conn = sqlite3.connect("database/myquest.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (creator_id,))
    db_quests = cursor.fetchall()
    cursor.close()
    conn.close()
    return db_quests
