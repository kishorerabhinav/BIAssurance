# BI Migration & Assurance Workbench — Architecture Plan

Status: **Revision 3 — approved; Phases 0 and 1 authorised.**
Date: 2026-10-30

## Revision log

| Rev | Date | Changes |
|---|---|---|
| 1 | 2026-10-30 | Initial plan |
| 3 | 2026-10-30 | Final safeguards: Models API is the runtime source of truth for model availability (§9.3); FIXED LOD support is conditional on filter-order analysis, with dedicated tests (§6.4.1); ATTR translation restricted to proven contexts (§6.4.2); synthetic benchmark results explicitly separated from real-world capability (§8.6.4); implementation limited to Phases 0–1 until Checkpoint A (§15) |
| 2 | 2026-10-30 | Incorporates review refinements: narrower MVP built around one end-to-end scenario (§2); formal Supported/Partial/Unsupported calculation policy with no silent translation (§6.4); validation benchmark with precision, recall, false-positive controls, masked-discrepancy and reproducibility checks, and independent oracles (§8.6); Tableau-authored demo workbook built in Desktop Public Edition (§6.6, new build guide); AI enforced outside the decision paths (§9); model identifier verified and configurable (§9.3); MVP acceptance checklist (§17); deferred-features list (§18); revised structure, tests and sequence (§14, §15, §19) |

---

## 0. Environment inspection (findings)

| Item | Finding | Consequence |
|---|---|---|
| OS | Windows 10 Home 19045, 11.7 GB RAM | Local-only design; demo datasets sized ~100k order lines |
| Python | 3.14.7 via `py` launcher only (`python` on PATH is the MS Store alias) | `py -3.14 -m venv .venv`; README gives Windows + macOS commands |
| Package manager | pip 26.2; uv not installed | Plain `venv` + `pip install -e .[dev]` |
| Binary wheels on 3.14 / win_amd64 | duckdb 2.0.0, pyarrow 26, pandas 3.1, polars 2.1, lxml 6.1, streamlit 1.66, sqlglot 30.26, anthropic 2.3, tableauhyperapi 0.0.26963 | No compiler needed; `requires-python >=3.12` for macOS users |
| Git | 2.56 | Repo initialised in Phase 0 |
| Tableau | Tableau Desktop 2026.3 installed (Public Edition) | Demo workbook is authored by you in Tableau (§6.6) |
| Anthropic credentials | `ANTHROPIC_API_KEY` not set; `ant` CLI not installed | The model ID could not be checked against the live API from this machine; verified against Anthropic's published model list instead, plus a startup check at runtime (§9.3) |

---

## 1. Product Requirements Document

### 1.1 Problem
When a Tableau dashboard is repointed from a legacy source to a standardised target model, teams usually check that it *opens* and that headline numbers *roughly match*. This misses semantic drift: changed filter semantics, a different date basis, altered calculation logic, join fan-out, different null handling, re-mapped dimensions. Headline totals can match while segments are wrong (compensating errors).

### 1.2 Product statement
A local workbench that (1) reads a Tableau workbook and extracts its analytical intent, (2) maps that intent from a legacy schema to a target schema with human-approved mappings, (3) recommends reviewable migration SQL, (4) runs deterministic, multi-grain equivalence tests between legacy and target data, (5) attaches diagnostic evidence to every discrepancy, and (6) produces a readiness assessment calculated by published rules. AI is optional and only explains or suggests.

### 1.3 Users
| Persona | Needs |
|---|---|
| BI developer | What does this workbook compute? What maps where? What SQL is needed? Which test failed and why? |
| Data engineer | Does the target model have the right grain, keys and definitions for this workbook? |
| Analytics lead | Is it ready to cut over? What is the evidence? What is unresolved and who must act? |

### 1.4 Functional requirements (MVP)
| ID | Requirement |
|---|---|
| FR-1 | Upload `.twb` / `.twbx`; safely extract and parse locally |
| FR-2 | Show data sources, connections, tables, joins and relationships, fields, calculated fields with dependency graph, parameters, filters, worksheets, dashboards |
| FR-3 | Support report: every element and every calculation classified Supported / Partial / Unsupported with a reason code |
| FR-4 | Define legacy and target schemas by YAML spec or by introspecting a DuckDB file |
| FR-5 | Profile both schemas (row counts, null %, distinct counts, key uniqueness) |
| FR-6 | Field mapping candidates with component scores, rationale, evidence and confidence; classes: exact / renamed / type-changed / missing / ambiguous / one-to-many |
| FR-7 | Review workflow: approve / reject / choose alternative / defer; nothing auto-approved; every decision recorded |
| FR-8 | Analyse calculated fields: classification, dependencies, and SQL translation for **Supported** calculations only (§6.4) |
| FR-9 | Logic comparison legacy vs target: filters, date basis, aggregation, grain, join cardinality, value domains |
| FR-10 | Migration plan: mapping table, transformations, SQL suggestions, calc changes, dependency order, breakages, manual review list; Markdown + `.sql` export |
| FR-11 | Generate and run multi-grain tests (KPI × total / dimension / period, counts, nulls, boundaries, fan-out, domains) |
| FR-12 | Discrepancy report: test name, expected, actual, difference, difference %, severity, likely explanation, supporting SQL, recommended investigation |
| FR-13 | Deterministic diagnostic probes that produce evidence for likely causes |
| FR-14 | Readiness report: gates + transparent score, Markdown export |
| FR-15 | Synthetic demo environment with scenarios, sealed answer key and benchmark harness |
| FR-16 | Optional AI assistance, disclosed, previewed, audited, replayable, never in decision paths |

### 1.5 Non-functional requirements
- Windows and macOS; local only; `streamlit run` on `127.0.0.1`.
- Full demo pipeline (build data → parse → map → test → report) completes in < 2 min on this laptop.
- Reproducible: same seed and inputs ⇒ byte-identical test results and report.
- Every number on screen traceable to a SQL statement, a run id and a data fingerprint.

---

## 2. MVP scope and exclusions

### 2.1 Guiding rule
**One end-to-end migration scenario, done properly**, before any breadth: the "Sales Performance" workbook migrated from the legacy e-commerce model to the target model (§13, §17). A feature is in the MVP only if that scenario needs it.

### 2.2 In scope (MVP)
1. Workbook intelligence for workbooks with file-based connections (what Public Edition produces), including logical relationships and physical joins.
2. Schema import (YAML spec, DuckDB introspection) and profiling.
3. Deterministic field mapping with review and approval records.
4. Calculation analysis with Supported / Partial / Unsupported classification; SQL translation for Supported only.
5. Migration plan and SQL recommendations (read-only, exportable).
6. Multi-grain deterministic validation, diagnostic probes, discrepancy explorer.
7. Readiness report with gates and transparent score.
8. Benchmark harness proving detection quality on the synthetic scenarios.
9. AI layer (optional, last phase): calc explanation, mapping suggestion, discrepancy narrative.

### 2.3 Exclusions (MVP)
| Excluded | Reason |
|---|---|
| Modifying or writing `.twb` files | Recommendations only; high risk of producing invalid workbooks |
| Tableau Server/Cloud APIs, published data sources | No access; published definitions are not in the workbook |
| Executing arbitrary or user-written SQL | Security requirement |
| Remote warehouses | Local-only; DuckDB adapter abstraction leaves room |
| Full calculation-language support | See §6.4; only the Supported subset is translated |
| Multi-user, auth, RBAC | Single-user local tool |
| Comparing rendered visuals | We compare data, not pixels |

The full list of deferred capabilities is in §18.

---

## 3. System architecture

