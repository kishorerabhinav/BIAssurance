"""Checks that the planted defects are really in the data, match their pre-registered signatures,
and that the controls are clean — all measured by the independent oracle, not the engine.

This builds the full-size demo (all scenarios incl. held-out seeds) once, into a temp folder.
"""

import json
from pathlib import Path

import pytest

from benchmark import matching, oracle
from demo.generator.build import build_all
from demo.generator.scenarios import SCENARIOS

pytestmark = pytest.mark.slow

PROFILES = {
    "B1": oracle.TargetProfile(columns={"fct_order_line": {"net_amount": "line_net_amount"},
                                        "dim_region": {"region_name": "region_label"}}),
    "B5": oracle.TargetProfile(cancelled_values=frozenset({"Void"})),
}


@pytest.fixture(scope="session")
def demo(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo")
    data, manifests = root / "data", root / "manifests"
    build_all(list(SCENARIOS), seed=42, data_root=data, manifest_root=manifests, log=lambda *_: None)
    return data, manifests


@pytest.fixture(scope="session")
def comparisons(demo):
    data, _ = demo
    legacy = {}
    out = {}
    for sid, sc in SCENARIOS.items():
        seed = sc.seed or 42
        if seed not in legacy:
            legacy[seed] = oracle.all_kpis(*oracle.legacy_lines(data / f"seed_{seed}" / "legacy_csv"))
        target = oracle.all_kpis(*oracle.target_lines(data / f"seed_{seed}" / "target" / sid / "csv",
                                                      PROFILES.get(sid)))
        out[sid] = oracle.compare(legacy[seed], target)
    return out


def _failures(cmp):
    return cmp[~cmp["passes"]]


@pytest.mark.parametrize("sid", ["S0", "B1", "B2", "B3", "B4", "B5"])
def test_controls_reconcile_everywhere(comparisons, sid):
    fails = _failures(comparisons[sid])
    assert fails.empty, fails.head(10).to_string()


@pytest.mark.parametrize("sid", [f"S{i}" for i in range(1, 9)])
def test_single_defect_is_present_and_inside_signature(comparisons, sid):
    (defect,) = SCENARIOS[sid].defects
    fails = _failures(comparisons[sid])
    assert not fails.empty, f"{defect} left no observable difference"
    outside = [
        (r.grain, r.kpi) for r in fails.itertuples()
        if not matching.matches(defect, r.kpi, *matching.GRAIN_FAMILY[r.grain])
    ]
    assert not outside, f"{defect} differences outside its signature: {sorted(set(outside))[:10]}"


def test_region_remap_leaves_totals_unchanged(comparisons):
    cmp = comparisons["S8"]
    assert cmp[cmp["grain"] != "region"]["passes"].all()
    region = cmp[(cmp["grain"] == "region") & (cmp["kpi"] == "net_revenue")]
    assert region["diff"].sum() == pytest.approx(0, abs=0.01)
    assert (region["diff_pct"].abs() > 0.05).sum() >= 2


def test_headline_trap_masks_segment_differences(comparisons, demo):
    cmp = comparisons["S10"]
    head = cmp[(cmp["grain"] == "total") & (cmp["kpi"] == "net_revenue")].iloc[0]
    assert head["passes"] and abs(head["diff_pct"]) < 0.0005
    region = cmp[(cmp["grain"] == "region") & (cmp["kpi"] == "net_revenue")]
    assert (region["diff_pct"].abs() > 0.05).any()
    month = cmp[(cmp["grain"] == "month") & (cmp["kpi"] == "net_revenue")]
    assert not month["passes"].all()
    manifest = json.loads((demo[1] / "seed_42" / "S10.json").read_text(encoding="utf-8"))
    assert abs(manifest["calibration"]["residual_rel"]) < 0.0005


@pytest.mark.parametrize("sid", ["S9", "H1", "H2", "H3"])
def test_combined_scenarios_show_differences(comparisons, sid):
    fails = _failures(comparisons[sid])
    families = {matching.GRAIN_FAMILY[g][0] for g in fails["grain"]}
    assert {"kpi_total", "kpi_by_dimension", "kpi_by_period"} <= families


def test_heldout_magnitudes_are_randomised(demo):
    _, manifests = demo
    params = [json.loads((manifests / f"seed_{s}" / f"H{i}.json").read_text(encoding="utf-8"))["defects"]
              for i, s in ((1, 101), (2, 202), (3, 303))]
    assert len({json.dumps(p["D1"]["params"], sort_keys=True) for p in params}) == 3
    assert len({json.dumps(p["D8"]["params"], sort_keys=True) for p in params}) >= 2


def test_documented_target_grain_holds_in_clean_scenario(demo):
    import duckdb

    from demo.generator.io import load_schema

    data, _ = demo
    con = duckdb.connect(str(data / "seed_42" / "target" / "S0" / "target.duckdb"), read_only=True)
    try:
        for table, spec in load_schema("target_schema")["tables"].items():
            keys = ", ".join(spec["grain"])
            dupes = con.execute(f"SELECT COUNT(*) FROM (SELECT {keys} FROM {table} GROUP BY {keys} "
                                f"HAVING COUNT(*) > 1)").fetchone()[0]
            assert dupes == 0, table
    finally:
        con.close()


def test_data_folder_contains_no_answer_material(demo):
    data, _ = demo
    names = {p.name for p in Path(data).rglob("*")}
    assert not any("manifest" in n or n.endswith(".json") or "defect" in n for n in names)
