import io

import mongomock
import pytest
from pymongo import ASCENDING

from social_app import create_app
from social_app.migrations import migrate_sqlite


@pytest.fixture
def app(tmp_path):
    database = tmp_path / "app.db"
    migrate_sqlite(database)
    mongo = mongomock.MongoClient()
    mongo["test_app"]["poll_votes"].create_index([("postID", ASCENDING), ("userID", ASCENDING)], unique=True)
    application = create_app({
        "TESTING": True, "RATELIMIT_ENABLED": False, "SECRET_KEY": "test-secret-key",
        "SQLITE_PATH": str(database), "MONGO_CLIENT": mongo, "MONGO_DB_NAME": "test_app",
        "UPLOAD_DIR": str(tmp_path / "uploads"), "SESSION_COOKIE_SECURE": False,
    })
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client):
    return client.get("/api/csrf").get_json()["data"]["csrfToken"]


def api(client, method, path, *, json=None, data=None, content_type=None):
    token = csrf(client)
    return client.open(path, method=method, json=json, data=data, content_type=content_type, headers={"X-CSRF-Token": token})


def signup(client, username, password="password9"):
    return api(client, "POST", "/api/auth/signup", json={"username": username, "password": password})


def login(client, username, password="password9"):
    return api(client, "POST", "/api/auth/login", json={"username": username, "password": password})
