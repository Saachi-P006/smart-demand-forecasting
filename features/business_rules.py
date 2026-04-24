import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS RULES FOR DEMAND ADJUSTMENT
# These run AFTER the ML model produces raw predictions.
# Each rule corresponds to a defined business requirement.
# ─────────────────────────────────────────────────────────────────────────────

# ── Rule constants (tune as needed) ──────────────────────────────
STOCKOUT_UPLIFT        = 1.20   # +20% when stockout_flag=1 (demand > recorded sales)
EVENT_LOW_UPLIFT       = 1.10   # impact_score 1
EVENT_MED_UPLIFT       = 1.20   # impact_score 2
EVENT_HIGH_UPLIFT      = 1.35   # impact_score 3
WEEKEND_UPLIFT         = 1.10   # +10% on weekends
RAIN_DAMPENER          = 0.90   # -10% on rainy days
SIGNAL_SPIKE_THRESHOLD = 0.70   # realtime signal_strength threshold
SIGNAL_SPIKE_UPLIFT    = 1.30   # +30% on strong realtime spike
SAFETY_STOCK_PCT       = 0.15   # 15% safety buffer (between 10–20% as per rule)
HIGH_VOLATILITY_EXTRA  = 0.05   # +5% extra safety for high-volatility products
TARIFF_RISK_BUFFER     = 0.10   # +10% inventory buffer if supplier tariff risk


def apply_demand_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all business rules to the raw predicted_units column.
    Returns df with a new 'adjusted_demand' column.
    """
    df = df.copy()

    # ── RULE 1: Demand ≠ Sales (stockout correction) ──────────────
    # If stockout_flag=1, actual demand was higher than recorded sales.
    # Uplift the ML prediction to compensate.
    df["adjusted_demand"] = df["predicted_units"].astype("float64")
    df.loc[df["stockout_flag"] == 1, "adjusted_demand"] *= STOCKOUT_UPLIFT

    # ── RULE 2: Promotion Impact ──────────────────────────────────
    # Higher discount → higher demand uplift.
    # discount_pct is 0–100; convert to multiplier.
    promo_mask = (df.get("promo_flag", pd.Series(0, index=df.index)) == 1)
    if "discount_pct" in df.columns:
        df.loc[promo_mask, "adjusted_demand"] *= (
            1 + df.loc[promo_mask, "discount_pct"] / 100
        )

    # ── RULE 3: Event / Festival Impact ───────────────────────────
    if "impact_score" in df.columns:
        df.loc[df["impact_score"] == 1, "adjusted_demand"] *= EVENT_LOW_UPLIFT
        df.loc[df["impact_score"] == 2, "adjusted_demand"] *= EVENT_MED_UPLIFT
        df.loc[df["impact_score"] == 3, "adjusted_demand"] *= EVENT_HIGH_UPLIFT

    # ── RULE 4: Weekend Effect ────────────────────────────────────
    if "is_weekend" in df.columns:
        df.loc[df["is_weekend"] == 1, "adjusted_demand"] *= WEEKEND_UPLIFT

    # ── RULE 5: Weather Impact ────────────────────────────────────
    # Rainy weather reduces store footfall → lower demand
    if "is_rainy" in df.columns:
        df.loc[df["is_rainy"] == 1, "adjusted_demand"] *= RAIN_DAMPENER

    # ── RULE 6: Real-Time Signal Adjustment (BONUS) ───────────────
    # If a strong demand spike signal was detected, boost demand
    if "signal_strength" in df.columns:
        df.loc[df["signal_strength"] > SIGNAL_SPIKE_THRESHOLD, "adjusted_demand"] *= SIGNAL_SPIKE_UPLIFT

    # ── RULE 7: Ensure non-negative ───────────────────────────────
    df["adjusted_demand"] = df["adjusted_demand"].clip(lower=0)

    return df


def calculate_inventory_recommendation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply inventory recommendation rules:
      - Safety Stock (10–20% of adjusted demand, more for volatile products)
      - Lead Time Buffer (cover demand during replenishment window)
      - Tariff Risk Buffer (extra if supplier has tariff risk)
    """
    df = df.copy()

    # ── RULE 8: Safety Stock ──────────────────────────────────────
    safety_pct = SAFETY_STOCK_PCT
    if "high_volatility" in df.columns:
        # high-volatility products get extra safety buffer
        df["safety_stock"] = df["adjusted_demand"] * (
            safety_pct + df["high_volatility"] * HIGH_VOLATILITY_EXTRA
        )
    else:
        df["safety_stock"] = df["adjusted_demand"] * safety_pct

    # ── RULE 9: Lead Time Demand ──────────────────────────────────
    # Stock needed to cover demand while waiting for replenishment
    lead_col = "effective_lead_time" if "effective_lead_time" in df.columns else "lead_time_days"
    df["lead_time_demand"] = df["adjusted_demand"] * df.get(lead_col, pd.Series(1, index=df.index))

    # ── Tariff Risk Buffer ─────────────────────────────────────────
    if "tariff_risk_flag" in df.columns:
        tariff_mask = df["tariff_risk_flag"] == 1
        df.loc[tariff_mask, "lead_time_demand"] *= (1 + TARIFF_RISK_BUFFER)

    # ── RULE (combined): Recommended Inventory ─────────────────────
    # Recommended Inventory = Predicted Demand + Safety Stock + Lead Time Demand
    df["recommended_inventory"] = (
        df["adjusted_demand"]
        + df["safety_stock"]
        + df["lead_time_demand"]
    ).clip(lower=0)

    return df
