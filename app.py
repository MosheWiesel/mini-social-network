import os
import sqlite3

from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_cors import CORS

app = Flask(__name__)

mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
sqlite_path = os.environ.get("SQLITE_PATH", "app.db")

client = MongoClient(mongo_uri)

db = client["app"]

posts = db["posts"]

def get_sql_connection():
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@app.route("/")
def home():
    return app.send_static_file("index.html")

@app.route("/signup", methods=["POST"])
def signup():
    cunn = get_sql_connection()
    cur = cunn.cursor()
    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    username = data["username"]
    password = data["password"]
    
    try:
        cur.execute("""INSERT INTO users(username , password) VALUES (? , ?)""" , (username , password))
        cunn.commit()
        return jsonify({"message": "User registered successfully",}), 201  
    except sqlite3.IntegrityError:
        cunn.rollback()
        return jsonify({"error": "Username already exists"}), 400
    finally:
        cunn.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    cunn = get_sql_connection()
    cur = cunn.cursor()
    username = data["username"]
    password = data["password"]
    
    try:
        cur.execute("SELECT userID, username FROM users WHERE username = ? AND password = ?",(username, password))
        user = cur.fetchone()
        if user:
            if user:
                return jsonify({"message": "Signed in successfully","userID": user["userID"],"username": user["username"]}), 200
        else:
            return jsonify({ "error": "Invalid username or password"}), 401
    finally:
        cunn.close()

@app.route("/posts/<int:user_id>")
def get_posts(user_id):
    conn = get_sql_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        CASE
            WHEN follower_id = ? THEN followed_id
            ELSE follower_id
        END AS friendID,
        status
    FROM friendships
    WHERE follower_id = ? OR followed_id = ?
""", (user_id, user_id, user_id))

    rows = cur.fetchall()
    conn.close()

    friend_ids = [row["friendID"] for row in rows if row["status"] == 2]
    friend_ids.append(user_id)

    mongo_posts = list(
        posts.find({"userID": {"$in": friend_ids}, "type": "post"})
        .sort("_id", -1)
    )
    
    post_ids = [post["_id"] for post in mongo_posts]
    
    all_comments = list(posts.find({"type": "comment","postID": {"$in": post_ids}}))
    
    comments_by_post = {}
    for comment in all_comments:
        comment["_id"] = str(comment["_id"])
        pid_str = str(comment["postID"])
        comment["postID"] = pid_str
        if comment.get("replyTo"):
            comment["replyTo"] = str(comment["replyTo"])
            
        if pid_str not in comments_by_post:
            comments_by_post[pid_str] = []
        comments_by_post[pid_str].append(comment)
        
    result = []
    for post in mongo_posts:
        post["_id"] = str(post["_id"])
        post["comments"] = comments_by_post.get(post["_id"], [])
        result.append(post)
        
    return jsonify(result), 200

@app.route("/my/requests")
def my_requests():
    user_id = request.headers.get("user_id")

    if not user_id:
        return jsonify({
            "error": "Unauthorized - Missing User-ID header"
        }), 401

    conn = get_sql_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT follower_id
        FROM friendships
        WHERE followed_id = ?
        AND status = 1
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows]), 200

@app.route("/my/requests/<int:follower_id>/<string:action>", methods=["PUT"])
def handle_request(follower_id, action):
    user_id = request.headers.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized - Missing User-ID header"}), 401

    if action not in ["approve", "reject"]:
        return jsonify({"error": "Invalid action"}), 400

    conn = get_sql_connection()
    cur = conn.cursor()

    try:
        if action == "approve":
            cur.execute("""
                UPDATE friendships
                SET status = 2
                WHERE follower_id = ?
                AND followed_id = ?
                AND status = 1
            """, (follower_id, int(user_id)))

        if action == "reject":
            cur.execute("""
                DELETE FROM friendships
                WHERE follower_id = ?
                AND followed_id = ?
                AND status = 1
            """, (follower_id, int(user_id)))

        if cur.rowcount == 0:
            return jsonify({"error": "Request not found"}), 404

        conn.commit()

        return jsonify({
            "message": "Request handled successfully"
        }), 200

    finally:
        conn.close()

@app.route("/my/profile", methods=["PUT"])
def update_profile():
    user_id = request.headers.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized - Missing User-ID header"}), 401

    data = request.get_json(silent=True)
    username = data.get("username", "").strip() if data else ""

    if not username:
        return jsonify({"error": "Missing username"}), 400

    if len(username) > 80:
        return jsonify({"error": "Username is too long"}), 400

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user ID"}), 400

    conn = get_sql_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE users SET username = ? WHERE userID = ?",
            (username, user_id)
        )

        if cur.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        conn.commit()
        return jsonify({
            "message": "Profile updated successfully",
            "userID": user_id,
            "username": username
        }), 200
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Username already exists"}), 400
    finally:
        conn.close()

@app.route("/friend-request/<int:follower_id>/<int:followed_id>", methods=["POST"])
def friend_request(follower_id, followed_id):
    conn = get_sql_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO friendships
            (follower_id, followed_id, status)
            VALUES (?, ?, 1)
        """, (follower_id, followed_id))

        conn.commit()

        return jsonify({
            "message": "Request sent successfully"
        }), 201

    except sqlite3.IntegrityError:
        conn.rollback()

        return jsonify({
            "error": "Already following or invalid request"
        }), 400

    finally:
        conn.close()

