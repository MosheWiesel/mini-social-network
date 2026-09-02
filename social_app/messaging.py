from datetime import datetime

from flask import Blueprint, request

from .db import get_mongo, get_sql
from .notifications import notify
from .security import current_user, error, limiter, login_required, success
from .users import PROFILE_QUERY, friendship_state, profile_for
from .utils import clamp_int, clean_text, iso_now, json_datetime, object_id, utcnow


messaging_bp = Blueprint("messaging", __name__)


def _member(conversation_id, user_id):
    return get_sql().execute(
        "SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?", (conversation_id, user_id)
    ).fetchone()


def _blocked(first, second):
    return get_sql().execute(
        "SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)",
        (first, second, second, first),
    ).fetchone()


def _participants(conversation_id, viewer_id):
    rows = get_sql().execute(
        "SELECT user_id FROM conversation_members WHERE conversation_id=?", (conversation_id,)
    ).fetchall()
    result = []
    for row in rows:
        profile = get_sql().execute(PROFILE_QUERY + " AND u.userID=?", (row["user_id"],)).fetchone()
        if profile:
            result.append(profile_for(profile, viewer_id))
    return result


def _serialize_message(document):
    return {
        "id": str(document["_id"]), "conversationId": document["conversationID"],
        "senderId": document["senderID"], "content": document.get("content", ""),
        "media": document.get("media", []),
        "createdAt": json_datetime(document.get("createdAt") or document["_id"].generation_time),
        "edited": bool(document.get("edited")),
    }


@messaging_bp.get("/api/conversations")
@login_required
def conversations():
    user_id = current_user()["userID"]
    rows = get_sql().execute(
        """SELECT c.conversation_id, c.updated_at, cm.last_read_at
           FROM conversations c JOIN conversation_members cm ON cm.conversation_id=c.conversation_id
           WHERE cm.user_id=? ORDER BY c.updated_at DESC LIMIT 50""",
        (user_id,),
    ).fetchall()
    items = []
    for row in rows:
        last = get_mongo()["messages"].find_one({"conversationID": row["conversation_id"]}, sort=[("_id", -1)])
        last_read = datetime.fromisoformat(row["last_read_at"]) if row["last_read_at"] else None
        unread_query = {
            "conversationID": row["conversation_id"], "senderID": {"$ne": user_id},
        }
        if last_read:
            unread_query["createdAt"] = {"$gt": last_read}
        unread = get_mongo()["messages"].count_documents(unread_query)
        items.append({
            "id": row["conversation_id"], "participants": _participants(row["conversation_id"], user_id),
            "lastMessage": _serialize_message(last) if last else None, "unread": unread, "updatedAt": row["updated_at"],
        })
    return success(items)


@messaging_bp.post("/api/conversations")
@login_required
def create_conversation():
    target_id = (request.get_json(silent=True) or {}).get("userId")
    if not isinstance(target_id, int) or target_id == current_user()["userID"]:
        return error("INVALID_TARGET", "Invalid conversation participant", 422)
    user_id = current_user()["userID"]
    target = get_sql().execute("SELECT userID FROM users WHERE userID=? AND account_status='active'", (target_id,)).fetchone()
    if not target or _blocked(user_id, target_id):
        return error("USER_UNAVAILABLE", "This user is unavailable", 403)
    privacy = get_sql().execute("SELECT message_privacy FROM profiles WHERE user_id=?", (target_id,)).fetchone()[0]
    if privacy == "nobody" or (privacy == "friends" and friendship_state(user_id, target_id) != "friends"):
        return error("MESSAGES_DISABLED", "This user is not accepting messages", 403)
    existing = get_sql().execute(
        """SELECT cm1.conversation_id FROM conversation_members cm1
           JOIN conversation_members cm2 ON cm2.conversation_id=cm1.conversation_id
           WHERE cm1.user_id=? AND cm2.user_id=?
           AND (SELECT COUNT(*) FROM conversation_members x WHERE x.conversation_id=cm1.conversation_id)=2 LIMIT 1""",
        (user_id, target_id),
    ).fetchone()
    if existing:
        return success({"id": existing["conversation_id"], "participants": _participants(existing["conversation_id"], user_id)})
    now = iso_now()
    with get_sql():
        cursor = get_sql().execute("INSERT INTO conversations(created_at,updated_at) VALUES(?,?)", (now, now))
        conversation_id = cursor.lastrowid
        get_sql().executemany(
            "INSERT INTO conversation_members(conversation_id,user_id,last_read_at,joined_at) VALUES(?,?,?,?)",
            [(conversation_id, user_id, now, now), (conversation_id, target_id, None, now)],
        )
    return success({"id": conversation_id, "participants": _participants(conversation_id, user_id)}, 201)


