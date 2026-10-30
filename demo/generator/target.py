"""Target architecture: the truth as the new standardised model stores it (clean, defect-free)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from demo.generator.truth import Truth

STATUS_LABELS = {"C": "COMPLETED", "S": "SHIPPED", "X": "CANCELLED", "P": "PENDING"}
OPEN_END = date(9999, 12, 31)


def date_key(d: pd.Series) -> pd.Series:
    ts = pd.to_datetime(d)
    return (ts.dt.year * 10000 + ts.dt.month * 100 + ts.dt.day).astype("Int64")


def build_dim_date(start: date = date(2023, 1, 1), end: date = date(2026, 12, 31)) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    return pd.DataFrame({
        "date_key": (days.year * 10000 + days.month * 100 + days.day).astype("int64"),
        "calendar_date": days.date,
        "year": days.year.astype("int64"),
        "quarter": days.quarter.astype("int64"),
        "month": days.month.astype("int64"),
        "month_name": days.strftime("%B"),
        "year_month": days.strftime("%Y-%m"),
    })


def build_target(truth: Truth) -> dict[str, pd.DataFrame]:
    regions = truth.regions.sort_values("region_code").reset_index(drop=True)
    dim_region = pd.DataFrame({
        "region_key": range(1, len(regions) + 1),
        "region_code": regions["region_code"],
        "region_name": regions["region_name"],
    })
    region_key = dict(zip(dim_region["region_code"], dim_region["region_key"], strict=True))

    cu = truth.customers.sort_values("customer_id").reset_index(drop=True)
    dim_customer = pd.DataFrame({
        "customer_key": range(1, len(cu) + 1),
        "customer_id": cu["customer_id"],
        "customer_name": cu["customer_name"],
        "segment": cu["segment"],
        "state_code": cu["state_code"],
        "region_key": cu["region_code"].map(region_key).astype("Int64"),
        "signup_date": cu["signup_date"],
    })
    customer_key = dict(zip(dim_customer["customer_id"], dim_customer["customer_key"], strict=True))

    pr = truth.products
    cat_name = dict(zip(truth.categories["category_code"], truth.categories["category_name"], strict=True))
    dim_product = pd.DataFrame({
        "product_key": range(1, len(pr) + 1),
        "product_code": pr["product_code"],
        "product_name": pr["product_name"],
        "category_code": pr["category_code"],
        "category_name": pr["category_code"].map(cat_name),
        "list_price": pr["price_v2"] * 100,
        "standard_cost": pr["cost_v2_paise"],
        "valid_from": truth.params.start,
        "valid_to": OPEN_END,
        "is_current": True,
    })

    o = truth.orders
    fct_order = pd.DataFrame({
        "order_id": o["order_id"],
        "customer_key": o["customer_id"].map(customer_key).astype("int64"),
        "order_date": o["order_date"],
        "ship_date": o["ship_date"],
        "order_status": o["status"].map(STATUS_LABELS),
        "order_date_key": date_key(o["order_date"]),
    })

    first_promo = truth.order_promotions.drop_duplicates("order_id").set_index("order_id")["promotion_code"]
    li = truth.lines
    order_info = o.set_index("order_id")
    fct_order_line = pd.DataFrame({
        "order_line_id": li["order_id"] + "-" + li["line_number"].astype(str),
        "order_id": li["order_id"],
        "line_number": li["line_number"],
        "customer_key": li["order_id"].map(order_info["customer_id"]).map(customer_key).astype("int64"),
        "product_code": li["product_code"],
        "order_date_key": date_key(li["order_id"].map(order_info["order_date"])),
        "promotion_id": li["order_id"].map(first_promo),
        "quantity": li["quantity"],
        "unit_price": li["unit_price"] * 100,
        "discount_pct": li["discount_pct"],
        "gross_amount": li["gross_paise"],
        "discount_amount": li["discount_paise"],
        "net_amount": li["net_paise"],
        "unit_cost": li["unit_cost_paise"],
        "cost_amount": li["cost_paise"],
    })

    r = truth.returns
    fct_return = pd.DataFrame({
        "return_id": r["return_id"],
        "order_line_id": r["order_id"] + "-" + r["line_number"].astype(str),
        "return_date": r["return_date"],
        "return_quantity": r["return_quantity"],
        "return_amount": r["return_paise"],
    })

    return {
        "dim_region": dim_region,
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_date": build_dim_date(),
        "dim_promotion": truth.promotions.rename(
            columns={"promotion_code": "promotion_id", "promotion_name": "promotion_name"}),
        "fct_order": fct_order,
        "fct_order_line": fct_order_line,
        "fct_return": fct_return,
        "bridge_order_promotion": truth.order_promotions.rename(columns={"promotion_code": "promotion_id"}),
    }
