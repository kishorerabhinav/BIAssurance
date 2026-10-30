"""Independent oracle: the dashboard's KPIs computed with pandas from CSV files.

It deliberately shares no code with the engine (no DuckDB, no sqlglot, no biwb imports) so that
engine results can be checked against a second, separately written implementation.

KPI semantics follow the demo workbook build guide (docs/demo-workbook-build-guide.md):
  * data source filter: cancelled orders excluded (applies before the FIXED LOD)
  * every worksheet filters to order year 2025 (dimension filter: applies after the FIXED LOD)
  * Cohort Year = YEAR({FIXED [CustNo] : MIN([OrdDt])}) over non-cancelled orders, all years
  * Net Revenue = SUM(QTY*UnitPx*(1-ZN(DiscPct))); Gross Profit = Net - SUM(QTY*UnitCost)
  * Return Rate = SUM(RtnAmt) / Net Revenue, for returns of the lines in view
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

YEAR = 2025
NULL_LABEL = "<NULL>"
GRAINS = ("total", "region", "category", "product", "month", "cohort_year")
MONEY_KPIS = ("net_revenue", "gross_profit", "discount_amount", "returns_amount", "aov")
RATIO_KPIS = ("gp_margin", "return_rate")
COUNT_KPIS = ("orders",)
KPIS = ("net_revenue", "gross_profit", "gp_margin", "discount_amount", "orders", "aov",
        "return_rate", "returns_amount")

# Line frame columns produced by both loaders.
LINE_COLS = ["order_id", "line_key", "customer", "order_date", "gross", "discount", "net", "cost",
             "returns", "region", "product_code", "cohort_year"]


def _read(folder: Path, table: str) -> pd.DataFrame:
    for name in (f"{table}.csv", f"{table}.csv.gz"):
        path = folder / name
        if path.exists():
            return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    raise FileNotFoundError(folder / f"{table}.csv")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="raise").astype(float)


# --- legacy (the workbook's own semantics) -------------------------------------------------------

def legacy_lines(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (line frame, product attributes) for the legacy CSVs in `folder`."""
    hdr = _read(folder, "ORDERS_HDR")
    lines = _read(folder, "ord_lines")
    cust = _read(folder, "CUSTMR")
    rgn = _read(folder, "RGN_LKP")
    prod = _read(folder, "PROD_MSTR")
    cat = _read(folder, "prod_cat")
    rtn = _read(folder, "RTN_LOG")

    hdr = hdr[hdr["OrdStat"] != "X"]                      # data source filter
    hdr = hdr.assign(OrdDt=pd.to_datetime(hdr["OrdDt"]))
    first = hdr.groupby("CustNo")["OrdDt"].min().dt.year  # FIXED [CustNo] : MIN([OrdDt])

    f = lines.merge(hdr[["OrdID", "CustNo", "OrdDt"]], on="OrdID", how="inner")
    qty, px, cost = _num(f["QTY"]), _num(f["UnitPx"]), _num(f["UnitCost"])
    disc_pct = _num(f["DiscPct"].fillna("0"))             # ZN()
    gross = qty * px
    rtn_amt = rtn.assign(RtnAmt=_num(rtn["RtnAmt"])).groupby(["OrdID", "line_no"])["RtnAmt"].sum()
    region_name = cust.merge(rgn, on="Rgn_Cd", how="left").set_index("CustNo")["Rgn_Nm"]

    out = pd.DataFrame({
        "order_id": f["OrdID"],
        "line_key": f["OrdID"] + "-" + f["line_no"],
        "customer": f["CustNo"],
        "order_date": f["OrdDt"],
        "gross": gross,
        "discount": gross * disc_pct,
        "net": gross - gross * disc_pct,
        "cost": qty * cost,
        "returns": pd.MultiIndex.from_arrays([f["OrdID"], f["line_no"]]).map(rtn_amt).fillna(0.0)
        .to_numpy(dtype=float),
        "region": f["CustNo"].map(region_name),
        "product_code": f["ProdCode"],
        "cohort_year": f["CustNo"].map(first),
    })
    products = prod.merge(cat, on="CatCd", how="left").rename(
        columns={"ProdCode": "product_code", "CatNm": "category"})[["product_code", "category"]]
    return out[LINE_COLS], products


# --- target (the migrated model, read through a mapping profile) --------------------------------

@dataclass(frozen=True)
class TargetProfile:
    """How the migrated dashboard reads the target model (the approved mapping, scripted)."""
    cancelled_values: frozenset[str] = frozenset({"CANCELLED"})
    columns: dict[str, dict[str, str]] = field(default_factory=dict)  # table -> {logical: physical}

    def col(self, table: str, logical: str) -> str:
        return self.columns.get(table, {}).get(logical, logical)