```
┌──────────────────────────── Streamlit UI (127.0.0.1) ────────────────────────────┐
│ Overview │ Workbook │ Mapping │ Logic │ Planner │ Validation Lab │ Discrepancies │ Readiness │
└───────────────┬──────────────────────────────────────────────────────────────────┘
                │ pages call services only
┌───────────────▼─────────────── Application services ─────────────────────────────┐
│ Project  Workbook  Schema  Mapping  Logic  Planner  Validation  Readiness        │
└──┬───────────────────────────────────────────────────────────────┬───────────────┘
   │ DETERMINISTIC CORE  (decision path)                           │ ANNOTATION PATH
┌──▼───────────┐ ┌──────────────┐ ┌───────────────┐ ┌────────────┐ ┌▼─────────────────┐
│ workbook/    │ │ calc/        │ │ mapping/      │ │ validation/│ │ ai/ (optional)   │
│ loader, XML, │ │ parser, AST, │ │ candidates,   │ │ tests, run,│ │ gateway,         │
│ model, shelf │ │ classifier,  │ │ scores,       │ │ compare,   │ │ redaction,       │
│ decoder,     │ │ Supported-   │ │ validators    │ │ severity,  │ │ preview, replay, │
│ support map  │ │ only → SQL   │ │               │ │ probes     │ │ model registry   │
└──────────────┘ └──────────────┘ └───────────────┘ └────────────┘ └──────────────────┘
┌──────────────┐ ┌──────────────┐ ┌───────────────┐ ┌────────────┐   writes only to
│ schema/      │ │ planner/     │ │ readiness/    │ │ safety/    │   ai_annotation;
│ spec, intro- │ │ plan, order, │ │ gates, score, │ │ sql_guard, │   never imported by
│ spect,profile│ │ SQL export   │ │ report        │ │ file_guard │   decision packages
└──────────────┘ └──────────────┘ └───────────────┘ └────────────┘
┌──────────────── Persistence ──────────────────────────────────────────────────────┐
│ app.db (SQLite): projects, parsed workbook, mappings, decisions, runs, results,    │
│                  ai_annotation, audit_log                                          │
│ legacy.duckdb / target.duckdb: analytical data, opened READ-ONLY for validation    │
│ workspace/projects/<id>/: uploads (sha256-named), exports                          │
└────────────────────────────────────────────────────────────────────────────────────┘
   Outside the engine (never imported by src/):
   demo/generator · answer_key/ (sealed) · benchmark/ (harness + independent oracle)
```

Principles:
1. **Deterministic core first.** Every service produces a complete result without AI.
2. **Thin pages.** All logic in services; services are unit-testable.
3. **Evidence objects everywhere.** Mappings, findings, discrepancies, readiness factors each carry evidence: SQL, counts, XML path and line, rule id.
4. **SQLite + DuckDB.** SQLite for transactional app state (approvals, audit); DuckDB for analytical scans, opened read-only during validation.
5. **Fail closed.** Anything not understood is reported as Partial/Unsupported and blocks dependent tests rather than being guessed.

---

## 4. Component architecture

| Package (`src/biwb/…`) | Responsibility |
|---|---|
| `domain/` | Pydantic models: `Workbook`, `Datasource`, `Field`, `CalcField`, `Worksheet`, `Filter`, `Parameter`, `SchemaModel`, `MappingCandidate`, `MappingDecision`, `MetricSpec`, `TestCase`, `TestResult`, `Discrepancy`, `Evidence`, `ReadinessAssessment` |
| `workbook/loader.py` | Validate extension and size; safe `.twbx` unzip; locate root `.twb`; inventory embedded files |
| `workbook/xml_parser.py` | Hardened lxml parse; version detection; raw extraction with XPath and source line |
| `workbook/model_builder.py` | Resolve internal names to captions; link worksheets → fields → datasources; relationships and joins |
| `workbook/shelf_decoder.py` | Decode `[federated.x].[sum:Calculation_123:qk]` into datasource, derivation, field, pivot |
| `workbook/support_matrix.py` | Element-level Supported / Partial / Unsupported with reason codes |
| `workbook/complexity.py` | Count-based complexity bands |
| `calc/lexer.py`, `parser.py`, `ast.py` | Tableau calculation language → AST (Pratt parser) |
| `calc/functions.py` | Function catalogue: arity, kind, **support level**, SQL template |
| `calc/classifier.py` | Per-node and per-calc support level; propagation through dependencies |
| `calc/analyzer.py` | Kind (row/aggregate/LOD/table calc), date logic, filters inside calcs, dependency graph |
| `calc/to_sql.py` | AST → sqlglot (DuckDB) for **Supported** calcs only; raises `NotTranslatable` otherwise |
| `schema/` | YAML spec loader, DuckDB introspection, profiler |
| `mapping/` | `normalize.py`, `candidates.py`, `scorers.py`, `validators.py`, `service.py` |
| `logic/compare.py` | Legacy vs target definitions: filters, date basis, grain, aggregation, domains |
| `planner/` | `plan_builder.py`, `dependency_order.py`, `sql_generator.py`, `export.py` |
| `validation/` | `specs.py`, `test_generator.py`, `sql_builder.py`, `runner.py`, `compare.py`, `severity.py`, `probes/`, `fingerprint.py`, `service.py` |
| `readiness/` | `rules.py` (versioned), `scoring.py`, `report.py` |
| `ai/` | `gateway.py`, `model_registry.py`, `redaction.py`, `schemas.py`, `prompts/`, `replay_cache.py` |
| `safety/` | `sql_guard.py`, `file_guard.py` |
| `persistence/` | SQLite connection, SQL migrations, repositories |
| `audit/` | Append-only audit log |

---

## 5. Database schema (SQLite `app.db`)

All tables have `id INTEGER PK` and `created_at`. JSON columns hold pydantic-serialised detail.

| Table | Key columns |
|---|---|
| `project` | name, description, status, legacy_db_path, target_db_path |
| `artifact` | project_id, kind (`workbook`/`schema_spec`/`dataset`/`export`), original_name, sha256, stored_path, size_bytes |
| `workbook` | project_id, artifact_id, tableau_version, source_build, parsed_json, complexity_json |
| `wb_datasource` | workbook_id, internal_name, caption, connection_class, relation_tree_json, object_graph_json, is_parameters |
| `wb_field` | datasource_id, internal_name, caption, datatype, role, type, default_agg, is_calculated, remote_name, remote_table, xml_path, xml_line |
| `wb_calculation` | field_id, formula, ast_json, kind, support_level, reason_codes_json, sql_translation (NULL unless Supported) |
| `wb_dependency` | from_field_id, to_field_id, dep_type (`calc_ref`/`filter`/`shelf`) |
| `wb_worksheet` | workbook_id, name, shelves_json |
| `wb_worksheet_field` | worksheet_id, field_id, shelf, derivation, pivot |
| `wb_filter` | worksheet_id (NULL = datasource filter), field_id, filter_class, spec_json, is_context, support_level |
| `wb_parameter` | workbook_id, name, datatype, current_value, domain_json |
| `wb_dashboard` | workbook_id, name, worksheet_names_json |
| `wb_support_item` | workbook_id, element_type, element_ref, level, reason_code, detail |
| `schema_model` | project_id, side (`legacy`/`target`), source_kind, spec_json |
| `schema_column` | schema_model_id, table_name, column_name, data_type, nullable, is_key, description |
| `column_profile` | schema_column_id, row_count, null_pct, distinct_count, is_unique, min_val, max_val, sample_values_json (local only) |
| `table_grain` | schema_model_id, table_name, grain_columns_json, verified, evidence_json |
| `mapping_candidate` | project_id, wb_field_id, legacy_column_id, target_column_id, match_class, score, score_components_json, rationale, confidence_band |
| `mapping_decision` | candidate_id, decision (`approved`/`rejected`/`alternative`/`deferred`), chosen_target_column_id, reviewer, comment, decided_at |
| `assumption_ack` | project_id, subject_ref (calc or filter), assumption_text, acknowledged_by, acknowledged_at |
| `logic_finding` | project_id, subject_ref, finding_type, equivalence_level, status, evidence_json |
| `migration_plan` | project_id, version, plan_json, decisions_hash |
| `sql_artifact` | plan_id, purpose, sql_text, dialect, guard_passed, origin (`template`) |
| `metric_spec` | project_id, name, legacy_expr, target_expr, filters_json, date_field_legacy, date_field_target, testability (`testable`/`conditional`/`not_testable`) |
| `test_case` | project_id, metric_spec_id, family, dimension, period_grain, tolerance_abs, tolerance_rel |
| `test_run` | project_id, started_at, finished_at, legacy_fingerprint, target_fingerprint, decisions_hash, rules_version, engine_version |
| `test_result` | run_id, test_case_id, status, expected, actual, diff, diff_pct, severity, legacy_sql, target_sql, segments_json, result_hash |
| `discrepancy` | run_id, test_result_id, title, severity, explanation_deterministic, recommended_investigation, masked (bool) |
| `probe_result` | discrepancy_id, probe_name, outcome (`supports`/`refutes`/`inconclusive`), evidence_json, sql |
| `ai_annotation` | project_id, subject_ref, purpose, model_requested, model_answered, payload_json (exact bytes sent), payload_sha256, response_json, status |
| `readiness_assessment` | project_id, run_id, status, score, factors_json, gates_json, rules_version |
| `audit_log` | project_id, actor, action, entity, entity_id, detail_json |

