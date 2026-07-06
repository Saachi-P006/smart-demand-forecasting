# Changelog — Bugs Found & Fixed

This project started as a working demo but had several issues under the
hood. Below is a record of what was found, why it mattered, and how it
was fixed — kept here as an honest record of the debugging process.

## 1. Data leakage in lag/rolling features (accuracy bug)

**Found:** The model reported ~99.96% accuracy (MAE 0.006, MAPE 0.04%),
which is not realistic for a demand forecasting problem.

**Root cause:** `lag_7`, `lag_14`, and `rolling_avg_7` — meant to represent
past sales — were actually computed from the **current row's own
`units_sold`** (the training target itself), multiplied by a scaling
factor. The model wasn't forecasting; it was reverse-engineering a
near-linear formula.

**Fix:** Added `compute_true_lag_features()` in `data/processing.py`,
which computes genuine time-shifted features per `(store_id, product_id)`
using `groupby().shift()` — so `lag_7` is the actual value from 7 days
ago, and `rolling_avg_7` is the mean of the *prior* 7 days only (never
including today).

**Result:** MAE went from 0.006 → 4.07 and MAPE from 0.04% → 82%. Worse
numbers, but honest ones — and feature importance shifted from the fake
lag columns to genuinely predictive signals (`is_weekend`,
`stockout_flag`, `day_of_week`).

## 2. Random (non-time-based) train/test split

**Found:** After fixing #1, model evaluation still used
`train_test_split(..., random_state=42)`, which shuffles rows randomly.

**Why it's a problem:** For time-series data, random shuffling lets the
model train on rows from *after* the test period — unrealistic, since in
production you only ever have the past to predict the future.

**Fix:** `train_model()` now sorts by `date` and splits chronologically —
the earliest ~80% of days become the training set, the most recent ~20%
become the test set.

## 3. No baseline model for comparison

**Found:** There was no way to know if XGBoost was actually adding value
over a much simpler approach.

**Fix:** Added a naive baseline ("assume today's sales = the trailing
7-day average") evaluated on the same time-based test set. XGBoost beats
it by ~7.7% on MAE — a modest, believable, and now evidence-backed
improvement.

## 4. Alert fatigue — binary "Critical" flag

**Found:** Every product with `inventory < demand` was labeled
identically `"🔴 Critical – Stockout"`, with no way to distinguish a
shortfall of 2 units from a shortfall of 500 units. Reviewers had no way
to triage what actually needed attention first.

**Fix:** Added `severity_score` (shortfall size, scaled by volatility)
and `severity_tier` (None/Low/Medium/High/Critical) in `utils/risk.py`.
`email_alerts.py` now sorts by severity and only sends High/Critical
tiers, capped at a sane batch size, instead of dumping an unordered
top-20 slice.

## 5. Exposed credentials in `.env`

**Found:** A real Gmail address and app password were committed in
plaintext in `.env` and referenced in a code comment.

**Fix:** Replaced with placeholders, added `.gitignore` so `.env` is
never committed, and removed the real credentials from the docstring in
`email_alerts.py`.

## 6. Dead weight: unused 178MB CSV loaded every run

**Found:** `load_all_data()` loads `demand_forecast.csv` (178MB) into
memory on every pipeline run, but it is never referenced anywhere else in
the codebase.

**Status:** Documented, not yet removed — flagged here as a known
opportunity for a quick performance win.

---

### Testing

Unit tests covering fixes #1 and #4 live in `tests/`:
- `tests/test_processing.py` — verifies lag features come from real
  history, respect store/product boundaries, and don't leak the current
  day's value.
- `tests/test_risk.py` — verifies severity scoring ranks shortfalls
  correctly and produces varied tiers instead of one flat "Critical"
  bucket.

Run with:
```bash
pytest tests/ -v
```
