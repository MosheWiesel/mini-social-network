# Circa

Circa is a bilingual Hebrew/English social network built with Flask, SQLite, MongoDB Atlas, and a modular Vanilla JavaScript frontend. It supports secure accounts, public and friends feeds, profiles, friendships, posts with media and polls, threaded comments, reactions, bookmarks, search, private messages, notifications, blocking, and reporting.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python migrate.py
flask --app app run --debug
```

MongoDB should be available at `mongodb://localhost:27017`, or set `MONGO_URI` in an uncommitted `.env`/shell environment. Never use `seed_data.py` against production; it contains an explicit production guard.

Run the test suite with:

```bash
pytest -q
```

See [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), and [DEPLOYMENT.md](DEPLOYMENT.md) for design and operations details.
