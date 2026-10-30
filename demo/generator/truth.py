"""Canonical business truth for the synthetic e-commerce company.

Everything downstream (legacy model, target model, defects, oracle expectations) derives from
this single model, so a clean migration is equivalent by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

REGIONS = [
    ("NTH", "North"), ("STH", "South"), ("EST", "East"),
    ("WST", "West"), ("CTR", "Central"), ("NES", "Northeast"),
]

# (state_code, state_name, region_code, weight). Weights shape regional revenue shares.
STATES = [
    ("DL", "Delhi", "NTH", 6.0), ("HR", "Haryana", "NTH", 4.0), ("PB", "Punjab", "NTH", 3.0),
    ("UP", "Uttar Pradesh", "NTH", 2.0), ("RJ", "Rajasthan", "NTH", 3.0), ("JK", "Jammu and Kashmir", "NTH", 1.0),
    ("KA", "Karnataka", "STH", 7.0), ("TN", "Tamil Nadu", "STH", 6.0), ("KL", "Kerala", "STH", 3.0),
    ("TG", "Telangana", "STH", 4.0), ("AP", "Andhra Pradesh", "STH", 3.0),
    ("WB", "West Bengal", "EST", 5.0), ("OD", "Odisha", "EST", 2.0), ("BR", "Bihar", "EST", 2.0),
    ("JH", "Jharkhand", "EST", 1.5),
    ("MH", "Maharashtra", "WST", 10.0), ("GJ", "Gujarat", "WST", 5.0), ("GA", "Goa", "WST", 1.0),
    ("MP", "Madhya Pradesh", "CTR", 5.0), ("CG", "Chhattisgarh", "CTR", 2.0),
    ("AS", "Assam", "NES", 1.5), ("ML", "Meghalaya", "NES", 0.5), ("TR", "Tripura", "NES", 0.5),
]

# (category_code, category_name, median_price_inr, product nouns)
CATEGORIES = [
    ("ELEC", "Electronics", 2500, ["Headphones", "Speaker", "Smartwatch", "Camera", "Earbuds"]),
    ("MOBL", "Mobiles", 12000, ["Smartphone", "Feature Phone", "Tablet"]),
    ("COMP", "Computers", 30000, ["Laptop", "Monitor", "Keyboard", "Mouse", "Router"]),
    ("HOME", "Home & Kitchen", 1500, ["Mixer", "Kettle", "Cookware Set", "Water Bottle", "Lamp"]),
    ("FURN", "Furniture", 9000, ["Office Chair", "Study Table", "Bookshelf", "Sofa"]),
    ("FASH", "Fashion", 1200, ["Kurta", "T-Shirt", "Jeans", "Saree", "Jacket"]),
    ("FOOT", "Footwear", 2000, ["Running Shoes", "Sandals", "Sneakers", "Formal Shoes"]),
    ("BEAU", "Beauty", 600, ["Face Wash", "Moisturiser", "Shampoo", "Perfume"]),
    ("SPRT", "Sports", 1800, ["Cricket Bat", "Yoga Mat", "Football", "Dumbbells"]),
    ("BOOK", "Books", 450, ["Novel", "Cookbook", "Textbook", "Comic"]),
    ("TOYS", "Toys", 900, ["Puzzle", "Board Game", "Building Blocks", "Doll"]),
    ("GROC", "Grocery", 350, ["Tea", "Coffee", "Basmati Rice", "Dry Fruits", "Spices"]),
]

PROMOTIONS = [
    ("DIWALI", "Diwali Dhamaka"), ("NEWYR", "New Year Sale"), ("SUMMER", "Summer Splash"),
    ("MONSOON", "Monsoon Deals"), ("FIRST10", "First Order 10"), ("LOYAL", "Loyalty Reward"),
    ("BANKHDF", "Bank Card Offer"), ("FREESHP", "Free Shipping"),
]

SEGMENTS = ["Consumer", "Corporate", "Small Business"]
FIRST_NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Ishita", "Kabir", "Meera", "Rohan",
               "Saanvi", "Aditya", "Kavya", "Nikhil", "Priya", "Rahul", "Sneha", "Vikram", "Zoya"]
LAST_NAMES = ["Sharma", "Iyer", "Patel", "Reddy", "Singh", "Das", "Nair", "Gupta", "Khan", "Mehta",
              "Bose", "Kulkarni", "Joshi", "Menon", "Chopra", "Rao"]

DISCOUNT_STEPS = np.array([5, 10, 15, 20, 25, 30])          # percent; multiples of 5 keep paise exact
DISCOUNT_P = np.array([0.25, 0.25, 0.20, 0.15, 0.10, 0.05])


@dataclass(frozen=True)
class TruthParams:
    n_customers: int = 5_000
    n_orders: int = 40_000
    n_products: int = 300
    start: date = date(2024, 1, 1)
    end: date = date(2025, 12, 31)
    cancel_rate: float = 0.04
    cancel_after_ship_share: float = 0.6
    null_region_rate: float = 0.015
    return_rate: float = 0.06
    discount_share: float = 0.35
    price_change_share: float = 0.10
    price_change_date: date = date(2025, 7, 1)
    promo_count_p: tuple[float, float, float] = (0.6, 0.3, 0.1)  # P(0, 1, 2 promotions)


@dataclass
class Truth:
    seed: int
    params: TruthParams
    regions: pd.DataFrame
    states: pd.DataFrame
    categories: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    promotions: pd.DataFrame
    orders: pd.DataFrame
    order_promotions: pd.DataFrame
    lines: pd.DataFrame
    returns: pd.DataFrame
    notes: dict = field(default_factory=dict)


def _round_price(x: np.ndarray) -> np.ndarray:
    """Integer rupee prices ending in 9 (e.g. 1499); integers keep discounted amounts exact in paise."""
    return np.maximum(np.round(x / 10.0) * 10 - 1, 49).astype(np.int64)


def _order_day_weights(days: pd.DatetimeIndex) -> np.ndarray:
    t = np.arange(len(days)) / max(len(days) - 1, 1)
    growth = 1.0 + 0.35 * t
    festive = np.where(days.month.isin([10, 11]), 1.45, 1.0)
    weekend = np.where(days.day_of_week >= 5, 1.1, 1.0)
    w = growth * festive * weekend
    return w / w.sum()


def build_truth(seed: int, params: TruthParams | None = None) -> Truth:
    p = params or TruthParams()
    rng = np.random.default_rng(seed)

    regions = pd.DataFrame(REGIONS, columns=["region_code", "region_name"])
    states = pd.DataFrame(STATES, columns=["state_code", "state_name", "region_code", "weight"])
    categories = pd.DataFrame([(c, n) for c, n, _, _ in CATEGORIES], columns=["category_code", "category_name"])

    # --- products -------------------------------------------------------------------------------
    cat_idx = rng.integers(0, len(CATEGORIES), size=p.n_products)
    medians = np.array([CATEGORIES[i][2] for i in cat_idx], dtype=float)
    price_v1 = _round_price(medians * rng.lognormal(0.0, 0.45, size=p.n_products))
    cost_v1 = np.round(price_v1 * 100 * rng.uniform(0.45, 0.75, size=p.n_products)).astype(np.int64)
    changed = rng.random(p.n_products) < p.price_change_share
    price_v2 = np.where(changed, _round_price(price_v1 * rng.uniform(1.05, 1.15, p.n_products)), price_v1)
    cost_v2 = np.where(changed, np.round(cost_v1 * rng.uniform(1.03, 1.12, p.n_products)), cost_v1)
    nouns = [CATEGORIES[i][3][rng.integers(0, len(CATEGORIES[i][3]))] for i in cat_idx]
    products = pd.DataFrame({
        "product_code": [f"P{i + 1:04d}" for i in range(p.n_products)],
        "product_name": [f"{n} {chr(65 + rng.integers(0, 26))}{rng.integers(100, 999)}" for n in nouns],
        "category_code": [CATEGORIES[i][0] for i in cat_idx],
        "price_v1": price_v1,
        "cost_v1_paise": cost_v1,
        "price_v2": price_v2.astype(np.int64),
        "cost_v2_paise": cost_v2.astype(np.int64),
        "price_changed": changed,
    })
    popularity = rng.zipf(1.6, size=p.n_products).astype(float)
    popularity = np.minimum(popularity, 50) / np.minimum(popularity, 50).sum()

    # --- customers ------------------------------------------------------------------------------
    st_w = states["weight"].to_numpy() / states["weight"].sum()
    st_idx = rng.choice(len(states), size=p.n_customers, p=st_w)
    state_code = states["state_code"].to_numpy()[st_idx].astype(object)
    region_code = states["region_code"].to_numpy()[st_idx].astype(object)
    unknown = rng.random(p.n_customers) < p.null_region_rate
    state_code[unknown] = None
    region_code[unknown] = None
    signup_offsets = rng.integers(0, 3 * 365, size=p.n_customers)
    customers = pd.DataFrame({
        "customer_id": [f"C{i + 1:05d}" for i in range(p.n_customers)],
        "customer_name": [f"{FIRST_NAMES[a]} {LAST_NAMES[b]}" for a, b in zip(
            rng.integers(0, len(FIRST_NAMES), p.n_customers), rng.integers(0, len(LAST_NAMES), p.n_customers),
            strict=True)],
        "segment": rng.choice(SEGMENTS, size=p.n_customers, p=[0.7, 0.2, 0.1]),
        "state_code": state_code,
        "region_code": region_code,
        "signup_date": [date(2021, 1, 1) + timedelta(days=int(d)) for d in signup_offsets],
    })
    cust_w = rng.lognormal(0.0, 1.0, size=p.n_customers)
    cust_w /= cust_w.sum()

    # --- orders ---------------------------------------------------------------------------------
    days = pd.date_range(p.start, p.end, freq="D")
    day_idx = np.sort(rng.choice(len(days), size=p.n_orders, p=_order_day_weights(days)))
    order_date = days[day_idx]
    cust_idx = rng.choice(p.n_customers, size=p.n_orders, p=cust_w)
    ship_lag = np.minimum(rng.geometric(0.35, size=p.n_orders), 10)
    ship_date = order_date + pd.to_timedelta(ship_lag, unit="D")

    cancelled = rng.random(p.n_orders) < p.cancel_rate
    after_ship = rng.random(p.n_orders) < p.cancel_after_ship_share
    end_ts = pd.Timestamp(p.end)
    pending = (~cancelled) & (order_date > end_ts - pd.Timedelta(days=3)) & (rng.random(p.n_orders) < 0.5)
    in_transit = (~cancelled) & (~pending) & (ship_date > end_ts - pd.Timedelta(days=5))
    status = np.full(p.n_orders, "C", dtype=object)
    status[in_transit] = "S"
    status[pending] = "P"
    status[cancelled] = "X"
    no_ship = pending | (cancelled & ~after_ship)
    ship_series = pd.Series(ship_date).where(~no_ship)

    orders = pd.DataFrame({
        "order_id": [f"O{i + 1:06d}" for i in range(p.n_orders)],
        "customer_id": customers["customer_id"].to_numpy()[cust_idx],
        "order_date": order_date.date,
        "ship_date": [d.date() if pd.notna(d) else None for d in ship_series],
        "status": status,
        "cancelled_after_ship": cancelled & after_ship,
    })

    # --- promotions per order ------------------------------------------------------------------
    n_promos = rng.choice(3, size=p.n_orders, p=list(p.promo_count_p))
    promo_rows = []
    for oid, k in zip(orders["order_id"], n_promos, strict=True):
        if k:
            for j in rng.choice(len(PROMOTIONS), size=k, replace=False):
                promo_rows.append((oid, PROMOTIONS[j][0]))
    order_promotions = pd.DataFrame(promo_rows, columns=["order_id", "promotion_code"])
    promotions = pd.DataFrame(PROMOTIONS, columns=["promotion_code", "promotion_name"])

    # --- order lines ---------------------------------------------------------------------------
    n_lines = 1 + np.minimum(rng.poisson(1.5, size=p.n_orders), 4)
    line_order = np.repeat(np.arange(p.n_orders), n_lines)
    line_number = np.concatenate([np.arange(1, k + 1) for k in n_lines])
    n = len(line_order)
    prod_idx = rng.choice(p.n_products, size=n, p=popularity)
    qty = np.minimum(rng.geometric(0.55, size=n), 5)
    after_change = np.asarray(order_date[line_order] >= pd.Timestamp(p.price_change_date))
    use_v2 = products["price_changed"].to_numpy()[prod_idx] & after_change
    unit_price = np.where(use_v2, price_v2[prod_idx], price_v1[prod_idx]).astype(np.int64)
    unit_cost = np.where(use_v2, cost_v2[prod_idx], cost_v1[prod_idx]).astype(np.int64)
    discounted = rng.random(n) < p.discount_share
    disc = np.where(discounted, rng.choice(DISCOUNT_STEPS, size=n, p=DISCOUNT_P), 0).astype(np.int64)

    gross = qty * unit_price * 100
    discount_amt = qty * unit_price * disc          # paise: price*100*disc/100
    lines = pd.DataFrame({
        "order_id": orders["order_id"].to_numpy()[line_order],
        "line_number": line_number,
        "product_code": products["product_code"].to_numpy()[prod_idx],
        "quantity": qty.astype(np.int64),
        "unit_price": unit_price,                    # whole INR
        "discount_pct": disc,                        # whole percent, 0 = none
        "unit_cost_paise": unit_cost,
        "gross_paise": gross,
        "discount_paise": discount_amt,
        "net_paise": gross - discount_amt,
        "cost_paise": qty * unit_cost,
    })

    # --- returns (only on completed orders) ----------------------------------------------------
    line_status = status[line_order]
    eligible = (line_status == "C") & (rng.random(n) < p.return_rate)
    r_idx = np.flatnonzero(eligible)
    r_qty = np.array([rng.integers(1, q + 1) for q in qty[r_idx]], dtype=np.int64)
    r_ship = pd.to_datetime(pd.Series(orders["ship_date"].to_numpy()[line_order[r_idx]]))
    r_date = (r_ship + pd.to_timedelta(rng.integers(3, 31, size=len(r_idx)), unit="D")).dt.date
    returns = pd.DataFrame({
        "return_id": [f"R{i + 1:06d}" for i in range(len(r_idx))],
        "order_id": lines["order_id"].to_numpy()[r_idx],
        "line_number": line_number[r_idx],
        "return_date": r_date.to_numpy(),
        "return_quantity": r_qty,
        "return_paise": r_qty * unit_price[r_idx] * (100 - disc[r_idx]),
    })

    return Truth(
        seed=seed, params=p, regions=regions, states=states, categories=categories,
        products=products, customers=customers, promotions=promotions, orders=orders,
        order_promotions=order_promotions, lines=lines, returns=returns,
    )


def current_product_attributes(truth: Truth) -> pd.DataFrame:
    """Products with their current (latest) price and cost, as master data shows them."""
    pr = truth.products
    return pd.DataFrame({
        "product_code": pr["product_code"],
        "product_name": pr["product_name"],
        "category_code": pr["category_code"],
        "list_price": pr["price_v2"],
        "cost_paise": pr["cost_v2_paise"],
    })
