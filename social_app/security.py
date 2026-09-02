import secrets
from functools import wraps

from flask import g, jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .db import get_sql


limiter = Limiter(key_func=get_remote_address, default_limits=["600 per hour"], storage_uri="memory://")


def success(data=None, status=200, **meta):
    payload = {"data": data}
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status


def error(code, message, status=400):
    return jsonify({"error": {"code": code, "message": message}}), status


def ensure_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def current_user():
    if hasattr(g, "current_user"):
        return g.current_user
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    row = get_sql().execute(
        "SELECT userID, username, role, account_status, created_at FROM users WHERE userID = ?",
        (user_id,),
    ).fetchone()
    if not row or row["account_status"] != "active":
        session.clear()
        g.current_user = None
        return None
    g.current_user = row
    return row


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return error("AUTH_REQUIRED", "Authentication required", 401)
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "admin":
            return error("FORBIDDEN", "Administrator access required", 403)
        return view(*args, **kwargs)

    return wrapped


def init_security(app):
    limiter.init_app(app)

    @app.before_request
    def csrf_protection():
        if request.method in {"GET", "HEAD", "OPTIONS"} or not request.path.startswith("/api/"):
            return None
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            return error("CSRF_FAILED", "The security token is missing or invalid", 403)
        return None

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
            "object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_exception):
        if request.path.startswith("/api/"):
            return error("NOT_FOUND", "Resource not found", 404)
        return app.send_static_file("index.html")

    @app.errorhandler(413)
    def too_large(_exception):
        return error("PAYLOAD_TOO_LARGE", "The uploaded file is too large", 413)

    @app.errorhandler(ValueError)
    def invalid_value(exception):
        return error("VALIDATION_ERROR", str(exception), 422)

    @app.errorhandler(429)
    def rate_limited(_exception):
        return error("RATE_LIMITED", "Too many requests. Please try again shortly", 429)

    @app.errorhandler(500)
    def server_error(_exception):
        return error("SERVER_ERROR", "An unexpected error occurred", 500)
