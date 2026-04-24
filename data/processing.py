"""
data/processing.py
==================
Merges all raw tables into one flat training dataframe.

Key changes from previous version
───────────────────────────────────
Several tables that previously had named signal columns now use a single
generic `value` column (date, store_id, product_id, value). This module
handles each one correctly:

  feature_store       → value  renamed to `feature_store_score`
  supplier_lead_times → value  renamed to `avg_lead_time_days`  (scaled)
  store_capacity      → value  renamed to `capacity_score`       (scaled)
  demand_volatility   → value  renamed to `volatility_score`
  web_traffic_signals → value  renamed to `web_signal_score`
  price_history       → value  renamed to `price_index`
  forecast_review     → value  renamed to `review_score`

Other schema changes:
  - ws_events_calendar renamed to events_calendar (handled in load_data.py)
    impact_level is now uppercase (LOW / MEDIUM / HIGH)
  - stores  – now has store_name, state, store_size_sqft (extra cols are fine)
  - promotions – discount_pct is a fraction (0-1); we multiply by 100
  - products, weather – unchanged
"""

import pandas as pd
import numpy as np


def _rename_value_col(df: pd.DataFrame, new_name: str,
                      key_cols: list) -> pd.DataFrame:
    """Rename 'value' column to new_name and dedup on key_cols."""
    if df.empty:
        return df
    if "value" in df.columns:
        df = df.rename(columns={"value": new_name})
    return df.drop_duplicates(subset=key_cols)


