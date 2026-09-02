import re
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .db import get_mongo, get_sql
from .notifications import notify
from .security import current_user, error, limiter, login_required, success
from .users import PROFILE_QUERY, friendship_state, profile_for
from .utils import clamp_int, clean_text, extract_hashtags, extract_mentions, json_datetime, object_id, utcnow


content_bp = Blueprint("content", __name__)


def _blocked_ids(user_id):
    rows = get_sql().execute(
        "SELECT blocked_id AS id FROM blocks WHERE blocker_id=? UNION SELECT blocker_id AS id FROM blocks WHERE blocked_id=?",
        (user_id, user_id),
    ).fetchall()
    return {row["id"] for row in rows}


def _friend_ids(user_id):
    rows = get_sql().execute(
        """SELECT CASE WHEN follower_id=? THEN followed_id ELSE follower_id END AS id
           FROM friendships WHERE status=2 AND (follower_id=? OR followed_id=?)""",
        (user_id, user_id, user_id),
    ).fetchall()
    return {row["id"] for row in rows}


def _can_view_post(post, user_id):
    author_id = int(post.get("userID", 0))
    if author_id in _blocked_ids(user_id):
        return False
    visibility = post.get("visibility", "public")
    return author_id == user_id or visibility == "public" or (visibility == "friends" and author_id in _friend_ids(user_id))


def _author(user_id, viewer_id):
    row = get_sql().execute(PROFILE_QUERY + " AND u.userID=?", (user_id,)).fetchone()
    if not row:
        return {"id": user_id, "username": "deleted", "displayName": "Deleted account", "avatar": None}
    item = profile_for(row, viewer_id)
    return {key: item[key] for key in ("id", "username", "displayName", "avatar")}


def _media_items(media_ids, viewer_id, conversation_id=None):
    if not media_ids:
        return []
    placeholders = ",".join("?" for _ in media_ids)
    rows = get_sql().execute(
        f"SELECT media_id, kind, mime_type, is_private, conversation_id FROM media_files WHERE media_id IN ({placeholders})",
        tuple(media_ids),
    ).fetchall()
    result = []
    for row in rows:
        if row["is_private"] and row["conversation_id"] != conversation_id:
            continue
        result.append({"id": row["media_id"], "kind": row["kind"], "mimeType": row["mime_type"], "url": f"/api/media/{row['media_id']}"})
    return result


def _comment_count(post_id):
    return get_mongo()["posts"].count_documents({"type": "comment", "postID": post_id, "deleted": {"$ne": True}})


def serialize_comment(document, viewer_id):
    comment_id = str(document["_id"])
    reaction_count = get_sql().execute("SELECT COUNT(*) FROM comment_reactions WHERE comment_id=?", (comment_id,)).fetchone()[0]
    reacted = bool(get_sql().execute("SELECT 1 FROM comment_reactions WHERE comment_id=? AND user_id=?", (comment_id, viewer_id)).fetchone())
    return {
        "id": comment_id, "postId": str(document.get("postID")),
        "parentId": str(document.get("replyTo")) if document.get("replyTo") else None,
        "author": _author(int(document.get("userID", 0)), viewer_id),
        "content": "" if document.get("deleted") else document.get("content", ""),
        "deleted": bool(document.get("deleted")), "edited": bool(document.get("edited")),
        "createdAt": json_datetime(document.get("createdAt") or document["_id"].generation_time),
        "reactionCount": reaction_count, "reacted": reacted,
        "canEdit": int(document.get("userID", 0)) == viewer_id and not document.get("deleted"),
    }


