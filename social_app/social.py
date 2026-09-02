import sqlite3

from flask import Blueprint, request

from .db import get_sql
from .notifications import notify
from .security import current_user, error, limiter, login_required, success
from .users import PROFILE_QUERY, friendship_state, profile_for
from .utils import clean_text, iso_now


social_bp = Blueprint("social", __name__)


def _active_user(user_id):
    return get_sql().execute("SELECT 1 FROM users WHERE userID = ? AND account_status = 'active'", (user_id,)).fetchone()


def _blocked_pair(first, second):
    return get_sql().execute(
        "SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)",
        (first, second, second, first),
    ).fetchone()


@social_bp.get("/api/friends")
@login_required
def friends():
    user_id = current_user()["userID"]
    rows = get_sql().execute(
        """SELECT CASE WHEN f.follower_id = ? THEN f.followed_id ELSE f.follower_id END AS friend_id
           FROM friendships f WHERE (f.follower_id = ? OR f.followed_id = ?) AND f.status = 2""",
        (user_id, user_id, user_id),
    ).fetchall()
    profiles = []
    for item in rows:
        row = get_sql().execute(PROFILE_QUERY + " AND u.userID = ?", (item["friend_id"],)).fetchone()
        if row:
            profiles.append(profile_for(row, user_id))
    return success(profiles)


@social_bp.get("/api/friend-requests")
@login_required
def requests_list():
    user_id = current_user()["userID"]
    incoming = get_sql().execute(
        "SELECT follower_id AS user_id, created_at FROM friendships WHERE followed_id = ? AND status = 1 ORDER BY _id DESC",
        (user_id,),
    ).fetchall()
    outgoing = get_sql().execute(
        "SELECT followed_id AS user_id, created_at FROM friendships WHERE follower_id = ? AND status = 1 ORDER BY _id DESC",
        (user_id,),
    ).fetchall()
    def expand(items):
        result = []
        for item in items:
            row = get_sql().execute(PROFILE_QUERY + " AND u.userID = ?", (item["user_id"],)).fetchone()
            if row:
                result.append({"user": profile_for(row, user_id), "createdAt": item["created_at"]})
        return result
    return success({"incoming": expand(incoming), "outgoing": expand(outgoing)})


@social_bp.post("/api/friend-requests/<int:target_id>")
@login_required
@limiter.limit("30 per hour")
def send_request(target_id):
    user_id = current_user()["userID"]
    if target_id == user_id or not _active_user(target_id):
        return error("INVALID_TARGET", "User not found", 404)
    if _blocked_pair(user_id, target_id):
        return error("BLOCKED", "This action is unavailable", 403)
    privacy = get_sql().execute("SELECT friend_request_privacy FROM profiles WHERE user_id = ?", (target_id,)).fetchone()
    if privacy and privacy[0] == "nobody":
        return error("REQUESTS_DISABLED", "This user is not accepting requests", 403)
    existing = get_sql().execute(
        "SELECT follower_id, followed_id, status FROM friendships WHERE (follower_id=? AND followed_id=?) OR (follower_id=? AND followed_id=?)",
        (user_id, target_id, target_id, user_id),
    ).fetchone()
    if existing:
        code = "ALREADY_FRIENDS" if existing["status"] == 2 else "REQUEST_EXISTS"
        return error(code, "A friendship or request already exists", 409)
    now = iso_now()
    try:
        with get_sql():
            get_sql().execute(
                "INSERT INTO friendships(follower_id, followed_id, status, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                (user_id, target_id, now, now),
            )
    except sqlite3.IntegrityError:
        return error("REQUEST_EXISTS", "A friendship or request already exists", 409)
    notify(target_id, user_id, "friend_request", {"userId": user_id}, f"friend-request:{user_id}:{target_id}")
    return success({"state": "outgoing"}, 201)


