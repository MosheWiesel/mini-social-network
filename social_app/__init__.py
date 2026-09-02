from flask import Flask, send_from_directory

from .config import configure_app
from .db import close_databases, get_mongo, get_sql, init_databases
from .security import init_security


def create_app(test_config=None):
    app = Flask(__name__, static_folder="../static", static_url_path="/static")
    configure_app(app, test_config)
    init_databases(app)
    init_security(app)

    from .auth import auth_bp
    from .content import content_bp
    from .media import media_bp
    from .messaging import messaging_bp
    from .notifications import notifications_bp
    from .social import social_bp
    from .users import users_bp

    for blueprint in (auth_bp, users_bp, social_bp, content_bp, messaging_bp, notifications_bp, media_bp):
        app.register_blueprint(blueprint)

    @app.get("/health")
    def health():
        get_sql().execute("SELECT 1").fetchone()
        get_mongo().client.admin.command("ping")
        return {"status": "ok"}

    @app.get("/")
    @app.get("/home/<path:unused>")
    @app.get("/explore")
    @app.get("/search")
    @app.get("/people")
    @app.get("/requests")
    @app.get("/messages")
    @app.get("/messages/<path:unused>")
    @app.get("/u/<path:unused>")
    @app.get("/notifications")
    @app.get("/bookmarks")
    @app.get("/settings/<path:unused>")
    def spa_shell(unused=None):
        return app.send_static_file("index.html")

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.webmanifest")

    @app.get("/service-worker.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "service-worker.js")
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    app.teardown_appcontext(close_databases)
    return app
