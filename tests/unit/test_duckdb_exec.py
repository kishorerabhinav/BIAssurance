import duckdb
import pytest

from biwb.safety.duckdb_exec import QueryLimitError, list_tables, open_readonly, run_guarded
from biwb.safety.sql_guard import SqlGuardError


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "data.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE t AS SELECT range AS id, range % 7 AS grp FROM range(1000)")
    con.close()
    return path


@pytest.fixture
def con(db_path):
    c = open_readonly(db_path)
    yield c
    c.close()


def test_runs_guarded_query(con):
    res = run_guarded(con, "SELECT grp, COUNT(*) AS n FROM t GROUP BY grp ORDER BY grp", list_tables(con))
    assert res.columns == ["grp", "n"]
    assert sum(r[1] for r in res.rows) == 1000


def test_list_tables_is_schema_qualified(con):
    assert "main.t" in list_tables(con)


def test_guard_runs_before_execution(con):
    with pytest.raises(SqlGuardError):
        run_guarded(con, "SELECT * FROM read_csv('x.csv')", list_tables(con))


def test_connection_is_read_only(con):
    with pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE x (a INT)")


def test_external_access_disabled_even_without_guard(con, tmp_path):
    csv = tmp_path / "secret.csv"
    csv.write_text("a\n1\n")
    with pytest.raises(duckdb.Error):
        con.execute(f"SELECT * FROM read_csv('{csv.as_posix()}')").fetchall()


def test_configuration_locked(con):
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")


def test_row_cap(con):
    with pytest.raises(QueryLimitError, match="rows"):
        run_guarded(con, "SELECT * FROM t", ["t"], row_cap=10)


def test_timeout_interrupts_long_query(con):
    slow = "SELECT COUNT(*) FROM t a, t b, t c, t d"
    with pytest.raises(QueryLimitError, match="exceeded"):
        run_guarded(con, slow, ["t"], timeout_s=0.2)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_readonly(tmp_path / "nope.duckdb")
