"""SQLite connection handling and forward-only schema migrations for app.db."""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def connect(path: Path | str) -> sqlite3.Connection:
    """Open app.db with foreign keys enforced. Use ':memory:' for tests."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _migration_files() -> list[tuple[int, str, str]]:
    folder = resources.files("biwb.persistence") / "migrations"
    found = []
    for entry in folder.iterdir():
        match = _MIGRATION_NAME.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry.name, entry.read_text(encoding="utf-8")))
    found.sort()
    versions = [v for v, _, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError(f"Migration numbering must be contiguous from 0001, got {versions}")
    return found


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations in order; returns the names applied in this call."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
        " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    newly_applied = []
    for version, name, sql in _migration_files():
        if version in applied:
            continue
        # executescript commits implicitly; wrap so a failing migration leaves nothing behind.
        conn.executescript(f"BEGIN;\n{sql}\nINSERT INTO schema_migrations(version, name) "
                           f"VALUES ({version}, '{name}');\nCOMMIT;")
        newly_applied.append(name)
    return newly_applied


def open_app_db(path: Path | str) -> sqlite3.Connection:
    conn = connect(path)
    apply_migrations(conn)
    return conn