def preprocess_data(
    sales, feature_store, promotions, events,
    products, stores, weather, supplier,
    store_capacity, volatility, web_traffic, price_history
) -> pd.DataFrame:
    """
    Merge all relevant tables into one flat training dataframe.
    """

    # ── Parse dates ──────────────────────────────────────────────────────────
    for df in [sales, feature_store, promotions, events, weather,
               price_history, web_traffic]:
        for col in ["date", "log_date", "return_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

    # ── Base: sales_history ──────────────────────────────────────────────────
    df = sales.copy()

    # ── feature_store  (generic value → feature_store_score) ─────────────────
    fs = _rename_value_col(
        feature_store.copy(), "feature_store_score",
        ["date", "store_id", "product_id"]
    )
    if not fs.empty and "feature_store_score" in fs.columns:
        df = df.merge(
            fs[["date", "store_id", "product_id", "feature_store_score"]],
            on=["date", "store_id", "product_id"], how="left"
        )

    # ── promotions  (richer schema preserved; discount_pct is 0-1 fraction) ──
    promo_cols = ["date", "store_id", "product_id",
                  "discount_pct", "display_flag", "promo_type"]
    p_avail = [c for c in promo_cols if c in promotions.columns]
    if p_avail:
        df = df.merge(
            promotions[p_avail].drop_duplicates(
                ["date", "store_id", "product_id"]
            ),
            on=["date", "store_id", "product_id"], how="left"
        )
        # Convert fraction → percentage points
        if "discount_pct" in df.columns and df["discount_pct"].max() <= 1.5:
            df["discount_pct"] = df["discount_pct"] * 100

    if "promo_flag" not in df.columns:
        df["promo_flag"] = (df.get("discount_pct", pd.Series(0, index=df.index)) > 0).astype(int)

    # ── Add city from stores (needed for events & weather joins) ─────────────
    stores_city = stores[["store_id", "city"]].drop_duplicates("store_id")
    df = df.merge(stores_city, on="store_id", how="left")

    # ── events_calendar  (city-level; impact_level uppercase) ────────────────
    if not events.empty and "impact_level" in events.columns:
        events = events.copy()
        events["impact_score"] = (
            events["impact_level"].str.upper()
            .map({"LOW": 1, "MEDIUM": 2, "HIGH": 3})
            .fillna(0)
        )
        ev_cols  = [c for c in ["date", "city", "event_name", "impact_score"] if c in events.columns]
        ev_dedup = events[ev_cols].drop_duplicates(["date", "city"])
        df = df.merge(ev_dedup, on=["date", "city"], how="left")

    if "event_flag" not in df.columns:
        df["event_flag"] = (df.get("impact_score", pd.Series(0, index=df.index)) > 0).astype(int)

    # ── weather  (join via [date, city]) ─────────────────────────────────────
    w_cols  = [c for c in ["date", "city", "avg_temp", "rainfall_mm",
                            "humidity", "weather_condition"] if c in weather.columns]
    if w_cols:
        df = df.merge(
            weather[w_cols].drop_duplicates(["date", "city"]),
            on=["date", "city"], how="left"
        )

    # ── price_history  (generic value → price_index 0-1) ─────────────────────
    ph = _rename_value_col(
        price_history.copy(), "price_index",
        ["date", "store_id", "product_id"]
    )
    if not ph.empty and "price_index" in ph.columns:
        df = df.merge(
            ph[["date", "store_id", "product_id", "price_index"]],
            on=["date", "store_id", "product_id"], how="left"
        )

    # ── web_traffic_signals  (generic value → web_signal_score 0-1) ──────────
    wt = _rename_value_col(
        web_traffic.copy(), "web_signal_score",
        ["date", "store_id", "product_id"]
    )
    if not wt.empty and "web_signal_score" in wt.columns:
        df = df.merge(
            wt[["date", "store_id", "product_id", "web_signal_score"]],
            on=["date", "store_id", "product_id"], how="left"
        )

    # ── products ─────────────────────────────────────────────────────────────
    prod_cols = [c for c in ["product_id", "lead_time_days",
                              "shelf_life_days", "mrp"] if c in products.columns]
    if prod_cols:
        df = df.merge(
            products[prod_cols].drop_duplicates("product_id"),
            on="product_id", how="left"
        )

    # Derive price columns from mrp + price_index
    if "mrp" in df.columns:
        price_idx = df.get("price_index", pd.Series(0.5, index=df.index)).fillna(0.5)
        df["regular_price"] = df["mrp"] * (0.8 + price_idx * 0.4)
        disc_frac = df.get("discount_pct", pd.Series(0, index=df.index)).fillna(0) / 100
        df["promo_price"] = df["regular_price"] * (1 - disc_frac)
    else:
        df["regular_price"] = 0.0
        df["promo_price"]   = 0.0

    # ── store_capacity  (generic value → capacity_score, scale to days) ───────
    cap = _rename_value_col(
        store_capacity.copy(), "capacity_score",
        ["store_id", "product_id"]
    )
    if not cap.empty and "capacity_score" in cap.columns:
        cap_agg = (cap.groupby(["store_id", "product_id"])["capacity_score"]
                      .mean().reset_index())
        cap_agg["safety_stock_days"] = (cap_agg["capacity_score"] * 29 + 1).round()
        cap_agg["reorder_point"]     = cap_agg["safety_stock_days"] * 2
        df = df.merge(
            cap_agg[["store_id", "product_id", "safety_stock_days", "reorder_point"]],
            on=["store_id", "product_id"], how="left"
        )
    else:
        df["safety_stock_days"] = 7.0
        df["reorder_point"]     = 14.0

    # ── supplier_lead_times  (generic value → avg_lead_time_days) ────────────
    sup = _rename_value_col(
        supplier.copy(), "lead_time_score",
        ["store_id", "product_id"]
    )
    if not sup.empty and "lead_time_score" in sup.columns:
        sup_agg = (sup.groupby(["store_id", "product_id"])["lead_time_score"]
                      .mean().reset_index())
        sup_agg["avg_lead_time_days"] = (sup_agg["lead_time_score"] * 29 + 1).round()
        sup_agg["tariff_risk_flag"]   = (sup_agg["lead_time_score"] > 0.7).astype(int)
        df = df.merge(
            sup_agg[["store_id", "product_id",
                      "avg_lead_time_days", "tariff_risk_flag"]],
            on=["store_id", "product_id"], how="left"
        )
    else:
        df["avg_lead_time_days"] = df.get("lead_time_days", pd.Series(7, index=df.index))
        df["tariff_risk_flag"]   = 0

    # ── demand_volatility  (generic value → volatility_score) ────────────────
    vol = _rename_value_col(
        volatility.copy(), "volatility_score",
        ["store_id", "product_id"]
    )
    if not vol.empty and "volatility_score" in vol.columns:
        vol_agg = (vol.groupby(["store_id", "product_id"])["volatility_score"]
                      .mean().reset_index())
        df = df.merge(vol_agg, on=["store_id", "product_id"], how="left")

    # ── Synthetic lag / rolling features from feature_store_score ─────────────
    if "feature_store_score" in df.columns:
        score = df["feature_store_score"].fillna(0)
        base  = df.get("units_sold", pd.Series(1, index=df.index)).fillna(1)
        df["lag_7"]         = (base * (0.8 + score * 0.4)).round(2)
        df["lag_14"]        = (base * (0.7 + score * 0.3)).round(2)
        df["rolling_avg_7"] = (base * (0.85 + score * 0.3)).round(2)
    else:
        base = df.get("units_sold", pd.Series(0, index=df.index)).fillna(0)
        df["lag_7"]         = base
        df["lag_14"]        = base
        df["rolling_avg_7"] = base

    # ── Synthetic web traffic columns from web_signal_score ───────────────────
    if "web_signal_score" in df.columns:
        score = df["web_signal_score"].fillna(0)
        df["page_views"]        = (score * 5000).round().astype(int)
        df["add_to_cart_count"] = (score * 500).round().astype(int)
        df["search_rank"]       = ((1 - score) * 100 + 1).round().astype(int)
    else:
        df["page_views"]        = 0
        df["add_to_cart_count"] = 0
        df["search_rank"]       = 50

    # ── Fill missing values ───────────────────────────────────────────────────
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].fillna("unknown")

    print(f"[processing] Merged dataframe shape: {df.shape}")
    return df
