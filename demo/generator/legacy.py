"""Legacy architecture: the truth as the old reporting source stores it."""

from __future__ import annotations

import pandas as pd

from demo.generator.truth import Truth, current_product_attributes


def build_legacy(truth: Truth) -> dict[str, pd.DataFrame]:
    o, li, cu = truth.orders, truth.lines, truth.customers
    order_totals = li.groupby("order_id", sort=False)["net_paise"].sum()

    orders_hdr = pd.DataFrame({
        "OrdID": o["order_id"],
        "CustNo": o["customer_id"],
        "OrdDt": o["order_date"],
        "ShipDt": o["ship_date"],
        "OrdStat": o["status"],
        "OrdTotAmt": o["order_id"].map(order_totals).fillna(0).astype("int64"),
    })
    ord_lines = pd.DataFrame({
        "OrdID": li["order_id"],
        "line_no": li["line_number"],
        "ProdCode": li["product_code"],
        "QTY": li["quantity"],
        "UnitPx": li["unit_price"] * 100,
        # Legacy stores "no discount" as an empty value rather than 0.
        "DiscPct": li["discount_pct"].where(li["discount_pct"] > 0).astype("Int64"),
        "UnitCost": li["unit_cost_paise"],
        "LineAmt": li["net_paise"],
    })
    cur = current_product_attributes(truth)
    prod_mstr = pd.DataFrame({
        "ProdCode": cur["product_code"],
        "ProdNm": cur["product_name"],
        "CatCd": cur["category_code"],
        "ListPx": cur["list_price"] * 100,
        "StdCost": cur["cost_paise"],
        "ActiveFlg": "Y",
    })
    prod_cat = truth.categories.rename(columns={"category_code": "CatCd", "category_name": "CatNm"})
    custmr = pd.DataFrame({
        "CustNo": cu["customer_id"],
        "CustNm": cu["customer_name"],
        "Seg": cu["segment"],
        "StCd": cu["state_code"],
        "Rgn_Cd": cu["region_code"],
        "SignupDt": cu["signup_date"],
    })
    rgn_lkp = truth.regions.rename(columns={"region_code": "Rgn_Cd", "region_name": "Rgn_Nm"})
    r = truth.returns
    rtn_log = pd.DataFrame({
        "RtnID": r["return_id"],
        "OrdID": r["order_id"],
        "line_no": r["line_number"],
        "RtnDt": r["return_date"],
        "RtnQty": r["return_quantity"],
        "RtnAmt": r["return_paise"],
    })
    promo_xref = truth.order_promotions.rename(columns={"order_id": "OrdID", "promotion_code": "PromoCd"})
    return {
        "ORDERS_HDR": orders_hdr, "ord_lines": ord_lines, "PROD_MSTR": prod_mstr, "prod_cat": prod_cat,
        "CUSTMR": custmr, "RGN_LKP": rgn_lkp, "RTN_LOG": rtn_log, "PROMO_XREF": promo_xref,
    }
