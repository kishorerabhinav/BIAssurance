# Phase 0 report — Foundation

Date: 2026-10-30 · Status: **complete**

## Files created or modified

| File | Purpose |
|---|---|
| `docs/architecture-plan.md` | Rev 3: Models API as runtime source of truth (§9.3), FIXED LOD filter-order rules and tests (§6.4.1), ATTR restrictions (§6.4.2), synthetic-vs-real-world statement (§8.6.4), Phases 0–1 only (§15) |
| `pyproject.toml` | Package `biwb`, core deps, extras `demo`, `ui`, `ai`, `dev`; pytest + ruff config |
| `.gitignore`, `.env.example`, `.streamlit/config.toml`, `README.md` | Repo hygiene, config template (no secrets), local-only UI settings for later |
| `src/biwb/__init__.py`, `src/biwb/config.py` | Settings from environment; AI disabled by default; API key never held in settings |
| `src/biwb/persistence/db.py` | SQLite connection (foreign keys on, WAL), contiguous forward-only migrations |
| `src/biwb/persistence/migrations/0001_init.sql` | All 32 tables from plan §5, plus append-only triggers on `audit_log`; `sql_artifact.origin` limited to `template` |
| `src/biwb/audit/log.py` | Append-only audit API |
| `src/biwb/safety/sql_guard.py` | sqlglot allowlist guard: single read-only query, allowlisted tables, no table functions, file paths or file/network/extension functions |
| `src/biwb/safety/duckdb_exec.py` | Read-only DuckDB connection with external access disabled and configuration locked; guarded execution with timeout and row cap |
| `src/biwb/safety/file_guard.py` | Upload validation, hardened XML parsing (DTD/entity rejection + lxml no-network), safe `.twbx` extraction |
| `tests/unit/*` (5 files), `tests/architecture/test_boundaries.py` | Tests below |

Git repository initialised on `main`; **nothing committed** (commits only on your instruction).

## Tests executed

`.\.venv\Scripts\python.exe -m pytest` → **96 passed** (1.7 s). `ruff check src tests` → **all checks passed**.

| Area | Tests | What they prove |
|---|---|---|
| Config | 5 | AI off by default; model/effort configurable; invalid values fail; key not in settings |
| Persistence + audit | 10 | All planned tables exist; migrations idempotent; FK enforced; AI-origin SQL rows refused; audit log rejects UPDATE/DELETE at database level |
| SQL guard | 33 | 7 legitimate query shapes pass; 24 attack/unsafe shapes rejected (DDL/DML, multi-statement, COPY, ATTACH, INSTALL/LOAD, PRAGMA, SET, `read_csv`/`read_parquet`, file-path FROM, `getenv`, `glob`, non-allowlisted tables incl. inside CTEs/subqueries), oversized and unparseable SQL |
| DuckDB sandbox | 9 | Read-only; external file access blocked even when the guard is bypassed; configuration locked; row cap; timeout interrupts a long query |
| File guard | 15 | XXE, billion laughs, any DTD, malformed XML rejected; zip slip, absolute paths, Windows drive paths, zero/two root workbooks, ZIP bomb ratio rejected; valid package extracts |
| Architecture | 24 | Engine files never import or mention the answer key, benchmark, demo generator; decision packages never import the AI layer; scanner self-test |

## Acceptance criteria (plan §15, Phase 0)

| Criterion | Status |
|---|---|
| Repo, `pyproject.toml`, venv instructions (Windows/macOS) | Met |
| ruff + pytest configured and green | Met |
| Config, SQLite migrations, audit log | Met |
| `sql_guard`, `file_guard` with negative tests passing | Met |
| Architecture-boundary tests | Met (they apply automatically to packages as they are created) |

Outstanding: none for Phase 0. macOS commands are documented but not executed (no macOS machine here).

## Technical decisions

1. **Plain venv + pip** (uv not installed); `requires-python >=3.12`; developed on 3.14.7.
2. **Demo dependencies separated**: numpy/pandas are in the `demo`/`dev` extras, not core engine dependencies — the engine does not need them, and it keeps the independent oracle's library distinct from the engine's DuckDB path.
3. **Audit immutability in the database** (triggers), not only in Python.
4. **Two-layer SQL safety**: guard (static) + sandboxed connection (`read_only`, `enable_external_access=false`, `lock_configuration=true`). A test proves the second layer blocks file reads even if the guard were bypassed.
5. **Unqualified table names** are matched against `main.<name>` (DuckDB's default schema).
6. **Timeouts** use `connection.interrupt()` from a timer thread (DuckDB has no statement timeout setting).

## Risks or blockers

- None blocking. DuckDB 2.0.0 is new; the sandbox settings were verified by tests on this version.

## Commands to verify

```powershell
cd D:\BIAssurance
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
```
