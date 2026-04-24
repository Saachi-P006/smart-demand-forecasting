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
    """
    feature_cols = get_available_features(df)

    if TARGET_COL not in df.columns:
        raise ValueError(f"Target column '{TARGET_COL}' not found in dataframe.")

    X = df[feature_cols].copy()
    y = df[TARGET_COL].copy()

    mask = y.notna()
    X, y = X[mask], y[mask]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"[train] Train size: {len(X_train)} | Test size: {len(X_test)}")

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
    print(f"\n[train] Evaluation Metrics → {metrics}")

    importance = pd.Series(model.feature_importances_, index=feature_cols)
    print("\n[train] Top 15 Feature Importances:")
    print(importance.nlargest(15).to_string())

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(FEATURES_PATH, "wb") as f:
        pickle.dump(feature_cols, f)

    print(f"\n[train] Model saved to {MODEL_PATH}")
    return model, feature_cols, metrics
