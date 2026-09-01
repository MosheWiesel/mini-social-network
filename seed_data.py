import os
import sqlite3
from pymongo import MongoClient


# =========================
# SQL
# =========================

sqlite_path = os.environ.get("SQLITE_PATH", "app.db")
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")

conn = sqlite3.connect(sqlite_path)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()


# ניקוי
cur.execute("DELETE FROM friendships")
cur.execute("DELETE FROM users")
conn.commit()


# משתמשים
users = [
    ("moshe", "1234"),
    ("david", "1234"),
    ("yossi", "1234"),
    ("avi", "1234"),
    ("daniel", "1234")
]

user_ids = {}

for username, password in users:

    cur.execute(
        """
        INSERT INTO users(username, password)
        VALUES (?, ?)
        """,
        (username, password)
    )

    user_ids[username] = cur.lastrowid


conn.commit()


# חברויות
friendships = [
    ("moshe", "david"),
    ("moshe", "yossi"),
    ("david", "avi")
]

for user1, user2 in friendships:

    id1 = user_ids[user1]
    id2 = user_ids[user2]

    smaller = min(id1, id2)
    bigger = max(id1, id2)

    cur.execute(
        """
        INSERT INTO friendships(follower_id, followed_id, status)
        VALUES (?, ?, 2)
        """,
        (smaller, bigger)
    )


conn.commit()
conn.close()


# =========================
# MongoDB
# =========================

client = MongoClient(mongo_uri)

db = client["app"]

posts = db["posts"]


# ניקוי Mongo
posts.delete_many({})


# פוסטים
post1 = posts.insert_one({
    "type": "post",
    "userID": user_ids["david"],
    "content": "Hello from David"
})

post2 = posts.insert_one({
    "type": "post",
    "userID": user_ids["yossi"],
    "content": "Yossi's first post"
})

post3 = posts.insert_one({
    "type": "post",
    "userID": user_ids["avi"],
    "content": "Post from Avi"
})

post4 = posts.insert_one({
    "type": "post",
    "userID": user_ids["daniel"],
    "content": "Moshe should NOT see this post"
})


# תגובות
comment1 = posts.insert_one({
    "type": "comment",
    "userID": user_ids["moshe"],
    "content": "Nice post David!",
    "postID": post1.inserted_id,
    "replyTo": None
})

comment2 = posts.insert_one({
    "type": "comment",
    "userID": user_ids["yossi"],
    "content": "I agree",
    "postID": post1.inserted_id,
    "replyTo": comment1.inserted_id
})

comment3 = posts.insert_one({
    "type": "comment",
    "userID": user_ids["david"],
    "content": "Thanks!",
    "postID": post2.inserted_id,
    "replyTo": None
})


print("Seed completed successfully")
print()
print("Users:")
print(user_ids)
print()
print("Test Moshe:")
print(f"http://127.0.0.1:5000/posts/{user_ids['moshe']}")
