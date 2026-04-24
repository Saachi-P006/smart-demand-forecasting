"""
features/feature_engineering.py
================================
Add time-based, rolling, and encoded features to the merged dataframe.

Key fix: display_flag arrives as bool/object ("True"/"False" or True/False).
We cast ALL bool and object columns to numeric before handing off to XGBoost.
"""

import pandas as pd
import numpy as np


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["day_of_week"]  = df["date"].dt.dayofweek
        df["is_weekend"]   = df["day_of_week"].isin([5, 6]).astype(int)
        df["month"]        = df["date"].dt.month
        df["quarter"]      = df["date"].dt.quarter
        df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    else:
        for col in ["day_of_week", "is_weekend", "month", "quarter", "week_of_year"]:
            df[col] = 0

    # ── Demand volatility flag ────────────────────────────────────────────────
    df["high_volatility"] = (
        df.get("volatility_score", pd.Series(0, index=df.index)) > 0.5
    ).astype(int)

    # ── Weather encoded ───────────────────────────────────────────────────────
    if "weather_condition" in df.columns:
        df["is_rainy"] = df["weather_condition"].str.lower().isin(
            ["rain", "rainy", "heavy rain"]
        ).astype(int)
    else:
        df["is_rainy"] = 0

    # ── Price features ────────────────────────────────────────────────────────
    if "regular_price" in df.columns and "promo_price" in df.columns:
        reg = df["regular_price"].replace(0, np.nan)
        df["price_discount_depth"] = (
            (df["regular_price"] - df["promo_price"]) / reg
        ).fillna(0).clip(0, 1)
    elif "price_index" in df.columns:
        df["price_discount_depth"] = df["price_index"].fillna(0)
    else:
        df["price_discount_depth"] = 0.0

    # ── Online demand signal ──────────────────────────────────────────────────
    if "page_views" in df.columns and "add_to_cart_count" in df.columns:
        df["online_interest_score"] = (
            df["page_views"] * 0.01 + df["add_to_cart_count"] * 0.5
        )
    elif "web_signal_score" in df.columns:
        df["online_interest_score"] = df["web_signal_score"] * 100
    else:
        df["online_interest_score"] = 0.0

    # ── Lead-time urgency ─────────────────────────────────────────────────────
    if "avg_lead_time_days" in df.columns and "lead_time_days" in df.columns:
        df["effective_lead_time"] = df["avg_lead_time_days"].where(
            df["avg_lead_time_days"] > 0, df["lead_time_days"]
        )
    elif "avg_lead_time_days" in df.columns:
        df["effective_lead_time"] = df["avg_lead_time_days"]
    elif "lead_time_days" in df.columns:
        df["effective_lead_time"] = df["lead_time_days"]
    else:
        df["effective_lead_time"] = 7

    # ── Lag ratio ─────────────────────────────────────────────────────────────
    lag7  = df.get("lag_7",  pd.Series(1, index=df.index)).replace(0, np.nan)
    lag14 = df.get("lag_14", pd.Series(1, index=df.index)).replace(0, np.nan)
    df["lag_ratio"] = (lag7 / lag14).fillna(1)

    # ── Drop non-numeric columns that can't go into XGBoost ──────────────────
    drop_cols = [
        "date", "city", "state", "event_name", "weather_condition",
        "promo_type", "price_change_reason", "campaign_name",
        "store_name", "store_type", "event_type",
    ]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    # ── Cast ALL bool / object columns to numeric ─────────────────────────────
    # This handles: display_flag (bool True/False), any other stray object cols
    for col in df.columns:
        if df[col].dtype == bool:
            df[col] = df[col].astype(int)
        elif df[col].dtype == object:
            converted = pd.to_numeric(df[col], errors="coerce")
            df[col] = converted.fillna(0).astype(float)

    # ── Final fillna ──────────────────────────────────────────────────────────
    df.fillna(0, inplace=True)

    print(f"[feature_engineering] Final feature set shape: {df.shape}")
    obj_remaining = df.select_dtypes(include="object").columns.tolist()
    if obj_remaining:
        print(f"[feature_engineering] WARNING – object cols still present: {obj_remaining}")
    return df
