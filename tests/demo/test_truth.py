import numpy as np
import pandas as pd
import pytest

from demo.generator.truth import TruthParams, build_truth

SMALL = TruthParams(n_customers=400, n_orders=3_000, n_products=60)


@pytest.fixture(scope="module")
def truth():
    return build_truth(7, SMALL)


def test_same_seed_is_identical():
    a, b = build_truth(7, SMALL), build_truth(7, SMALL)
    for name in ("products", "customers", "orders", "lines", "returns", "order_promotions"):
        pd.testing.assert_frame_equal(getattr(a, name), getattr(b, name))


def test_different_seed_differs():
    a, b = build_truth(7, SMALL), build_truth(8, SMALL)
    assert not a.lines["net_paise"].equals(b.lines["net_paise"])


def test_amounts_are_exact_and_consistent(truth):
    li = truth.lines
    assert (li["gross_paise"] == li["quantity"] * li["unit_price"] * 100).all()
    assert (li["discount_paise"] == li["quantity"] * li["unit_price"] * li["discount_pct"]).all()
    assert (li["net_paise"] == li["gross_paise"] - li["discount_paise"]).all()
    assert set(np.unique(li["discount_pct"])) <= {0, 5, 10, 15, 20, 25, 30}
    assert (li["unit_price"] % 10 == 9).all()


def test_order_status_rules(truth):
    o = truth.orders
    assert set(o["status"]) <= {"C", "S", "X", "P"}
    assert o.loc[o["status"] == "P", "ship_date"].isna().all()
    assert o.loc[o["status"].isin(["C", "S"]), "ship_date"].notna().all()
    assert (o.loc[o["cancelled_after_ship"], "status"] == "X").all()
    assert o.loc[o["cancelled_after_ship"], "ship_date"].notna().all()
    shipped = o[o["ship_date"].notna()]
    assert (pd.to_datetime(shipped["ship_date"]) > pd.to_datetime(shipped["order_date"])).all()


def test_returns_only_on_completed_orders_and_bounded(truth):
    r = truth.returns.merge(truth.orders[["order_id", "status"]], on="order_id")
    assert (r["status"] == "C").all()
    m = truth.returns.merge(truth.lines, on=["order_id", "line_number"])
    assert (m["return_quantity"] <= m["quantity"]).all()
    assert (m["return_paise"] == m["return_quantity"] * m["unit_price"] * (100 - m["discount_pct"])).all()


def test_rates_are_plausible(truth):
    o = truth.orders
    assert 0.02 < (o["status"] == "X").mean() < 0.06
    assert 0.005 < truth.customers["region_code"].isna().mean() < 0.03
    assert 0.1 < (truth.lines["discount_pct"] > 0).mean() < 0.5
    assert len(truth.order_promotions.groupby("order_id").filter(lambda g: len(g) > 1)) > 0


def test_price_changes_apply_from_change_date(truth):
    changed = set(truth.products.loc[truth.products["price_changed"], "product_code"])
    li = truth.lines.merge(truth.orders[["order_id", "order_date"]], on="order_id")
    li = li[li["product_code"].isin(changed)]
    prices = truth.products.set_index("product_code")
    late = pd.to_datetime(li["order_date"]) >= pd.Timestamp(SMALL.price_change_date)
    expect = np.where(late, li["product_code"].map(prices["price_v2"]), li["product_code"].map(prices["price_v1"]))
    assert (li["unit_price"].to_numpy() == expect).all()
