import os
import sqlite3
from pymongo import MongoClient


# =========================
# SQL - SQLite
# =========================

sqlite_path = os.environ.get("SQLITE_PATH", "app.db")
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")

conn = sqlite3.connect(sqlite_path)
cur = conn.cursor()

# חשוב: SQLite לא אוכף FOREIGN KEY כברירת מחדל
cur.execute("PRAGMA foreign_keys = ON")


# Users
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    userID INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")


# Friendships
cur.execute("""
CREATE TABLE IF NOT EXISTS friendships (
    _id INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id INTEGER NOT NULL,
    followed_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1 CHECK (status BETWEEN 0 AND 2),

    FOREIGN KEY (follower_id)
        REFERENCES users(userID)
        ON DELETE CASCADE,

    FOREIGN KEY (followed_id)
        REFERENCES users(userID)
        ON DELETE CASCADE,

    UNIQUE (follower_id, followed_id)

    CHECK (follower_id != followed_id)
)
""")


conn.commit()
conn.close()


# =========================
# MongoDB
# =========================

client = MongoClient(mongo_uri)

db = client["app"]

# יצירת collection אם הוא עדיין לא קיים
if "posts" not in db.list_collection_names():
    db.create_collection("posts")

posts = db["posts"]

print("Database initialization completed")