`ai_annotation` is the only table the AI layer writes to; it has no foreign key into decision tables other than `subject_ref` for display.

---

## 6. Tableau workbook parsing approach

### 6.1 File formats
- **`.twb`**: one XML document, root `<workbook source-build=… version=…>`. No public schema; structure changes between versions (e.g. 2020.2 added the logical relationships layer, `<object-graph>`).
- **`.twbx`**: a ZIP with one `.twb` plus embedded assets: extracts (`.hyper`), CSV/Excel files, images.

### 6.2 Library evaluation
| Library | Verdict |
|---|---|
| `tableaudocumentapi` (Tableau, MIT) | Latest release 0.11, effectively unmaintained; no filters, shelves, relationships. Not used |
| `tableauhyperapi` | Reads `.hyper` extracts; proprietary free licence. Deferred (§18) |
| `tableauserverclient`, REST/Metadata API | Server/Cloud only. Excluded |
| `lxml` + `defusedxml` pre-check | **Chosen**: XPath, source line numbers for evidence, hardened parser |
| stdlib `zipfile` | **Chosen**, wrapped by `file_guard` |

### 6.3 What we extract
| Element | XML location (typical) | Reliability |
|---|---|---|
| Version | `workbook/@source-build`, `@version` | High |
| Datasources | `datasources/datasource` (`name`, `caption`); `Parameters` datasource special | High |
| Connections | `connection[@class='federated']/named-connections/named-connection/connection` (e.g. `textscan` for CSV with `directory`, `filename`) | High |
| Physical joins | `relation[@type='join']` with `clause/expression` | High |
| Logical relationships | `object-graph/objects/object`, `relationships/relationship/expression` | Medium (version-sensitive) — **required for the demo**, because Tableau defaults to relationships when several CSVs are added |
| Custom SQL | `relation[@type='text']` | Text extracted, parsed best effort with sqlglot, flagged Partial |
| Column metadata | `metadata-records/metadata-record[@class='column']` | High |
| Fields | `datasource/column` (`name`, `caption`, `datatype`, `role`, `type`) | High |
| Calculations | `column/calculation[@class='tableau']/@formula` | Text: High. Meaning: §6.4 |
| Groups, bins, sets | `calculation[@class='categorical-bin'|'bin']`, `group` | Detected; Partial |
| Parameters | `column[@param-domain-type]` with `range` / `members` | High |
| Worksheets | `worksheet/table/view/datasource-dependencies`, `rows`, `cols`, `panes/pane/encodings` | Medium (shelf encoding decoded) |
| Filters | `view/filter[@class='categorical'|'quantitative'|'relative-date']`, `groupfilter`, `slices` (context), datasource filters | Categorical/quantitative: High. Relative date, top-N, context ordering: Partial |
| Dashboards | `dashboards/dashboard/zones//zone[@name]` | High for sheet membership; actions detected only |

Shelf decoding: `[federated.0a1b2c].[sum:Calculation_123:qk]` → datasource `federated.0a1b2c`, derivation `sum`, field `Calculation_123` (caption "Gross Profit"), pivot `qk` (quantitative). Derivations (`none`, `sum`, `avg`, `ctd`, `yr`, `mn`, `tmn`, `usr`, …) map to SQL aggregation and date grain; unknown derivations are reported as Unsupported.

### 6.4 Calculation support policy

#### Definitions
| Level | Meaning | What the product does |
|---|---|---|
| **Supported** | Every AST node is in the Supported catalogue, and the result does not depend on viz context | Translated to SQL; KPI is **testable** |
| **Partial** | Translation is possible only under an explicit assumption (e.g. worksheet context for INCLUDE/EXCLUDE, week-start, relative-date anchor, Top-N ordering) | **No SQL is produced until a reviewer acknowledges the stated assumption** (`assumption_ack`); then SQL is produced with the assumption embedded as a comment and the KPI is **conditional** — results are labelled "conditional on assumption A-n" everywhere they appear |
| **Unsupported** | Any node outside the catalogue, or semantics not recoverable from XML | **No SQL is produced, ever.** KPI is **not testable**; this counts against validation coverage and appears under manual actions |

#### Rules (enforced in code and tests)
1. Classification is per AST node; a calculation takes its **worst** node's level.
2. Levels **propagate** through dependencies: a calc referencing a Partial calc is at most Partial; referencing an Unsupported calc makes it Unsupported.
3. `to_sql` either returns SQL for the whole expression or raises `NotTranslatable(reasons)`. It never drops, approximates or skips a node.
4. Unknown functions are Unsupported by default (allowlist, not denylist).
5. Every classification carries reason codes (e.g. `LOD_INCLUDE_NEEDS_CONTEXT`, `TABLE_CALC_ADDRESSING`, `RAWSQL`, `UNKNOWN_FUNCTION:XYZ`).

#### MVP catalogue
| Category | Examples | Level |
|---|---|---|
| Arithmetic, comparison, logical | `+ - * / = <> AND OR NOT` | Supported (integer-division rule documented) |
| Conditionals and nulls | `IF/ELSEIF/ELSE`, `CASE`, `IIF`, `IFNULL`, `ZN`, `ISNULL` | Supported |
| Aggregates | `SUM AVG MIN MAX COUNT COUNTD` | Supported |
| `MEDIAN` | | Supported |
| `ATTR` | | **Conditional** — see §6.4.2; Unsupported outside the proven contexts |
| Date | `DATETRUNC DATEPART DATEADD DATEDIFF YEAR QUARTER MONTH DAY` | Supported for `year/quarter/month/day`; **week** parts Partial (week-start assumption) |
| `TODAY() NOW()` | | Partial (anchor-date assumption) |
| String | `LEFT RIGHT MID CONTAINS UPPER LOWER TRIM LEN REPLACE` | Supported |
| Type conversion | `INT FLOAT STR DATE` | Supported |
| Parameters in calcs | `[Parameters].[Top N]` | Supported (bound to current value, flagged as user-variable) |
| FIXED LOD | `{FIXED [Customer]: MIN([Order Date])}` | **Conditional** — Supported only when the filter-order analysis in §6.4.1 succeeds; otherwise Partial or Unsupported |
| INCLUDE / EXCLUDE LOD | | Partial (needs worksheet context) |
| Table calculations | `RUNNING_SUM WINDOW_* LOOKUP RANK INDEX TOTAL` | Unsupported in MVP: detected, classified, listed for manual review |
| Pass-through and scripts | `RAWSQL_*`, `SCRIPT_*` | Unsupported |
| User functions (RLS) | `USERNAME() ISMEMBEROF()` | Unsupported |
| Spatial, regex | `MAKEPOINT`, `REGEXP_*` | Unsupported |

Order-of-operations caveat (extract → data source → context → FIXED → dimension filters → INCLUDE/EXCLUDE → measure filters → table calcs) is shown in the UI. The SQL generator replicates filter placement for Supported cases.

#### 6.4.1 FIXED LOD: conditional support and filter-order semantics
A FIXED expression is **not** Supported by default. It is classified per *usage* (calc × worksheet), because the same expression gives different results depending on which filters apply before it.

