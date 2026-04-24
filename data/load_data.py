"""
data/load_data.py
=================
Loads all CSV files from data/raw/ and returns them as a dict.

Schema notes for the new synthetic_data CSVs
─────────────────────────────────────────────
Most "signal" tables now use a generic wide-pivoted format:
    date, store_id, product_id, value

Tables that kept their original rich schema:
    sales_history        – date, store_id, product_id, units_sold, sell_price,
                           inventory_on_hand, stockout_flag
    promotions           – date, store_id, product_id, promo_type, discount_pct,
                           display_flag, campaign_name
    products             – product_id, product_name, category, subcategory,
                           brand, mrp, shelf_life_days, lead_time_days
    stores               – store_id, store_name, city, state, store_type,
                           store_size_sqft
    weather              – date, city, avg_temp, rainfall_mm, humidity,
                           weather_condition
    ws_events_calendar   – date, event_name, event_type, city, impact_level
    demand_forecast      – date, store_id, product_id, units_sold, sell_price,
                           inventory_on_hand, stockout_flag,
                           predicted_units_sold, recommended_inventory_level,
                           confidence_score

Tables now using generic 'value' column:
    feature_store, supplier_lead_times, store_capacity, demand_volatility,
    web_traffic_signals, price_history, forecast_review, alerts,
    realtime_signals, forecast_accuracy_log, competitor_pricing,
    customer_segments, product_returns, test_input
"""

import pandas as pd
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "raw")

# Rename map: filename stem → internal key
_FILENAME_MAP = {
    "ws_events_calendar": "events_calendar",  # renamed in new data
}


def load_all_data() -> dict:
    """
    Load all CSV files from data/raw/ and return as a dict keyed by table name.
    """
    dataframes: dict = {}
    for file in sorted(os.listdir(DATA_PATH)):
        if not file.endswith(".csv"):
            continue
        stem = file.replace(".csv", "")
        key  = _FILENAME_MAP.get(stem, stem)
        try:
            dataframes[key] = pd.read_csv(os.path.join(DATA_PATH, file))
        except Exception as exc:
            print(f"[load_data] WARNING – could not read {file}: {exc}")
    print(f"[load_data] Loaded {len(dataframes)} tables: {sorted(dataframes.keys())}")
    return dataframes


def get_core_tables(data: dict):
    """
    Pull out the specific tables needed for training.
    Returns a 13-tuple matching the old signature.
    """
    def _get(key: str) -> pd.DataFrame:
        df = data.get(key, pd.DataFrame())
        if df.empty:
            print(f"[load_data] WARNING – table '{key}' not found or empty.")
        return df.copy()

    sales           = _get("sales_history")
    feature_store   = _get("feature_store")
    promotions      = _get("promotions")
    events          = _get("events_calendar")      # loaded from ws_events_calendar.csv
    products        = _get("products")
    stores          = _get("stores")
    weather         = _get("weather")
    supplier        = _get("supplier_lead_times")
    store_capacity  = _get("store_capacity")
    volatility      = _get("demand_volatility")
    web_traffic     = _get("web_traffic_signals")
    price_history   = _get("price_history")
    forecast_review = _get("forecast_review")

    return (sales, feature_store, promotions, events, products,
            stores, weather, supplier, store_capacity, volatility,
            web_traffic, price_history, forecast_review)