def serialize_post(document, viewer_id, include_comments=True):
    post_id = str(document["_id"])
    object_post_id = document["_id"]
    reaction_count = get_sql().execute("SELECT COUNT(*) FROM post_reactions WHERE post_id=?", (post_id,)).fetchone()[0]
    reacted = bool(get_sql().execute("SELECT 1 FROM post_reactions WHERE post_id=? AND user_id=?", (post_id, viewer_id)).fetchone())
    bookmarked = bool(get_sql().execute("SELECT 1 FROM bookmarks WHERE post_id=? AND user_id=?", (post_id, viewer_id)).fetchone())
    result = {
        "id": post_id, "author": _author(int(document.get("userID", 0)), viewer_id),
        "content": document.get("content", ""), "postType": document.get("postType", "text"),
        "visibility": document.get("visibility", "public"),
        "media": _media_items(document.get("media", []), viewer_id),
        "mentions": document.get("mentions", []), "hashtags": document.get("hashtags", []),
        "poll": document.get("poll"), "edited": bool(document.get("edited")),
        "createdAt": json_datetime(document.get("createdAt") or document["_id"].generation_time),
        "updatedAt": json_datetime(document.get("updatedAt")),
        "commentCount": _comment_count(object_post_id), "reactionCount": reaction_count,
        "reacted": reacted, "bookmarked": bookmarked,
        "canEdit": int(document.get("userID", 0)) == viewer_id,
    }
    if result["poll"]:
        votes = list(get_mongo()["poll_votes"].find({"postID": object_post_id}))
        totals = [0] * len(result["poll"].get("options", []))
        own_vote = None
        for vote in votes:
            option = vote.get("option")
            if isinstance(option, int) and 0 <= option < len(totals):
                totals[option] += 1
            if vote.get("userID") == viewer_id:
                own_vote = option
        result["poll"] = {**result["poll"], "totals": totals, "totalVotes": sum(totals), "ownVote": own_vote}
    if include_comments:
        comments = list(get_mongo()["posts"].find({"type": "comment", "postID": object_post_id}).sort("createdAt", 1).limit(50))
        result["comments"] = [serialize_comment(comment, viewer_id) for comment in comments]
    return result


def _feed_query(kind, user_id):
    blocked = list(_blocked_ids(user_id))
    if kind == "global":
        return {"type": "post", "visibility": "public", "userID": {"$nin": blocked}}
    allowed = list(_friend_ids(user_id) | {user_id})
    return {
        "type": "post", "userID": {"$in": allowed, "$nin": blocked},
        "$or": [{"visibility": {"$in": ["public", "friends"]}}, {"userID": user_id}],
    }


@content_bp.get("/api/feed/<kind>")
@login_required
def feed(kind):
    if kind not in {"global", "friends"}:
        return error("INVALID_FEED", "Feed not found", 404)
    user_id = current_user()["userID"]
    limit = clamp_int(request.args.get("limit"), 20, 1, 30)
    query = _feed_query(kind, user_id)
    cursor = object_id(request.args.get("cursor"))
    if cursor:
        query["_id"] = {"$lt": cursor}
    documents = list(get_mongo()["posts"].find(query).sort("_id", -1).limit(limit + 1))
    has_more = len(documents) > limit
    documents = documents[:limit]
    return success(
        [serialize_post(post, user_id) for post in documents],
        nextCursor=str(documents[-1]["_id"]) if has_more else None,
    )


@content_bp.get("/api/users/<username>/posts")
@login_required
def profile_posts(username):
    user_id = current_user()["userID"]
    target = get_sql().execute("SELECT userID FROM users WHERE username=? COLLATE NOCASE AND account_status='active'", (username,)).fetchone()
    if not target:
        return error("PROFILE_NOT_FOUND", "Profile not found", 404)
    documents = list(get_mongo()["posts"].find({"type": "post", "userID": target["userID"]}).sort("_id", -1).limit(21))
    visible = [item for item in documents if _can_view_post(item, user_id)][:20]
    return success([serialize_post(post, user_id) for post in visible])


