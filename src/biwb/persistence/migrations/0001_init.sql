-- 0001_init: application state schema (architecture plan §5).
-- Analytical data lives in separate DuckDB files; this database holds projects, parsed
-- metadata, review decisions, test evidence and the audit log.

CREATE TABLE project (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    legacy_db_path  TEXT,
    target_db_path  TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE artifact (
    id             INTEGER PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES project(id),
    kind           TEXT NOT NULL CHECK (kind IN ('workbook', 'schema_spec', 'dataset', 'export')),
    original_name  TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    stored_path    TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE workbook (
    id               INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES project(id),
    artifact_id      INTEGER NOT NULL REFERENCES artifact(id),
    tableau_version  TEXT,
    source_build     TEXT,
    parsed_json      TEXT NOT NULL,
    complexity_json  TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_datasource (
    id                  INTEGER PRIMARY KEY,
    workbook_id         INTEGER NOT NULL REFERENCES workbook(id),
    internal_name       TEXT NOT NULL,
    caption             TEXT,
    connection_class    TEXT,
    relation_tree_json  TEXT,
    object_graph_json   TEXT,
    is_parameters       INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_field (
    id             INTEGER PRIMARY KEY,
    datasource_id  INTEGER NOT NULL REFERENCES wb_datasource(id),
    internal_name  TEXT NOT NULL,
    caption        TEXT,
    datatype       TEXT,
    role           TEXT,
    type           TEXT,
    default_agg    TEXT,
    is_calculated  INTEGER NOT NULL DEFAULT 0,
    remote_name    TEXT,
    remote_table   TEXT,
    xml_path       TEXT,
    xml_line       INTEGER,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_calculation (
    id                 INTEGER PRIMARY KEY,
    field_id           INTEGER NOT NULL REFERENCES wb_field(id),
    formula            TEXT NOT NULL,
    ast_json           TEXT,
    kind               TEXT,
    support_level      TEXT NOT NULL CHECK (support_level IN ('supported', 'partial', 'unsupported')),
    reason_codes_json  TEXT NOT NULL DEFAULT '[]',
    -- Only ever populated for supported calcs (or partial calcs with an acknowledged assumption).
    sql_translation    TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_dependency (
    id             INTEGER PRIMARY KEY,
    from_field_id  INTEGER NOT NULL REFERENCES wb_field(id),
    to_field_id    INTEGER NOT NULL REFERENCES wb_field(id),
    dep_type       TEXT NOT NULL CHECK (dep_type IN ('calc_ref', 'filter', 'shelf')),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_worksheet (
    id            INTEGER PRIMARY KEY,
    workbook_id   INTEGER NOT NULL REFERENCES workbook(id),
    name          TEXT NOT NULL,
    shelves_json  TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_worksheet_field (
    id            INTEGER PRIMARY KEY,
    worksheet_id  INTEGER NOT NULL REFERENCES wb_worksheet(id),
    field_id      INTEGER NOT NULL REFERENCES wb_field(id),
    shelf         TEXT NOT NULL,
    derivation    TEXT,
    pivot         TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_filter (
    id             INTEGER PRIMARY KEY,
    worksheet_id   INTEGER REFERENCES wb_worksheet(id),  -- NULL = data source filter
    field_id       INTEGER REFERENCES wb_field(id),
    filter_class   TEXT NOT NULL,
    spec_json      TEXT NOT NULL,
    is_context     INTEGER NOT NULL DEFAULT 0,
    support_level  TEXT NOT NULL CHECK (support_level IN ('supported', 'partial', 'unsupported')),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_parameter (
    id             INTEGER PRIMARY KEY,
    workbook_id    INTEGER NOT NULL REFERENCES workbook(id),
    name           TEXT NOT NULL,
    datatype       TEXT,
    current_value  TEXT,
    domain_json    TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_dashboard (
    id                    INTEGER PRIMARY KEY,
    workbook_id           INTEGER NOT NULL REFERENCES workbook(id),
    name                  TEXT NOT NULL,
    worksheet_names_json  TEXT NOT NULL DEFAULT '[]',
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE wb_support_item (
    id            INTEGER PRIMARY KEY,
    workbook_id   INTEGER NOT NULL REFERENCES workbook(id),
    element_type  TEXT NOT NULL,
    element_ref   TEXT NOT NULL,
    level         TEXT NOT NULL CHECK (level IN ('supported', 'partial', 'unsupported')),
    reason_code   TEXT,
    detail        TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE schema_model (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES project(id),
    side         TEXT NOT NULL CHECK (side IN ('legacy', 'target')),
    source_kind  TEXT NOT NULL,
    spec_json    TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE schema_column (
    id               INTEGER PRIMARY KEY,
    schema_model_id  INTEGER NOT NULL REFERENCES schema_model(id),
    table_name       TEXT NOT NULL,
    column_name      TEXT NOT NULL,
    data_type        TEXT NOT NULL,
    nullable         INTEGER NOT NULL DEFAULT 1,
    is_key           INTEGER NOT NULL DEFAULT 0,
    description      TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE column_profile (
    id                  INTEGER PRIMARY KEY,
    schema_column_id    INTEGER NOT NULL REFERENCES schema_column(id),
    row_count           INTEGER,
    null_pct            REAL,
    distinct_count      INTEGER,
    is_unique           INTEGER,
    min_val             TEXT,
    max_val             TEXT,
    sample_values_json  TEXT,  -- local only; never sent to an external API
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE table_grain (
    id                  INTEGER PRIMARY KEY,
    schema_model_id     INTEGER NOT NULL REFERENCES schema_model(id),
    table_name          TEXT NOT NULL,
    grain_columns_json  TEXT NOT NULL,
    verified            INTEGER NOT NULL DEFAULT 0,
    evidence_json       TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE mapping_candidate (
    id                     INTEGER PRIMARY KEY,
    project_id             INTEGER NOT NULL REFERENCES project(id),
    wb_field_id            INTEGER REFERENCES wb_field(id),
    legacy_column_id       INTEGER REFERENCES schema_column(id),
    target_column_id       INTEGER REFERENCES schema_column(id),
    match_class            TEXT NOT NULL,
    score                  REAL NOT NULL,
    score_components_json  TEXT NOT NULL,
    rationale              TEXT NOT NULL,
    confidence_band        TEXT NOT NULL CHECK (confidence_band IN ('high', 'medium', 'low', 'blocked')),
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE mapping_decision (
    id                       INTEGER PRIMARY KEY,
    candidate_id             INTEGER NOT NULL REFERENCES mapping_candidate(id),
    decision                 TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'alternative', 'deferred')),
    chosen_target_column_id  INTEGER REFERENCES schema_column(id),
    reviewer                 TEXT NOT NULL,
    comment                  TEXT,
    decided_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE assumption_ack (
    id               INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES project(id),
    subject_ref      TEXT NOT NULL,
    assumption_text  TEXT NOT NULL,
    acknowledged_by  TEXT NOT NULL,
    acknowledged_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE logic_finding (
    id                 INTEGER PRIMARY KEY,
    project_id         INTEGER NOT NULL REFERENCES project(id),
    subject_ref        TEXT NOT NULL,
    finding_type       TEXT NOT NULL,
    equivalence_level  TEXT NOT NULL CHECK (equivalence_level IN ('technical', 'semantic', 'business')),
    status             TEXT NOT NULL,
    evidence_json      TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE migration_plan (
    id               INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES project(id),
    version          INTEGER NOT NULL,
    plan_json        TEXT NOT NULL,
    decisions_hash   TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE sql_artifact (
    id           INTEGER PRIMARY KEY,
    plan_id      INTEGER NOT NULL REFERENCES migration_plan(id),
    purpose      TEXT NOT NULL,
    sql_text     TEXT NOT NULL,
    dialect      TEXT NOT NULL DEFAULT 'duckdb',
    guard_passed INTEGER NOT NULL,
    origin       TEXT NOT NULL CHECK (origin IN ('template')),  -- AI drafts are never stored here
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE metric_spec (
    id                 INTEGER PRIMARY KEY,
    project_id         INTEGER NOT NULL REFERENCES project(id),
    name               TEXT NOT NULL,
    legacy_expr        TEXT,
    target_expr        TEXT,
    filters_json       TEXT NOT NULL DEFAULT '[]',
    date_field_legacy  TEXT,
    date_field_target  TEXT,
    testability        TEXT NOT NULL CHECK (testability IN ('testable', 'conditional', 'not_testable')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE test_case (
    id              INTEGER PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES project(id),
    metric_spec_id  INTEGER REFERENCES metric_spec(id),
    family          TEXT NOT NULL,
    dimension       TEXT,
    period_grain    TEXT,
    tolerance_abs   REAL NOT NULL,
    tolerance_rel   REAL NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE test_run (
    id                  INTEGER PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES project(id),
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    legacy_fingerprint  TEXT NOT NULL,
    target_fingerprint  TEXT NOT NULL,
    decisions_hash      TEXT NOT NULL,
    rules_version       TEXT NOT NULL,
    engine_version      TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE test_result (
    id             INTEGER PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES test_run(id),
    test_case_id   INTEGER NOT NULL REFERENCES test_case(id),
    status         TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'blocked', 'error')),
    expected       TEXT,
    actual         TEXT,
    diff           TEXT,
    diff_pct       TEXT,
    severity       TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    legacy_sql     TEXT,
    target_sql     TEXT,
    segments_json  TEXT,
    result_hash    TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE discrepancy (
    id                         INTEGER PRIMARY KEY,
    run_id                     INTEGER NOT NULL REFERENCES test_run(id),
    test_result_id             INTEGER REFERENCES test_result(id),
    title                      TEXT NOT NULL,
    severity                   TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    explanation_deterministic  TEXT NOT NULL,
    recommended_investigation  TEXT NOT NULL,
    masked                     INTEGER NOT NULL DEFAULT 0,
    created_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE probe_result (
    id              INTEGER PRIMARY KEY,
    discrepancy_id  INTEGER NOT NULL REFERENCES discrepancy(id),
    probe_name      TEXT NOT NULL,
    outcome         TEXT NOT NULL CHECK (outcome IN ('supports', 'refutes', 'inconclusive')),
    evidence_json   TEXT NOT NULL,
    sql             TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- The only table the optional AI layer may write to.
CREATE TABLE ai_annotation (
    id               INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES project(id),
    subject_ref      TEXT NOT NULL,
    purpose          TEXT NOT NULL,
    model_requested  TEXT NOT NULL,
    model_answered   TEXT,
    payload_json     TEXT NOT NULL,
    payload_sha256   TEXT NOT NULL,
    response_json    TEXT,
    status           TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE readiness_assessment (
    id             INTEGER PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES project(id),
    run_id         INTEGER REFERENCES test_run(id),
    status         TEXT NOT NULL CHECK (status IN
                     ('ready', 'ready_with_conditions', 'not_ready', 'blocked', 'insufficient_evidence')),
    score          REAL,
    factors_json   TEXT NOT NULL,
    gates_json     TEXT NOT NULL,
    rules_version  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER REFERENCES project(id),
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    entity       TEXT NOT NULL,
    entity_id    TEXT,
    detail_json  TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Append-only: the database itself refuses edits and deletions of audit records.
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE INDEX idx_mapping_decision_candidate ON mapping_decision(candidate_id);
CREATE INDEX idx_test_result_run ON test_result(run_id);
CREATE INDEX idx_audit_log_project ON audit_log(project_id, id);
