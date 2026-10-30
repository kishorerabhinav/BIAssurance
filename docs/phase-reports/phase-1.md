# Phase 1 report — Synthetic environment and benchmark foundation

Date: 2026-10-30 · Status: **complete — stopped at Checkpoint A**

## Files created or modified

| File | Purpose |
|---|---|
| `demo/schemas/legacy_schema.yaml` | Documented legacy model: 8 tables, mixed naming, status codes, stored derived values |
| `demo/schemas/target_schema.yaml` | Documented target model: 9 tables, snake_case, surrogate keys, documented grain and definitions |
| `demo/generator/truth.py` | Canonical business truth (seeded): 6 regions, 23 states, 12 categories, 300 products, 5,000 customers, 40,000 orders, ~100k lines, returns, promotions. Money in integer paise |
| `demo/generator/legacy.py`, `target.py` | Legacy and clean target models derived from the same truth |
| `demo/generator/io.py` | Typed DuckDB writer driven by the schema YAML; CSV export |
| `demo/generator/defects.py` | 8 planted defects (D1–D8) and 5 benign changes (B1–B5) |
| `demo/generator/scenarios.py` | Scenario registry S0–S10, B1–B5, H1–H3; headline calibration for S10; randomised magnitudes for held-out seeds |
| `demo/generator/build.py`, `scripts/build_demo.py` | Build to `demo/data/` (git-ignored); per-scenario magnitudes to `answer_key/generated/` |
| `answer_key/planted_defects.yaml`, `answer_key/SEALED.sha256` | Sealed answer key (v2) with pre-registered signatures and matching rule |
| `benchmark/oracle.py` | Independent pandas oracle (no DuckDB, sqlglot or engine code) |
| `benchmark/matching.py`, `benchmark/seal.py` | Pre-registered matching rule; LF-normalised seal |
| `tests/golden/legacy/*.csv`, `tests/golden/expected.yaml` | 6-order dataset with KPI values computed by hand |
| `tests/demo/*`, `tests/benchmark/*` | Tests below |
| `docs/demo-workbook-build-guide.md` | **Checkpoint A guide** |
| `fixtures/tableau/expected_inventory.yaml`, `fixtures/tableau/FIXTURE.md` | What Phase 2 must find; notes template for you |
| `pyproject.toml`, `.gitattributes`, `README.md` | pytest path, line length 120, LF normalisation |

`src/biwb` (the engine) was **not changed** in Phase 1. Nothing is committed.

## Generated data (seed 42)

| Item | Value |
|---|---|
| Location | `demo/data/seed_42/` (legacy DuckDB + CSV; target DuckDB + schema + CSV.gz per scenario) |
| CSVs for Tableau | `demo/data/seed_42/legacy_csv/` — 8 files, ~7 MB |
| Build time | 32 s for all 19 scenarios (207 MB on disk) |
| Reproducibility | Deleted and rebuilt: all 8 legacy CSVs byte-identical (SHA-256 checked) |
| FY2025 legacy | Net revenue ₹405,668,723.55 · 20,694 orders · GP margin 40.91% · return rate 4.67% |

## Tests executed

`pytest` → **185 passed** (55 s; 89 new in Phase 1). `ruff check .` → **all checks passed**.

| Area | Tests | What they prove |
|---|---|---|
| Truth model | 7 | Same seed ⇒ identical frames; amounts exact in paise; status/ship-date rules; returns only on completed orders and never exceed quantity; price versions apply from the change date |
| Writers | 5 | Every legacy table, column, type and nullability matches the YAML; documented grain unique; stored `LineAmt` equals recomputation; CSV row counts and headers match DuckDB; CSVs byte-reproducible |
| Golden set | 30 | Oracle equals hand-computed values for every listed KPI × segment, including the FIXED-LOD filter-order case (cancelled 2024 order must not set a 2024 cohort; 2025 filter must not hide a 2024 first order) |
| Answer key | 6 | Seal unchanged; LF/CRLF-independent hash; key covers every generator defect, benign change and scenario; every revision documented; matching rule examples |
| Scenarios (oracle) | 21 | S0 and B1–B5 reconcile on all 2,672 KPI × segment comparisons; each single defect S1–S8 leaves differences **only inside its pre-registered signature**; D8 leaves every total unchanged; S10 headline within 0.05% while regions and months differ; S9/H1–H3 differ at total, dimension and period level; held-out magnitudes differ by seed; documented target grain holds in S0; data folders contain no answer material |