def target_lines(folder: Path, profile: TargetProfile | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = profile or TargetProfile()
    lines = _read(folder, "fct_order_line")
    orders = _read(folder, "fct_order")
    dates = _read(folder, "dim_date")
    cust = _read(folder, "dim_customer")
    region = _read(folder, "dim_region")
    prod = _read(folder, "dim_product")
    ret = _read(folder, "fct_return")

    ok_orders = orders.loc[~orders["order_status"].isin(p.cancelled_values), "order_id"]
    f = lines[lines["order_id"].isin(set(ok_orders))]
    cal = dates.set_index("date_key")["calendar_date"]
    f = f.assign(order_date=pd.to_datetime(f["order_date_key"].map(cal)))
    first = f.groupby("customer_key")["order_date"].min().dt.year

    region_name = cust.merge(region, on="region_key", how="left").set_index("customer_key")[
        p.col("dim_region", "region_name")]
    ret_amt = ret.assign(a=_num(ret["return_amount"])).groupby("order_line_id")["a"].sum()
    gross = _num(f[p.col("fct_order_line", "gross_amount")])
    out = pd.DataFrame({
        "order_id": f["order_id"],
        "line_key": f["order_line_id"],
        "customer": f["customer_key"],
        "order_date": f["order_date"],
        "gross": gross,
        "discount": _num(f[p.col("fct_order_line", "discount_amount")]),
        "net": _num(f[p.col("fct_order_line", "net_amount")]),
        "cost": _num(f[p.col("fct_order_line", "cost_amount")]),
        "returns": f["order_line_id"].map(ret_amt).fillna(0.0).to_numpy(dtype=float),
        # Unknown customers (dropped from the dimension) behave like Tableau's unmatched rows: NULL.
        "region": f["customer_key"].map(region_name),
        "product_code": f["product_code"],
        "cohort_year": f["customer_key"].map(first),
    })
    products = prod.rename(columns={"category_name": "category"})[["product_code", "category"]]
    return out[LINE_COLS], products


# --- KPIs ---------------------------------------------------------------------------------------

def _segment_frame(lines: pd.DataFrame, products: pd.DataFrame, grain: str) -> tuple[pd.DataFrame, str | None]:
    f = lines[lines["order_date"].dt.year == YEAR]         # worksheet filter, after FIXED
    if grain == "total":
        return f.assign(segment="ALL"), "segment"
    if grain == "region":
        return f.assign(segment=f["region"].fillna(NULL_LABEL)), "segment"
    if grain == "category":
        # Product attributes come from a related table: joined only when the view needs them, so a
        # product table with duplicate keys multiplies rows here and nowhere else.
        g = f.merge(products, on="product_code", how="left")
        return g.assign(segment=g["category"].fillna(NULL_LABEL)), "segment"
    if grain == "product":
        g = f.merge(products[["product_code"]], on="product_code", how="left")
        return g.assign(segment=g["product_code"]), "segment"
    if grain == "month":
        return f.assign(segment=f["order_date"].dt.strftime("%Y-%m")), "segment"
    if grain == "cohort_year":
        return f.assign(segment=f["cohort_year"].astype("Int64").astype(str)), "segment"
    raise ValueError(grain)


def kpis(lines: pd.DataFrame, products: pd.DataFrame, grain: str) -> pd.DataFrame:
    f, key = _segment_frame(lines, products, grain)
    g = f.groupby(key, dropna=False)
    out = pd.DataFrame({
        "net_revenue": g["net"].sum(),
        "gross_profit": g["net"].sum() - g["cost"].sum(),
        "discount_amount": g["discount"].sum(),
        "orders": g["order_id"].nunique().astype(float),
        "returns_amount": g["returns"].sum(),
    })
    with np.errstate(divide="ignore", invalid="ignore"):
        out["gp_margin"] = out["gross_profit"] / out["net_revenue"]
        out["aov"] = out["net_revenue"] / out["orders"]
        out["return_rate"] = out["returns_amount"] / out["net_revenue"]
    return out[list(KPIS)].sort_index()


def all_kpis(lines: pd.DataFrame, products: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {g: kpis(lines, products, g) for g in GRAINS}


# --- comparison ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Tolerance:
    money_abs: float = 0.005
    rel: float = 0.001

    def passes(self, kpi: str, expected: float, actual: float) -> bool:
        if np.isnan(expected) and np.isnan(actual):
            return True
        if np.isnan(expected) or np.isnan(actual):
            return False
        diff = abs(actual - expected)
        if diff == 0:
            return True
        if kpi in COUNT_KPIS:
            return diff == 0
        if kpi in MONEY_KPIS and diff <= self.money_abs:
            return True
        return expected != 0 and diff / abs(expected) <= self.rel


def compare(legacy: dict[str, pd.DataFrame], target: dict[str, pd.DataFrame],
            tol: Tolerance | None = None) -> pd.DataFrame:
    """Long-format comparison of every grain x segment x KPI (FULL OUTER on segments)."""
    tol = tol or Tolerance()
    rows = []
    for grain in GRAINS:
        lf, tf = legacy[grain], target[grain]
        for seg in lf.index.union(tf.index):
            for k in KPIS:
                e = float(lf.at[seg, k]) if seg in lf.index else np.nan
                a = float(tf.at[seg, k]) if seg in tf.index else np.nan
                diff = a - e
                rows.append({
                    "grain": grain, "segment": seg, "kpi": k, "expected": e, "actual": a, "diff": diff,
                    "diff_pct": diff / abs(e) if e not in (0.0,) and not np.isnan(e) else np.nan,
                    "passes": tol.passes(k, e, a),
                })
    return pd.DataFrame(rows)
