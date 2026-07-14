import sqlite3

# Gets a specific user by its id
def get_user_by_id(user_id):
    query = "SELECT * FROM USERS WHERE user_id = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    db_user = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_user

#Gets a specific user by its identifier (in this case the email)
def get_user_by_identifier(identifier):
    query = "SELECT * FROM USERS WHERE email = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (identifier,))
    db_user = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_user

# Checks if a user already exists in my database
def identifier_exists(identifier):
    query = "SELECT 1 FROM USERS WHERE email = ?"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (identifier,))
    db_user = cursor.fetchone()
    cursor.close()
    conn.close()
    return db_user is not None

# Creates a new user
def create_user(identifier, password_hash, role):
    query = "INSERT INTO USERS (email, password_hash, role) VALUES (?, ?, ?)"
    conn = sqlite3.connect("database/dragonlaria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, (identifier, password_hash, role))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id