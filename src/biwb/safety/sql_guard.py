"""Allowlist validation for every SQL statement the workbench executes.

The workbench never runs free-form SQL. Statements are built by the engine, and each one must pass
`check_sql` before execution: exactly one read-only query, only allowlisted tables, no table
functions, no file/network/extension functions. The DuckDB connection is also opened read-only
with external access disabled (see `duckdb_exec`), so this guard is one of two layers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_SQL_CHARS = 200_000

# Statement / clause node types that must never appear anywhere in the tree.
_BANNED_NODE_NAMES = (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterTable", "TruncateTable",
    "Command", "Copy", "Pragma", "Set", "Use", "Transaction", "Commit", "Rollback", "Into",
    "LoadData", "Attach", "Detach", "Install", "Grant", "Revoke", "Export", "Summarize", "Describe",
)
_BANNED_NODE_TYPES = tuple(
    getattr(exp, name) for name in _BANNED_NODE_NAMES if isinstance(getattr(exp, name, None), type)
)

# Functions that touch files, the network, extensions or engine state.
_BANNED_FUNCTIONS = {
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto", "read_json_objects",
    "read_ndjson", "read_ndjson_auto", "read_text", "read_blob", "read_xlsx", "parquet_scan",
    "parquet_metadata", "parquet_schema", "sniff_csv", "glob", "query", "query_table", "getenv",
    "current_setting", "duckdb_settings", "duckdb_extensions", "duckdb_secrets", "load", "install",
    "httpfs", "iceberg_scan", "delta_scan", "sqlite_scan", "postgres_scan", "mysql_scan",
    "duckdb_databases", "pragma_database_list", "which_secret",
}


class SqlGuardError(ValueError):
    """Raised when a statement is rejected. `reasons` lists every violation found."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class GuardResult:
    sql: str
    tables: frozenset[str]
    functions: frozenset[str] = field(default_factory=frozenset)


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return node.sql_name().lower()


def _table_name(table: exp.Table) -> str:
    parts = [p for p in (table.catalog, table.db, table.name) if p]
    return ".".join(parts).lower()


def check_sql(
    sql: str, allowed_tables: Iterable[str], *, dialect: str = "duckdb", default_schema: str = "main"
) -> GuardResult:
    """Validate `sql`; return what it reads, or raise SqlGuardError with all violations.

    An unqualified table name is allowed if either the bare name or `default_schema.name` is
    in `allowed_tables`.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise SqlGuardError(["empty statement"])
    if len(sql) > MAX_SQL_CHARS:
        raise SqlGuardError([f"statement longer than {MAX_SQL_CHARS} characters"])

    try:
        statements = [s for s in sqlglot.parse(sql, dialect=dialect) if s is not None]
    except ParseError as err:
        raise SqlGuardError([f"unparseable SQL: {err.errors[0]['description'] if err.errors else err}"]) \
            from err
    if len(statements) != 1:
        raise SqlGuardError([f"exactly one statement allowed, found {len(statements)}"])
    root = statements[0]

    reasons: list[str] = []
    if not isinstance(root, exp.Query):
        reasons.append(f"only SELECT queries are allowed, found {type(root).__name__}")

    for node in root.walk():
        if isinstance(node, _BANNED_NODE_TYPES):
            reasons.append(f"forbidden clause: {type(node).__name__}")

    functions = set()
    for func in root.find_all(exp.Func):
        name = _function_name(func)
        functions.add(name)
        if name in _BANNED_FUNCTIONS or name.startswith(("read_", "pragma_")):
            reasons.append(f"forbidden function: {name}")

    allowed = {t.lower() for t in allowed_tables}
    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    tables = set()
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            reasons.append(f"table functions and file paths are not allowed: {table.sql(dialect=dialect)}")
            continue
        name = _table_name(table)
        if any(ch in name for ch in ("/", "\\", ":")):
            reasons.append(f"table functions and file paths are not allowed: {name}")
            continue
        if name in cte_names:
            continue
        tables.add(name)
        qualified = name if (table.db or table.catalog) else f"{default_schema.lower()}.{name}"
        if name not in allowed and qualified not in allowed:
            reasons.append(f"table not in allowlist: {name}")

    if reasons:
        raise SqlGuardError(sorted(set(reasons)))
    return GuardResult(sql=sql, tables=frozenset(tables), functions=frozenset(functions))
