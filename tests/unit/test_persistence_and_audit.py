import sqlite3

import pytest

from biwb.audit import log as audit
from biwb.persistence.db import apply_migrations, connect, open_app_db

EXPECTED_TABLES = {
    "project", "artifact", "workbook", "wb_datasource", "wb_field", "wb_calculation", "wb_dependency",
    "wb_worksheet", "wb_worksheet_field", "wb_filter", "wb_parameter", "wb_dashboard",
    "wb_support_item", "schema_model", "schema_column", "column_profile", "table_grain",
    "mapping_candidate", "mapping_decision", "assumption_ack", "logic_finding", "migration_plan",
    "sql_artifact", "metric_spec", "test_case", "test_run", "test_result", "discrepancy",
    "probe_result", "ai_annotation", "readiness_assessment", "audit_log", "schema_migrations",
}


@pytest.fixture
def conn():
    c = open_app_db(":memory:")
    yield c
    c.close()


def test_all_planned_tables_exist(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= names


def test_migrations_are_idempotent(conn):
    assert apply_migrations(conn) == []


def test_file_database_survives_reopen(tmp_path):
    path = tmp_path / "sub" / "app.db"
    c1 = open_app_db(path)
    c1.execute("INSERT INTO project(name) VALUES ('demo')")
    c1.commit()
    c1.close()
    c2 = open_app_db(path)
    assert c2.execute("SELECT name FROM project").fetchone()[0] == "demo"
    c2.close()


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO artifact(project_id, kind, original_name, sha256, stored_path, size_bytes)"
                     " VALUES (999, 'workbook', 'a.twb', 'x', 'p', 1)")


def test_sql_artifact_rejects_non_template_origin(conn):
    conn.execute("INSERT INTO project(name) VALUES ('p')")
    conn.execute("INSERT INTO migration_plan(project_id, version, plan_json, decisions_hash)"
                 " VALUES (1, 1, '{}', 'h')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sql_artifact(plan_id, purpose, sql_text, guard_passed, origin)"
                     " VALUES (1, 'x', 'SELECT 1', 1, 'ai_suggested')")


def test_audit_record_and_read_back(conn):
    conn.execute("INSERT INTO project(name) VALUES ('p')")
    event_id = audit.record(conn, actor="analyst", action="approve", entity="mapping_candidate",
                            entity_id=7, project_id=1, detail={"comment": "ok"})
    events = audit.events(conn, project_id=1)
    assert [e.id for e in events] == [event_id]
    assert events[0].detail == {"comment": "ok"}
    assert events[0].entity_id == "7"


def test_audit_log_is_append_only(conn):
    audit.record(conn, actor="a", action="b", entity="c")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET actor = 'mallory'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")


def test_audit_requires_fields(conn):
    with pytest.raises(ValueError):
        audit.record(conn, actor="", action="x", entity="y")


def test_connect_memory_has_fk_pragma():
    c = connect(":memory:")
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