@app.route("/my/post/<string:action>" , methods= ["POST"])
def mange_posts(action):
    user_id = request.headers.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized - Missing User-ID header"}), 401
    if action not in ["add", "delete", "comment"]:
        return jsonify({"error": "Invalid action. Use 'add' or 'delete' or 'comment"}), 400
    data = request.get_json()
    if action == "add":
        if not data or "content" not in data:
            return jsonify({"error": "Missing content"}), 400
        post = {
        "type": "post",
        "userID": int(user_id),
        "content": data["content"]}
        result = posts.insert_one(post)
        return jsonify({
            "message": "Post created successfully",
            "post_id": str(result.inserted_id)
        }), 201
    if action == "delete":

        if not data or "post_id" not in data:
            return jsonify({"error": "Missing post_id"}), 400

        try:
            post_id = ObjectId(data["post_id"])
        except:
            return jsonify({"error": "Invalid post_id"}), 400

        result = posts.delete_one({
            "_id": post_id,
            "userID": int(user_id),
            "type": "post"
        })


        if result.deleted_count == 0:
            return jsonify({
                "error": "Post not found or does not belong to user"
            }), 404
        posts.delete_many({"type": "comment", "postID": post_id})

        return jsonify({
            "message": "Post deleted successfully"
        }), 200
    if action == "comment":
        if not data or "content" not in data or "post_id" not in data:
            return jsonify({"error": "Missing content or post_id"}), 400
        try:
            post_id = ObjectId(data["post_id"])
        except:
            return jsonify({"error": "Invalid post_id"}), 400

        post_exists = posts.find_one({"_id": post_id, "type": "post"})
        if not post_exists:
             return jsonify({"error": "Post not found"}), 404
        if data.get("replyTo"):
            try:
                reply_to = ObjectId(data["replyTo"])
            except:
                return jsonify({"error": "Invalid replyTo"}), 400
            comment = {"type": "comment","userID": int(user_id),"content": data["content"],"postID": post_id , "replyTo": reply_to}
        else:
            comment = {"type": "comment","userID": int(user_id),"content": data["content"],"postID": post_id}
        result = posts.insert_one(comment)
        return jsonify({"massage":"comment added successfully", "comment_id":str(result.inserted_id)}), 201

@app.route("/users", methods=["GET"])
def get_all_users():
    conn = get_sql_connection()
    cur = conn.cursor()

    cur.execute("SELECT userID, username FROM users")
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows]), 200

if __name__ == "__main__":
    app.run(debug=True)


    
    