@social_bp.post("/api/friend-requests/<int:target_id>/<action>")
@login_required
def handle_request(target_id, action):
    user_id = current_user()["userID"]
    if action not in {"accept", "reject", "cancel"}:
        return error("INVALID_ACTION", "Invalid request action", 422)
    now = iso_now()
    with get_sql():
        if action == "accept":
            cursor = get_sql().execute(
                "UPDATE friendships SET status=2, updated_at=? WHERE follower_id=? AND followed_id=? AND status=1",
                (now, target_id, user_id),
            )
        elif action == "reject":
            cursor = get_sql().execute(
                "DELETE FROM friendships WHERE follower_id=? AND followed_id=? AND status=1", (target_id, user_id)
            )
        else:
            cursor = get_sql().execute(
                "DELETE FROM friendships WHERE follower_id=? AND followed_id=? AND status=1", (user_id, target_id)
            )
    if cursor.rowcount == 0:
        return error("REQUEST_NOT_FOUND", "Friend request not found", 404)
    if action == "accept":
        notify(target_id, user_id, "friend_accepted", {"userId": user_id}, f"friend-accepted:{target_id}:{user_id}")
    return success({"state": "friends" if action == "accept" else "none"})


@social_bp.delete("/api/friends/<int:target_id>")
@login_required
def unfriend(target_id):
    user_id = current_user()["userID"]
    with get_sql():
        cursor = get_sql().execute(
            "DELETE FROM friendships WHERE status=2 AND ((follower_id=? AND followed_id=?) OR (follower_id=? AND followed_id=?))",
            (user_id, target_id, target_id, user_id),
        )
    if cursor.rowcount == 0:
        return error("FRIENDSHIP_NOT_FOUND", "Friendship not found", 404)
    return success({"state": "none"})


@social_bp.post("/api/blocks/<int:target_id>")
@login_required
def block(target_id):
    user_id = current_user()["userID"]
    if target_id == user_id or not _active_user(target_id):
        return error("INVALID_TARGET", "User not found", 404)
    with get_sql():
        get_sql().execute(
            "DELETE FROM friendships WHERE (follower_id=? AND followed_id=?) OR (follower_id=? AND followed_id=?)",
            (user_id, target_id, target_id, user_id),
        )
        get_sql().execute(
            "INSERT OR IGNORE INTO blocks(blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (user_id, target_id, iso_now()),
        )
    return success({"state": "blocked"}, 201)


@social_bp.delete("/api/blocks/<int:target_id>")
@login_required
def unblock(target_id):
    with get_sql():
        get_sql().execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?", (current_user()["userID"], target_id))
    return success({"state": "none"})


@social_bp.get("/api/blocks")
@login_required
def blocks():
    user_id = current_user()["userID"]
    rows = get_sql().execute("SELECT blocked_id FROM blocks WHERE blocker_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    result = []
    for row_id in rows:
        row = get_sql().execute(PROFILE_QUERY + " AND u.userID=?", (row_id["blocked_id"],)).fetchone()
        if row:
            item = profile_for(row, user_id)
            item["friendshipState"] = "blocked"
            result.append(item)
    return success(result)


@social_bp.post("/api/reports")
@login_required
@limiter.limit("20 per day")
def report_content():
    data = request.get_json(silent=True) or {}
    target_type = data.get("targetType")
    target_id = clean_text(data.get("targetId"), 100, required=True)
    reason = data.get("reason")
    details = clean_text(data.get("details"), 500)
    if target_type not in {"post", "comment", "user", "message"} or reason not in {"spam", "harassment", "inappropriate", "other"}:
        return error("INVALID_REPORT", "Invalid report details", 422)
    with get_sql():
        get_sql().execute(
            "INSERT INTO reports(reporter_id,target_type,target_id,reason,details,status,created_at) VALUES(?,?,?,?,?,'open',?)",
            (current_user()["userID"], target_type, target_id, reason, details, iso_now()),
        )
    return success({"reported": True}, 201)
