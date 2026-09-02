import io
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, request, send_file
from PIL import Image, UnidentifiedImageError

from .db import get_sql
from .security import current_user, error, limiter, login_required, success
from .utils import iso_now


media_bp = Blueprint("media", __name__)

IMAGE_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp"), "GIF": ("image/gif", ".gif")}
VIDEO_SIGNATURES = ((b"\x1aE\xdf\xa3", "video/webm", ".webm"),)


def _validate_image(data):
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Images may be up to 10 MB")
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError):
        raise ValueError("Invalid image file") from None
    if image.format not in IMAGE_FORMATS:
        raise ValueError("Only JPEG, PNG, WebP, and GIF images are supported")
    mime, suffix = IMAGE_FORMATS[image.format]
    output = io.BytesIO()
    if image.format == "GIF":
        image.save(output, format="GIF", save_all=True)
    else:
        image = image.convert("RGB") if image.mode not in {"RGB", "RGBA"} else image
        image.save(output, format=image.format, optimize=True)
    return output.getvalue(), mime, suffix


def _validate_video(data):
    if len(data) > 50 * 1024 * 1024:
        raise ValueError("Videos may be up to 50 MB")
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return data, "video/mp4", ".mp4"
    for signature, mime, suffix in VIDEO_SIGNATURES:
        if data.startswith(signature):
            return data, mime, suffix
    raise ValueError("Only valid MP4 and WebM videos are supported")


@media_bp.post("/api/media")
@login_required
@limiter.limit("30 per hour")
def upload_media():
    upload = request.files.get("file")
    kind = request.form.get("kind", "post")
    conversation_id = request.form.get("conversationId", type=int)
    if not upload or kind not in {"post", "avatar", "cover", "message"}:
        return error("INVALID_UPLOAD", "A valid media file is required", 422)
    data = upload.read(50 * 1024 * 1024 + 1)
    try:
        if kind in {"avatar", "cover"} or not upload.mimetype.startswith("video/"):
            clean_data, mime, suffix = _validate_image(data)
            media_kind = "image"
        else:
            clean_data, mime, suffix = _validate_video(data)
            media_kind = "video"
    except ValueError as exception:
        return error("INVALID_UPLOAD", str(exception), 422)
    if kind == "message":
        membership = get_sql().execute(
            "SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?",
            (conversation_id, current_user()["userID"]),
        ).fetchone()
        if not membership:
            return error("CONVERSATION_NOT_FOUND", "Conversation not found", 404)
    media_id = uuid.uuid4().hex
    storage_name = f"{uuid.uuid4().hex}{suffix}"
    directory = Path(current_app.config["UPLOAD_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / storage_name
    temporary = directory / f".{storage_name}.tmp"
    temporary.write_bytes(clean_data)
    os.replace(temporary, final_path)
    is_private = kind == "message"
    with get_sql():
        get_sql().execute(
            """INSERT INTO media_files(media_id,owner_id,kind,mime_type,storage_name,size_bytes,is_private,conversation_id,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (media_id, current_user()["userID"], media_kind, mime, storage_name, len(clean_data), int(is_private), conversation_id, iso_now()),
        )
        if kind in {"avatar", "cover"}:
            column = "avatar" if kind == "avatar" else "cover_image"
            get_sql().execute(f"UPDATE profiles SET {column}=?, updated_at=? WHERE user_id=?", (media_id, iso_now(), current_user()["userID"]))
    return success({"id": media_id, "kind": media_kind, "mimeType": mime, "url": f"/api/media/{media_id}"}, 201)


@media_bp.get("/api/media/<media_id>")
@login_required
def serve_media(media_id):
    row = get_sql().execute(
        "SELECT owner_id,mime_type,storage_name,is_private,conversation_id FROM media_files WHERE media_id=?", (media_id,)
    ).fetchone()
    if not row:
        return error("MEDIA_NOT_FOUND", "Media not found", 404)
    if row["is_private"]:
        membership = get_sql().execute(
            "SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?",
            (row["conversation_id"], current_user()["userID"]),
        ).fetchone()
        if not membership:
            return error("MEDIA_NOT_FOUND", "Media not found", 404)
    path = Path(current_app.config["UPLOAD_DIR"]) / row["storage_name"]
    if not path.is_file():
        return error("MEDIA_NOT_FOUND", "Media not found", 404)
    response = send_file(path, mimetype=row["mime_type"], conditional=True, max_age=86400 if not row["is_private"] else 0)
    response.headers["Content-Disposition"] = "inline"
    if row["is_private"]:
        response.headers["Cache-Control"] = "private, no-store"
    return response
