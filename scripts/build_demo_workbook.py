"""Generate the demo Tableau workbook as a packaged .twbx, and release it only if it passes checks.

Usage:
    python scripts/build_demo.py --scenarios S0      # CSVs must exist first
    python scripts/build_demo_workbook.py            # build + check + release .twbx
    python scripts/build_demo_workbook.py --twb      # also write the unpackaged .twb

Release gate (every generated workbook goes through it before anyone is asked to open it):
  1. static check against Tableau's content-model rules (demo/workbook/validate.py)
  2. live load in Tableau Desktop (scripts/tableau_load_check.ps1), capturing any error text
The workbook is built in fixtures/tableau/generated/.staging/ and copied to
fixtures/tableau/generated/ only when both checks pass. If Tableau is not installed, step 2 is
reported as skipped and the file is NOT released unless --allow-unverified is given.

The output is generated, not Tableau-authored; see fixtures/tableau/FIXTURE.md.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.workbook.build_twb import write_twb, write_twbx  # noqa: E402
from demo.workbook.tableau_check import load_in_tableau  # noqa: E402
from demo.workbook.validate import check_twbx  # noqa: E402

CSV_DIR = ROOT / "demo" / "data" / "seed_42" / "legacy_csv"
OUT_DIR = ROOT / "fixtures" / "tableau" / "generated"
NAME = "sales_performance_legacy"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--twb", action="store_true", help="also write the unpackaged .twb")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="release even if Tableau Desktop is unavailable for the live check")
    args = ap.parse_args()
    if not (CSV_DIR / "ORDERS_HDR.csv").exists():
        print(f"CSV files not found in {CSV_DIR}; run scripts/build_demo.py first", file=sys.stderr)
        return 1

    staging = OUT_DIR / ".staging"
    staged = write_twbx(CSV_DIR, staging / f"{NAME}.twbx")

    problems = check_twbx(staged)
    print(f"[1/2] static content-model check: {'PASS' if not problems else 'FAIL'}")
    for p in problems:
        print(f"      {p}")
    if problems:
        return 1

    # 2a: the release file as-is; 2b: a check-only copy that opens on a dashboard of all sheets,
    # so Tableau runs every sheet's queries.
    gate_copy = write_twbx(CSV_DIR, staging / "gate" / f"{NAME}.twbx", gate=True)
    for label, path in (("2a release file", staged), ("2b all-sheets copy", gate_copy)):
        result = load_in_tableau(path)
        print(f"[{label}] Tableau Desktop load check: {result.status.upper()}")
        if result.status != "pass":
            print("      " + result.details.replace("\n", "\n      "))
            if not (result.status == "unavailable" and args.allow_unverified):
                print("not released: fix the generator and rebuild", file=sys.stderr)
                return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    final = OUT_DIR / staged.name
    shutil.copyfile(staged, final)
    print(f"released {final.relative_to(ROOT)} ({final.stat().st_size:,} bytes)")
    if args.twb:
        twb = write_twb(CSV_DIR, OUT_DIR / f"{NAME}.twb")
        print(f"wrote {twb.relative_to(ROOT)} (not separately load-checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
