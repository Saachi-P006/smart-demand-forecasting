"""
tests/test_processing.py
=========================
Unit tests for data/processing.py — specifically compute_true_lag_features(),
which fixed the data-leakage bug (lag_7/lag_14/rolling_avg_7 used to be
derived from the SAME ROW's target instead of real history).

Run with:  pytest tests/test_processing.py -v
"""
import sys
import os
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.processing import compute_true_lag_features


def _make_sales(units_by_day, store_id=1, product_id=1, start="2023-01-01"):
    """Helper: build a single store/product time series from a list of units_sold."""
    dates = pd.date_range(start, periods=len(units_by_day), freq="D")
    return pd.DataFrame({
        "date": dates,
        "store_id": store_id,
        "product_id": product_id,
        "units_sold": units_by_day,
    })


def test_lag_7_matches_value_from_7_days_ago():
    """lag_7 on day N should equal units_sold on day N-7, not day N itself."""
    units = list(range(1, 21))  # 1, 2, 3, ..., 20
    df = compute_true_lag_features(_make_sales(units))

    row_day_10 = df[df["date"] == "2023-01-11"].iloc[0]  # day index 10 (0-indexed), units=11
    expected_lag_7 = units[10 - 7]  # units_sold from 7 days earlier
    assert row_day_10["lag_7"] == expected_lag_7


def test_lag_features_do_not_equal_same_row_target():
    """
    Regression test for the original bug: lag_7 must NOT be derived from the
    same row's units_sold (e.g. units_sold * some_factor). We check that for
    rows with enough history, lag_7 varies independently of the current row's
    units_sold rather than being a fixed multiple of it.
    """
    units = [10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10, 20]
    df = compute_true_lag_features(_make_sales(units))

    valid = df[df["lag_7"].notna()]
    # If lag_7 were `units_sold * constant` (the old bug), the ratio
    # lag_7/units_sold would be identical for every row. Real historical
    # lag values should NOT maintain a constant ratio to the current row.
    ratios = (valid["lag_7"] / valid["units_sold"]).round(4).unique()
    assert len(ratios) > 1, (
        "lag_7 appears to be a fixed multiple of units_sold — "
        "this is the leakage bug, not a real historical lag."
    )


def test_rolling_avg_7_excludes_current_day():
    """
    rolling_avg_7 must be the average of the PRIOR 7 days, never including
    today's own units_sold value.
    """
    units = [0] * 7 + [1000]  # day 7 has a huge spike; prior 7 days are all 0
    df = compute_true_lag_features(_make_sales(units))

    spike_row = df[df["units_sold"] == 1000].iloc[0]
    # If today's spike leaked into rolling_avg_7, it would be > 0.
    assert spike_row["rolling_avg_7"] == 0, (
        "rolling_avg_7 includes the current day's value — leakage detected."
    )


def test_cold_start_rows_get_fallback_not_nan():
    """The first few rows of a series (no 7/14-day history yet) should be
    filled with a fallback mean, not left as NaN (which would break XGBoost)."""
    units = [5, 6, 7]  # too short for any real lag_7/lag_14
    df = compute_true_lag_features(_make_sales(units))
    assert df["lag_7"].isna().sum() == 0
    assert df["lag_14"].isna().sum() == 0
    assert df["rolling_avg_7"].isna().sum() == 0


def test_lag_features_respect_store_product_boundaries():
    """
    lag_7 for store/product A should never leak in values from store/product B,
    even if their rows are adjacent after sorting.
    """
    df_a = _make_sales([1, 2, 3, 4, 5, 6, 7, 8], store_id=1, product_id=1)
    df_b = _make_sales([100, 200, 300, 400, 500, 600, 700, 800], store_id=1, product_id=2)
    combined = pd.concat([df_a, df_b], ignore_index=True)

    result = compute_true_lag_features(combined)
    product_2_rows = result[result["product_id"] == 2]

    # None of product 2's lag values should come from product 1's small values (1-8)
    assert not any(product_2_rows["lag_7"].isin([1, 2, 3, 4, 5, 6, 7, 8]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