@messaging_bp.get("/api/conversations/<int:conversation_id>/messages")
@login_required
def messages(conversation_id):
    user_id = current_user()["userID"]
    if not _member(conversation_id, user_id):
        return error("CONVERSATION_NOT_FOUND", "Conversation not found", 404)
    limit = clamp_int(request.args.get("limit"), 40, 1, 60)
    query = {"conversationID": conversation_id}
    cursor = object_id(request.args.get("cursor"))
    if cursor:
        query["_id"] = {"$lt": cursor}
    documents = list(get_mongo()["messages"].find(query).sort("_id", -1).limit(limit + 1))
    has_more = len(documents) > limit
    documents = documents[:limit]
    with get_sql():
        get_sql().execute(
            "UPDATE conversation_members SET last_read_at=? WHERE conversation_id=? AND user_id=?",
            (iso_now(), conversation_id, user_id),
        )
    return success(
        [_serialize_message(item) for item in reversed(documents)],
        nextCursor=str(documents[-1]["_id"]) if has_more else None,
        participants=_participants(conversation_id, user_id),
    )


@messaging_bp.post("/api/conversations/<int:conversation_id>/messages")
@login_required
@limiter.limit("120 per hour")
def send_message(conversation_id):
    user_id = current_user()["userID"]
    if not _member(conversation_id, user_id):
        return error("CONVERSATION_NOT_FOUND", "Conversation not found", 404)
    participants = [row["user_id"] for row in get_sql().execute(
        "SELECT user_id FROM conversation_members WHERE conversation_id=? AND user_id != ?", (conversation_id, user_id)
    )]
    if not participants or any(_blocked(user_id, participant) for participant in participants):
        return error("MESSAGING_BLOCKED", "Messaging is unavailable", 403)
    data = request.get_json(silent=True) or {}
    try:
        text = clean_text(data.get("content"), 4000)
    except ValueError as exception:
        return error("VALIDATION_ERROR", str(exception), 422)
    media_ids = list(dict.fromkeys(str(item) for item in data.get("media", [])))[:1]
    if not text and not media_ids:
        return error("EMPTY_MESSAGE", "Add a message or an image", 422)
    if media_ids:
        row = get_sql().execute(
            "SELECT 1 FROM media_files WHERE media_id=? AND owner_id=? AND is_private=1 AND conversation_id=?",
            (media_ids[0], user_id, conversation_id),
        ).fetchone()
        if not row:
            return error("INVALID_MEDIA", "Message attachment is unavailable", 422)
    now = utcnow()
    document = {"conversationID": conversation_id, "senderID": user_id, "content": text, "media": media_ids, "createdAt": now, "edited": False}
    result = get_mongo()["messages"].insert_one(document)
    with get_sql():
        get_sql().execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?", (now.isoformat(), conversation_id))
        get_sql().execute("UPDATE conversation_members SET last_read_at=? WHERE conversation_id=? AND user_id=?", (now.isoformat(), conversation_id, user_id))
    for participant in participants:
        notify(participant, user_id, "message", {"conversationId": conversation_id, "messageId": str(result.inserted_id)}, f"message:{result.inserted_id}:{participant}")
    return success(_serialize_message({**document, "_id": result.inserted_id}), 201)


@messaging_bp.post("/api/conversations/<int:conversation_id>/read")
@login_required
def mark_read(conversation_id):
    if not _member(conversation_id, current_user()["userID"]):
        return error("CONVERSATION_NOT_FOUND", "Conversation not found", 404)
    with get_sql():
        get_sql().execute("UPDATE conversation_members SET last_read_at=? WHERE conversation_id=? AND user_id=?", (iso_now(), conversation_id, current_user()["userID"]))
    return success({"read": True})
