"""Scenario registry and assembly of target frames per scenario (benchmark material)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from demo.generator import defects as dfx
from demo.generator.io import load_schema
from demo.generator.target import build_target
from demo.generator.truth import STATES, Truth

HEADLINE_YEAR = 2025
CALIBRATION_TOLERANCE = 0.0005  # |relative diff| the calibrated headline must reach

DEFAULT_PARAMS = {
    "D1": {"fraction": 1.0},
    "D6": {"fraction": 1.0},
    "D7": {"cutoff": "2025-06-30"},
    "D8": {"moves": {"UP": "CTR"}},
}


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    defects: tuple[str, ...] = ()
    benign: tuple[str, ...] = ()
    calibrate_headline: bool = False      # choose D1 orders so FY headline revenue matches legacy
    randomise_params: bool = False        # held-out runs draw defect magnitudes from the seed
    seed: int | None = None               # held-out runs use their own seed
    notes: str = field(default="")


ALL_DEFECTS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8")

SCENARIOS: dict[str, Scenario] = {s.id: s for s in [
    Scenario("S0", "Clean migration (control)"),
    *[Scenario(f"S{i}", f"Single defect {d}", defects=(d,)) for i, d in enumerate(ALL_DEFECTS, start=1)],
    Scenario("S9", "All defects combined", defects=ALL_DEFECTS),
    Scenario("S10", "Headline trap: compensating defects", defects=("D1", "D2", "D5", "D8"),
             calibrate_headline=True),
    Scenario("B1", "Benign: column renames", benign=("B1",)),
    Scenario("B2", "Benign: integer widening", benign=("B2",)),
    Scenario("B3", "Benign: row reordering", benign=("B3",)),
    Scenario("B4", "Benign: float rounding within tolerance", benign=("B4",)),
    Scenario("B5", "Benign: status labels changed (needs approved value mapping)", benign=("B5",)),
    Scenario("H1", "Held-out: all defects, randomised magnitudes", defects=ALL_DEFECTS,
             randomise_params=True, seed=101),
    Scenario("H2", "Held-out: all defects, randomised magnitudes", defects=ALL_DEFECTS,
             randomise_params=True, seed=202),
    Scenario("H3", "Held-out: all defects, randomised magnitudes", defects=ALL_DEFECTS,
             randomise_params=True, seed=303),
]}


def random_params(rng: np.random.Generator) -> dict:
    region_codes = sorted({r for _, _, r, _ in STATES})
    states = [s for s, _, _, _ in STATES]
    moves = {}
    for st in rng.choice(states, size=int(rng.integers(1, 3)), replace=False):
        current = next(r for s, _, r, _ in STATES if s == st)
        moves[str(st)] = str(rng.choice([r for r in region_codes if r != current]))
    cutoff_month = int(rng.integers(3, 12))
    cutoff = (pd.Timestamp(2025, cutoff_month, 1) + pd.offsets.MonthEnd(0)).date().isoformat()
    return {
        "D1": {"fraction": round(float(rng.uniform(0.05, 1.0)), 3)},
        "D6": {"fraction": round(float(rng.uniform(0.2, 1.0)), 3)},
        "D7": {"cutoff": cutoff},
        "D8": {"moves": moves},
    }


def _fy_net(lines: pd.DataFrame, orders: pd.DataFrame, cancelled: str) -> int:
    status = lines["order_id"].map(orders.set_index("order_id")["order_status"])
    year = lines["order_date_key"] // 10000
    return int(lines.loc[(status != cancelled) & (year == HEADLINE_YEAR), "net_amount"].sum())


def _legacy_fy_net(truth: Truth) -> int:
    o = truth.orders.set_index("order_id")
    li = truth.lines
    ok = (li["order_id"].map(o["status"]) != "X") & \
         (pd.to_datetime(li["order_id"].map(o["order_date"])).dt.year == HEADLINE_YEAR)
    return int(li.loc[ok, "net_paise"].sum())


def _calibrate_d1(t: dfx.Frames, truth: Truth, rng: np.random.Generator) -> dict:
    """Pick after-ship cancellations to relabel so the FY headline matches legacy."""
    legacy = _legacy_fy_net(truth)
    gap = legacy - _fy_net(t["fct_order_line"], t["fct_order"], "CANCELLED")
    if gap <= 0:
        raise RuntimeError(f"calibration impossible: target already exceeds legacy by {-gap} paise")
    lines = t["fct_order_line"]
    in_year = lines[(lines["order_date_key"] // 10000) == HEADLINE_YEAR]
    per_order = in_year.groupby("order_id")["net_amount"].sum()
    present = set(t["fct_order"]["order_id"])
    candidates = [o for o in truth.orders.loc[truth.orders["cancelled_after_ship"], "order_id"]
                  if o in per_order.index and o in present]
    rng.shuffle(candidates)
    chosen, total = [], 0
    for oid in candidates:
        amount = int(per_order[oid])
        if abs(gap - (total + amount)) < abs(gap - total):
            chosen.append(oid)
            total += amount
    residual = (gap - total) / legacy
    if abs(residual) > CALIBRATION_TOLERANCE:
        raise RuntimeError(f"calibration residual {residual:.5f} exceeds {CALIBRATION_TOLERANCE}")
    return {"order_ids": chosen, "residual_rel": residual}


def build_scenario(truth: Truth, scenario: Scenario, rng: np.random.Generator) -> tuple[dfx.Frames, dict, dict]:
    """Return (target frames, target schema document, manifest of what was planted)."""
    frames = build_target(truth)
    schema = copy.deepcopy(load_schema("target_schema"))
    params = random_params(rng) if scenario.randomise_params else copy.deepcopy(DEFAULT_PARAMS)
    manifest: dict = {"scenario": scenario.id, "title": scenario.title, "seed": truth.seed,
                      "defects": {}, "benign": {}}

    for d in dfx.DEFECT_ORDER:
        if d not in scenario.defects:
            continue
        p = params.get(d, {})
        if d == "D1" and scenario.calibrate_headline:
            calib = _calibrate_d1(frames, truth, rng)
            p = {"order_ids": calib["order_ids"]}
            manifest["calibration"] = {"residual_rel": calib["residual_rel"],
                                       "orders_chosen": len(calib["order_ids"])}
        result = dfx.DEFECTS[d](frames, truth, p, rng)
        manifest["defects"][d] = {"params": {k: v for k, v in p.items() if k != "order_ids"}, "effect": result}

    for b in scenario.benign:
        manifest["benign"][b] = dfx.BENIGN[b](frames, schema, rng)
    return frames, schema, manifest
