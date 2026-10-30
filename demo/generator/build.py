"""Build the demo environment on disk.

Layout (all under demo/data/, git-ignored):
    seed_<seed>/legacy/legacy.duckdb
    seed_<seed>/legacy_csv/*.csv                 <- connect Tableau here
    seed_<seed>/target/<scenario>/target.duckdb
    seed_<seed>/target/<scenario>/target_schema.yaml
    seed_<seed>/target/<scenario>/csv/*.csv.gz   <- read by the independent pandas oracle
Planted-defect manifests go to answer_key/generated/, never next to the data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from demo.generator.io import export_csv, load_schema, write_duckdb, write_schema_yaml
from demo.generator.legacy import build_legacy
from demo.generator.scenarios import SCENARIOS, build_scenario
from demo.generator.truth import Truth, build_truth

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "demo" / "data"
MANIFEST_ROOT = ROOT / "answer_key" / "generated"
DEFAULT_SEED = 42


def seed_dir(seed: int, data_root: Path = DATA_ROOT) -> Path:
    return data_root / f"seed_{seed}"


def build_legacy_files(truth: Truth, data_root: Path = DATA_ROOT) -> Path:
    base = seed_dir(truth.seed, data_root)
    db = base / "legacy" / "legacy.duckdb"
    write_duckdb(db, build_legacy(truth), load_schema("legacy_schema"))
    export_csv(db, base / "legacy_csv")
    return db


def build_scenario_files(truth: Truth, scenario_id: str, data_root: Path = DATA_ROOT,
                         manifest_root: Path = MANIFEST_ROOT) -> Path:
    scenario = SCENARIOS[scenario_id]
    # Independent stream per scenario, derived from the seed, so scenarios do not affect each other.
    rng = np.random.default_rng([truth.seed, int.from_bytes(scenario_id.encode(), "big")])
    frames, schema, manifest = build_scenario(truth, scenario, rng)
    out = seed_dir(truth.seed, data_root) / "target" / scenario_id
    db = out / "target.duckdb"
    write_duckdb(db, frames, schema)
    write_schema_yaml(schema, out / "target_schema.yaml")
    export_csv(db, out / "csv", gzip=True)

    mdir = manifest_root / f"seed_{truth.seed}"
    mdir.mkdir(parents=True, exist_ok=True)
    with open(mdir / f"{scenario_id}.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    return db


def build_all(scenario_ids: list[str] | None = None, *, seed: int = DEFAULT_SEED, data_root: Path = DATA_ROOT,
              manifest_root: Path = MANIFEST_ROOT, log=print) -> list[str]:
    """Build legacy data for `seed` and the requested scenarios. Held-out scenarios (H*) carry their
    own seed and get their own legacy data."""
    ids = scenario_ids or [s for s in SCENARIOS if not s.startswith("H")]
    built = []
    truths: dict[int, Truth] = {}
    for sid in ids:
        s_seed = SCENARIOS[sid].seed or seed
        if s_seed not in truths:
            log(f"[seed {s_seed}] building truth and legacy model")
            truths[s_seed] = build_truth(s_seed)
            build_legacy_files(truths[s_seed], data_root)
        log(f"[seed {s_seed}] scenario {sid}: {SCENARIOS[sid].title}")
        build_scenario_files(truths[s_seed], sid, data_root, manifest_root)
        built.append(sid)
    return built
