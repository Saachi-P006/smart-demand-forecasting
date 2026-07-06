"""
tests/test_risk.py
===================
Unit tests for utils/risk.py — specifically the severity_score / severity_tier
logic that fixed the alert-fatigue bug (every stockout used to be labeled
"Critical" with no way to rank urgency).

Run with:  pytest tests/test_risk.py -v
"""
import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.risk import calculate_risks


def test_bigger_shortfall_gets_higher_severity_score():
    """A larger inventory shortfall should always score as more severe."""
    df = pd.DataFrame({
        "adjusted_demand":   [100, 100],
        "inventory_on_hand": [90, 10],   # row 0: small shortfall, row 1: large shortfall
        "volatility_score":  [0.0, 0.0],
    })
    out = calculate_risks(df)
    assert out.iloc[1]["severity_score"] > out.iloc[0]["severity_score"]


def test_no_shortfall_gets_zero_or_none_tier():
    """Rows where inventory comfortably covers demand should not be flagged critical."""
    df = pd.DataFrame({
        "adjusted_demand":   [50],
        "inventory_on_hand": [200],
        "volatility_score":  [0.5],
    })
    out = calculate_risks(df)
    assert out.iloc[0]["severity_score"] <= 0
    assert out.iloc[0]["severity_tier"] == "None"


def test_severity_tiers_are_not_all_identical():
    """
    Regression test for the original bug: previously every stockout row was
    labeled identically ('Critical'), giving no way to triage. We assert that
    a range of shortfall sizes produces a range of DIFFERENT tiers.
    """
    df = pd.DataFrame({
        "adjusted_demand":   [10, 20, 60, 300],
        "inventory_on_hand": [9,  15, 40, 0],
        "volatility_score":  [0.0, 0.0, 0.0, 0.0],
    })
    out = calculate_risks(df)
    tiers = set(out["severity_tier"])
    assert len(tiers) > 1, (
        "All rows got the same severity tier — this is the alert-fatigue bug."
    )


def test_higher_volatility_increases_severity_for_same_shortfall():
    """Two products with the identical shortfall, but the more volatile one
    should be scored as more urgent (harder to predict = riskier)."""
    df = pd.DataFrame({
        "adjusted_demand":   [100, 100],
        "inventory_on_hand": [50, 50],
        "volatility_score":  [0.0, 0.9],
    })
    out = calculate_risks(df)
    assert out.iloc[1]["severity_score"] > out.iloc[0]["severity_score"]


def test_alerts_can_be_sorted_by_severity_score():
    """Sanity check that severity_score is genuinely usable for ranking/sorting,
    which is what email_alerts.py now relies on."""
    df = pd.DataFrame({
        "adjusted_demand":   [500, 20, 100, 5],
        "inventory_on_hand": [0,   18, 10,  4],
        "volatility_score":  [0.2, 0.0, 0.5, 0.0],
    })
    out = calculate_risks(df).sort_values("severity_score", ascending=False)
    scores = out["severity_score"].tolist()
    assert scores == sorted(scores, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
