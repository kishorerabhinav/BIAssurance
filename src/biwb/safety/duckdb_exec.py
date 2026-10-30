"""Read-only, sandboxed execution of guarded queries against a DuckDB analytical database."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from biwb.safety.sql_guard import check_sql

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_ROW_CAP = 100_000


class QueryLimitError(RuntimeError):
    """Raised when a query exceeds the row cap or the time limit."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]


def open_readonly(path: Path | str) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB file read-only with file/network access disabled and configuration locked."""
    db_path = Path(path)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    con = duckdb.connect(
        str(db_path),
        read_only=True,
        config={"enable_external_access": False, "autoinstall_known_extensions": False,
                "autoload_known_extensions": False},
    )
    con.execute("SET lock_configuration = true")
    return con


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Tables and views in the database, as 'schema.table' (lower-case)."""
    rows = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables ORDER BY 1, 2"
    ).fetchall()
    return [f"{s}.{t}".lower() for s, t in rows]


def run_guarded(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    allowed_tables: Iterable[str],
    *,
    params: list | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    row_cap: int = DEFAULT_ROW_CAP,
) -> QueryResult:
    """Guard-check then execute. Raises SqlGuardError, QueryLimitError or duckdb errors."""
    check_sql(sql, allowed_tables)
    timed_out = threading.Event()

    def _interrupt() -> None:
        timed_out.set()
        con.interrupt()

    timer = threading.Timer(timeout_s, _interrupt)
    timer.start()
    try:
        cursor = con.execute(sql, params or [])
        rows = cursor.fetchmany(row_cap + 1)
        columns = [d[0] for d in cursor.description]
    except duckdb.InterruptException as err:
        raise QueryLimitError(f"query exceeded {timeout_s}s") from err
    finally:
        timer.cancel()
    if timed_out.is_set():
        raise QueryLimitError(f"query exceeded {timeout_s}s")
    if len(rows) > row_cap:
        raise QueryLimitError(f"query returned more than {row_cap} rows")
    return QueryResult(columns=columns, rows=rows)
