"""
Reason Flags – Explainability Layer

For every prediction, generate human-readable flags explaining WHY
the demand is predicted at that level. This is shown in the
Data Reviewer dashboard and Admin dashboard.
"""

import pandas as pd

# Thresholds
SPIKE_MULTIPLIER = 1.5   # predicted > rolling_avg * 1.5 → spike
DROP_MULTIPLIER  = 0.5   # predicted < rolling_avg * 0.5 → drop
HIGH_DISCOUNT    = 20    # discount_pct > 20% = notable promotion
HIGH_VOL_THRESH  = 0.5   # volatility_score above this = high volatility


def generate_flags(row: pd.Series) -> str:
    """
    Generate comma-separated reason flags for a single row.
    """
    flags = []

    # ── Trend detection ───────────────────────────────────────────
    baseline = row.get("rolling_avg_7", 0)
    predicted = row.get("predicted_units", 0)

    if baseline > 0:
        if predicted > baseline * SPIKE_MULTIPLIER:
            flags.append("Sudden Spike ↑")
        elif predicted < baseline * DROP_MULTIPLIER:
            flags.append("Sudden Drop ↓")

    # ── External factors ──────────────────────────────────────────
    if row.get("event_flag", 0) == 1 or row.get("impact_score", 0) > 0:
        flags.append("Festival/Event Impact")

    if row.get("promo_flag", 0) == 1:
        disc = row.get("discount_pct", 0)
        if disc >= HIGH_DISCOUNT:
            flags.append(f"High Discount ({disc:.0f}%)")
        else:
            flags.append("Promotion Active")

    if row.get("is_weekend", 0) == 1:
        flags.append("Weekend Effect")

    if row.get("is_rainy", 0) == 1:
        flags.append("Rain Dampener ☔")

    # ── Stockout history ──────────────────────────────────────────
    if row.get("stockout_flag", 0) == 1:
        flags.append("Stockout Corrected")

    # ── Volatility ────────────────────────────────────────────────
    if row.get("volatility_score", 0) > HIGH_VOL_THRESH:
        flags.append("High Volatility ⚡")

    # ── Online signals ────────────────────────────────────────────
    if row.get("add_to_cart_count", 0) > 300:
        flags.append("High Online Interest 🛒")

    # ── Tariff risk ───────────────────────────────────────────────
    if row.get("tariff_risk_flag", 0) == 1:
        flags.append("Supplier Tariff Risk ⚠️")

    return ", ".join(flags) if flags else "Normal"


def add_flags_column(df: pd.DataFrame) -> pd.DataFrame:
    """Apply generate_flags row-wise to the full dataframe."""
    df = df.copy()
    df["reason_flags"] = df.apply(generate_flags, axis=1)
    print(f"[flags] Reason flags generated for {len(df)} rows.")
    return df
