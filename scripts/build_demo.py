"""Build the synthetic demonstration environment.

Usage:
    python scripts/build_demo.py                 # seed 42: legacy + S0..S10, B1..B5
    python scripts/build_demo.py --heldout       # also H1..H3 (seeds 101, 202, 303)
    python scripts/build_demo.py --scenarios S0 S10
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.generator.build import DEFAULT_SEED, build_all  # noqa: E402
from demo.generator.scenarios import SCENARIOS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--scenarios", nargs="*", choices=sorted(SCENARIOS), help="default: all except held-out")
    ap.add_argument("--heldout", action="store_true", help="also build held-out scenarios H1-H3")
    args = ap.parse_args()

    ids = args.scenarios or [s for s in SCENARIOS if not s.startswith("H")]
    if args.heldout:
        ids += [s for s in SCENARIOS if s.startswith("H") and s not in ids]
    start = time.perf_counter()
    build_all(ids, seed=args.seed)
    print(f"done: {len(ids)} scenarios in {time.perf_counter() - start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
