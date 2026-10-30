"""Typed writing of generator frames to DuckDB and CSV, driven by the schema YAML documents.

Convention: every DECIMAL(p,2) column arrives as integer hundredths (paise for money, hundredths
for fractions such as 15 -> 0.15) so values are exact. A float column is cast as-is (used only by
the benign float-noise scenario).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import yaml

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def load_schema(name: str) -> dict:
    with open(SCHEMA_DIR / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _select_expr(col: str, sql_type: str, series: pd.Series) -> str:
    q = f'"{col}"'
    if sql_type.upper().startswith("DECIMAL") and pd.api.types.is_integer_dtype(series):
        return f"CAST(CAST({q} AS DECIMAL(20,0)) * 0.01 AS {sql_type})"
    return f"CAST({q} AS {sql_type})"


def write_duckdb(db_path: Path, frames: dict[str, pd.DataFrame], schema: dict) -> None:
    """Create one table per schema entry (in schema order), with declared types and NOT NULLs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        for table, spec in schema["tables"].items():
            df = frames[table]
            cols = spec["columns"]
            missing = set(cols) - set(df.columns)
            if missing:
                raise ValueError(f"{table}: frame lacks columns {sorted(missing)}")
            src = df[list(cols)].copy()
            for col, cspec in cols.items():
                if cspec["type"].upper() == "DATE":
                    src[col] = pd.to_datetime(src[col])
            ddl = ", ".join(
                f'"{c}" {s["type"]}{"" if s.get("nullable", True) else " NOT NULL"}' for c, s in cols.items()
            )
            con.execute(f'CREATE TABLE "{table}" ({ddl})')
            con.register("src_frame", src)
            exprs = ", ".join(_select_expr(c, s["type"], src[c]) for c, s in cols.items())
            con.execute(f'INSERT INTO "{table}" SELECT {exprs} FROM src_frame')
            con.unregister("src_frame")
    finally:
        con.close()


def export_csv(db_path: Path, out_dir: Path, *, gzip: bool = False) -> list[Path]:
    """Write every table of db_path to out_dir/<table>.csv[.gz] (header, empty string for NULL)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1").fetchall()]
        for t in tables:
            path = out_dir / (f"{t}.csv.gz" if gzip else f"{t}.csv")
            opts = "HEADER, DELIMITER ','" + (", COMPRESSION gzip" if gzip else "")
            con.execute(f"COPY (SELECT * FROM \"{t}\") TO '{path.as_posix()}' ({opts})")
            written.append(path)
    finally:
        con.close()
    return written


def write_schema_yaml(schema: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(schema, fh, sort_keys=False, allow_unicode=True)
