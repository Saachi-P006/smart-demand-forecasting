"""
smart-demand-forecasting / main.py
===================================
Memory-safe pipeline — processes sales data in chunks to avoid RAM crashes.
"""

import sys
import os
import pandas as pd
import numpy as np
import gc

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from data.load_data          import load_all_data, get_core_tables
from data.processing         import preprocess_data
from features.feature_engineering import create_features
from features.business_rules import apply_demand_adjustments, calculate_inventory_recommendation
from models.train            import train_model, FEATURE_COLS
from models.predict          import predict, load_model
from models.feedback         import apply_feedback
from utils.flags             import add_flags_column
from utils.risk              import calculate_risks

OUTPUT_DIR = os.path.join(ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

RETRAIN    = True    # Set False to load saved model after first run
CHUNK_SIZE = 100_000 # rows per chunk — lower this if still out of memory (try 50000)
SAMPLE_FOR_TRAINING = 200_000  # rows used for XGBoost training (fits in RAM)


def run_pipeline():
    print("\n" + "="*60)
    print("  SMART DEMAND FORECASTING PIPELINE  (memory-safe mode)")
    print("="*60 + "\n")

    # ── STEP 1: Load all lookup tables (small) + sales header ────
    print("── STEP 1: Loading data ──────────────────────────────────")
    data = load_all_data()

    (sales, feature_store, promotions, events, products,
     stores, weather, supplier, store_capacity, volatility,
     web_traffic, price_history, forecast_review) = get_core_tables(data)

    print(f"  Sales rows: {len(sales):,}  |  Processing in chunks of {CHUNK_SIZE:,}")

    # ── STEP 2 & 3: Train on a sample first ───────────────────────
    print("\n── STEP 2-3: Building training sample ────────────────────")
    sample_sales = sales.sample(min(SAMPLE_FOR_TRAINING, len(sales)), random_state=42)

    df_train = preprocess_data(
        sample_sales, feature_store, promotions, events, products,
        stores, weather, supplier, store_capacity, volatility,
        web_traffic, price_history
    )

    # Save meta cols before feature engineering drops them
    train_meta = {}
    for col in ["date", "city"]:
        if col in df_train.columns:
            train_meta[col] = df_train[col].values

    df_train = create_features(df_train)
    for col, vals in train_meta.items():
        df_train[col] = vals

    # ── STEP 4: Train model ───────────────────────────────────────
    if RETRAIN:
        print("\n── STEP 4: Training XGBoost model ────────────────────────")
        model, feature_cols, metrics = train_model(df_train)
    else:
        print("\n── STEP 4: Loading saved model ───────────────────────────")
        model, feature_cols = load_model()
        metrics = {}

    del df_train
    gc.collect()
    print("  Training sample freed from memory.")

    # ── STEP 5-9: Process full data in chunks ─────────────────────
    print("\n── STEP 5-9: Processing full dataset in chunks ───────────")

    dashboard_cols = [
        "date", "city", "store_id", "product_id",
        "units_sold", "predicted_units", "adjusted_demand",
        "recommended_inventory", "safety_stock", "lead_time_demand",
        "inventory_on_hand", "stockout_flag", "stockout_risk",
        "overstock_risk", "stockout_probability", "risk_severity",
        "reason_flags", "promo_flag", "discount_pct", "impact_score",
        "is_weekend", "volatility_score",
    ]
    forecast_cols = [
        "date", "city", "store_id", "product_id",
        "predicted_units", "adjusted_demand",
        "recommended_inventory", "reason_flags",
    ]

    # Open output files (write header on first chunk, append after)
    dash_path     = os.path.join(OUTPUT_DIR, "dashboard_output.csv")
    forecast_path = os.path.join(OUTPUT_DIR, "demand_forecast_output.csv")
    alerts_path   = os.path.join(OUTPUT_DIR, "alerts_output.csv")
    full_path     = os.path.join(OUTPUT_DIR, "full_pipeline_output.csv")

    # Clear existing files
    for p in [dash_path, forecast_path, alerts_path, full_path]:
        if os.path.exists(p):
            os.remove(p)

    total_rows    = 0
    total_stockout  = 0
    total_overstock = 0
    chunk_num     = 0

    chunks = [sales[i:i+CHUNK_SIZE] for i in range(0, len(sales), CHUNK_SIZE)]
    print(f"  Total chunks: {len(chunks)}")

    for chunk_sales in chunks:
        chunk_num += 1
        print(f"\n  Chunk {chunk_num}/{len(chunks)}  ({len(chunk_sales):,} rows) ...", end=" ", flush=True)

        try:
            # Merge
            df = preprocess_data(
                chunk_sales, feature_store, promotions, events, products,
                stores, weather, supplier, store_capacity, volatility,
                web_traffic, price_history
            )

            # Save meta
            meta = {}
            for col in ["date", "city"]:
                if col in df.columns:
                    meta[col] = df[col].values

            # Features
            df = create_features(df)
            for col, vals in meta.items():
                df[col] = vals

            # Predict
            df["predicted_units"] = predict(model, feature_cols, df)

            # Business rules
            df = apply_demand_adjustments(df)
            df = calculate_inventory_recommendation(df)
            df = apply_feedback(df, target_col="adjusted_demand")
            df = add_flags_column(df)
            df = calculate_risks(df)

            # Accumulate stats
            total_rows      += len(df)
            total_stockout  += int(df["stockout_risk"].sum())
            total_overstock += int(df["overstock_risk"].sum())

            # Write to CSVs (header only on first chunk)
            write_header = (chunk_num == 1)
            mode = "w" if write_header else "a"

            avail_dash = [c for c in dashboard_cols if c in df.columns]
            df[avail_dash].to_csv(dash_path, mode=mode, header=write_header, index=False)

            avail_fc = [c for c in forecast_cols if c in df.columns]
            df[avail_fc].to_csv(forecast_path, mode=mode, header=write_header, index=False)

            df.to_csv(full_path, mode=mode, header=write_header, index=False)

            alert_mask = (
                df["risk_severity"].str.startswith("🔴") |
                df["risk_severity"].str.startswith("🟡")
            )
            if alert_mask.any():
                df[alert_mask][avail_dash].to_csv(
                    alerts_path, mode=mode, header=write_header, index=False
                )

            print(f"done  (total so far: {total_rows:,})")

        except Exception as e:
            print(f"ERROR in chunk {chunk_num}: {e}")
            import traceback
            traceback.print_exc()

        finally:
            del df
            gc.collect()

    # ── STEP 10: Summary ──────────────────────────────────────────
    print("\n── STEP 10: Output files ─────────────────────────────────")
    for p in [dash_path, forecast_path, alerts_path, full_path]:
        if os.path.exists(p):
            size_mb = os.path.getsize(p) / 1_048_576
            print(f"  ✅ {os.path.basename(p)}  ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {os.path.basename(p)}  NOT CREATED")

    print("\n" + "="*60)
    print("  PIPELINE COMPLETE – SUMMARY")
    print("="*60)
    print(f"  Total rows processed  : {total_rows:,}")
    print(f"  Stockout risks        : {total_stockout:,}")
    print(f"  Overstock risks       : {total_overstock:,}")
    if metrics:
        print(f"  Model MAE             : {metrics.get('MAE')}")
        print(f"  Model RMSE            : {metrics.get('RMSE')}")
        print(f"  Model MAPE            : {metrics.get('MAPE_%')}%")
    print(f"  Trained on            : {SAMPLE_FOR_TRAINING:,} rows sample")
    print("="*60 + "\n")
    print("  Now run:  streamlit run app.py")


if __name__ == "__main__":
    run_pipeline()