@content_bp.post("/api/posts")
@login_required
@limiter.limit("20 per hour")
def create_post():
    data = request.get_json(silent=True) or {}
    try:
        text = clean_text(data.get("content"), 5000)
    except ValueError as exception:
        return error("VALIDATION_ERROR", str(exception), 422)
    visibility = data.get("visibility", "public")
    if visibility not in {"public", "friends", "private"}:
        return error("INVALID_VISIBILITY", "Invalid post visibility", 422)
    media_ids = list(dict.fromkeys(str(item) for item in data.get("media", [])))[:6]
    poll_data = data.get("poll")
    poll = None
    if poll_data:
        try:
            question = clean_text(poll_data.get("question") or text, 280, required=True)
            options = [clean_text(item, 100, required=True) for item in poll_data.get("options", [])]
        except ValueError as exception:
            return error("INVALID_POLL", str(exception), 422)
        if not 2 <= len(options) <= 6 or len(set(options)) != len(options):
            return error("INVALID_POLL", "A poll requires 2–6 unique options", 422)
        poll = {"question": question, "options": options}
    if not text and not media_ids and not poll:
        return error("EMPTY_POST", "Add text, media, or a poll", 422)
    if media_ids:
        placeholders = ",".join("?" for _ in media_ids)
        rows = get_sql().execute(
            f"SELECT media_id FROM media_files WHERE media_id IN ({placeholders}) AND owner_id=? AND is_private=0",
            (*media_ids, current_user()["userID"]),
        ).fetchall()
        if {row["media_id"] for row in rows} != set(media_ids):
            return error("INVALID_MEDIA", "One or more media files are unavailable", 422)
    mention_names = extract_mentions(text)
    mention_rows = []
    if mention_names:
        placeholders = ",".join("?" for _ in mention_names)
        mention_rows = get_sql().execute(
            f"SELECT userID, username FROM users WHERE LOWER(username) IN ({placeholders}) AND account_status='active'",
            tuple(mention_names),
        ).fetchall()
    now = utcnow()
    document = {
        "type": "post", "postType": "poll" if poll else ("media" if media_ids else "text"),
        "userID": current_user()["userID"], "content": text, "createdAt": now, "updatedAt": now,
        "visibility": visibility, "media": media_ids,
        "mentions": [{"userID": row["userID"], "username": row["username"]} for row in mention_rows],
        "hashtags": extract_hashtags(text), "poll": poll, "edited": False,
    }
    result = get_mongo()["posts"].insert_one(document)
    for row in mention_rows:
        notify(row["userID"], current_user()["userID"], "mention", {"postId": str(result.inserted_id)}, f"mention:{result.inserted_id}:{row['userID']}")
    return success(serialize_post({**document, "_id": result.inserted_id}, current_user()["userID"]), 201)


