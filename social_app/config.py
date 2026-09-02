import os
import secrets


def configure_app(app, overrides=None):
    environment = os.getenv("APP_ENV", "development").lower()
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        if environment == "production":
            raise RuntimeError("SECRET_KEY must be configured in production")
        secret_key = secrets.token_hex(32)

    app.config.from_mapping(
        APP_ENV=environment,
        SECRET_KEY=secret_key,
        SQLITE_PATH=os.getenv("SQLITE_PATH", "app.db"),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        MONGO_DB_NAME=os.getenv("MONGO_DB_NAME", "app"),
        UPLOAD_DIR=os.getenv("UPLOAD_DIR", os.path.abspath("uploads")),
        MAX_CONTENT_LENGTH=55 * 1024 * 1024,
        SESSION_COOKIE_NAME="circa_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=environment == "production",
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
        JSON_SORT_KEYS=False,
    )
    if overrides:
        app.config.update(overrides)
