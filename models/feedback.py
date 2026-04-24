"""
models/feedback.py
==================
Feedback Loop – Human-in-the-loop Machine Learning

When a Data Reviewer edits a prediction that correction is stored in
forecast_review.csv.  In the new data format forecast_review is a
generic (date, store_id, product_id, value) table where `value` is a
normalised score (0-1).  We treat a score > 0.5 as a positive
adjustment signal and < 0.5 as a negative signal, scaling the actual
adjustment to ±20% of predicted demand.

If the CSV has the old rich schema (predicted_units, adjusted_units,
status) those columns are used directly as before.
"""

import pandas as pd
import numpy as np
import os

REVIEW_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "forecast_review.csv"
)


def load_corrections() -> pd.DataFrame:
    """
    Load human-reviewed corrections from forecast_review.csv.
    Handles both old rich schema and new generic value schema.
    """
    if not os.path.exists(REVIEW_PATH):
        print("[feedback] No forecast_review.csv found – skipping feedback.")
        return pd.DataFrame()

    review = pd.read_csv(REVIEW_PATH)

    # ── Old rich schema: has status, adjusted_units, predicted_units ──────────
    if "status" in review.columns and "adjusted_units" in review.columns:
        valid = review[review["status"].isin(["edited", "approved"])].copy()
        valid["adjustment"] = valid["adjusted_units"] - valid["predicted_units"]
        print(f"[feedback] Loaded {len(valid)} human corrections (rich schema).")
        return valid

    # ── New generic schema: only value column ─────────────────────────────────
    if "value" in review.columns:
        # Interpret score: 0.5 = neutral, >0.5 = increase demand, <0.5 = decrease
        review = review.copy()
        # Scale: max adjustment ±20 units (can be tuned)
        review["adjustment"] = (review["value"] - 0.5) * 40
        print(f"[feedback] Loaded {len(review)} review signals (generic schema).")
        return review

    print("[feedback] forecast_review.csv has unrecognised schema – skipping.")
    return pd.DataFrame()


def compute_bias_table(corrections: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-(product_id, store_id) mean adjustment from human reviews.
    """
    if corrections.empty or "adjustment" not in corrections.columns:
        return pd.DataFrame(columns=["product_id", "store_id", "mean_adjustment"])

    if "product_id" not in corrections.columns or "store_id" not in corrections.columns:
        return pd.DataFrame(columns=["product_id", "store_id", "mean_adjustment"])

    bias = (
        corrections
        .groupby(["product_id", "store_id"])["adjustment"]
        .mean()
        .reset_index()
        .rename(columns={"adjustment": "mean_adjustment"})
    )
    print(f"[feedback] Bias table computed for {len(bias)} product-store pairs.")
    return bias


def apply_feedback(df: pd.DataFrame,
                   target_col: str = "adjusted_demand") -> pd.DataFrame:
    """
    Apply human-correction bias to predictions.
    """
    corrections = load_corrections()
    if corrections.empty:
        return df

    bias = compute_bias_table(corrections)
    if bias.empty:
        return df

    df = df.merge(bias, on=["product_id", "store_id"], how="left")
    df["mean_adjustment"] = df["mean_adjustment"].fillna(0)
    df[target_col] = (df[target_col] + df["mean_adjustment"]).clip(lower=0)

    print(f"[feedback] Bias correction applied. "
          f"Mean adjustment: {df['mean_adjustment'].mean():.2f}")
    df.drop(columns=["mean_adjustment"], inplace=True)
    return df
