"""Planted migration defects and benign (must-not-fail) changes, applied to the clean target frames.

This module is benchmark material: the engine never imports it (enforced by an architecture test).
Each function mutates the frames dict in place and returns a record of what it changed, which
the build writes to answer_key/generated/ — never next to the data the engine reads.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from demo.generator.target import date_key
from demo.generator.truth import Truth

Frames = dict[str, pd.DataFrame]


# --- planted defects ----------------------------------------------------------------------------

def d1_cancelled_included(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """ETL maps cancellations that happened after shipping to COMPLETED, so they count as revenue."""
    orders = truth.orders
    if "order_ids" in params:
        chosen = list(params["order_ids"])
    else:
        candidates = orders.loc[orders["cancelled_after_ship"], "order_id"].to_numpy()
        k = int(round(len(candidates) * params.get("fraction", 1.0)))
        chosen = list(rng.choice(candidates, size=k, replace=False)) if k else []
    mask = t["fct_order"]["order_id"].isin(chosen)
    t["fct_order"].loc[mask, "order_status"] = "COMPLETED"
    lines = t["fct_order_line"]
    return {"orders_relabelled": int(mask.sum()),
            "net_paise_added": int(lines.loc[lines["order_id"].isin(chosen), "net_amount"].sum())}


def d2_date_basis(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Line-level date key is populated from the ship date instead of the order date."""
    ship = truth.orders.set_index("order_id")["ship_date"]
    lines = t["fct_order_line"]
    before = lines["order_date_key"].copy()
    lines["order_date_key"] = date_key(lines["order_id"].map(ship))
    return {"lines_changed": int((before != lines["order_date_key"]).fillna(True).sum())}


