import secrets
import sqlite3

from flask import Blueprint, g, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_mongo, get_sql
from .security import current_user, ensure_csrf_token, error, limiter, login_required, success
from .utils import clean_text, iso_now, valid_username


auth_bp = Blueprint("auth", __name__)


def public_me(row):
    profile = get_sql().execute(
        "SELECT display_name, bio, avatar, cover_image, location, website, profile_visibility, message_privacy FROM profiles WHERE user_id = ?",
        (row["userID"],),
    ).fetchone()
    return {
        "id": row["userID"],
        "username": row["username"],
        "displayName": profile["display_name"] or row["username"],
        "bio": profile["bio"],
        "avatar": profile["avatar"],
        "coverImage": profile["cover_image"],
        "location": profile["location"],
        "website": profile["website"],
        "profileVisibility": profile["profile_visibility"],
        "messagePrivacy": profile["message_privacy"],
        "role": row["role"],
        "createdAt": row["created_at"],
    }


@auth_bp.get("/api/csrf")
def csrf():
    return success({"csrfToken": ensure_csrf_token()})


@auth_bp.post("/api/auth/signup")
@limiter.limit("5 per minute; 20 per hour")
def signup():
    data = request.get_json(silent=True) or {}
    username = clean_text(data.get("username"), 30)
    password = str(data.get("password") or "")
    if not valid_username(username):
        return error("INVALID_USERNAME", "Use 3–30 letters, numbers, dots, dashes, or underscores", 422)
    if len(password) < 8 or len(password) > 128:
        return error("WEAK_PASSWORD", "Password must contain 8–128 characters", 422)
    now = iso_now()
    connection = get_sql()
    try:
        with connection:
            cursor = connection.execute(
                """INSERT INTO users(username, password, password_hash, created_at, updated_at)
                   VALUES (?, '', ?, ?, ?)""",
                (username, generate_password_hash(password), now, now),
            )
            user_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO profiles(user_id, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, username, now, now),
            )
            connection.execute("INSERT INTO notification_settings(user_id) VALUES (?)", (user_id,))
    except sqlite3.IntegrityError:
        return error("USERNAME_TAKEN", "That username is unavailable", 409)
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    csrf_token = ensure_csrf_token()
    row = connection.execute(
        "SELECT userID, username, role, account_status, created_at FROM users WHERE userID = ?", (user_id,)
    ).fetchone()
    return success({"user": public_me(row), "csrfToken": csrf_token}, 201)


@auth_bp.post("/api/auth/login")
@limiter.limit("8 per minute; 40 per hour")
def login():
    data = request.get_json(silent=True) or {}
    username = clean_text(data.get("username"), 80)
    password = str(data.get("password") or "")
    row = get_sql().execute(
        "SELECT userID, username, password_hash, role, account_status, created_at FROM users WHERE username = ? COLLATE NOCASE",
        (username,),
    ).fetchone()
    valid = bool(row and row["account_status"] == "active" and row["password_hash"] and check_password_hash(row["password_hash"], password))
    if not valid:
        return error("INVALID_CREDENTIALS", "Invalid username or password", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = row["userID"]
    csrf_token = ensure_csrf_token()
    return success({"user": public_me(row), "csrfToken": csrf_token})


@auth_bp.post("/api/auth/logout")
@login_required
def logout():
    session.clear()
    return success({"loggedOut": True})


@auth_bp.get("/api/me")
def me():
    row = current_user()
    if not row:
        return success({"user": None, "csrfToken": ensure_csrf_token()})
    return success({"user": public_me(row), "csrfToken": ensure_csrf_token()})


@auth_bp.put("/api/account/password")
@login_required
@limiter.limit("5 per hour")
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("currentPassword") or "")
    new_password = str(data.get("newPassword") or "")
    row = get_sql().execute("SELECT password_hash FROM users WHERE userID = ?", (current_user()["userID"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], current_password):
        return error("INVALID_CURRENT_PASSWORD", "Current password is incorrect", 401)
    if len(new_password) < 8 or len(new_password) > 128:
        return error("WEAK_PASSWORD", "Password must contain 8–128 characters", 422)
    with get_sql():
        get_sql().execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE userID = ?",
            (generate_password_hash(new_password), iso_now(), current_user()["userID"]),
        )
    return success({"changed": True})


@auth_bp.delete("/api/account")
@login_required
@limiter.limit("3 per hour")
def delete_account():
    data = request.get_json(silent=True) or {}
    password = str(data.get("password") or "")
    user = current_user()
    row = get_sql().execute("SELECT password_hash FROM users WHERE userID = ?", (user["userID"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return error("INVALID_PASSWORD", "Password confirmation failed", 401)
    now = iso_now()
    replacement = f"deleted-{user['userID']}-{secrets.token_hex(4)}"
    with get_sql():
        get_sql().execute(
            "UPDATE users SET username = ?, password_hash = '', account_status = 'deleted', updated_at = ? WHERE userID = ?",
            (replacement, now, user["userID"]),
        )
        get_sql().execute(
            "UPDATE profiles SET display_name = 'Deleted account', bio = '', avatar = NULL, cover_image = NULL, location = '', website = '', updated_at = ? WHERE user_id = ?",
            (now, user["userID"]),
        )
        get_sql().execute("DELETE FROM friendships WHERE follower_id=? OR followed_id=?", (user["userID"], user["userID"]))
        get_sql().execute("DELETE FROM blocks WHERE blocker_id=? OR blocked_id=?", (user["userID"], user["userID"]))
    get_mongo()["notifications"].delete_many({"userID": user["userID"]})
    session.clear()
    return success({"deleted": True})
