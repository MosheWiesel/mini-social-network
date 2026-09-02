import sqlite3

from flask import Blueprint, request

from .db import get_sql
from .security import current_user, error, limiter, login_required, success
from .utils import clean_text, iso_now, valid_username, valid_website


users_bp = Blueprint("users", __name__)


def _blocked(viewer_id, target_id):
    return bool(get_sql().execute(
        "SELECT 1 FROM blocks WHERE (blocker_id = ? AND blocked_id = ?) OR (blocker_id = ? AND blocked_id = ?)",
        (viewer_id, target_id, target_id, viewer_id),
    ).fetchone())


def friendship_state(viewer_id, target_id):
    if viewer_id == target_id:
        return "self"
    if get_sql().execute("SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?", (viewer_id, target_id)).fetchone():
        return "blocked"
    if get_sql().execute("SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?", (target_id, viewer_id)).fetchone():
        return "unavailable"
    row = get_sql().execute(
        """SELECT follower_id, followed_id, status FROM friendships
           WHERE (follower_id = ? AND followed_id = ?) OR (follower_id = ? AND followed_id = ?)
           ORDER BY status DESC LIMIT 1""",
        (viewer_id, target_id, target_id, viewer_id),
    ).fetchone()
    if not row:
        return "none"
    if row["status"] == 2:
        return "friends"
    return "outgoing" if row["follower_id"] == viewer_id else "incoming"


def profile_for(row, viewer_id):
    target_id = row["userID"]
    state = friendship_state(viewer_id, target_id) if viewer_id else "none"
    return {
        "id": target_id,
        "username": row["username"],
        "displayName": row["display_name"] or row["username"],
        "bio": row["bio"],
        "avatar": row["avatar"],
        "coverImage": row["cover_image"],
        "location": row["location"],
        "website": row["website"],
        "profileVisibility": row["profile_visibility"],
        "messagePrivacy": row["message_privacy"],
        "friendshipState": state,
        "createdAt": row["created_at"],
    }


PROFILE_QUERY = """SELECT u.userID, u.username, u.created_at, p.display_name, p.bio, p.avatar,
    p.cover_image, p.location, p.website, p.profile_visibility, p.message_privacy
    FROM users u JOIN profiles p ON p.user_id = u.userID WHERE u.account_status = 'active'"""


@users_bp.get("/api/users")
@login_required
@limiter.limit("60 per minute")
def list_users():
    viewer_id = current_user()["userID"]
    query = clean_text(request.args.get("q"), 60).lower()
    limit = min(max(request.args.get("limit", 24, type=int), 1), 50)
    rows = get_sql().execute(
        PROFILE_QUERY + " AND u.userID != ? AND (LOWER(u.username) LIKE ? OR LOWER(p.display_name) LIKE ?) ORDER BY u.username LIMIT ?",
        (viewer_id, f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    return success([profile_for(row, viewer_id) for row in rows if not _blocked(viewer_id, row["userID"])])


@users_bp.get("/api/users/<username>")
@login_required
def get_profile(username):
    viewer_id = current_user()["userID"]
    row = get_sql().execute(PROFILE_QUERY + " AND u.username = ? COLLATE NOCASE", (username,)).fetchone()
    if not row or _blocked(viewer_id, row["userID"]):
        return error("PROFILE_NOT_FOUND", "Profile not found", 404)
    if row["profile_visibility"] == "friends" and friendship_state(viewer_id, row["userID"]) not in {"self", "friends"}:
        return error("PROFILE_PRIVATE", "This profile is private", 403)
    return success(profile_for(row, viewer_id))


@users_bp.put("/api/me/profile")
@login_required
@limiter.limit("20 per hour")
def update_profile():
    data = request.get_json(silent=True) or {}
    username = clean_text(data.get("username"), 30, required=True)
    display_name = clean_text(data.get("displayName"), 60, required=True)
    bio = clean_text(data.get("bio"), 300)
    location = clean_text(data.get("location"), 80)
    website = clean_text(data.get("website"), 200)
    if not valid_username(username):
        return error("INVALID_USERNAME", "Use 3–30 letters, numbers, dots, dashes, or underscores", 422)
    if not valid_website(website):
        return error("INVALID_WEBSITE", "Website must be a valid http or https URL", 422)
    user_id = current_user()["userID"]
    now = iso_now()
    try:
        with get_sql():
            get_sql().execute("UPDATE users SET username = ?, updated_at = ? WHERE userID = ?", (username, now, user_id))
            get_sql().execute(
                "UPDATE profiles SET display_name = ?, bio = ?, location = ?, website = ?, updated_at = ? WHERE user_id = ?",
                (display_name, bio, location, website, now, user_id),
            )
    except sqlite3.IntegrityError:
        return error("USERNAME_TAKEN", "That username is unavailable", 409)
    row = get_sql().execute(PROFILE_QUERY + " AND u.userID = ?", (user_id,)).fetchone()
    return success(profile_for(row, user_id))


@users_bp.put("/api/me/privacy")
@login_required
def update_privacy():
    data = request.get_json(silent=True) or {}
    profile_visibility = data.get("profileVisibility", "public")
    message_privacy = data.get("messagePrivacy", "everyone")
    request_privacy = data.get("friendRequestPrivacy", "everyone")
    if profile_visibility not in {"public", "friends"} or message_privacy not in {"everyone", "friends", "nobody"} or request_privacy not in {"everyone", "friends_of_friends", "nobody"}:
        return error("INVALID_PRIVACY", "Invalid privacy selection", 422)
    with get_sql():
        get_sql().execute(
            "UPDATE profiles SET profile_visibility = ?, message_privacy = ?, friend_request_privacy = ?, updated_at = ? WHERE user_id = ?",
            (profile_visibility, message_privacy, request_privacy, iso_now(), current_user()["userID"]),
        )
    return success({"updated": True})
