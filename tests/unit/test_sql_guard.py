import pytest

from biwb.safety.sql_guard import SqlGuardError, check_sql

ALLOWED = {"main.fct_order_line", "main.dim_region", "fct_order_line", "dim_region"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT SUM(net_amount) FROM fct_order_line",
        "SELECT r.region_name, SUM(f.net_amount) FROM main.fct_order_line f "
        "JOIN main.dim_region r ON f.region_key = r.region_key GROUP BY 1",
        "WITH x AS (SELECT * FROM fct_order_line) SELECT COUNT(*) FROM x",
        "SELECT 1 AS a UNION ALL SELECT 2",
        "SELECT * FROM (SELECT net_amount FROM fct_order_line) t WHERE t.net_amount IS NOT DISTINCT FROM 0",
        "SELECT COUNT(DISTINCT order_id) FROM fct_order_line -- trailing comment",
    ],
)
def test_allows_read_only_queries(sql):
    result = check_sql(sql, ALLOWED)
    assert result.sql == sql


def test_reports_tables_read():
    result = check_sql("SELECT * FROM fct_order_line JOIN dim_region USING (region_key)", ALLOWED)
    assert result.tables == {"fct_order_line", "dim_region"}


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("", "empty"),
        ("SELECT 1; SELECT 2", "exactly one statement"),
        ("SELECT 1; DROP TABLE fct_order_line", "exactly one statement"),
        ("INSERT INTO fct_order_line VALUES (1)", "only SELECT"),
        ("UPDATE fct_order_line SET net_amount = 0", "only SELECT"),
        ("DELETE FROM fct_order_line", "only SELECT"),
        ("DROP TABLE fct_order_line", "only SELECT"),
        ("CREATE TABLE t AS SELECT 1", "only SELECT"),
        ("COPY fct_order_line TO 'out.csv'", "only SELECT"),
        ("ATTACH 'other.duckdb' AS o", "only SELECT"),
        ("INSTALL httpfs", "only SELECT"),
        ("LOAD httpfs", "only SELECT"),
        ("PRAGMA database_list", "only SELECT"),
        ("SET enable_external_access = true", "only SELECT"),
        ("SELECT * FROM read_csv('C:/secrets.csv')", "forbidden"),
        ("SELECT * FROM read_parquet('s3://bucket/x.parquet')", "forbidden"),
        ("SELECT * FROM 'C:/secrets.csv'", "not allowed"),
        ("SELECT getenv('ANTHROPIC_API_KEY')", "forbidden function"),
        ("SELECT current_setting('home_directory')", "forbidden function"),
        ("SELECT * FROM glob('*')", "forbidden"),
        ("SELECT * FROM secret_table", "table not in allowlist"),
        ("SELECT * FROM other_db.main.fct_order_line", "table not in allowlist"),
        ("WITH x AS (SELECT * FROM secret_table) SELECT * FROM x", "table not in allowlist"),
        ("SELECT * FROM fct_order_line WHERE order_id IN (SELECT id FROM secret_table)",
         "table not in allowlist"),
    ],
)
def test_rejects_unsafe_statements(sql, reason):
    with pytest.raises(SqlGuardError) as err:
        check_sql(sql, ALLOWED)
    assert any(reason in r for r in err.value.reasons), err.value.reasons


def test_rejects_oversized_sql():
    with pytest.raises(SqlGuardError):
        check_sql("SELECT " + "1+" * 150_000 + "1", ALLOWED)


def test_unparseable_sql_rejected():
    with pytest.raises(SqlGuardError, match="unparseable|only SELECT|exactly one"):
        check_sql("SELEC FROM WHERE", ALLOWED)