| Filter that applies to the worksheet | Effect on FIXED in Tableau | Translation rule | Level |
|---|---|---|---|
| Extract filter | Applied before FIXED | Must be applied inside the FIXED subquery; extract filters are read from XML | Supported if parsed, else Unsupported |
| Data source filter | Applied before FIXED | Applied inside the FIXED subquery | Supported |
| Context filter (categorical, explicit members) | Applied before FIXED | Applied inside the FIXED subquery | Supported |
| Context filter (Top-N, relative date, conditional/formula) | Applied before FIXED | Requires evaluating the context filter itself | Partial (assumption) |
| Ordinary dimension filter | Applied **after** FIXED | Must **not** filter the FIXED subquery; applied to the outer query only | Supported |
| Measure filter | Applied after FIXED | Outer query, after aggregation | Supported for simple comparisons, else Partial |
| Filter on the FIXED field itself | Applied after FIXED (dimension filter on result) | Outer query | Supported |
| Unknown or unparsed filter class | — | — | Unsupported |
| FIXED with no dimensions (`{FIXED : SUM(x)}`) | Table-scoped | Scalar subquery with pre-FIXED filters | Supported |
| Nested LODs, FIXED over a table calc, FIXED referencing Partial/Unsupported calcs | — | — | Level of the worst part (propagation rule) |

**Null behaviour**: FIXED dimensions group NULL as its own member (Tableau behaviour); the SQL uses `GROUP BY` (which groups NULLs together in DuckDB) and joins back with `IS NOT DISTINCT FROM`, never `=`, so rows with NULL dimension keys keep their LOD value. Aggregates inside FIXED ignore NULLs (`MIN`, `SUM`) like Tableau; `COUNT` vs `COUNTD` semantics are preserved.

**Required tests (Phase 2/4)**: each row of the table above has unit tests on the classifier, and SQL tests on a hand-computed dataset for: data source filter inside FIXED; categorical context filter inside FIXED; ordinary dimension filter *not* applied inside FIXED (result must equal the unfiltered LOD); filter on the FIXED result; NULL dimension members (NULL group retained, join back with `IS NOT DISTINCT FROM`); NULL measure values inside FIXED; FIXED with no dimensions; Top-N context filter → Partial; unknown filter class → Unsupported. Expected values are computed by hand in `tests/golden/lod/`.

#### 6.4.2 ATTR: restricted translation
`ATTR(x)` returns x when all values in the partition are equal, otherwise `*` (shown as a mixed value). A SQL expression `CASE WHEN MIN(x) = MAX(x) THEN MIN(x) END` is equivalent only under specific conditions.

| Context | Level | Reason |
|---|---|---|
| `ATTR` on a dimension used in a text label/tooltip, grouped by worksheet dimensions where a deterministic key proves x is functionally dependent on the group (e.g. `ATTR([Region Name])` grouped by `[Region Code]`, with key uniqueness verified by a profiling check) | Supported | The CASE form can only return the single value; equivalence is proven by the data check, recorded as evidence |
| `ATTR` where functional dependency is not proven | Partial | Result may be `*`/NULL; reviewer must acknowledge |
| `ATTR` used inside arithmetic or comparisons, or as an input to other calcs | Unsupported | Tableau's `*` has no SQL equivalent; NULL substitution changes downstream results |
| `ATTR` on fields with NULLs | Unsupported unless NULL handling is proven (Tableau ignores NULLs in MIN/MAX; the mixed-value state differs) | |
| `ATTR` inside table calcs or LODs | Unsupported | Context-dependent |
| `ATTR` across relationship boundaries (field from a related table at a different level of detail) | Unsupported | Relationship query semantics not reproduced |

These unsupported contexts are listed in the support report and in the README.

### 6.5 Known limits of XML-only interpretation
- XML holds definitions, not results; results come from executing SQL on data.
- Published data sources (`sqlproxy`) cannot be resolved offline.
- Data blending, dashboard actions, story points: detected, not interpreted.
- Version drift: unknown elements are reported rather than silently ignored; tested on Tableau 2026.3 output only (stated in the README).

### 6.6 Realistic demo workbook (Tableau-authored)

**Approach:** you build the demo workbook in **Tableau Desktop Public Edition 2026.3** from generated CSV files, following an exact build guide (`docs/demo-workbook-build-guide.md`, written in Phase 1). The parser is developed and tested against that Tableau-authored file, not against XML we generate ourselves.

Build guide contents: CSV location; which tables to add; one **physical join** (order header ⇄ order lines, inside a logical table) plus **relationships** to products, customers, regions, returns, so both structures are exercised; exact calculated-field formulas; worksheets, filters (cancelled-order exclusion, order-date year), the `Top N` parameter, one FIXED LOD, one table calc (to exercise the Unsupported path), and the dashboard; then save as `.twb` and as packaged `.twbx`.

Fixtures are stored in `fixtures/tableau/sales_performance_legacy.{twb,twbx}` with a `FIXTURE.md` noting the Tableau version and build date.

**Limitations to document:**
| Limitation | Impact | Handling |
|---|---|---|
| Public Edition connects to files (CSV/Excel), not DuckDB or databases | Workbook connection class is `textscan`, not a warehouse | Realistic for many legacy workbooks; parser treats connection class generically |
| Local save: Public Edition supports local saving of workbooks; confirm on your install at build time | If local save is unavailable, the fallback is saving to Tableau Public and downloading the `.twbx` — acceptable only because data is synthetic | Checked in step 1 of the build guide |
| Workbook contains absolute local paths (e.g. `D:\BIAssurance\demo\out\csv`) | Path leakage in fixtures | Parser masks paths in UI and exports; fixtures note the path |
| Single author, single Tableau version | Parser may be tuned to one style | Small hand-written XML snippets cover variants (older join-only layout, custom SQL, sqlproxy) in unit tests; version scope stated |
| Hand-built workbook can deviate from the guide | Benchmark expectations drift | Phase 2 starts with a parse-and-compare check against the guide's expected inventory (sheets, calcs, filters) |
| Tableau data is not recalculated by us from the `.twbx` | Workbook numbers are not compared to Tableau's own rendering | Stated as a limitation; validation compares legacy vs target data via SQL |
| Nothing is published | — | Demo never requires Tableau Public publishing |

A small template-generated `.twb` is kept **only** as a unit-test snippet source, not as the demo fixture.

---

## 7. Data model mapping approach

1. **Anchor** each workbook field to a legacy column deterministically from `metadata-records` (remote name + parent table) and the relationship/join tree. Calculated fields resolve to their base columns.
2. **Candidate generation** for each legacy column against all target columns.
3. **Component scores** (0–1 each, all displayed):
   | Component | Method | Weight |
   |---|---|---|
   | Name | token normalisation (case split, abbreviation dictionary `cust→customer`, `amt→amount`, `dt→date`, `qty→quantity`, `px→price`), token Jaccard + `rapidfuzz` ratio | 0.30 |
   | Description | overlap with target column description / glossary | 0.10 |
   | Type compatibility | rule table: exact, widening, narrowing, incompatible | 0.15 |
   | Value overlap | categorical distinct-value overlap; numeric/date range and distribution overlap | 0.25 |
   | Structural | role match (key/measure/attribute), table concept, key-to-key | 0.20 |
4. **Match class**: exact, renamed, type-changed, one-to-many (split/merged), missing, ambiguous (top-2 within 0.05).
5. **Deterministic validators** on the selected candidate: type and lossy-cast risk; target key uniqueness (grain); **join fan-out** (`COUNT(*)` vs `COUNT(DISTINCT grain_key)` along the target join path); value-domain comparison (e.g. status `X` vs `CANCELLED`); null-rate comparison.
6. **Confidence band**: High (score ≥ 0.85 and all validators pass), Medium (≥ 0.65), Low, or **Blocked** (any validator fails). Bands only pre-select a default in the UI; **every mapping needs an explicit human decision**. Bulk approve is limited to High rows and is still an explicit action.
7. **Value mappings**: when domains differ (status codes, region labels), the reviewer records an explicit value mapping table; it becomes part of the generated target SQL and the plan.
8. **Records**: decisions in `mapping_decision` + `audit_log`; each plan and test run stores the hash of the decision set it used.

---

## 8. Semantic validation framework

### 8.1 Equivalence levels
| Level | Question | Established by |
|---|---|---|
| Technical | Does the target query compile and run, types compatible, all fields resolved? | sqlglot compile + execution + type checks |
| Semantic | Is the definition the same (filters, date basis, grain, aggregation, null rule, value domains)? | `logic/compare.py` |
| Business | Do results reconcile at every grain the dashboard exposes, and has an owner signed off? | Test results + human sign-off; never claimed without evidence |

