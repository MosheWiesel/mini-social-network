from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, request
from pymongo.errors import DuplicateKeyError

from .db import get_mongo, get_sql
from .security import current_user, login_required, success
from .utils import clamp_int, json_datetime, object_id


notifications_bp = Blueprint("notifications", __name__)


def notify(user_id, actor_id, kind, target=None, dedupe_key=None, text=None):
    if int(user_id) == int(actor_id):
        return
    document = {
        "userID": int(user_id), "actorID": int(actor_id), "kind": kind,
        "target": target or {}, "text": text or "", "read": False,
        "createdAt": datetime.now(timezone.utc),
    }
    if dedupe_key:
        document["dedupeKey"] = dedupe_key
    try:
        get_mongo()["notifications"].insert_one(document)
    except DuplicateKeyError:
        return


def serialize(document):
    actor_id = document.get("actorID")
    actor = get_sql().execute(
        """SELECT u.username, p.display_name, p.avatar FROM users u JOIN profiles p ON p.user_id=u.userID
           WHERE u.userID=? AND u.account_status='active'""", (actor_id,)
    ).fetchone()
    return {
        "id": str(document["_id"]), "actorId": actor_id,
        "actor": {"id": actor_id, "username": actor["username"], "displayName": actor["display_name"] or actor["username"], "avatar": actor["avatar"]} if actor else None,
        "kind": document.get("kind"), "target": document.get("target", {}),
        "text": document.get("text", ""), "read": bool(document.get("read")),
        "createdAt": json_datetime(document.get("createdAt")),
    }


@notifications_bp.get("/api/notifications")
@login_required
def list_notifications():
    user_id = current_user()["userID"]
    limit = clamp_int(request.args.get("limit"), 30, 1, 50)
    query = {"userID": user_id}
    cursor = object_id(request.args.get("cursor"))
    if cursor:
        query["_id"] = {"$lt": cursor}
    documents = list(get_mongo()["notifications"].find(query).sort("_id", -1).limit(limit + 1))
    has_more = len(documents) > limit
    documents = documents[:limit]
    unread = get_mongo()["notifications"].count_documents({"userID": user_id, "read": False})
    return success([serialize(item) for item in documents], nextCursor=str(documents[-1]["_id"]) if has_more else None, unread=unread)


@notifications_bp.post("/api/notifications/read")
@login_required
def mark_read():
    ids = (request.get_json(silent=True) or {}).get("ids", [])
    object_ids = [value for value in (object_id(item) for item in ids[:100]) if value]
    get_mongo()["notifications"].update_many(
        {"_id": {"$in": object_ids}, "userID": current_user()["userID"]}, {"$set": {"read": True}}
    )
    return success({"updated": True})


@notifications_bp.post("/api/notifications/read-all")
@login_required
def mark_all_read():
    get_mongo()["notifications"].update_many(
        {"userID": current_user()["userID"], "read": False}, {"$set": {"read": True}}
    )
    return success({"updated": True})
