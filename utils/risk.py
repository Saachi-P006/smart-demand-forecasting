"""
Risk Detection Module

Detects:
  - Stockout Risk   → current inventory < adjusted demand
  - Overstock Risk  → current inventory >> adjusted demand
  - Stockout Probability (High / Low)
  - High Volatility flag (already computed, used for alert severity)
"""

import pandas as pd

OVERSTOCK_MULTIPLIER = 2.0   # inventory > demand * 2 = overstock


def calculate_risks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add risk columns to the predictions dataframe.
    """
    df = df.copy()

    demand_col    = "adjusted_demand"
    inventory_col = "inventory_on_hand"

    if demand_col not in df.columns:
        print("[risk] 'adjusted_demand' not found. Skipping risk calculation.")
        return df

    # ── RULE: Stockout Risk ───────────────────────────────────────
    if inventory_col in df.columns:
        df["stockout_risk"] = df[inventory_col] < df[demand_col]
        df["overstock_risk"] = df[inventory_col] > (df[demand_col] * OVERSTOCK_MULTIPLIER)

        # ── RULE: Stockout Probability ────────────────────────────
        df["stockout_probability"] = df["stockout_risk"].map(
            {True: "High", False: "Low"}
        )

        # ── Severity classification (for alert dashboard) ─────────
        def classify_severity(row):
            if row["stockout_risk"]:
                return "🔴 Critical – Stockout"
            elif row["overstock_risk"]:
                return "🟡 Warning – Overstock"
            else:
                return "🟢 OK"

        df["risk_severity"] = df.apply(classify_severity, axis=1)
    else:
        print(f"[risk] '{inventory_col}' column not found – risk columns set to unknown.")
        df["stockout_risk"]      = False
        df["overstock_risk"]     = False
        df["stockout_probability"] = "Unknown"
        df["risk_severity"]      = "Unknown"

    n_stockout  = df["stockout_risk"].sum()
    n_overstock = df["overstock_risk"].sum()
    print(f"[risk] Stockout risks: {n_stockout} | Overstock risks: {n_overstock}")

    return df