def d3_discount_formula(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Discount computed per unit instead of per line (quantity omitted)."""
    lines = t["fct_order_line"]
    new_discount = (lines["unit_price"] // 100) * lines["discount_pct"]
    changed = new_discount != lines["discount_amount"]
    delta = int((lines["discount_amount"] - new_discount).sum())
    lines["discount_amount"] = new_discount
    lines["net_amount"] = lines["gross_amount"] - new_discount
    return {"lines_changed": int(changed.sum()), "net_paise_added": delta}


def d4_promotion_fanout(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Lines joined to every promotion of their order: multi-promotion orders duplicate lines."""
    lines = t["fct_order_line"].drop(columns=["promotion_id"])
    bridge = t["bridge_order_promotion"]
    joined = lines.merge(bridge, on="order_id", how="left")
    extra = len(joined) - len(lines)
    dup_net = int(joined["net_amount"].sum() - lines["net_amount"].sum())
    t["fct_order_line"] = joined[t["fct_order_line"].columns].reset_index(drop=True)
    return {"extra_rows": int(extra), "net_paise_added": dup_net}


def d5_null_region_dropped(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Customers with unknown region are lost by an inner join to dim_region, with their facts."""
    cust = t["dim_customer"]
    lost = set(cust.loc[cust["region_key"].isna(), "customer_key"])
    t["dim_customer"] = cust[~cust["customer_key"].isin(lost)].reset_index(drop=True)
    orders = t["fct_order"]
    lost_orders = set(orders.loc[orders["customer_key"].isin(lost), "order_id"])
    t["fct_order"] = orders[~orders["order_id"].isin(lost_orders)].reset_index(drop=True)
    lines = t["fct_order_line"]
    lost_lines = set(lines.loc[lines["order_id"].isin(lost_orders), "order_line_id"])
    dropped_net = int(lines.loc[lines["order_id"].isin(lost_orders), "net_amount"].sum())
    t["fct_order_line"] = lines[~lines["order_id"].isin(lost_orders)].reset_index(drop=True)
    ret = t["fct_return"]
    t["fct_return"] = ret[~ret["order_line_id"].isin(lost_lines)].reset_index(drop=True)
    return {"customers_dropped": len(lost), "orders_dropped": len(lost_orders), "net_paise_removed": dropped_net}


def d6_product_version_grain(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """dim_product keeps historical versions although its documented grain is one row per product."""
    pr = truth.products
    changed = pr.loc[pr["price_changed"], "product_code"].to_numpy()
    k = int(round(len(changed) * params.get("fraction", 1.0)))
    chosen = set(rng.choice(changed, size=k, replace=False)) if k else set()
    dim = t["dim_product"]
    change = truth.params.price_change_date
    old = dim[dim["product_code"].isin(chosen)].copy()
    hist = pr.set_index("product_code").loc[old["product_code"]]
    old["list_price"] = (hist["price_v1"] * 100).to_numpy()
    old["standard_cost"] = hist["cost_v1_paise"].to_numpy()
    old["valid_to"] = change - timedelta(days=1)
    old["is_current"] = False
    old["product_key"] = np.arange(len(dim) + 1, len(dim) + 1 + len(old))
    dim.loc[dim["product_code"].isin(chosen), "valid_from"] = change
    t["dim_product"] = pd.concat([dim, old], ignore_index=True)
    return {"products_versioned": len(chosen)}


def d7_returns_truncated(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Returns stopped loading after a cutoff date (incremental load stalled)."""
    cutoff = date.fromisoformat(params["cutoff"])
    ret = t["fct_return"]
    keep = pd.to_datetime(ret["return_date"]) <= pd.Timestamp(cutoff)
    t["fct_return"] = ret[keep].reset_index(drop=True)
    return {"returns_dropped": int((~keep).sum()), "return_paise_dropped": int(ret.loc[~keep, "return_amount"].sum())}


def d8_region_remap(t: Frames, truth: Truth, params: dict, rng: np.random.Generator) -> dict:
    """Some states are assigned to a different sales region in the target customer dimension."""
    region_key = dict(zip(t["dim_region"]["region_code"], t["dim_region"]["region_key"], strict=True))
    cust = t["dim_customer"]
    moved = 0
    for state, to_region in params["moves"].items():
        mask = cust["state_code"] == state
        cust.loc[mask, "region_key"] = region_key[to_region]
        moved += int(mask.sum())
    return {"customers_moved": moved}


DEFECTS = {
    "D1": d1_cancelled_included, "D2": d2_date_basis, "D3": d3_discount_formula,
    "D4": d4_promotion_fanout, "D5": d5_null_region_dropped, "D6": d6_product_version_grain,
    "D7": d7_returns_truncated, "D8": d8_region_remap,
}
# Application order: dimension changes first, row removals, value changes, status, then fan-out.
DEFECT_ORDER = ["D8", "D5", "D2", "D3", "D7", "D6", "D1", "D4"]


# --- benign changes (a correct engine must not flag these) ---------------------------------------

B1_RENAMES = {"fct_order_line": {"net_amount": "line_net_amount"}, "dim_region": {"region_name": "region_label"}}
B5_STATUS = {"COMPLETED": "Complete", "SHIPPED": "In Transit", "CANCELLED": "Void", "PENDING": "Awaiting"}
FACT_TABLES = ("fct_order", "fct_order_line", "fct_return", "bridge_order_promotion")


def b1_renames(t: Frames, schema: dict, rng: np.random.Generator) -> dict:
    for table, renames in B1_RENAMES.items():
        t[table] = t[table].rename(columns=renames)
        cols = schema["tables"][table]["columns"]
        schema["tables"][table]["columns"] = {renames.get(c, c): s for c, s in cols.items()}
    return {"renamed": B1_RENAMES}


def b2_type_widening(t: Frames, schema: dict, rng: np.random.Generator) -> dict:
    schema["tables"]["fct_order_line"]["columns"]["quantity"]["type"] = "BIGINT"
    schema["tables"]["fct_return"]["columns"]["return_quantity"]["type"] = "BIGINT"
    return {"widened": ["fct_order_line.quantity", "fct_return.return_quantity"]}


def b3_row_reorder(t: Frames, schema: dict, rng: np.random.Generator) -> dict:
    for table in FACT_TABLES:
        t[table] = t[table].sample(frac=1.0, random_state=rng.integers(0, 2**31 - 1)).reset_index(drop=True)
    return {"shuffled": list(FACT_TABLES)}


def b4_float_rounding(t: Frames, schema: dict, rng: np.random.Generator) -> dict:
    money = ["gross_amount", "discount_amount", "net_amount", "cost_amount"]
    lines = t["fct_order_line"]
    for col in money:
        lines[col] = lines[col] / 100.0 + rng.uniform(-0.004, 0.004, size=len(lines))
        schema["tables"]["fct_order_line"]["columns"][col]["type"] = "DOUBLE"
    return {"noise_abs_max": 0.004, "columns": money}


def b5_status_labels(t: Frames, schema: dict, rng: np.random.Generator) -> dict:
    t["fct_order"]["order_status"] = t["fct_order"]["order_status"].map(B5_STATUS)
    return {"status_map": B5_STATUS}


BENIGN = {"B1": b1_renames, "B2": b2_type_widening, "B3": b3_row_reorder, "B4": b4_float_rounding,
          "B5": b5_status_labels}
