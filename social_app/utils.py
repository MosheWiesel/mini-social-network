import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bson import ObjectId


USERNAME_PATTERN = re.compile(r"^[\w.-]{3,30}$", re.UNICODE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w\u0590-\u05ff]{2,40})", re.UNICODE)
MENTION_PATTERN = re.compile(r"(?<!\w)@([\w.-]{3,30})", re.UNICODE)


def utcnow():
    return datetime.now(timezone.utc)


def iso_now():
    return utcnow().isoformat()


def json_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def clean_text(value, maximum, *, required=False):
    text = str(value or "").strip()
    if required and not text:
        raise ValueError("This field is required")
    if len(text) > maximum:
        raise ValueError(f"This field may contain at most {maximum} characters")
    return text


def valid_username(value):
    return bool(USERNAME_PATTERN.fullmatch(str(value or "")))


def valid_website(value):
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def object_id(value):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def extract_hashtags(text):
    return list(dict.fromkeys(match.lower() for match in HASHTAG_PATTERN.findall(text)))[:20]


def extract_mentions(text):
    return list(dict.fromkeys(match.lower() for match in MENTION_PATTERN.findall(text)))[:20]


def clamp_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
