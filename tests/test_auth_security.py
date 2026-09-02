import sqlite3

import mongomock
from werkzeug.security import check_password_hash

from social_app import create_app
from social_app.migrations import migrate_sqlite
from tests.conftest import api, csrf, login, signup


def test_signup_hashes_password_and_me_uses_session(app, client):
    response = signup(client, "alice")
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["user"]["username"] == "alice"
    connection = sqlite3.connect(app.config["SQLITE_PATH"])
    legacy, hashed = connection.execute("SELECT password,password_hash FROM users WHERE username='alice'").fetchone()
    connection.close()
    assert legacy == ""
    assert check_password_hash(hashed, "password9")
    assert client.get("/api/me").get_json()["data"]["user"]["username"] == "alice"


def test_login_logout_wrong_password_and_csrf(app, client):
    signup(client, "alice")
    api(client, "POST", "/api/auth/logout")
    assert login(client, "alice", "wrong-password").status_code == 401
    assert login(client, "alice").status_code == 200
    assert client.post("/api/auth/logout").status_code == 403
    assert api(client, "POST", "/api/auth/logout").status_code == 200
    assert client.get("/api/me").get_json()["data"]["user"] is None


def test_password_change_requires_current_password(client):
    signup(client, "alice")
    assert api(client, "PUT", "/api/account/password", json={"currentPassword":"bad", "newPassword":"new-password9"}).status_code == 401
    assert api(client, "PUT", "/api/account/password", json={"currentPassword":"password9", "newPassword":"new-password9"}).status_code == 200
    api(client, "POST", "/api/auth/logout")
    assert login(client, "alice", "new-password9").status_code == 200


def test_plaintext_migration_is_idempotent_and_backed_up(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE users(userID INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL)")
    connection.execute("CREATE TABLE friendships(_id INTEGER PRIMARY KEY,follower_id INTEGER,followed_id INTEGER,status INTEGER)")
    connection.execute("INSERT INTO users VALUES(1,'legacy','plain-password')")
    connection.commit(); connection.close()
    migrate_sqlite(path); migrate_sqlite(path)
    connection = sqlite3.connect(path)
    legacy, hashed = connection.execute("SELECT password,password_hash FROM users").fetchone()
    versions = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    connection.close()
    assert legacy == "" and check_password_hash(hashed, "plain-password")
    assert versions == 2
    assert (tmp_path / "backups" / "app-pre-circa-v2.db").exists()


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]


def test_login_rate_limit_is_enforced(tmp_path):
    path = tmp_path / "limited.db"
    migrate_sqlite(path)
    limited_app = create_app({
        "TESTING": True, "RATELIMIT_ENABLED": True, "SECRET_KEY": "limit-secret",
        "SQLITE_PATH": str(path), "MONGO_CLIENT": mongomock.MongoClient(),
        "MONGO_DB_NAME": "limited", "SESSION_COOKIE_SECURE": False,
    })
    limited_client = limited_app.test_client()
    statuses = [login(limited_client, "missing-user", "not-the-password").status_code for _ in range(9)]
    assert statuses[-1] == 429
