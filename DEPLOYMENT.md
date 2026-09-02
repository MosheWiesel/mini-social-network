# Railway deployment

Production uses the Railway project `adventurous-tranquility`, environment `production`, service `mini-social-network`, and a persistent volume mounted at `/data`.

## Required variables

Configure these in Railway without committing their values:

- `MONGO_URI` — MongoDB Atlas connection URI
- `SQLITE_PATH=/data/app.db`
- `SECRET_KEY` — a long random secret
- `UPLOAD_DIR=/data/uploads`
- `APP_ENV=production`

The Railway service's deployment settings use this explicit start command:

```text
python migrate.py && gunicorn app:app --bind 0.0.0.0:$PORT
```

`migrate.py` creates a consistent SQLite backup before the first v2 schema change, applies each SQL migration once through `schema_migrations`, safely hashes legacy plaintext passwords, normalizes old Mongo documents, and creates indexes. It never seeds or deletes production content. `seed_data.py` refuses to run when `APP_ENV=production`.

## Release procedure

1. Run `pytest -q`, JavaScript syntax checks, Python compilation, and the security audit.
2. Review the complete branch diff and confirm no secret or database file is staged.
3. Push `feature/circa-v2`, review it, then merge/push to `main`.
4. Wait for Railway to report a successful deployment.
5. Inspect deployment logs for migration completion, Gunicorn worker boot, and exceptions.
6. Smoke-test the public domain, session authentication, both feeds, profile editing, content, messaging, notifications, uploads, Hebrew/English, themes, and mobile layout.

Do not scale the service above one replica while SQLite is the relational store. PostgreSQL is the recommended future migration for horizontal scaling.
