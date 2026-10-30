# BI Migration & Assurance Workbench

Checks whether a migrated Tableau dashboard keeps the business meaning of the original: it parses
the workbook, maps fields from a legacy schema to a target schema with human approval, and runs
deterministic multi-grain equivalence tests with evidence for every discrepancy.

**Status:** Phase 1 of the plan in [docs/architecture-plan.md](docs/architecture-plan.md)
(foundation + synthetic demonstration environment). No UI or AI layer yet.
Phase reports: [docs/phase-reports/](docs/phase-reports/).

## Setup

Windows (PowerShell):

```powershell
py -3.14 -m venv .venv          # any Python 3.12+ works
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

## Build the synthetic demo data

```powershell
.\.venv\Scripts\python.exe scripts\build_demo.py            # seed 42, all scenarios
```

Outputs go to `demo/data/` (git-ignored, reproducible from the seed). The CSVs for building the
Tableau workbook are in `demo/data/seed_42/legacy_csv/`; see
[docs/demo-workbook-build-guide.md](docs/demo-workbook-build-guide.md).

## Principles

- Local processing only. Synthetic data only. No proprietary data or credentials.
- Deterministic code decides every result; AI (optional, later phase) only annotates.
- No free-form SQL is executed: every statement passes an allowlist guard and runs on a read-only,
  sandboxed DuckDB connection.
- Synthetic benchmark results describe detection of **planted** defects only; they are not a
  measure of real-world detection capability (plan §8.6.4).
