"""Generate the demo Tableau workbook (.twb and packaged .twbx) from the seed-42 legacy CSVs.

Usage:
    python scripts/build_demo.py --scenarios S0      # CSVs must exist first
    python scripts/build_demo_workbook.py

Writes fixtures/tableau/generated/sales_performance_legacy.{twb,twbx}. These are generated, not
Tableau-authored; open them in Tableau Desktop and save a copy to obtain the Tableau-normalised
fixture (see fixtures/tableau/FIXTURE.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.workbook.build_twb import write_twb, write_twbx  # noqa: E402

CSV_DIR = ROOT / "demo" / "data" / "seed_42" / "legacy_csv"
OUT_DIR = ROOT / "fixtures" / "tableau" / "generated"


def main() -> int:
    if not (CSV_DIR / "ORDERS_HDR.csv").exists():
        print(f"CSV files not found in {CSV_DIR}; run scripts/build_demo.py first", file=sys.stderr)
        return 1
    twb = write_twb(CSV_DIR, OUT_DIR / "sales_performance_legacy.twb")
    twbx = write_twbx(CSV_DIR, OUT_DIR / "sales_performance_legacy.twbx")
    for p in (twb, twbx):
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
