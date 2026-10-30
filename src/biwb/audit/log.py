"""Append-only audit log of user decisions and engine actions.

Immutability is enforced by triggers in the database (see migration 0001), not only by this API.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    id: int
    project_id: int | None
    actor: str
    action: str
    entity: str
    entity_id: str | None
    detail: dict[str, Any]
    created_at: str


def record(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    project_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    if not actor or not action or not entity:
        raise ValueError("actor, action and entity are required")
    cur = conn.execute(
        "INSERT INTO audit_log(project_id, actor, action, entity, entity_id, detail_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            project_id,
            actor,
            action,
            entity,
            None if entity_id is None else str(entity_id),
            json.dumps(detail or {}, sort_keys=True, default=str),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def events(conn: sqlite3.Connection, project_id: int | None = None) -> list[AuditEvent]:
    sql = "SELECT * FROM audit_log"
    params: tuple = ()
    if project_id is not None:
        sql += " WHERE project_id = ?"
        params = (project_id,)
    rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    return [
        AuditEvent(
            id=r["id"],
            project_id=r["project_id"],
            actor=r["actor"],
            action=r["action"],
            entity=r["entity"],
            entity_id=r["entity_id"],
            detail=json.loads(r["detail_json"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]