@content_bp.get("/api/posts/<post_id>")
@login_required
def get_post(post_id):
    oid = object_id(post_id)
    document = get_mongo()["posts"].find_one({"_id": oid, "type": "post"}) if oid else None
    if not document or not _can_view_post(document, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Post not found", 404)
    return success(serialize_post(document, current_user()["userID"]))


@content_bp.put("/api/posts/<post_id>")
@login_required
def edit_post(post_id):
    oid = object_id(post_id)
    data = request.get_json(silent=True) or {}
    try:
        text = clean_text(data.get("content"), 5000, required=True)
    except ValueError as exception:
        return error("VALIDATION_ERROR", str(exception), 422)
    visibility = data.get("visibility", "public")
    if visibility not in {"public", "friends", "private"}:
        return error("INVALID_VISIBILITY", "Invalid post visibility", 422)
    document = get_mongo()["posts"].find_one_and_update(
        {"_id": oid, "type": "post", "userID": current_user()["userID"]},
        {"$set": {"content": text, "visibility": visibility, "hashtags": extract_hashtags(text), "edited": True, "updatedAt": utcnow()}},
        return_document=ReturnDocument.AFTER,
    ) if oid else None
    if not document:
        return error("POST_NOT_FOUND", "Post not found or access denied", 404)
    return success(serialize_post(document, current_user()["userID"]))


@content_bp.delete("/api/posts/<post_id>")
@login_required
def delete_post(post_id):
    oid = object_id(post_id)
    result = get_mongo()["posts"].delete_one({"_id": oid, "type": "post", "userID": current_user()["userID"]}) if oid else None
    if not result or result.deleted_count == 0:
        return error("POST_NOT_FOUND", "Post not found or access denied", 404)
    get_mongo()["posts"].delete_many({"type": "comment", "postID": oid})
    get_mongo()["poll_votes"].delete_many({"postID": oid})
    with get_sql():
        get_sql().execute("DELETE FROM post_reactions WHERE post_id=?", (post_id,))
        get_sql().execute("DELETE FROM bookmarks WHERE post_id=?", (post_id,))
    return success({"deleted": True})


@content_bp.post("/api/posts/<post_id>/reaction")
@login_required
def react_post(post_id):
    oid = object_id(post_id)
    document = get_mongo()["posts"].find_one({"_id": oid, "type": "post"}) if oid else None
    if not document or not _can_view_post(document, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Post not found", 404)
    user_id = current_user()["userID"]
    existing = get_sql().execute("SELECT 1 FROM post_reactions WHERE user_id=? AND post_id=?", (user_id, post_id)).fetchone()
    with get_sql():
        if existing:
            get_sql().execute("DELETE FROM post_reactions WHERE user_id=? AND post_id=?", (user_id, post_id))
        else:
            get_sql().execute("INSERT INTO post_reactions(user_id,post_id,reaction,created_at) VALUES(?,?,'like',datetime('now'))", (user_id, post_id))
    if not existing:
        notify(document["userID"], user_id, "reaction", {"postId": post_id}, f"reaction:{post_id}:{user_id}")
    count = get_sql().execute("SELECT COUNT(*) FROM post_reactions WHERE post_id=?", (post_id,)).fetchone()[0]
    return success({"reacted": not bool(existing), "count": count})


@content_bp.post("/api/posts/<post_id>/bookmark")
@login_required
def bookmark(post_id):
    oid = object_id(post_id)
    document = get_mongo()["posts"].find_one({"_id": oid, "type": "post"}) if oid else None
    if not document or not _can_view_post(document, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Post not found", 404)
    user_id = current_user()["userID"]
    existing = get_sql().execute("SELECT 1 FROM bookmarks WHERE user_id=? AND post_id=?", (user_id, post_id)).fetchone()
    with get_sql():
        if existing:
            get_sql().execute("DELETE FROM bookmarks WHERE user_id=? AND post_id=?", (user_id, post_id))
        else:
            get_sql().execute("INSERT INTO bookmarks(user_id,post_id,created_at) VALUES(?,?,datetime('now'))", (user_id, post_id))
    return success({"bookmarked": not bool(existing)})


@content_bp.get("/api/bookmarks")
@login_required
def bookmarks():
    user_id = current_user()["userID"]
    ids = [object_id(row["post_id"]) for row in get_sql().execute("SELECT post_id FROM bookmarks WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user_id,))]
    documents = {doc["_id"]: doc for doc in get_mongo()["posts"].find({"_id": {"$in": [item for item in ids if item]}, "type": "post"})}
    return success([serialize_post(documents[item], user_id) for item in ids if item in documents and _can_view_post(documents[item], user_id)])


@content_bp.post("/api/posts/<post_id>/comments")
@login_required
@limiter.limit("60 per hour")
def create_comment(post_id):
    oid = object_id(post_id)
    post = get_mongo()["posts"].find_one({"_id": oid, "type": "post"}) if oid else None
    if not post or not _can_view_post(post, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Post not found", 404)
    data = request.get_json(silent=True) or {}
    try:
        text = clean_text(data.get("content"), 1500, required=True)
    except ValueError as exception:
        return error("VALIDATION_ERROR", str(exception), 422)
    parent = object_id(data.get("parentId"))
    if data.get("parentId") and not get_mongo()["posts"].find_one({"_id": parent, "type": "comment", "postID": oid}):
        return error("COMMENT_NOT_FOUND", "Parent comment not found", 404)
    now = utcnow()
    document = {"type": "comment", "postID": oid, "replyTo": parent, "userID": current_user()["userID"], "content": text, "createdAt": now, "updatedAt": now, "edited": False, "deleted": False}
    result = get_mongo()["posts"].insert_one(document)
    kind = "reply" if parent else "comment"
    target_user = post["userID"]
    if parent:
        parent_doc = get_mongo()["posts"].find_one({"_id": parent})
        target_user = parent_doc.get("userID", target_user)
    notify(target_user, current_user()["userID"], kind, {"postId": post_id, "commentId": str(result.inserted_id)}, f"{kind}:{result.inserted_id}:{target_user}")
    for mention_name in extract_mentions(text):
        row = get_sql().execute("SELECT userID FROM users WHERE username=? COLLATE NOCASE AND account_status='active'", (mention_name,)).fetchone()
        if row:
            notify(row["userID"], current_user()["userID"], "mention", {"postId": post_id, "commentId": str(result.inserted_id)}, f"mention-comment:{result.inserted_id}:{row['userID']}")
    return success(serialize_comment({**document, "_id": result.inserted_id}, current_user()["userID"]), 201)


@content_bp.get("/api/posts/<post_id>/comments")
@login_required
def list_comments(post_id):
    post_oid = object_id(post_id)
    post = get_mongo()["posts"].find_one({"_id": post_oid, "type": "post"}) if post_oid else None
    if not post or not _can_view_post(post, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Post not found", 404)
    limit = clamp_int(request.args.get("limit"), 30, 1, 50)
    query = {"type": "comment", "postID": post_oid}
    cursor = object_id(request.args.get("cursor"))
    if cursor:
        query["_id"] = {"$gt": cursor}
    documents = list(get_mongo()["posts"].find(query).sort("_id", 1).limit(limit + 1))
    has_more = len(documents) > limit
    documents = documents[:limit]
    return success(
        [serialize_comment(item, current_user()["userID"]) for item in documents],
        nextCursor=str(documents[-1]["_id"]) if has_more else None,
    )


@content_bp.put("/api/comments/<comment_id>")
@login_required
def edit_comment(comment_id):
    oid = object_id(comment_id)
    try:
        text = clean_text((request.get_json(silent=True) or {}).get("content"), 1500, required=True)
    except ValueError as exception:
        return error("VALIDATION_ERROR", str(exception), 422)
    document = get_mongo()["posts"].find_one_and_update(
        {"_id": oid, "type": "comment", "userID": current_user()["userID"], "deleted": {"$ne": True}},
        {"$set": {"content": text, "edited": True, "updatedAt": utcnow()}}, return_document=ReturnDocument.AFTER,
    ) if oid else None
    if not document:
        return error("COMMENT_NOT_FOUND", "Comment not found or access denied", 404)
    return success(serialize_comment(document, current_user()["userID"]))


@content_bp.delete("/api/comments/<comment_id>")
@login_required
def delete_comment(comment_id):
    oid = object_id(comment_id)
    document = get_mongo()["posts"].find_one({"_id": oid, "type": "comment", "userID": current_user()["userID"]}) if oid else None
    if not document:
        return error("COMMENT_NOT_FOUND", "Comment not found or access denied", 404)
    has_replies = get_mongo()["posts"].count_documents({"type": "comment", "replyTo": oid}) > 0
    if has_replies:
        get_mongo()["posts"].update_one({"_id": oid}, {"$set": {"content": "", "deleted": True, "updatedAt": utcnow()}})
    else:
        get_mongo()["posts"].delete_one({"_id": oid})
    return success({"deleted": True, "tombstone": has_replies})


@content_bp.post("/api/comments/<comment_id>/reaction")
@login_required
def react_comment(comment_id):
    oid = object_id(comment_id)
    comment = get_mongo()["posts"].find_one({"_id": oid, "type": "comment", "deleted": {"$ne": True}}) if oid else None
    if not comment:
        return error("COMMENT_NOT_FOUND", "Comment not found", 404)
    user_id = current_user()["userID"]
    existing = get_sql().execute("SELECT 1 FROM comment_reactions WHERE user_id=? AND comment_id=?", (user_id, comment_id)).fetchone()
    with get_sql():
        if existing:
            get_sql().execute("DELETE FROM comment_reactions WHERE user_id=? AND comment_id=?", (user_id, comment_id))
        else:
            get_sql().execute("INSERT INTO comment_reactions(user_id,comment_id,reaction,created_at) VALUES(?,?,'like',datetime('now'))", (user_id, comment_id))
    count = get_sql().execute("SELECT COUNT(*) FROM comment_reactions WHERE comment_id=?", (comment_id,)).fetchone()[0]
    return success({"reacted": not bool(existing), "count": count})


@content_bp.post("/api/posts/<post_id>/vote")
@login_required
def vote(post_id):
    oid = object_id(post_id)
    post = get_mongo()["posts"].find_one({"_id": oid, "type": "post", "poll": {"$ne": None}}) if oid else None
    option = (request.get_json(silent=True) or {}).get("option")
    if not post or not _can_view_post(post, current_user()["userID"]):
        return error("POST_NOT_FOUND", "Poll not found", 404)
    if not isinstance(option, int) or not 0 <= option < len(post["poll"].get("options", [])):
        return error("INVALID_OPTION", "Invalid poll option", 422)
    try:
        get_mongo()["poll_votes"].insert_one({"postID": oid, "userID": current_user()["userID"], "option": option, "createdAt": utcnow()})
    except DuplicateKeyError:
        return error("ALREADY_VOTED", "You already voted in this poll", 409)
    return success(serialize_post(post, current_user()["userID"])["poll"])


@content_bp.get("/api/hashtags/<tag>/posts")
@login_required
def hashtag_posts(tag):
    tag = clean_text(tag, 40).lower().lstrip("#")
    user_id = current_user()["userID"]
    documents = list(get_mongo()["posts"].find({"type": "post", "hashtags": tag}).sort("_id", -1).limit(30))
    return success([serialize_post(doc, user_id) for doc in documents if _can_view_post(doc, user_id)])


@content_bp.get("/api/explore")
@login_required
def explore():
    user_id = current_user()["userID"]
    pipeline = [
        {"$match": {"type": "post", "visibility": "public", "hashtags.0": {"$exists": True}}},
        {"$unwind": "$hashtags"}, {"$group": {"_id": "$hashtags", "count": {"$sum": 1}, "latest": {"$max": "$createdAt"}}},
        {"$sort": {"count": -1, "latest": -1}}, {"$limit": 10},
    ]
    trends = [{"tag": row["_id"], "count": row["count"]} for row in get_mongo()["posts"].aggregate(pipeline)]
    recent = list(get_mongo()["posts"].find(_feed_query("global", user_id)).sort("_id", -1).limit(10))
    return success({"hashtags": trends, "posts": [serialize_post(item, user_id) for item in recent]})


@content_bp.get("/api/search")
@login_required
@limiter.limit("30 per minute")
def search():
    query = clean_text(request.args.get("q"), 60)
    if len(query) < 2:
        return error("QUERY_TOO_SHORT", "Enter at least two characters", 422)
    user_id = current_user()["userID"]
    like = f"%{query.lower()}%"
    users = get_sql().execute(
        PROFILE_QUERY + " AND u.userID != ? AND (LOWER(u.username) LIKE ? OR LOWER(p.display_name) LIKE ?) LIMIT 10",
        (user_id, like, like),
    ).fetchall()
    blocked = _blocked_ids(user_id)
    safe_query = re.escape(query)
    posts = list(get_mongo()["posts"].find({"type": "post", "visibility": "public", "content": {"$regex": safe_query, "$options": "i"}, "userID": {"$nin": list(blocked)}}).sort("_id", -1).limit(10))
    tags = list(get_mongo()["posts"].aggregate([
        {"$match": {"type": "post", "visibility": "public", "hashtags": {"$regex": safe_query, "$options": "i"}}},
        {"$unwind": "$hashtags"}, {"$match": {"hashtags": {"$regex": safe_query, "$options": "i"}}},
        {"$group": {"_id": "$hashtags", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10},
    ]))
    return success({
        "users": [profile_for(row, user_id) for row in users if row["userID"] not in blocked],
        "posts": [serialize_post(post, user_id, include_comments=False) for post in posts],
        "hashtags": [{"tag": item["_id"], "count": item["count"]} for item in tags],
    })
