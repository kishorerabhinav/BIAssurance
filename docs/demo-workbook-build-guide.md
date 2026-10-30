# Demo workbook build guide — "Sales Performance" (legacy)

**Who:** you, at Checkpoint A. **Tool:** Tableau Desktop Public Edition 2026.3. **Time:** about 45–60 minutes.
**Data:** synthetic only (seed 42). Nothing in this guide publishes anything to Tableau Public.

> **Shortcut now available.** A script-generated version of this exact workbook exists at
> `fixtures/tableau/generated/` (`scripts/build_demo_workbook.py`). Opening it in Tableau and
> saving a copy takes about 5 minutes; see `fixtures/tableau/FIXTURE.md`. This guide remains the
> fallback if Tableau won't open the generated file, and the specification the generator follows.

The workbench's parser will be developed and tested against the file you create here, so it is a
genuinely Tableau-authored workbook. Follow names and formulas exactly; if Tableau shows a
different name or behaves differently from what is written, **don't work around it — note it**
in the fixture notes (step 9). Differences are useful evidence.

---

## 0. Before you start

1. Build the data (skip if already done):
   ```powershell
   cd D:\BIAssurance
   .\.venv\Scripts\python.exe scripts\build_demo.py --scenarios S0
   ```
2. The CSV folder is `D:\BIAssurance\demo\data\seed_42\legacy_csv\`. It holds 8 files:
   `ORDERS_HDR.csv`, `ord_lines.csv`, `PROD_MSTR.csv`, `prod_cat.csv`, `CUSTMR.csv`, `RGN_LKP.csv`,
   `RTN_LOG.csv`, `PROMO_XREF.csv`. **Do not use `PROMO_XREF.csv`** in the workbook.
3. Check that local saving works: open Tableau, then **File → Save As**. If you can't save a `.twb` or
   `.twbx` to your disk, stop and tell me; don't publish to Tableau Public as a workaround without
   agreeing it first.
4. Note your exact version from **Help → About Tableau** (for the fixture notes).

## 1. Connect to the CSV files

1. On the start page: **Connect → To a File → Text file**, and choose `ORDERS_HDR.csv`.
2. All CSVs in the folder appear under **Files** in the left pane.
3. Keep the connection **Live** (not Extract).

## 2. Build the data model: physical joins + one relationship

The model deliberately uses **both** structures, because real legacy workbooks do: lookups are
joined physically into the order logical table, and returns stay a separate logical table at their
own grain, connected by a relationship.

(Revised 2026-10-30. An earlier version related products → categories and customers → regions
as chained relationships; workbooks generated with that layout failed Tableau 2026.3's query
checker, so the generated workbook and this guide use the layout below, which loads cleanly.)

**2a. Physical joins (inside the order logical table)**
1. `ORDERS_HDR.csv` is on the canvas as a logical table. **Double-click it** to open its physical layer.
2. Drag in each file and set the join, in this order:

| Drag in | Join type | Join clause |
|---|---|---|
| `ord_lines.csv` | **Inner** | `OrdID` (ORDERS_HDR.csv) = `OrdID` (ord_lines.csv) |
| `PROD_MSTR.csv` | **Left** | `ProdCode` (ord_lines.csv) = `ProdCode` (PROD_MSTR.csv) |
| `prod_cat.csv` | **Left** | `CatCd` (PROD_MSTR.csv) = `CatCd` (prod_cat.csv) |
| `CUSTMR.csv` | **Left** | `CustNo` (ORDERS_HDR.csv) = `CustNo` (CUSTMR.csv) |
| `RGN_LKP.csv` | **Left** | `Rgn_Cd` (CUSTMR.csv) = `Rgn_Cd` (RGN_LKP.csv) |

3. Close the physical layer to return to the logical canvas.

The left joins keep customers without a region (they appear as **Null** region), exactly as before.

**2b. Relationship (logical layer)** — drag `RTN_LOG.csv` onto the logical canvas next to the
order table and relate it on **two** field pairs: `OrdID` = `OrdID` **and** `line_no` = `line_no`
(use "Add more fields" in the relationship dialog). Leave performance options at their defaults.

**2c. Check data types** in the data grid (the icon above each column):

| Field(s) | Required type |
|---|---|
| `OrdDt`, `ShipDt`, `RtnDt`, `SignupDt` | Date |
| `QTY`, `line_no`, `RtnQty` | Number (whole) |
| `UnitPx`, `DiscPct`, `UnitCost`, `LineAmt`, `OrdTotAmt`, `ListPx`, `StdCost`, `RtnAmt` | Number (decimal) |
| all codes and ids (`OrdID`, `CustNo`, `ProdCode`, `CatCd`, `Rgn_Cd`, `StCd`, `RtnID`, `OrdStat`) | String |

Tableau gives duplicated column names a suffix, e.g. `OrdID (ord_lines.csv)` or
`CustNo (CUSTMR.csv)`. In the steps below, **`OrdID`, `CustNo` and `OrdDt` always mean the
ORDERS_HDR fields** (the ones without a suffix).

## 3. Data source filter: exclude cancelled orders

1. On the Data Source page, top right: **Filters → Add… → Add…**, choose `OrdStat`.
2. Select `X`, tick **Exclude**, then OK.

(This filter applies before FIXED level-of-detail calculations; the parser must notice that.)

## 4. Parameter

**Create Parameter** (data pane menu ▾ → Create Parameter):

| Property | Value |
|---|---|
| Name | `Top N` |
| Data type | Integer |
| Current value | 10 |
| Allowable values | Range: minimum 5, maximum 50, step size 5 |

## 5. Calculated fields

Use **Analysis → Create Calculated Field**. Copy each formula exactly. If Tableau labels a field
differently (for example with a file-name suffix), use the name Tableau shows and note the difference.

| # | Name | Formula |
|---|---|---|
| 1 | `Line Gross` | `[QTY] * [UnitPx]` |
| 2 | `Discount Amount` | `[QTY] * [UnitPx] * ZN([DiscPct])` |
| 3 | `Line Net` | `[Line Gross] - [Discount Amount]` |
| 4 | `Line Cost` | `[QTY] * [UnitCost]` |
| 5 | `Gross Profit` | `[Line Net] - [Line Cost]` |
| 6 | `Net Revenue` | `SUM([Line Net])` |
| 7 | `GP Margin %` | `SUM([Gross Profit]) / SUM([Line Net])` |
| 8 | `Orders` | `COUNTD([OrdID])` |
| 9 | `AOV` | `SUM([Line Net]) / COUNTD([OrdID])` |
| 10 | `Return Rate` | `SUM([RtnAmt]) / SUM([Line Net])` |
| 11 | `Customer First Order` | `{ FIXED [CustNo] : MIN([OrdDt]) }` |
| 12 | `Cohort Year` | `YEAR([Customer First Order])` |
| 13 | `Running Net Revenue` | `RUNNING_SUM(SUM([Line Net]))` |

Formatting (optional but helpful): `GP Margin %` and `Return Rate` → Percentage, 2 decimals.
After creating **Cohort Year**: in the data pane, right-click it → **Convert to Dimension**, then
**Convert to Discrete** if offered.

## 6. Worksheets

On **every** worksheet, add the year filter: drag `OrdDt` to **Filters** → choose **Years** →
select **2025** only → OK. This is a normal (dimension) filter unless a step says otherwise.

| # | Sheet name (exact) | Build |
|---|---|---|
| 1 | `KPI Summary` | Drag **Measure Names** to Rows and **Measure Values** to Text. In the Measure Values card keep only: `Net Revenue`, `SUM(Gross Profit)`, `GP Margin %`, `Orders`, `AOV`, `Return Rate`, `SUM(Discount Amount)`, `SUM(RtnAmt)`. Year filter 2025. |
| 2 | `Revenue by Region` | `Rgn_Nm` → Rows; `Net Revenue` → Columns; `SUM(Gross Profit)` → Tooltip. Sort descending by Net Revenue. Keep the **Null** region visible (don't filter or hide it). Year filter 2025. |
| 3 | `Monthly Trend` | `OrdDt` → Columns, then right-click the pill → **Month** in the *continuous* group (shows e.g. "May 2015"). `Net Revenue` → Rows. `Running Net Revenue` → Rows (second axis). Leave the table calculation's default "Compute using: Table (across)". Year filter 2025. |
| 4 | `Category Profitability` | `CatNm` → Rows; `SUM(Gross Profit)` → Columns; `GP Margin %` → Color. Year filter 2025. |
| 5 | `Top Products` | `ProdNm` → Rows; `Net Revenue` → Columns, sorted descending. Drag `ProdNm` to Filters → **Top** tab → **By field**: Top, `Top N` (the parameter), by `Net Revenue`. Year filter 2025, then **right-click the YEAR(OrdDt) filter pill → Add to Context** (it turns grey). Right-click the `Top N` parameter → Show Parameter. |
| 6 | `Customer Cohorts` | `Cohort Year` → Rows; `Net Revenue` → Columns; `Orders` → Label. Year filter 2025 as a **normal** filter (not context). |

## 7. Dashboard

**Dashboard → New Dashboard**, name it `Sales Performance`. Size: Automatic. Add these four sheets:
`KPI Summary` (top), `Revenue by Region`, `Monthly Trend`, `Category Profitability`. No actions
are needed.

## 8. Check your numbers (reference values, FY2025)

Computed independently by the workbench's oracle from the same CSVs. Small display rounding is fine.

| KPI Summary | Expected |
|---|---|
| Net Revenue | 405,668,723.55 |
| SUM(Gross Profit) | 165,958,444.73 |
| GP Margin % | 40.91% |
| Orders | 20,694 |
| AOV | 19,603.20 |
| Return Rate | 4.67% |
| SUM(Discount Amount) | 20,774,052.45 |
| SUM(RtnAmt) | 18,960,204.40 |

| Revenue by Region | Net Revenue |
|---|---|
| South | 120,287,591.30 |
| North | 105,471,760.65 |
| West | 79,737,339.25 |
| East | 50,919,888.50 |
| Central | 30,129,499.70 |
| Northeast | 10,732,755.40 |
| Null | 8,389,888.75 |

| Customer Cohorts | Net Revenue |
|---|---|
| 2024 | 381,891,059.40 |
| 2025 | 23,777,664.15 |

Top Products, first row: **Study Table F496**, 35,177,140.70. Monthly Trend, January 2025: 28,849,267.70.

If any value differs, **don't change the workbook to force a match**. Record the sheet, the value
you see and the expected value in the fixture notes. A difference could mean a build step differs
or that Tableau's semantics differ from the oracle's, and both are things the project needs to know.

## 9. Save and hand back

1. **File → Save As** → folder `D:\BIAssurance\fixtures\tableau\` → name `sales_performance_legacy` →
   type **Tableau Workbook (*.twb)**.
2. Save again as a packaged workbook: **File → Save As** → type **Tableau Packaged Workbook (*.twbx)**,
   same folder and name (or **File → Export Packaged Workbook**).
3. Fill in `D:\BIAssurance\fixtures\tableau\FIXTURE.md` (version, date, any deviations, any numbers that differed).
4. Tell me the files are there. That completes Checkpoint A.

## Known limitations of this fixture

| Limitation | Effect |
|---|---|
| File (CSV) connection only, as Public Edition allows | Connection class is a text-file connection, not a database |
| Absolute paths to `D:\BIAssurance\…` are stored in the workbook | The parser masks paths in output; the fixture notes record them |
| One author, one Tableau version (2026.3) | Parser support is stated for this version; other layouts are covered by small XML snippets in tests |
| Hand-built | Phase 2 starts by comparing the parsed inventory with `fixtures/tableau/expected_inventory.yaml` |
| Workbench does not read Tableau's rendered numbers | Validation compares legacy and target data via SQL; section 8 is a manual check only |