### 8.2 Metric specs
Each KPI in the workbook becomes a `MetricSpec` (measure expression, filters, date field, grain), compiled to SQL against legacy (via anchors) and target (via approved mappings and value mappings). Testability: `testable` (all Supported, all mapped), `conditional` (Partial with acknowledged assumption), `not_testable` (Unsupported calc or unapproved mapping). Not-testable KPIs produce **blocked** tests, never passes.

### 8.3 Test families
| Family | Checks |
|---|---|
| `kpi_total` | KPI over the full filtered population |
| `kpi_by_dimension` | KPI per member of each dimension used in the workbook |
| `kpi_by_period` | KPI per month / quarter / year on the workbook's date field |
| `row_count`, `distinct_count` | rows, distinct orders / customers / products |
| `fanout` | rows vs distinct grain key along the join path |
| `null_profile` | null counts on key fields; size of NULL / unknown segment |
| `date_boundary` | min/max dates; counts in first/last period |
| `filter_population` | rows excluded by each filter on each side |
| `domain` | set difference of categorical members |

### 8.4 Comparison and severity (deterministic)
- Segment comparison: FULL OUTER JOIN of grouped legacy and target results; a segment missing on either side is a finding.
- `diff = actual − expected`; `diff_pct = diff / NULLIF(|expected|, 0)`. Pass if `|diff| ≤ tol_abs` or `|diff_pct| ≤ tol_rel` (defaults: money 0.005 abs / 0.1% rel; counts exact). Decimal arithmetic for money.
- Severity rule table (versioned):
  | Severity | Rule |
  |---|---|
  | Critical | headline `|diff_pct|` > 1%; or a segment `|diff_pct|` > 5% where the segment holds ≥ 5% of the KPI; or fan-out on a revenue path; or a masked discrepancy |
  | High | headline 0.1–1%; or material segment 1–5%; or domain members missing |
  | Medium | non-material segment > 5%; null-profile change; boundary shift |
  | Low | outside tolerance but within 2× tolerance |
- **Masked discrepancy**: the KPI's headline test passes while any dimension or period test for the same KPI fails at High or above → separate Critical finding "headline match conceals segment differences", linking the hidden failures.

### 8.5 Diagnostic probes
Deterministic SQL experiments; each returns `supports` / `refutes` / `inconclusive` with numbers and SQL.
| Probe | Experiment |
|---|---|
| status_filter | Recompute target KPI excluding each status value; does the diff vanish? |
| date_basis | Recompute by each alternative date column; does the period diff vanish? |
| fanout | Duplicate grain keys after each join; duplicated amount |
| null_bucket | Is the diff concentrated in the NULL/unknown segment or in rows dropped by inner joins? |
| dimension_remap | Cross-tab legacy vs target member for the same entity key |
| returns_component | Return amounts subtracted on each side |
| discount_formula | Recompute target with the legacy discount formula; compare |
| aggregation_grain | Compare aggregate at product grain vs line grain (duplicate dimension rows, averaging of averages) |

The "likely explanation" is template text driven by probe outcomes. Each discrepancy has a recommended investigation checklist chosen by rule from the probe outcome.

### 8.6 Validation benchmark

The benchmark measures whether the engine finds real problems, avoids false alarms and produces reproducible evidence. It lives in `benchmark/` and `answer_key/`, outside `src/`, and is run by `scripts/run_benchmark.py`, which writes `benchmark/report.md`.

#### 8.6.1 Independence
| Safeguard | How |
|---|---|
| Sealed answer key | `answer_key/planted_defects.yaml` is written in Phase 1, **before** the validation engine exists; its SHA-256 is recorded in `answer_key/SEALED.sha256` and checked by the benchmark |
| Pre-registered matching | For each defect the key lists its expected signature: affected KPI(s), affected test families and dimensions/periods. A finding *matches* a defect if its (KPI, family, dimension) is in that signature. Written before the engine, so the matching cannot be tuned afterwards |
| Engine isolation | Architecture test: `src/biwb` never imports or reads `answer_key/`, `benchmark/` or `demo/generator`; the engine's only inputs are the workbook, schema specs and DuckDB files |
| Independent oracle | `benchmark/oracle.py` computes every KPI × segment with **pandas** directly from the generator's canonical truth tables, without sqlglot, DuckDB or engine code. Engine numbers must match the oracle (differential test) |
| Hand-computed golden set | `tests/golden/`: a ~40-row dataset with KPI values worked out by hand in a YAML file, used to check the oracle and engine against human-computed values |
| Held-out seeds | Seeds 101, 202 and 303 with randomised defect magnitudes are run only by the benchmark, never used while developing |

#### 8.6.2 Scenarios
| ID | Scenario | Purpose |
|---|---|---|
| S0 | Clean migration (no defects) | False-positive control |
| S1–S8 | Each planted defect alone | Per-defect recall and attribution |
| S9 | All defects combined (the demo) | Realistic interaction |
| S10 | Compensating pair tuned so the headline is within tolerance | Masked-discrepancy detection |
| B1–B5 | **Benign changes** that must not fail: column renames, `INT→BIGINT` widening, row reordering, float rounding within tolerance, status labels changed but covered by an approved value mapping | False-positive checks |
| H1–H3 | Held-out seeds of S9 with randomised magnitudes, incl. near-threshold magnitudes | Generalisation and sensitivity floor |

#### 8.6.3 Metrics and thresholds (MVP gate)
| Metric | Definition | Threshold |
|---|---|---|
| Recall | planted defects with ≥ 1 matching finding at Medium+ ÷ planted defects (S1–S10, H1–H3) | 100% for magnitudes above the documented detectability floor |
| Precision | findings at Medium+ that match a planted defect ÷ all findings at Medium+ (S1–S10) | ≥ 90% |
| False positives | findings at Medium+ in S0 and B1–B5 | 0 |
| Attribution accuracy | defects whose top supporting probe matches the defect class ÷ detected defects | ≥ 85% (reported per class) |
| Masked-discrepancy detection | S10 raises the masked flag; S0 and B1–B5 never do | 100% / 0 |
| Evidence reproducibility | (a) two runs on the same inputs give identical `result_hash` for every test; (b) re-executing each stored discrepancy SQL standalone reproduces the stored numbers; (c) data fingerprints match | 100% |
| Oracle agreement | engine KPI × segment values vs pandas oracle, within 1e-9 relative | 100% |
| Sensitivity floor | smallest defect magnitude detected, per class (reported, not gated) | Reported |

The benchmark report is also shown in the README, so readers can see the claims and their evidence.

#### 8.6.4 Synthetic benchmark vs real-world capability
The benchmark measures detection of **defect classes we designed, planted in data we generated, with signatures we specified**. It shows the engine works as designed on those classes. It is **not** evidence of real-world detection rates, and the product must never present it that way.

Rules for every place results appear (README, benchmark report, UI, demo script):
1. Results are labelled **"Synthetic benchmark — planted defects"**, with the seed list and defect classes.
2. The phrase "100% recall" never appears without "on N planted synthetic defects across M scenarios".
3. A standing limitations section lists what the benchmark does not cover: defect classes not planted; messy real data (late-arriving facts, slowly changing dimensions, currency/timezone issues, mixed grain in source systems); workbooks we did not author; Tableau features classified Partial/Unsupported; defects whose effect falls within tolerance; and the fact that the same team designed both the defects and the detector.
4. Real-world capability can only be claimed from evaluations on independent workbooks and data not designed by us (deferred, §18).
5. The readiness report states that a "Ready" status means "no failures found by the executed tests", not "migration proven correct".

---

## 9. AI design: optional and outside the decision paths

### 9.1 Responsibility matrix
| Task | Deterministic | AI (optional) | Decides |
|---|---|---|---|
| Parse workbook, classify calcs | ✔ | — | Code |
| Explain a calc in business language | AST-based template | ✔ narrative | Human reads |
| Mapping candidates | ✔ scored | ✔ extra suggestion shown separately, with rationale | **Human** |
| Validate mappings | ✔ | — | Code |
| Logic differences | ✔ | ✔ explain implications | Code + human |
| SQL for Unsupported calc | ✗ none generated | ✔ may draft text in the annotation panel, labelled "AI draft — not used by any test", never stored as a `sql_artifact` and never executed | Human writes manual action |
| Execute SQL, metrics, diffs, severity | ✔ | ✗ | Code |
| Likely explanation | ✔ probe template | ✔ narrative citing test/probe IDs | Human |
| Readiness status and score | ✔ | ✗ | Code |
| Declare migration successful | ✗ alone | ✗ never | Rules + evidence + human sign-off |

