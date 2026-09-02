"""Backward-compatible database initializer.

Railway now invokes migrate.py directly. Keeping this file avoids breaking
older local instructions while using the same safe, idempotent migrations.
"""

from social_app.migrations import run_all


if __name__ == "__main__":
    run_all()
    print("Circa database initialization completed")
