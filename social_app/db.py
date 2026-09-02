import sqlite3

from flask import current_app, g
from pymongo import MongoClient


def init_databases(app):
    mongo_client = app.config.get("MONGO_CLIENT")
    if mongo_client is None:
        mongo_client = MongoClient(
            app.config["MONGO_URI"],
            connect=False,
            serverSelectionTimeoutMS=10000,
            uuidRepresentation="standard",
        )
    app.extensions["mongo_client"] = mongo_client
    app.extensions["mongo_db"] = mongo_client[app.config["MONGO_DB_NAME"]]


def get_sql():
    if "sql" not in g:
        connection = sqlite3.connect(current_app.config["SQLITE_PATH"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        g.sql = connection
    return g.sql


def get_mongo():
    return current_app.extensions["mongo_db"]


def close_databases(_error=None):
    connection = g.pop("sql", None)
    if connection is not None:
        connection.close()
