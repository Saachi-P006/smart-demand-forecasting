"""
models/train.py
===============
Train XGBoost regression model to predict units_sold.

Changes vs previous version
────────────────────────────
• FEATURE_COLS updated to reflect new derived columns:
    - replaced `rolling_avg_7` lag features kept but sourced differently
    - added `feature_store_score`, `web_signal_score`, `price_index`,
      `online_interest_score` from the new generic-value tables
    - removed `signal_strength` (not present in new data)
    - removed `humidity` reference remains as optional
• All FEATURE_COLS are guarded via get_available_features() so missing
  columns are silently skipped rather than crashing.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb

# ── Feature columns ───────────────────────────────────────────────────────────
FEATURE_COLS = [
    # Lag / rolling (synthesised from feature_store_score in processing.py)
    "lag_7",
    "lag_14",
    "rolling_avg_7",
    "lag_ratio",

    # Feature store signal
    "feature_store_score",

    # Promotion
    "promo_flag",
    "event_flag",
    "discount_pct",
    "display_flag",

    # Events
    "impact_score",

    # Time
    "is_weekend",
    "day_of_week",
    "month",
    "quarter",
    "week_of_year",

    # Weather
    "is_rainy",
    "avg_temp",
    "rainfall_mm",
    "humidity",

    # Inventory & supply
    "inventory_on_hand",
    "stockout_flag",
    "effective_lead_time",
    "safety_stock_days",
    "reorder_point",
    "tariff_risk_flag",
    "shelf_life_days",

    # Product economics
    "mrp",
    "regular_price",
    "promo_price",
    "price_discount_depth",
    "price_index",

    # Online signals (derived from web_signal_score)
    "web_signal_score",
    "page_views",
    "add_to_cart_count",
    "search_rank",
    "online_interest_score",

    # Volatility
    "volatility_score",
    "high_volatility",

    # IDs
    "store_id",
    "product_id",
]

TARGET_COL = "units_sold"

MODEL_PATH    = os.path.join(os.path.dirname(__file__), "model.pkl")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "feature_cols.pkl")
METRICS_PATH  = os.path.join(os.path.dirname(__file__), "metrics.json")


def get_available_features(df: pd.DataFrame) -> list:
    """Return only columns present in df."""
    available = [c for c in FEATURE_COLS if c in df.columns]
    print(f"[train] Using {len(available)}/{len(FEATURE_COLS)} feature columns")
    return available


def train_model(df: pd.DataFrame):
    """
    Train XGBoost regression model to predict units_sold.
    Saves model + feature list to disk.
    Returns (model, feature_cols, eval_metrics).

    CHANGES (time-based split + baseline comparison):
    ───────────────────────────────────────────────────
    1. TIME-BASED SPLIT (fixes a second, subtler leakage issue):
       The old code used sklearn's train_test_split() with random shuffling.
       For time-series forecasting, that lets the model "see" data from
       AFTER the test period during training (e.g. train on day 200, test
       on day 100) — which is unrealistic, since in production you only
       ever have data from the past to predict the future. We now sort by
       `date` and take the most recent ~20% of days as the test set, with
       everything before that as train. This matches how the model would
       actually be used in production.

    2. BASELINE MODEL COMPARISON:
       A model is only useful if it beats a naive baseline. We compute a
       simple baseline forecast (predicting today's sales = rolling_avg_7,
       i.e. "assume today looks like the last week's average") on the same
       test set, and report its MAE/RMSE/MAPE alongside XGBoost's. This is
       standard practice in forecasting projects and answers the "why
       XGBoost and not something simpler?" question with evidence instead
       of assumption.
    """
    feature_cols = get_available_features(df)

    if TARGET_COL not in df.columns:
        raise ValueError(f"Target column '{TARGET_COL}' not found in dataframe.")

    if "date" not in df.columns:
        raise ValueError(
            "'date' column required for time-based train/test split. "
            "Make sure it's preserved through preprocessing (see main.py)."
        )

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date")

    X = df[feature_cols].copy()
    y = df[TARGET_COL].copy()
    dates = df["date"]

    mask = y.notna() & dates.notna()
    X, y, dates = X[mask], y[mask], dates[mask]

    # ── Time-based split: earliest ~80% of days = train, most recent ~20% = test
    split_date = dates.quantile(0.8, interpolation="nearest")
    train_mask = dates <= split_date
    test_mask = ~train_mask

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    print(f"[train] Time-based split at {split_date.date()} — "
          f"Train: {len(X_train):,} rows (up to {split_date.date()}) | "
          f"Test: {len(X_test):,} rows (after {split_date.date()})")

    model = xgb.XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    preds = model.predict(X_test)
    preds = np.clip(preds, 0, None)

    mae  = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mape = np.mean(np.abs((y_test - preds) / y_test.replace(0, np.nan))) * 100

    metrics = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "MAPE_%": round(mape, 2)}
    print(f"\n[train] XGBoost Evaluation Metrics → {metrics}")

    # ── Baseline comparison: naive "today = last 7-day average" forecast ──
    baseline_col = "rolling_avg_7" if "rolling_avg_7" in df.columns else None
    baseline_metrics = None
    if baseline_col:
        baseline_preds = df.loc[X_test.index, baseline_col].clip(lower=0)
        b_mae  = mean_absolute_error(y_test, baseline_preds)
        b_rmse = np.sqrt(mean_squared_error(y_test, baseline_preds))
        b_mape = np.mean(np.abs((y_test - baseline_preds) / y_test.replace(0, np.nan))) * 100
        baseline_metrics = {
            "MAE": round(b_mae, 3), "RMSE": round(b_rmse, 3), "MAPE_%": round(b_mape, 2)
        }
        improvement = round((1 - mae / b_mae) * 100, 1) if b_mae > 0 else None
        print(f"[train] Baseline (naive rolling-avg-7) Metrics → {baseline_metrics}")
        print(f"[train] XGBoost improves on baseline MAE by {improvement}%"
              if improvement is not None else
              "[train] Could not compute improvement % (baseline MAE was 0)")
        metrics["baseline"] = baseline_metrics
        metrics["improvement_over_baseline_%"] = improvement
    else:
        print("[train] Skipped baseline comparison — rolling_avg_7 not found.")

    importance = pd.Series(model.feature_importances_, index=feature_cols)
    print("\n[train] Top 15 Feature Importances:")
    print(importance.nlargest(15).to_string())

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(FEATURES_PATH, "wb") as f:
        pickle.dump(feature_cols, f)

    # ── Persist metrics + feature importance so the dashboard can show them ──
    dashboard_metrics = {
        "trained_at": pd.Timestamp.now().isoformat(),
        "split_date": str(split_date.date()),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "xgboost": {"MAE": metrics["MAE"], "RMSE": metrics["RMSE"], "MAPE_%": metrics["MAPE_%"]},
        "baseline": baseline_metrics,
        "improvement_over_baseline_%": metrics.get("improvement_over_baseline_%"),
        "feature_importance": importance.nlargest(15).round(4).to_dict(),
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(dashboard_metrics, f, indent=2)
    print(f"[train] Metrics saved to {METRICS_PATH}")

    print(f"\n[train] Model saved to {MODEL_PATH}")
    return model, feature_cols, metrics
