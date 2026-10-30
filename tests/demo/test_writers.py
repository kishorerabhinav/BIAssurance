import duckdb
import pytest

from demo.generator.build import build_legacy_files
from demo.generator.io import load_schema
from demo.generator.truth import TruthParams, build_truth

SMALL = TruthParams(n_customers=300, n_orders=1_500, n_products=40)


@pytest.fixture(scope="module")
def legacy_db(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    return build_legacy_files(build_truth(3, SMALL), data_root=root), root


def _columns(con, table):
    return con.execute(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position", [table]).fetchall()


def test_legacy_tables_match_documented_schema(legacy_db):
    db, _ = legacy_db
    schema = load_schema("legacy_schema")
    con = duckdb.connect(str(db), read_only=True)
    try:
        for table, spec in schema["tables"].items():
            cols = _columns(con, table)
            assert [c[0] for c in cols] == list(spec["columns"]), table
            for (name, dtype, nullable), (_, cspec) in zip(cols, spec["columns"].items(), strict=True):
                assert dtype.replace(" ", "") == cspec["type"].replace(" ", ""), (table, name)
                assert (nullable == "YES") == cspec.get("nullable", True), (table, name)
    finally:
        con.close()


def test_documented_grain_is_unique_in_legacy(legacy_db):
    db, _ = legacy_db
    con = duckdb.connect(str(db), read_only=True)
    try:
        for table, spec in load_schema("legacy_schema")["tables"].items():
            keys = ", ".join(f'"{k}"' for k in spec["grain"])
            dupes = con.execute(f'SELECT COUNT(*) FROM (SELECT {keys} FROM "{table}" GROUP BY {keys} '
                                f"HAVING COUNT(*) > 1)").fetchone()[0]
            assert dupes == 0, table
    finally:
        con.close()


def test_stored_line_amount_equals_recomputed(legacy_db):
    db, _ = legacy_db
    con = duckdb.connect(str(db), read_only=True)
    try:
        bad = con.execute('SELECT COUNT(*) FROM ord_lines WHERE "LineAmt" <> '
                          '"QTY" * "UnitPx" * (1 - COALESCE("DiscPct", 0))').fetchone()[0]
        assert bad == 0
    finally:
        con.close()


def test_csv_export_matches_database(legacy_db):
    db, root = legacy_db
    csv_dir = root / "seed_3" / "legacy_csv"
    con = duckdb.connect(str(db), read_only=True)
    try:
        for table in load_schema("legacy_schema")["tables"]:
            text = (csv_dir / f"{table}.csv").read_text(encoding="utf-8").splitlines()
            assert text[0].split(",") == [c[0] for c in _columns(con, table)]
            assert len(text) - 1 == con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    finally:
        con.close()
    first_line = (csv_dir / "ord_lines.csv").read_text(encoding="utf-8").splitlines()[1]
    assert first_line.split(",")[4].count(".") == 1          # decimals written with 2 places


def test_legacy_csv_is_byte_reproducible(tmp_path):
    a = build_legacy_files(build_truth(3, SMALL), data_root=tmp_path / "a")
    b = build_legacy_files(build_truth(3, SMALL), data_root=tmp_path / "b")
    for csv in (a.parents[1] / "legacy_csv").glob("*.csv"):
        assert csv.read_bytes() == (b.parents[1] / "legacy_csv" / csv.name).read_bytes(), csv.name