### 9.2 Enforcement
1. **Import boundary**: `validation`, `readiness`, `mapping.validators`, `calc`, `planner` must not import `biwb.ai`. Checked by an architecture test (AST scan of imports).
2. **Write boundary**: the AI layer writes only to `ai_annotation`. Repository functions for decision tables do not accept AI-originated objects.
3. **Input boundary**: readiness and severity functions take only deterministic inputs (test results, decisions, rules); their signatures contain no annotation types.
4. **Invariance test**: the full demo pipeline produces byte-identical test results and readiness assessment with AI on (replayed responses) and AI off.
5. **Output validation**: AI responses are parsed into pydantic schemas; any reference to a field, table, test or probe ID that does not exist in the project rejects the response.
6. **UI**: AI content is shown in a separately styled "AI annotation" panel with model name, timestamp and a link to the exact payload sent.

### 9.3 Model configuration and verification
- **Configurable**: `BIWB_AI_MODEL` (env or `.env`), `BIWB_AI_EFFORT` (default `medium`), `BIWB_AI_ENABLED` (default `false`).
- **Verified model identifiers** (checked 2026-10-30 against Anthropic's current published model list, dated 2026-10-06; a live API check was not possible because no API key or `ant` CLI is configured on this machine):
  | Model | ID | Note |
  |---|---|---|
  | Claude Opus 5.5 | `claude-opus-5-5` | Current Opus; Anthropic's recommended default — **proposed default** |
  | Claude Sonnet 5.5 | `claude-sonnet-5-5` | Current Sonnet; half the price; suitable if you prefer lower cost |
  | Claude Haiku 5.5 | `claude-haiku-5-5` | Cheapest; adequate for short calc explanations |
  This changes rev 1's proposed default (`claude-sonnet-5-5`) to `claude-opus-5-5`, Anthropic's current recommended default. The choice is a single config value.
- **Runtime source of truth**: the configured ID and the table above are only *requests*; the **Anthropic Models API** decides. When AI is enabled, `model_registry.py` calls `client.models.retrieve(model_id)` once per session (and again after any 404 from the Messages API). AI is enabled only if that call succeeds; on not-found, auth error, network error or timeout, AI stays **disabled** for the session with the reason shown, and the deterministic product continues unaffected. No hard-coded fallback model is tried silently. The verified `id` and `display_name` are stored with every `ai_annotation`.
- **Implementation notes for the current API** (to respect when Phase 8 is built): thinking cannot be disabled on Opus 5.5 — depth is controlled with `output_config.effort`, set explicitly; sampling parameters such as `temperature` are rejected, so reproducibility comes from the **replay cache**, not from temperature 0; structured output via the SDK's `messages.parse()` with pydantic models; handle `stop_reason == "refusal"` before reading content; the model that actually answered is recorded in `ai_annotation.model_answered`.
- **No key needed for the demo**: a committed replay cache (`demo/ai_replay/`) lets the AI panels be shown offline; replayed responses are labelled as replays.

---

## 10. Security architecture

| Concern | Control |
|---|---|
| Local processing | Streamlit bound to `127.0.0.1`; `browser.gatherUsageStats=false`; only optional outbound call is the Anthropic API |
| Data to LLM | Off by default. Redaction policy sends only: field names, types, the **selected** calc formula, schema metadata, aggregate test figures. Never row-level data, sample values, file paths, connection details or full XML. Payload preview with explicit "Send"; exact payload stored locally in `ai_annotation`; a test asserts payloads contain no sample values or paths |
| API keys | Environment / `.env` (git-ignored); `.env.example` committed; key never logged or displayed |
| XML attacks | defusedxml pre-check rejects DTDs and entities; lxml `resolve_entities=False, no_network=True`; 50 MB limit |
| ZIP attacks | Reject absolute paths and `..`; cap member count, total size and compression ratio |
| SQL execution | No free-form SQL. SQL built through sqlglot builders; every statement passes `sql_guard` (single `SELECT`, table allowlist, banned `COPY`/`ATTACH`/`INSTALL`/`LOAD`/`PRAGMA`/`read_*` file functions); DuckDB `read_only=True`, `enable_external_access=false`, `lock_configuration=true`, timeout, row cap |
| Record keeping | Append-only `audit_log`: uploads, mapping decisions, assumption acknowledgements, plan generations, test runs, AI sends, sign-offs |
| Confidentiality | Synthetic data only; README warns against publishing real workbooks to Tableau Public |

---

## 11. UI wireframe descriptions

Global: left sidebar with project selector, **workflow stepper** (8 steps, ✔ / ! / ○), and an **AI status chip** ("AI off" or "AI on · Claude Opus 5.5 · 3 requests sent"). Neutral enterprise styling; colour reserved for severity and support level. Every number has an "Evidence" expander (SQL, run id, XML line).

1. **Project Overview**: cards for workbook (version, complexity band, support summary), schemas, mappings (approved / pending / blocked), validation (last run, failures by severity), readiness status; "Next action" panel; "Load demo project" button.
2. **Workbook Intelligence**: tabs *Summary*, *Data sources* (connections, joins and relationships diagram), *Fields*, *Calculations* (formula, classification badge with reason codes, dependency graph, SQL preview only when Supported), *Worksheets & Dashboards*, *Support report*.
3. **Data Model Mapping**: schema loaders and profiles; mapping grid (workbook field → legacy column → target column, class, score bar, band, validator icons); side panel with score components, evidence, alternatives, value-mapping editor, Approve / Reject / Defer + comment.
4. **Business Logic Analysis**: one card per KPI: legacy vs target definition side by side (formula, filters, date basis, grain), differences highlighted, three equivalence badges, testability status, assumption acknowledgement for Partial calcs.
5. **Migration Planner**: ordered steps, transformations, SQL suggestions (read-only, guard status), calc changes, breakages, manual review checklist; export Markdown + `.sql`.
6. **Validation Lab**: generated test suite (family, KPI, dimension, tolerance), editable tolerances, Run, run history with fingerprints, pass/fail summary by family.
7. **Discrepancy Explorer**: filters (severity, KPI, family, dimension); detail: expected vs actual, diff and %, segment chart legacy vs target, masked-discrepancy banner, probe results with evidence, deterministic explanation, optional AI annotation panel, both SQL statements, investigation checklist.
8. **Migration Readiness Report**: status banner, gates, score breakdown (value × weight = contribution, with rule text), failed tests, unresolved ambiguities, assumptions in force, manual actions; export Markdown.

---

## 12. Readiness scoring (transparent rules)

**Gates (evaluated first; override the score):**
| Gate | Status if violated |
|---|---|
| Any Critical test failed | **Not ready** |
| Any KPI-referenced field without an approved mapping | **Blocked** |
| Validation coverage < 60% of the KPI × family matrix | **Insufficient evidence** |
| No test run on the current mapping-decision set | **Insufficient evidence** |

**Score (0–100), always shown with the gates:**
| Factor | Definition | Weight |
|---|---|---|
| Mapping completeness | approved required mappings ÷ required mappings | 25 |
| Logic testability | KPI calcs testable (Supported, or Partial with acknowledged assumption) ÷ KPI calcs | 15 |
| Validation coverage | executed KPI × family cells ÷ required cells | 20 |
| Validation pass rate | 1 − Σ severity weights of failures ÷ Σ severity weights of tests (C=8, H=4, M=2, L=1) | 30 |
| Ambiguity resolution | resolved ambiguities ÷ total ambiguities | 10 |

Bands when no gate fires: ≥ 90 **Ready**, 75–89 **Ready with conditions** (conditions listed, including all Partial-calc assumptions), < 75 **Not ready**. Complexity is reported as context, not a penalty. Each assessment stores `rules_version`.

---

## 13. Synthetic demonstration environment

**Business**: e-commerce, 2024-01-01 → 2025-12-31, `numpy.random.default_rng(seed)`. ~5,000 customers, ~40,000 orders, ~100,000 order lines, ~300 products, 12 categories, 6 regions, ~4% cancelled orders, ~6% returned lines, discounts on ~35% of lines, ~1.5% customers with missing region.

**Canonical truth → two writers**: one truth model; a legacy writer and a target writer derive the two architectures; defects are optional transforms in the target writer (`--scenario S0..S10|B1..B5`).

**Legacy** (`legacy.duckdb` + CSV export for Tableau): `ORDERS_HDR` (`OrdID`, `CustNo`, `OrdDt`, `ShipDt`, `OrdStat` codes `C/S/X/R`), `ord_lines` (`line_no`, `ProdCode`, `QTY`, `UnitPx`, `DiscPct`, stored `LineAmt`), `PROD_MSTR`, `prod_cat`, `CUSTMR` (`Rgn_Cd`), `RGN_LKP`, `RTN_LOG`; mixed naming conventions and duplicated derived columns.

**Target** (`target.duckdb`): `dim_customer`, `dim_product`, `dim_region`, `dim_date`, `fct_order` (grain: order), `fct_order_line` (grain: order line), `fct_return` (grain: returned line), `bridge_order_promotion` (grain: order × promotion); grain and definitions documented in `target_schema.yaml`.

**Defect classes** (details only in the sealed answer key): cancelled orders included; wrong date field; changed discount formula; one-to-many join duplicating revenue; different null handling; wrong product-level aggregation; returns excluded; region mapping changed.

---

## 14. Test strategy

| Layer | Content |
|---|---|
| Unit | calc lexer/parser golden tests (≥ 150 formulas); **classifier tests: every catalogue entry's level, propagation through dependencies, unknown function → Unsupported**; **translator contract: for Unsupported/unacknowledged Partial input, `to_sql` raises and emits nothing**; shelf decoder; XML parser on snippets (join-only layout, relationships, custom SQL, sqlproxy); mapping normaliser and scorers; severity table; masked-discrepancy rule; readiness gates and score; sql_guard negative suite; file_guard (zip slip, bombs, XXE) |
| Real Tableau fixture | parse `fixtures/tableau/sales_performance_legacy.{twb,twbx}`; compare inventory with the build guide's expected list (sheets, calcs, filters, parameter, join, relationships) |
| Golden | hand-computed ~40-row dataset; engine and oracle must both equal the hand values |
| Integration | demo build → parse → scripted mapping decisions → plan → run → report |
| Benchmark | `scripts/run_benchmark.py`: scenarios S0–S10, B1–B5, H1–H3; metrics and thresholds in §8.6.3; fails CI if any gate is missed |
| Reproducibility | double-run result hashes; standalone re-execution of stored discrepancy SQL |
| Architecture | import boundaries (engine ↛ answer_key/benchmark/demo.generator; decision packages ↛ ai) |
| AI | replay-cache contract tests; payload redaction test (no sample values or paths); hallucinated-ID rejection; **AI on vs off invariance** of results and readiness; model registry fail-closed when the model is unknown |
| UI smoke | `streamlit.testing.v1.AppTest` loads every page with the demo project |

---

## 15. Development phases (revised sequence)

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0 Foundation | `pyproject.toml`, venv instructions (Win/macOS), ruff, pytest, config, SQLite migrations, audit log, `sql_guard`, `file_guard`, architecture-boundary tests | `pytest` green; guard negative tests pass |
| 1 Synthetic environment + benchmark foundation | truth model, legacy/target writers, scenarios S0–S10 and B1–B5, CSV export, schema YAMLs, **sealed answer key with signatures**, pandas oracle, golden set, **demo workbook build guide** | Data reproducible by seed; answer key hash recorded; oracle matches golden set |
| ⏸ Checkpoint A — **you** | Build the workbook in Tableau Desktop Public Edition using the guide; save `.twb` and `.twbx`; return files | Fixtures committed under `fixtures/tableau/` |
| 2 Workbook intelligence | loader, XML parser (incl. relationships), shelf decoder, calc parser, **classifier**, support report, Workbook page | Tableau-authored fixture parses; inventory matches the build guide; every calc classified |
| 3 Mapping | schema import/profiling, candidates, scorers, validators, value mappings, review workflow, Mapping page | Demo fields mapped (correct top candidate or flagged ambiguous); decisions audited |
| 4 Logic + planner | Supported-only `to_sql`, assumption acknowledgement, logic comparison, plan + SQL export, Logic and Planner pages | KPI SQL for both sides; Unsupported calcs produce no SQL; guard passes |
| 5 Validation + probes | test generator, runner, compare, severity, masked rule, probes, fingerprints, Validation Lab and Discrepancy Explorer pages | Engine matches oracle; S9 demo shows the intended findings |
| 6 Benchmark + readiness | `run_benchmark.py`, report, readiness rules/score/report, Overview and Readiness pages | **All §8.6.3 thresholds met**, including held-out seeds |
| 7 End-to-end hardening | demo script, README, screenshots, fresh-clone run on Windows (and macOS if available) | MVP acceptance checklist §17 complete except AI items |
| 8 Optional AI layer | model registry with Models API check, gateway, redaction, payload preview, prompts, replay cache, annotation panels | AI items of §17 pass, including on/off invariance |

**Authorised now: Phases 0 and 1 only.** Work stops at Checkpoint A; no Streamlit pages or AI code are built before then. Each phase ends with a report (files, tests, acceptance criteria, decisions, risks, commands) in `docs/phase-reports/`.

Checkpoint A only needs Phase 1's CSVs and guide, so Phase 2 work on unit-level parsing (snippets, calc parser, classifier) can start while you build the workbook. Each phase ends with a short review with you.

---

## 16. Technical risks and limitations

| Risk | Impact | Mitigation |
|---|---|---|
| Tableau XML undocumented and version-dependent | Parser breaks on other versions | Defensive parsing; unknown-element reporting; tested scope stated as 2026.3; snippet variants |
| Calc semantics depend on viz context | Wrong translation | Supported/Partial/Unsupported policy; no silent translation; assumptions acknowledged explicitly |
| Synthetic benchmark flatters detection | Overclaiming | Sealed pre-registered key, oracle, benign controls, held-out seeds, reported sensitivity floor, limitations stated in README |
| Hand-built workbook deviates from the guide | Expectations drift | Inventory check at start of Phase 2 |
| Public Edition limits (file connections; local save to be confirmed) | Demo realism / logistics | CSV connections; fallback via synthetic-only Tableau Public download |
| Model ID changes over time | AI calls fail | Config value + Models API check at startup + fail closed |
| AI nondeterminism / hallucination | Misleading text | Schema validation, ID whitelist, labelling, replay cache, no decision-path access |
| Streamlit state for review workflows | Fiddly UX | Persist each decision to SQLite immediately; pages read from DB |
| Python 3.14 is new | Library edge cases | All wheels verified; test on 3.12 too |

---

## 17. MVP acceptance checklist

The MVP is accepted when every item is ticked, with evidence linked from `benchmark/report.md` or the demo script.

**Setup and platform**
- [ ] Fresh clone installs and runs on Windows with documented commands (macOS commands documented; run on macOS if a machine is available)
- [ ] App works with no API key and AI disabled
- [ ] No network calls when AI is disabled (checked by a test that blocks sockets)

**Workbook intelligence**
- [ ] Tableau-authored `.twb` and `.twbx` fixtures parse without errors
- [ ] Inventory (data sources, join, relationships, fields, calcs, parameter, filters, worksheets, dashboard) matches the build guide
- [ ] Every calculated field shows a level (Supported / Partial / Unsupported) with reason codes
- [ ] The table calc in the fixture is reported Unsupported and produces no SQL
- [ ] Malicious-file tests (XXE, zip slip, zip bomb) are rejected

**Mapping**
- [ ] Every workbook field has candidates with score components, rationale and confidence band
- [ ] No mapping is approved without an explicit user action; decisions appear in the audit log
- [ ] Domain mismatch (status codes) and an ambiguous date mapping are flagged in the demo
- [ ] Fan-out validator flags the one-to-many join path

**Logic and planning**
- [ ] SQL generated only for Supported calcs and acknowledged Partial calcs; every generated statement passes `sql_guard`
- [ ] Migration plan exports to Markdown and `.sql`, with dependency order, breakages and manual-review list

**Validation and discrepancies**
- [ ] Demo run (S9) executes the generated suite in < 2 min end-to-end
- [ ] Each discrepancy shows test name, expected, actual, difference, difference %, severity, likely explanation, supporting SQL and recommended investigation
- [ ] Masked-discrepancy finding raised in the demo when headline revenue is within tolerance

**Benchmark (§8.6.3)**
- [ ] Recall 100% (S1–S10, H1–H3, above floor)
- [ ] Precision ≥ 90%
- [ ] Zero Medium+ findings on S0 and B1–B5
- [ ] Attribution accuracy ≥ 85%
- [ ] Masked detection 100% on S10, 0 elsewhere
- [ ] Reproducibility 100% (result hashes, standalone SQL re-execution, fingerprints)
- [ ] Engine vs pandas oracle agreement 100%; golden set matches hand-computed values
- [ ] Answer-key hash unchanged since Phase 1; engine isolation test passes

**Readiness**
- [ ] Demo produces **Not ready** with the Critical gate cited
- [ ] S0 produces **Ready**
- [ ] Score breakdown shows value, weight, contribution and rule text for every factor

**AI (optional layer)**
- [ ] Configured model verified via the Models API at enable time; unknown model → AI stays off with a message
- [ ] Payload preview before each send; stored payload equals bytes sent; no sample values or paths in payloads
- [ ] Results and readiness identical with AI on and off
- [ ] AI panels demonstrable offline via labelled replay cache

---

## 18. Deferred to future releases

| Feature | Notes |
|---|---|
| Writing or modifying `.twb` (automated repointing) | Requires a validated writer and Tableau round-trip tests |
| Comparing a legacy workbook with a migrated workbook (`.twb` vs `.twb` logic diff) | Natural next step once the single-workbook parser is solid |
| Table-calculation translation (addressing/partitioning to SQL windows) | Unsupported in MVP |
| INCLUDE/EXCLUDE LOD translation without manual assumption | Needs worksheet-context inference |
| Relative-date, Top-N and context-filter semantics without assumptions | Partial in MVP |
| Data blending, sets/groups/bins translation, dashboard actions, story points | Detected only |
| Reading `.hyper` extracts in `.twbx` (`tableauhyperapi`) | Optional extra |
| Published data sources, Tableau Server/Cloud APIs | Needs server access |
| Remote warehouses (Snowflake, BigQuery, Postgres) | DuckDB adapter abstraction prepared |
| Batch processing of many workbooks, portfolio dashboard | After single-workbook flow |
| User-defined custom tests (form builder) | MVP only edits tolerances |
| HTML/PDF report export | MVP exports Markdown |
| Hash-chained tamper-evident audit log | MVP log is append-only |
| Multi-user, sign-in, RBAC, shared review | Single-user MVP |
| AI-drafted SQL for Unsupported calcs entering a verified pipeline | Would need a separate verification design |
| Other BI tools (Power BI `.pbix`, Looker) | Out of scope |

---

## 19. Changes to project structure (rev 2)

```
BIAssurance/
├─ pyproject.toml  README.md  .env.example  .gitignore  .streamlit/config.toml
├─ app/
│  ├─ Home.py                                   (Project Overview)
│  ├─ pages/1_Workbook_Intelligence.py … 7_Readiness_Report.py
│  └─ ui/                                        (stepper, evidence expander, badges, AI annotation panel)
├─ src/biwb/
│  ├─ config.py
│  ├─ domain/models.py
│  ├─ workbook/  loader.py xml_parser.py model_builder.py shelf_decoder.py support_matrix.py complexity.py
│  ├─ calc/      lexer.py parser.py ast.py functions.py classifier.py* analyzer.py to_sql.py
│  ├─ schema/    spec_loader.py introspect.py profiler.py
│  ├─ mapping/   normalize.py candidates.py scorers.py validators.py service.py
│  ├─ logic/     compare.py
│  ├─ planner/   plan_builder.py dependency_order.py sql_generator.py export.py
│  ├─ validation/ specs.py test_generator.py sql_builder.py runner.py compare.py severity.py fingerprint.py* probes/ service.py
│  ├─ readiness/ rules.py scoring.py report.py
│  ├─ ai/        gateway.py model_registry.py* redaction.py schemas.py prompts/ replay_cache.py
│  ├─ safety/    sql_guard.py file_guard.py
│  ├─ persistence/ db.py repositories.py migrations/
│  └─ audit/     log.py
├─ demo/
│  ├─ generator/  truth.py legacy_writer.py target_writer.py scenarios.py*
│  ├─ schemas/    legacy_schema.yaml target_schema.yaml
│  └─ ai_replay/* (recorded AI responses for offline demo)
├─ fixtures/tableau/*  sales_performance_legacy.twb  .twbx  FIXTURE.md     (Tableau-authored)
├─ answer_key/  planted_defects.yaml  SEALED.sha256*                       (sealed)
├─ benchmark/*  oracle.py  matching.py  report.md
├─ scripts/     build_demo.py  run_benchmark.py*  (replaces score_detection.py)
├─ tests/
│  ├─ unit/  integration/  ui/
│  ├─ golden/*        (hand-computed dataset + expected values)
│  ├─ architecture/*  (import and isolation boundaries)
│  ├─ benchmark/*     (threshold assertions)
│  └─ fixtures/snippets/  (small XML variants)
└─ docs/  architecture-plan.md  demo-workbook-build-guide.md*  demo-script.md
```
`*` = new or changed in rev 2. Removed from rev 1: `demo/workbook/build_twb.py` as the demo fixture source (a small snippet generator remains under `tests/fixtures/`), `logic/equivalence.py` (merged into `compare.py`).

---

## 20. Summary for final approval

### What the product will do (MVP)
For one workbook, a legacy dataset and a target dataset, it will: inventory the workbook and classify every calculation as Supported, Partial or Unsupported; propose field mappings with evidence for you to approve; generate KPI SQL for Supported logic only, plus a migration plan; run deterministic tests at total, segment and period grain; flag masked discrepancies; attach probe evidence to every discrepancy; and compute readiness from published gates and weights. It runs offline; AI is optional and annotates only.

### What makes it different
- Tableau's **Replace Data Source** repoints fields by name and does not check whether meaning is preserved; catalogue and lineage features (on licensed Server/Cloud) show dependencies, not result equivalence.
- A general AI assistant can summarise workbook XML but does not execute reconciliation and can state conclusions without evidence.
- This workbench treats migration as a **testing problem**, with a published benchmark (precision, recall, false-positive controls, reproducibility) showing how well it works.

### First demonstration scenario — "Sales Performance" headline trap
1. Load demo project (seed 42, scenario S9).
2. Workbook Intelligence: the Tableau-authored workbook — 4 worksheets, 1 dashboard, ~7 calcs (Net Revenue, Gross Profit, GP Margin %, Discount Amount, Orders, AOV, Return Rate), one FIXED LOD (Supported), one table calc (Unsupported, no SQL), `Top N` parameter, cancelled-order filter, order-year filter; join and relationships displayed.
3. Mapping: status-code domain mismatch and ambiguous date mapping flagged; fan-out on promotion bridge flagged; user decides.
4. Validation Lab: run the suite.
5. Reveal: FY2025 Net Revenue within 0.5% at headline, but the **masked discrepancy** fires: two regions off by ~8–10%, monthly shifts at boundaries, duplicated lines, category-level gross-profit differences, missing NULL-region segment.
6. Discrepancy Explorer: `dimension_remap` and `fanout` probes show the evidence.
7. Readiness: **Not ready** (Critical gate), with score breakdown and manual actions.
8. Benchmark report: recall, precision, false positives, masked detection, reproducibility — all against the sealed key and the independent oracle.

### Implementation sequence
Phase 0 → 1 → **Checkpoint A (you build the workbook in Tableau)** → 2 → 3 → 4 → 5 → 6 → 7 → 8 (optional AI), as in §15.

### Decisions needed for final approval
1. Default AI model `claude-opus-5-5` (changed from rev 1), with `claude-sonnet-5-5` available by setting `BIWB_AI_MODEL`.
2. Benchmark thresholds in §8.6.3.
3. You build the demo workbook at Checkpoint A, after Phase 1.