Oracle overview (failing comparisons out of 2,672, before any engine exists):

| Scenario | Headline net revenue | Failing comparisons |
|---|---|---|
| S0, B1–B5 | 0.0000% | 0 |
| S1 cancelled included | +2.39% | 1,454 |
| S2 date basis | −0.23% | 1,252 |
| S3 discount formula | +2.27% | 1,955 |
| S4 promotion fan-out | +10.32% | 1,868 |
| S5 null region dropped | −2.07% | 1,296 |
| S6 product version grain | 0.0000% | 178 (product/category only) |
| S7 returns truncated | 0.0000% | 498 (returns KPIs only) |
| S8 region remap | 0.0000% | 15 (region only) |
| S10 headline trap | +0.00003% | 1,871 |

## Acceptance criteria (plan §15, Phase 1)

| Criterion | Status |
|---|---|
| Truth model, legacy/target writers | Met |
| Scenarios S0–S10, B1–B5 (plus H1–H3) | Met |
| CSV export and schema YAMLs | Met |
| Sealed answer key with signatures | Met (v2; see decision 5) |
| Pandas oracle | Met |
| Golden set; oracle matches it | Met |
| Demo workbook build guide | Met |
| Data reproducible by seed | Met |

Outstanding (by design, later phases): engine-side detection, precision/recall measurement, evidence reproducibility of engine results — all need Phases 2–6. FIXED-LOD *engine* tests (§6.4.1) belong to Phases 2/4; Phase 1 covers the oracle's filter-order semantics only.

## Technical decisions

1. **Integer prices (whole rupees) and discounts in 5% steps** so every amount is exact to the paisa in every system (Tableau, DuckDB, pandas). Avoids false differences from rounding.
2. **Status codes** are `C/S/X/P` (complete, shipped, cancelled, pending) rather than rev 2's `C/S/X/R`: line-level returns live in `RTN_LOG`, so an order-level "returned" status would duplicate them.
3. **D6 redefined concretely** as "product dimension at version grain" (SCD history rows while facts join on product code). It is an aggregation-at-product-level defect that leaves totals unchanged and shows only where product attributes are used, as Tableau relationships behave.
4. **Demo scenario is S10, not S9.** All-defects S9 moves the headline by +12.9%, so it can't demonstrate a hidden discrepancy. S10 combines D1, D2, D5 and D8, with D1 calibrated so FY2025 headline revenue matches within 0.05%. S9 stays as a benchmark scenario.
5. **Answer key revised once (v1 → v2) before any engine code.** The signature test found that D1 also moves returns between customer cohorts. The sealed v1 missed this, so the rule was added, the revision documented in the key, and the key re-sealed. Re-sealing requires a recorded revision (tested). From Phase 2 onwards a revision would weaken the benchmark's independence; any further one will be reported to you explicitly.
6. **Oracle reads CSV only** (target CSVs are gzip-compressed); it shares no code or libraries with the engine's SQL path.
7. **Tableau semantics modelled in the oracle**: the data source filter applies before FIXED, the year filter after it, and product attributes are joined only when a view uses them (relationship behaviour). Your Tableau check in guide §8 will confirm or contradict these semantics.
8. **Real Indian state codes** for geography (data is synthetic); currency INR.

## Risks or blockers

| Item | Status |
|---|---|
| **Checkpoint A: workbook must be built by you in Tableau** | Blocking for Phase 2 |
| Local save in Desktop Public Edition not yet confirmed on your install | Guide step 0.3 checks it first |
| Tableau field naming for duplicate columns and UI labels in 2026.3 are not verifiable from here | Guide asks you to record deviations rather than work around them |
| Tableau may compute Return Rate across the relationship differently from the oracle | Guide §8 reference values will reveal it; recorded as a finding, not "fixed" |
| Synthetic benchmark ≠ real-world capability | Stated in plan §8.6.4, README and the key header |
| `demo/data` is 207 MB | Git-ignored; rebuilt from seed in ~30 s |

## Commands to verify

```powershell
cd D:\BIAssurance
.\.venv\Scripts\python.exe scripts\build_demo.py --heldout
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe benchmark\seal.py
.\.venv\Scripts\python.exe -m ruff check .
```
