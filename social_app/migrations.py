import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, MongoClient
from werkzeug.security import generate_password_hash


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _columns(connection, table):
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _add_column(connection, table, definition):
    name = definition.split()[0]
    if name not in _columns(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def backup_sqlite(sqlite_path):
    path = Path(sqlite_path)
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "app-pre-circa-v2.db"
    if backup_path.exists():
        return backup_path
    source = sqlite3.connect(path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def migration_001_core(connection):
    now = utcnow()
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            userID INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL DEFAULT '',
            password_hash TEXT,
            created_at TEXT,
            updated_at TEXT,
            account_status TEXT NOT NULL DEFAULT 'active',
            role TEXT NOT NULL DEFAULT 'user'
        )"""
    )
    for definition in (
        "password_hash TEXT", "created_at TEXT", "updated_at TEXT",
        "account_status TEXT NOT NULL DEFAULT 'active'", "role TEXT NOT NULL DEFAULT 'user'",
    ):
        _add_column(connection, "users", definition)
    connection.execute("UPDATE users SET created_at = COALESCE(created_at, ?), updated_at = COALESCE(updated_at, ?)", (now, now))

    connection.execute(
        """CREATE TABLE IF NOT EXISTS friendships (
            _id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            followed_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            status INTEGER NOT NULL DEFAULT 1 CHECK(status BETWEEN 0 AND 2),
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(follower_id, followed_id),
            CHECK(follower_id != followed_id)
        )"""
    )
    _add_column(connection, "friendships", "created_at TEXT")
    _add_column(connection, "friendships", "updated_at TEXT")
    connection.execute("UPDATE friendships SET created_at = COALESCE(created_at, ?), updated_at = COALESCE(updated_at, ?)", (now, now))

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(userID) ON DELETE CASCADE,
            display_name TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
            avatar TEXT, cover_image TEXT, location TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
            profile_visibility TEXT NOT NULL DEFAULT 'public', message_privacy TEXT NOT NULL DEFAULT 'everyone',
            friend_request_privacy TEXT NOT NULL DEFAULT 'everyone', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blocks (
            blocker_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            blocked_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            created_at TEXT NOT NULL, PRIMARY KEY(blocker_id, blocked_id), CHECK(blocker_id != blocked_id)
        );
        CREATE TABLE IF NOT EXISTS bookmarks (
            user_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            post_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(user_id, post_id)
        );
        CREATE TABLE IF NOT EXISTS post_reactions (
            user_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            post_id TEXT NOT NULL, reaction TEXT NOT NULL DEFAULT 'like', created_at TEXT NOT NULL,
            PRIMARY KEY(user_id, post_id)
        );
        CREATE TABLE IF NOT EXISTS comment_reactions (
            user_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            comment_id TEXT NOT NULL, reaction TEXT NOT NULL DEFAULT 'like', created_at TEXT NOT NULL,
            PRIMARY KEY(user_id, comment_id)
        );
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversation_members (
            conversation_id INTEGER NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            last_read_at TEXT, joined_at TEXT NOT NULL, PRIMARY KEY(conversation_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            target_type TEXT NOT NULL, target_id TEXT NOT NULL, reason TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notification_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(userID) ON DELETE CASCADE,
            friend_requests INTEGER NOT NULL DEFAULT 1, comments INTEGER NOT NULL DEFAULT 1,
            mentions INTEGER NOT NULL DEFAULT 1, reactions INTEGER NOT NULL DEFAULT 1,
            messages INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS media_files (
            media_id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(userID) ON DELETE CASCADE,
            kind TEXT NOT NULL, mime_type TEXT NOT NULL, storage_name TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL, is_private INTEGER NOT NULL DEFAULT 0,
            conversation_id INTEGER REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_friendships_follower_status ON friendships(follower_id, status);
        CREATE INDEX IF NOT EXISTS idx_friendships_followed_status ON friendships(followed_id, status);
        CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON blocks(blocked_id, blocker_id);
        CREATE INDEX IF NOT EXISTS idx_bookmarks_user_created ON bookmarks(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_reactions_post ON post_reactions(post_id);
        CREATE INDEX IF NOT EXISTS idx_members_user ON conversation_members(user_id, conversation_id);
        CREATE INDEX IF NOT EXISTS idx_reports_status_created ON reports(status, created_at DESC);
        """
    )
    connection.execute(
        """INSERT OR IGNORE INTO profiles(user_id, display_name, created_at, updated_at)
           SELECT userID, username, COALESCE(created_at, ?), COALESCE(updated_at, ?) FROM users""",
        (now, now),
    )
    connection.execute("INSERT OR IGNORE INTO notification_settings(user_id) SELECT userID FROM users")


def migration_002_hash_passwords(connection):
    rows = connection.execute("SELECT userID, password, password_hash FROM users").fetchall()
    now = utcnow()
    for user_id, legacy_password, password_hash in rows:
        if password_hash:
            if legacy_password:
                connection.execute("UPDATE users SET password = '', updated_at = ? WHERE userID = ?", (now, user_id))
            continue
        if not legacy_password:
            continue
        connection.execute(
            "UPDATE users SET password_hash = ?, password = '', updated_at = ? WHERE userID = ?",
            (generate_password_hash(legacy_password), now, user_id),
        )


SQL_MIGRATIONS = ((1, migration_001_core), (2, migration_002_hash_passwords))


def migrate_sqlite(sqlite_path):
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    backup_sqlite(sqlite_path)
    connection = sqlite3.connect(sqlite_path, timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for version, migration in SQL_MIGRATIONS:
            if version in applied:
                continue
            with connection:
                migration(connection)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, utcnow()),
                )
    finally:
        connection.close()


def migrate_mongo(uri, database_name="app"):
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[database_name]
    now = datetime.now(timezone.utc)
    posts = db["posts"]
    posts.update_many({"createdAt": {"$exists": False}}, [{"$set": {"createdAt": {"$toDate": "$_id"}}}])
    posts.update_many({"type": "post", "visibility": {"$exists": False}}, {"$set": {"visibility": "public"}})
    posts.update_many({"type": "post", "edited": {"$exists": False}}, {"$set": {"edited": False}})
    posts.create_index([("type", ASCENDING), ("createdAt", DESCENDING)])
    posts.create_index([("visibility", ASCENDING), ("createdAt", DESCENDING)])
    posts.create_index([("userID", ASCENDING), ("createdAt", DESCENDING)])
    posts.create_index([("hashtags", ASCENDING), ("createdAt", DESCENDING)])
    posts.create_index([("postID", ASCENDING), ("createdAt", ASCENDING)])
    db["messages"].create_index([("conversationID", ASCENDING), ("createdAt", DESCENDING)])
    db["notifications"].create_index([("userID", ASCENDING), ("read", ASCENDING), ("createdAt", DESCENDING)])
    db["notifications"].create_index(
        [("dedupeKey", ASCENDING)], unique=True, sparse=True
    )
    db["poll_votes"].create_index([("postID", ASCENDING), ("userID", ASCENDING)], unique=True)
    client.close()


def run_all():
    sqlite_path = os.getenv("SQLITE_PATH", "app.db")
    migrate_sqlite(sqlite_path)
    migrate_mongo(os.getenv("MONGO_URI", "mongodb://localhost:27017"), os.getenv("MONGO_DB_NAME", "app"))
