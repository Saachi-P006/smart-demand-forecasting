"""
frontend/pages/admin_dashboard.py — All bugs fixed including:

ORIGINAL 9 BUGS (already fixed in previous version):
BUG 1: kpi() f-string had literal quote mid-expression → broke Python parser
BUG 2: Nested f-string with same quote type → SyntaxError on Python <3.12
BUG 3: load_dashboard() mutated cached _read_csv_safe result in-place → cache corruption
BUG 4: load_forecast() returned load_dashboard() reference (same cached obj) → cross-mutation
BUG 5: apply_filters date compare crashed on NaT rows → dropna before filter
BUG 6: alerts[risk_col].str.contains on non-string column → explicit .astype(str) guard
BUG 7: agg_d used _fc() column that might not exist after apply_filters → column guard
BUG 8: fore["event_flag"] assignment mutated caller df → always .copy() fore at fn top
BUG 9: _read_csv_safe(@cached) called with set (unhashable) → converted to tuple

NEW BUGS FIXED IN THIS VERSION:
FIX A: load_alerts() never converted "date" column to datetime → AttributeError on .dt accessor
        in apply_filters() for alerts data (Overview, Insights & Alerts pages).
FIX B: apply_filters() has no dtype guard — if any loader skips datetime conversion the .dt
        accessor crashes → added pd.api.types.is_datetime64_any_dtype() check + forced parse.
FIX C: "promo_flag" absent from output CSVs (it is derived during preprocessing but not always
        saved) → derive it from discount_pct / promo_type / display_flag inside
        render_business_insights() before the column-existence check, same pattern used for
        event_flag.

BUSINESS INSIGHTS FIXES:
FIX D: Caption condition was wrong — display_flag is a valid promo source but was not checked,
        so the "no promotion signal" warning fired even when display_flag was present.
FIX E: Chart bar-label text had no explicit color → labels were invisible on light backgrounds.

FORECAST SECTION UPDATE (ROOT CAUSE OF "approved:0" BUG NOW FIXED):
FIX F: Removed "Top 10 Products by Forecasted Demand" bar chart from render_forecast().
FIX G: load_review_history() was looking for output/reviews.db and output/review_history.csv —
        NEITHER of which exist. data_reviewer.py writes to output/reviewer_edits.csv.
        REVIEWER_EDITS_CSV constant now points to the correct file.
FIX H: Column names corrected to match what data_reviewer.py → save_review() actually writes:
          status, adjusted_units, reviewer_notes, reviewed_by, reviewed_at
        Previous version used adj_units / notes / comment which do not exist in that CSV.
FIX I: Status values in reviewer_edits.csv are lowercase ("approved","edited","pending").
        load_review_history() now normalises to lowercase before filtering.
FIX J: _build_7day_forecast() now reads "adjusted_units" (the real column) and falls back
        to "predicted_units" when adjusted_units is absent or all-null.
FIX K: Badge-row counts read all rows (no status filter) directly from reviewer_edits.csv
        so Approved / Pending / Edited numbers always reflect reality.
FIX L: load_review_history() cache TTL set to 30 s so newly approved rows appear quickly.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from frontend.components.sidebar import render_sidebar
from frontend.components.email_alerts import start_hourly_alerts, send_critical_alerts

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
RAW_DIR    = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

# FIX G: correct path — this is what data_reviewer.py → save_review() writes
REVIEWER_EDITS_CSV = os.path.join(OUTPUT_DIR, "reviewer_edits.csv")

TEAL       = "#0d9488"
TEAL_LIGHT = "#5eead4"
TEAL_DARK  = "#0f766e"
SLATE      = "#0f172a"
PLOT_BG    = "#ffffff"
PAPER_BG   = "#f8fafc"
GRID_C     = "#f1f5f9"
TEXT_C     = "#1e293b"
MUTED_C    = "#64748b"
BLUE_C     = "#378ADD"   # reviewer-edited bars
GRAY_C     = "#B4B2A9"   # extrapolated bars


# ── Loaders ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def _read_csv_safe(filename: str, needed_cols: tuple = None) -> pd.DataFrame:
    # BUG 9 FIX: param is tuple not set (sets are unhashable, crash @cache_data)
    # BUG 3 FIX: return .copy() so callers can mutate without touching the cache
    path = os.path.join(OUTPUT_DIR, filename)
    try:
        if needed_cols:
            needed_set = set(needed_cols)
            df = pd.read_csv(path, usecols=lambda c: c in needed_set)
        else:
            df = pd.read_csv(path)
        return df.copy()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_dashboard() -> pd.DataFrame:
    for fname in ["dashboard_output.csv", "demand_forecast_output.csv", "full_pipeline_output.csv"]:
        df = _read_csv_safe(fname)
        if not df.empty:
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_alerts() -> pd.DataFrame:
    # FIX A: convert "date" to datetime here
    df = _read_csv_safe("alerts_output.csv")
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_forecast() -> pd.DataFrame:
    needed = (
        "date", "product_id", "store_id", "city", "units_sold", "predicted_units",
        "adjusted_demand", "promo_flag", "event_flag", "is_weekend", "discount_pct",
        "reason_flags", "risk_level", "inventory_on_hand", "promo_type", "display_flag",
    )
    for fname in ["demand_forecast_output.csv", "full_pipeline_output.csv"]:
        df = _read_csv_safe(fname, needed_cols=needed)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df
    return load_dashboard()


@st.cache_data(ttl=30, show_spinner=False)
def load_review_history() -> pd.DataFrame:
    """
    FIX G/H/I/L: Read reviewer decisions from output/reviewer_edits.csv —
    the exact file written by data_reviewer.py → save_review().

    Columns written by save_review():
        product_id, store_id, date, predicted_units, adjusted_units,
        status, reviewer_notes, reviewed_by, reviewed_at

    Returns ONLY rows where status IN ('approved', 'edited').
    TTL = 30 s so newly approved rows surface to admin quickly.
    """
    if not os.path.exists(REVIEWER_EDITS_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(REVIEWER_EDITS_CSV)
        if df.empty:
            return pd.DataFrame()

        # FIX I: normalise status to lowercase before filtering
        if "status" in df.columns:
            df["status"] = df["status"].astype(str).str.lower().str.strip()
            df = df[df["status"].isin(["approved", "edited"])]

        if df.empty:
            return pd.DataFrame()

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "reviewed_at" in df.columns:
            df["reviewed_at"] = pd.to_datetime(df["reviewed_at"], errors="coerce")

        return df.copy()
    except Exception:
        return pd.DataFrame()


def _fc(df: pd.DataFrame) -> str:
    for c in ["adjusted_demand", "predicted_units", "units_sold"]:
        if c in df.columns:
            return c
    return df.columns[-1] if not df.empty else "value"


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    # BUG 5 FIX + FIX B
    if df.empty:
        return df
    if filters.get("city") and "city" in df.columns:
        df = df[df["city"] == filters["city"]]
    if filters.get("store") and "store_id" in df.columns:
        df = df[df["store_id"].astype(str) == str(filters["store"])]
    if filters.get("product") and "product_id" in df.columns:
        df = df[df["product_id"].astype(str) == str(filters["product"])]
    if filters.get("date_range") and "date" in df.columns:
        s, e = filters["date_range"]
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df[(df["date"].dt.date >= s) & (df["date"].dt.date <= e)]
    return df


def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=Libre+Baskerville:wght@400;700&display=swap');
    #MainMenu, footer {{ visibility: hidden; }}
    html, body, .main, [data-testid="stAppViewContainer"] {{
        background: #f8fafc !important; font-family: 'Sora', sans-serif;
    }}
    .pg-header {{ font-family:'Libre Baskerville',serif; font-size:1.65rem; font-weight:700; color:{TEXT_C}; margin-bottom:0.2rem; }}
    .pg-sub {{ font-size:0.82rem; color:{MUTED_C}; font-weight:300; margin-bottom:1.4rem; }}
    .section-label {{ font-size:0.68rem; font-weight:600; letter-spacing:0.16em; text-transform:uppercase; color:{MUTED_C}; margin:1.4rem 0 0.7rem; }}
    .kpi-card {{ background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:1.2rem 1.4rem; box-shadow:0 1px 3px rgba(0,0,0,0.04); position:relative; overflow:hidden; }}
    .kpi-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg,{TEAL},{TEAL_LIGHT}); }}
    .kpi-label {{ font-size:0.7rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{MUTED_C}; margin-bottom:0.5rem; }}
    .kpi-value {{ font-family:'Libre Baskerville',serif; font-size:2.1rem; font-weight:700; color:{TEXT_C}; line-height:1; }}
    .kpi-sub {{ font-size:0.72rem; color:{MUTED_C}; margin-top:0.3rem; }}
    .risk-card-red {{ background:#fff1f2; border:1px solid #fecdd3; border-left:4px solid #f43f5e; border-radius:12px; padding:1.1rem 1.4rem; }}
    .risk-card-yellow {{ background:#fefce8; border:1px solid #fde68a; border-left:4px solid #eab308; border-radius:12px; padding:1.1rem 1.4rem; }}
    .risk-val {{ font-family:'Libre Baskerville',serif; font-size:1.9rem; font-weight:700; line-height:1; }}
    .risk-card-red  .kpi-label {{ color:{MUTED_C}; }}
    .risk-card-yellow .kpi-label {{ color:{MUTED_C}; }}
    [data-testid="stButton"] > button,
    [data-testid="stButton"] > button:focus,
    [data-testid="stButton"] > button:active {{
        font-family:'Sora',sans-serif !important; font-weight:600 !important; color:#ffffff !important;
        background:linear-gradient(135deg,{TEAL} 0%,{TEAL_DARK} 100%) !important;
        border:none !important; border-radius:8px !important; padding:0.6rem 1.4rem !important;
        box-shadow:0 2px 8px rgba(13,148,136,0.3) !important; transition:all 0.18s !important;
    }}
    [data-testid="stButton"] > button:hover {{
        box-shadow:0 4px 16px rgba(13,148,136,0.4) !important; transform:translateY(-1px) !important;
        background:linear-gradient(135deg,#0f9e92 0%,#0c857a 100%) !important;
    }}
    [data-testid="stButton"] > button *,
    [data-testid="stButton"] > button p,
    [data-testid="stButton"] > button span,
    [data-testid="stButton"] > button div {{ color:#ffffff !important; font-weight:600 !important; }}
    [data-testid="stTabs"] [role="tablist"] button[role="tab"] {{
        color:{TEXT_C} !important; font-family:'Sora',sans-serif !important;
        font-weight:500 !important; font-size:0.88rem !important; opacity:1 !important;
    }}
    [data-testid="stTabs"] [role="tablist"] button[role="tab"][aria-selected="true"] {{
        color:{TEAL} !important; font-weight:600 !important; border-bottom:2px solid {TEAL} !important;
    }}
    [data-testid="stTabs"] [role="tablist"] button[role="tab"]:hover {{ color:{TEAL} !important; opacity:1 !important; }}
    [data-testid="stTabs"] [role="tablist"] button[role="tab"] p,
    [data-testid="stTabs"] [role="tablist"] button[role="tab"] span,
    [data-testid="stTabs"] [role="tablist"] button[role="tab"] div {{ color:inherit !important; }}
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricLabel"] span {{ color:{MUTED_C} !important; font-family:'Sora',sans-serif !important; font-size:0.75rem !important; font-weight:600 !important; letter-spacing:0.1em !important; text-transform:uppercase !important; }}
    [data-testid="stMetricValue"]  {{ color:{TEXT_C} !important; font-family:'Libre Baskerville',serif !important; font-size:2rem !important; font-weight:700 !important; }}
    [data-testid="stMetricDelta"]  {{ font-family:'Sora',sans-serif !important; font-size:0.78rem !important; }}
    [data-testid="stDataFrame"] th {{
        background:#1e293b !important; color:#f1f5f9 !important;
        font-family:'Sora',sans-serif !important; font-size:0.78rem !important;
        font-weight:600 !important; letter-spacing:0.06em !important; text-transform:uppercase !important;
    }}
    [data-testid="stDataFrame"] td {{ color:{TEXT_C} !important; font-family:'Sora',sans-serif !important; font-size:0.82rem !important; }}
    [data-testid="stDataFrame"] tr:nth-child(even) td {{ background:rgba(13,148,136,0.04) !important; }}
    [data-testid="stSidebar"] * {{ color:{TEXT_C} !important; font-family:'Sora',sans-serif !important; }}
    [data-testid="stSidebar"] .pg-header,
    [data-testid="stSidebar"] label {{ color:{TEXT_C} !important; }}
    </style>
    """, unsafe_allow_html=True)


# ── Overview ─────────────────────────────────────────────────────────────────

def render_overview(filters):
    st.markdown('<div class="pg-header">Dashboard Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-sub">Real-time demand forecasting · all stores</div>', unsafe_allow_html=True)

    dash   = apply_filters(load_dashboard(), filters)
    alerts = apply_filters(load_alerts(),    filters)

    if dash.empty:
        st.warning("No data found. Run `python main.py` and check output/ CSVs exist.")
        return

    f = _fc(dash)
    stores_n   = int(dash["store_id"].nunique())   if "store_id"   in dash.columns else "—"
    products_n = int(dash["product_id"].nunique()) if "product_id" in dash.columns else "—"

    if "date" in dash.columns and "units_sold" in dash.columns:
        cutoff     = dash["date"].dropna().max() - pd.Timedelta(days=30)
        prev_sales = int(dash[dash["date"] >= cutoff]["units_sold"].sum())
    elif "units_sold" in dash.columns:
        prev_sales = int(dash["units_sold"].sum())
    else:
        prev_sales = "—"

    if "date" in dash.columns and f in dash.columns:
        max_date = dash["date"].dropna().max()
        next7    = int(dash[dash["date"] >= max_date - pd.Timedelta(days=7)][f].sum())
    elif f in dash.columns:
        next7 = int(dash[f].sum())
    else:
        next7 = "—"

    if not alerts.empty and all(col in alerts.columns for col in ["inventory_on_hand", f]):
        stockout  = (alerts[f] > alerts["inventory_on_hand"]).sum()
        overstock = (alerts["inventory_on_hand"] > alerts[f] * 1.5).sum()
    else:
        stockout = 0
        overstock = 0

    def kpi(col, icon, label, val, sub):
        val_str = "—" if val == "—" else f"{val:,}" if isinstance(val, int) else str(val)
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{icon} {label}</div>'
                f'<div class="kpi-value">{val_str}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "🏪", "Total Stores",     stores_n,   "Active locations")
    kpi(c2, "📦", "Products",         products_n,  "Across all stores")
    kpi(c3, "📊", "Sales (Last 30d)", prev_sales,  "Units sold")
    kpi(c4, "🔮", "Forecast (7d)",    next7,       "Predicted demand")

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(
            f'<div class="risk-card-red">'
            f'<div style="font-size:0.68rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#f43f5e;margin-bottom:0.4rem">🔴 Stockout Risks</div>'
            f'<div class="risk-val" style="color:#e11d48">{stockout:,}</div>'
            f'<div style="font-size:0.76rem;color:#9f1239;margin-top:0.3rem">Products below safe inventory threshold</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with r2:
        st.markdown(
            f'<div class="risk-card-yellow">'
            f'<div style="font-size:0.68rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#ca8a04;margin-bottom:0.4rem">🟡 Overstock Risks</div>'
            f'<div class="risk-val" style="color:#a16207">{overstock:,}</div>'
            f'<div style="font-size:0.76rem;color:#713f12;margin-top:0.3rem">Products exceeding demand forecast</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="section-label">Email Alerts</div>', unsafe_allow_html=True)
    st.info("⏰ Hourly critical stockout alerts are automatically sent to admin.")

    fore = apply_filters(load_forecast(), filters)
    if not fore.empty and "date" in fore.columns:
        f2 = _fc(fore)
        st.markdown('<div class="section-label">Demand Trend (last 30 days)</div>', unsafe_allow_html=True)
        fc2    = fore.dropna(subset=["date"])
        sample = fc2[fc2["date"] >= fc2["date"].max() - pd.Timedelta(days=30)]
        trend  = sample.groupby("date")[f2].sum().reset_index()
        fig    = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["date"], y=trend[f2],
            mode="lines", line=dict(color=TEAL, width=3)
        ))
        fig.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            font=dict(family="Sora", color=TEXT_C),
            xaxis=dict(title="Date", showgrid=True, gridcolor=GRID_C,
                       linecolor="#334155", tickfont=dict(color="#334155")),
            yaxis=dict(title="Demand", showgrid=True, gridcolor=GRID_C,
                       linecolor="#334155", tickfont=dict(color="#334155")),
            height=210, margin=dict(l=10, r=10, t=10, b=10), showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Forecast helpers ─────────────────────────────────────────────────────────

def _axis_style(title: str, gridded: bool = True) -> dict:
    return dict(
        title=title,
        title_font=dict(color=TEXT_C, size=12, family="Sora"),
        tickfont=dict(color=TEXT_C, size=11, family="Sora"),
        linecolor="#334155",
        showgrid=gridded,
        gridcolor=GRID_C if gridded else None,
    )


def _build_7day_forecast(reviews: pd.DataFrame) -> pd.DataFrame:
    """
    FIX J: Build a 7-day forward forecast from approved/edited reviewer rows.

    Reads 'adjusted_units' (written by data_reviewer.py → save_review()) and
    falls back to 'predicted_units' when adjusted_units is absent or all-null.

    Tags each projected day:
      'Approved' / 'Edited'  — exact date exists in review history
      'Extrapolated'         — day-of-week mean from approved history
    """
    if reviews.empty:
        return pd.DataFrame()

    # FIX J: resolve value column using the real column name from data_reviewer.py
    if "adjusted_units" in reviews.columns:
        val_series = pd.to_numeric(reviews["adjusted_units"], errors="coerce")
        if val_series.isna().all() and "predicted_units" in reviews.columns:
            val_series = pd.to_numeric(reviews["predicted_units"], errors="coerce")
    elif "predicted_units" in reviews.columns:
        val_series = pd.to_numeric(reviews["predicted_units"], errors="coerce")
    else:
        return pd.DataFrame()

    reviews = reviews.copy()
    reviews["_val"] = val_series.fillna(0)

    # Day-of-week mean from approved history
    dow_mean: dict = {}
    if "date" in reviews.columns:
        valid = reviews.dropna(subset=["date"]).copy()
        if not valid.empty:
            valid["_dow"] = valid["date"].dt.dayofweek
            dow_mean = valid.groupby("_dow")["_val"].mean().to_dict()

    base = reviews["_val"].mean() if reviews["_val"].sum() > 0 else 0

    today = pd.Timestamp.today().normalize()
    rows = []
    for i in range(7):
        day = today + pd.Timedelta(days=i)
        dow = day.dayofweek
        val = dow_mean.get(dow, base)

        if "date" in reviews.columns:
            matched = reviews[reviews["date"].dt.normalize() == day]
        else:
            matched = pd.DataFrame()

        if not matched.empty:
            tag = str(matched.iloc[0].get("status", "approved")).title()
        else:
            tag = "Extrapolated"

        rows.append({"date": day, "predicted": round(float(val), 2), "type": tag})

    return pd.DataFrame(rows)


# ── render_forecast ───────────────────────────────────────────────────────────

def render_forecast(filters):
    st.markdown('<div class="pg-header">Demand Forecast</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="pg-sub">30-day history · 7-day AI prediction — reviewer-approved only</div>',
        unsafe_allow_html=True,
    )

    fore = apply_filters(load_forecast(), filters)
    if fore.empty:
        st.warning("No forecast data. Run main.py first.")
        return

    f = _fc(fore)

    # BUG 7 FIX
    if f not in fore.columns:
        st.error(f"Column '{f}' not found in forecast data. Check output CSVs.")
        return

    if "date" not in fore.columns:
        st.warning("No 'date' column — cannot show trend or 7-day forecast.")
        return

    # ── Historical demand trend ─────────────────────────────────────────────
    fore_clean = fore.dropna(subset=["date"])
    agg_d = {f: "sum"}
    if "units_sold" in fore_clean.columns:
        agg_d["units_sold"] = "sum"
    agg = fore_clean.groupby("date").agg(agg_d).reset_index().sort_values("date")

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=agg["date"], y=agg[f],
        mode="lines", line=dict(color=TEAL, width=3), name="Forecast",
    ))
    fig_hist.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Sora", color=TEXT_C),
        xaxis=dict(**_axis_style("Date")),
        yaxis=dict(**_axis_style("Demand")),
        height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # ── 7-day reviewer-approved section ─────────────────────────────────────
    st.markdown(
        '<div class="section-label">7-Day Demand Forecast (Reviewer-Approved Only)</div>',
        unsafe_allow_html=True,
    )

    # FIX K: badge counts — read ALL rows, no status filter, directly from CSV
    approved_count = edited_count = pending_count = 0
    if os.path.exists(REVIEWER_EDITS_CSV):
        try:
            all_df = pd.read_csv(REVIEWER_EDITS_CSV)
            if "status" in all_df.columns:
                statuses = all_df["status"].astype(str).str.lower().str.strip()
                approved_count = int((statuses == "approved").sum())
                edited_count   = int((statuses == "edited").sum())
                pending_count  = int((statuses == "pending").sum())
        except Exception:
            pass

    st.markdown(
        f"""
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:0.9rem">
          <span style="background:#f0fdf4;color:#065f46;border:1.5px solid #6ee7b7;
                       padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600">
            ✅ Approved: {approved_count:,}
          </span>
          <span style="background:#fef9ec;color:#92400e;border:1.5px solid #fcd34d;
                       padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600">
            ⏳ Pending: {pending_count:,}
          </span>
          <span style="background:#eff6ff;color:#1d4ed8;border:1.5px solid #93c5fd;
                       padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600">
            ✏️ Edited: {edited_count:,}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # FIX G/H/I: load only approved+edited rows from the correct file
    reviews = load_review_history()

    if reviews.empty:
        st.info(
            "No approved or reviewer-edited forecasts yet. "
            "Ask a Data Reviewer to approve predictions — "
            "the 7-day chart will appear here once they do."
        )
        return

    pred_df = _build_7day_forecast(reviews)

    if pred_df.empty:
        st.warning("Could not compute 7-day forecast from review history.")
        return

    # ── Bar chart ───────────────────────────────────────────────────────────
    color_map  = {"Approved": TEAL, "Edited": BLUE_C, "Extrapolated": GRAY_C}
    bar_colors = pred_df["type"].map(color_map).fillna(GRAY_C).tolist()

    fig7 = go.Figure()
    fig7.add_trace(go.Bar(
        x=pred_df["date"].dt.strftime("%a %b %d"),
        y=pred_df["predicted"],
        marker_color=bar_colors,
        text=pred_df["predicted"].apply(lambda v: f"{v:.1f}"),
        textposition="outside",
        textfont=dict(color=TEXT_C, size=12, family="Sora"),
        showlegend=False,
    ))

    fig7.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Sora", color=TEXT_C),
        xaxis=dict(**_axis_style("Date", gridded=False)),
        yaxis=dict(**_axis_style("Predicted Units"), rangemode="tozero"),
        height=340, margin=dict(l=10, r=130, t=40, b=10),
        annotations=[
            dict(x=1.01, y=0.95, xref="paper", yref="paper", showarrow=False,
                 text=f"<span style='color:{TEAL}'>■</span> Approved",
                 font=dict(size=11, color=TEXT_C, family="Sora"), align="left"),
            dict(x=1.01, y=0.80, xref="paper", yref="paper", showarrow=False,
                 text=f"<span style='color:{BLUE_C}'>■</span> Edited",
                 font=dict(size=11, color=TEXT_C, family="Sora"), align="left"),
            dict(x=1.01, y=0.65, xref="paper", yref="paper", showarrow=False,
                 text=f"<span style='color:{GRAY_C}'>■</span> Projected",
                 font=dict(size=11, color=TEXT_C, family="Sora"), align="left"),
        ],
    )
    st.plotly_chart(fig7, use_container_width=True)

    # ── KPI summary cards ───────────────────────────────────────────────────
    total_7d   = pred_df["predicted"].sum()
    avg_day    = pred_df["predicted"].mean()
    peak_row   = pred_df.loc[pred_df["predicted"].idxmax()]
    peak_label = peak_row["date"].strftime("%a %b %d")
    peak_val   = peak_row["predicted"]

    def kpi(col, icon, label, val, sub):
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{icon} {label}</div>'
                f'<div class="kpi-value">{val}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    k1, k2, k3 = st.columns(3)
    kpi(k1, "📦", "7-Day Total",   f"{total_7d:,.1f}", "Reviewer-approved units")
    kpi(k2, "📊", "Daily Average", f"{avg_day:,.1f}",  "Based on approved history")
    kpi(k3, "📈", "Peak Day",      peak_label,          f"{peak_val:,.1f} units predicted")

    # ── Reviewer notes that influenced forecast ─────────────────────────────
    # FIX H: correct column is "reviewer_notes" (not "notes" or "comment")
    if "reviewer_notes" in reviews.columns:
        notable = reviews[
            reviews["reviewer_notes"].astype(str).str.strip()
            .str.len().gt(0) &
            reviews["reviewer_notes"].astype(str).str.lower().ne("nan")
        ]
        if not notable.empty:
            st.markdown(
                '<div class="section-label">Reviewer Notes Influencing This Forecast</div>',
                unsafe_allow_html=True,
            )
            for _, nr in notable.iterrows():
                note_text  = str(nr["reviewer_notes"])
                pid_v      = nr.get("product_id",    "—")
                sid_v      = nr.get("store_id",      "—")
                adj_v      = nr.get("adjusted_units", "—")
                stat_v     = str(nr.get("status", "")).title()
                badge_col  = TEAL if stat_v.lower() == "approved" else BLUE_C
                bg_col     = "#f0fdf4" if stat_v.lower() == "approved" else "#eff6ff"
                bdr_col    = "#6ee7b7" if stat_v.lower() == "approved" else "#93c5fd"
                st.markdown(
                    f"""
                    <div style="background:#ffffff;border:1px solid #e2e8f0;
                                border-left:4px solid {badge_col};border-radius:10px;
                                padding:0.75rem 1rem;margin-bottom:0.5rem;">
                      <div style="display:flex;gap:1rem;align-items:center;margin-bottom:0.3rem;">
                        <span style="font-size:0.72rem;font-weight:600;color:{MUTED_C};
                                     text-transform:uppercase;letter-spacing:0.08em;">
                          Product {pid_v} · Store {sid_v}
                        </span>
                        <span style="background:{bg_col};color:{badge_col};
                                     border:1px solid {bdr_col};padding:2px 8px;
                                     border-radius:12px;font-size:0.7rem;font-weight:600;">
                          {stat_v} · {adj_v} units
                        </span>
                      </div>
                      <div style="font-size:0.82rem;color:{TEXT_C};font-style:italic;">
                        "{note_text}"
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ── Detail table ────────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-label">Approved Review History Used for Forecast</div>',
        unsafe_allow_html=True,
    )
    # FIX H: display columns use the real names from reviewer_edits.csv
    disp_cols = [c for c in
                 ["date", "product_id", "store_id", "predicted_units",
                  "adjusted_units", "status", "reviewer_notes",
                  "reviewed_by", "reviewed_at"]
                 if c in reviews.columns]
    st.dataframe(reviews[disp_cols], use_container_width=True, height=260)


# ── Insights & Alerts ────────────────────────────────────────────────────────

def render_insights(filters):
    st.markdown('<div class="pg-header">Insights & Alerts</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-sub">Stockout and overstock risk breakdown</div>', unsafe_allow_html=True)

    alerts = apply_filters(load_alerts(), filters)
    if alerts.empty:
        st.warning("No alerts data. Run main.py first.")
        return

    stockout_df = (
        alerts[alerts["stockout_risk"].astype(str).str.lower().isin(["1", "true", "yes", "high", "medium"])]
        if "stockout_risk" in alerts.columns else
        alerts[alerts["stockout_flag"].astype(str).str.lower().isin(["1", "true"])]
        if "stockout_flag" in alerts.columns else
        alerts.iloc[0:0]
    )

    overstock_df = (
        alerts[alerts["overstock_risk"].astype(str).str.lower().isin(["1", "true", "yes", "high", "medium"])]
        if "overstock_risk" in alerts.columns else
        alerts.iloc[0:0]
    )

    if not overstock_df.empty and not stockout_df.empty:
        overstock_df = overstock_df[~overstock_df.index.isin(stockout_df.index)]

    ca = int(alerts["city"].nunique()) if "city" in alerts.columns else "—"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="risk-card-red">
          <div class="kpi-label">🔴 Stockout Alerts</div>
          <div class="risk-val" style="color:#f43f5e;">{len(stockout_df):,}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="risk-card-yellow">
          <div class="kpi-label">🟡 Overstock Alerts</div>
          <div class="risk-val" style="color:#eab308;">{len(overstock_df):,}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-label">🏙️ Cities Affected</div>
          <div class="kpi-value">{ca}</div>
        </div>""", unsafe_allow_html=True)

    if "city" in alerts.columns:
        st.markdown('<div class="section-label">Alerts by City</div>', unsafe_allow_html=True)
        chart_df = pd.concat([
            stockout_df.assign(alert_type="Stockout"),
            overstock_df.assign(alert_type="Overstock"),
        ])
        if not chart_df.empty:
            city_agg = chart_df.groupby(["city", "alert_type"]).size().reset_index(name="count")
            fig = px.bar(city_agg, x="city", y="count", color="alert_type", barmode="group",
                         color_discrete_map={"Stockout": "#f43f5e", "Overstock": "#eab308"})
            fig.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                font=dict(family="Sora", color=TEXT_C),
                xaxis=dict(showgrid=False, tickfont=dict(color=TEXT_C), title_font=dict(color=TEXT_C)),
                yaxis=dict(gridcolor=GRID_C, tickfont=dict(color=TEXT_C), title_font=dict(color=TEXT_C)),
                legend=dict(font=dict(color=TEXT_C)),
                height=320, margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    disp = [c for c in ["product_id", "store_id", "city", "inventory_on_hand",
                         "adjusted_demand", "predicted_units", "stockout_risk",
                         "overstock_risk", "risk_severity", "reason_flags"]
            if c in alerts.columns]

    st.markdown('<div class="section-label">🔴 Critical Stockout Details</div>', unsafe_allow_html=True)
    st.dataframe(stockout_df[disp].head(200), use_container_width=True, height=300)

    st.markdown('<div class="section-label">🟡 Overstock Details</div>', unsafe_allow_html=True)
    st.dataframe(overstock_df[disp].head(200), use_container_width=True, height=300)


# ── Business Insights ────────────────────────────────────────────────────────

def render_business_insights(filters):
    st.markdown('<div class="pg-header">Business Insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-sub">Demand patterns across promotions, weekends, and festivals</div>', unsafe_allow_html=True)

    fore = apply_filters(load_forecast(), filters).copy()
    if fore.empty:
        st.warning("No data.")
        return

    f = _fc(fore)

    _promo_source = "native"
    if "promo_flag" not in fore.columns:
        if "discount_pct" in fore.columns:
            fore["promo_flag"] = (pd.to_numeric(fore["discount_pct"], errors="coerce").fillna(0) > 0).astype(int)
            _promo_source = "discount_pct"
        elif "promo_type" in fore.columns:
            fore["promo_flag"] = fore["promo_type"].notna().astype(int)
            _promo_source = "promo_type"
        elif "display_flag" in fore.columns:
            fore["promo_flag"] = pd.to_numeric(fore["display_flag"], errors="coerce").fillna(0).astype(int)
            _promo_source = "display_flag"
        elif "reason_flags" in fore.columns:
            fore["promo_flag"] = fore["reason_flags"].astype(str).str.contains(
                r"promo|discount|sale|offer|bogo|coupon|deal",
                case=False, na=False, regex=True
            ).astype(int)
            _promo_source = "reason_flags"
        elif "is_weekend" in fore.columns:
            fore["promo_flag"] = pd.to_numeric(fore["is_weekend"], errors="coerce").fillna(0).astype(int)
            _promo_source = "is_weekend"
        else:
            fore["promo_flag"] = 0
            _promo_source = "none"

    if "event_flag" not in fore.columns and "reason_flags" in fore.columns:
        fore["event_flag"] = fore["reason_flags"].str.contains(
            "Festival|Event|Wedding|Diwali|holiday", case=False, na=False).astype(int)

    sample = fore.sample(min(50_000, len(fore)), random_state=42)
    tabs   = st.tabs(["🏷️ Promotions", "📅 Weekend Effect", "🎉 Festivals & Events"])

    def _axis(title, gridded=True):
        return dict(
            title=title,
            title_font=dict(color=TEXT_C, size=12, family="Sora"),
            tickfont=dict(color=TEXT_C, size=11, family="Sora"),
            linecolor="#cbd5e1",
            showgrid=gridded,
            gridcolor=GRID_C if gridded else None,
        )

    def _bar(x_val, y_val, color, label):
        return go.Bar(
            x=[x_val], y=[y_val],
            marker_color=color,
            text=[label],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=13, family="Sora"),
            showlegend=False,
        )

    with tabs[0]:
        if _promo_source == "none":
            st.info(
                "No promotion signal found in this CSV — "
                "`promo_flag`, `discount_pct`, `promo_type`, `display_flag`, "
                "`reason_flags`, and `is_weekend` are all absent. "
                "Showing top products by average demand instead."
            )
            if "product_id" in fore.columns:
                top = (fore.groupby("product_id")[f].mean()
                       .sort_values(ascending=False).head(15).reset_index())
                top.columns = ["Product ID", "Avg Demand"]
                top_max = top["Avg Demand"].max()
                fig = go.Figure()
                for i, row in top.iterrows():
                    shade = TEAL if i < 3 else (TEAL_LIGHT if i < 7 else "#64748b")
                    fig.add_trace(go.Bar(
                        x=[row["Avg Demand"]], y=[row["Product ID"]], orientation="h",
                        marker_color=shade, text=[f"{row['Avg Demand']:.1f}"],
                        textposition="inside", insidetextanchor="middle",
                        textfont=dict(color="#ffffff", size=11, family="Sora"),
                        showlegend=False,
                    ))
                fig.update_layout(
                    paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                    font=dict(family="Sora", color=TEXT_C),
                    yaxis=dict(autorange="reversed", showgrid=False,
                               tickfont=dict(color=TEXT_C, family="Sora"), linecolor="#cbd5e1"),
                    xaxis=dict(**_axis("Avg Demand (units)"), range=[0, top_max * 1.05]),
                    height=420, margin=dict(l=10, r=10, t=20, b=10), showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            promo     = sample.groupby("promo_flag")[f].mean().reset_index()
            promo_max = promo[f].max() if not promo.empty else 1
            promo["Status"] = promo["promo_flag"].map({1: "On Promotion 🏷️", 0: "Regular Price"})
            promo["Status"] = promo["Status"].fillna(promo["promo_flag"].astype(str))
            fig = go.Figure()
            for _, row in promo.iterrows():
                bar_c = TEAL if str(row["promo_flag"]) == "1" else "#64748b"
                fig.add_trace(_bar(row["Status"], row[f], bar_c, f"{row[f]:.1f}"))
            fig.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                font=dict(family="Sora", color=TEXT_C),
                showlegend=False, height=340,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis=dict(**_axis("Avg Forecast (units)"), range=[0, promo_max * 1.15]),
                xaxis=_axis("Promotion Status", gridded=False),
            )
            st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        if "date" in fore.columns:
            s2 = sample.dropna(subset=["date"]).copy()
            s2["day"] = s2["date"].dt.day_name()
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow   = s2.groupby("day")[f].mean().reindex(order).reset_index()
            dow.columns = ["Day", "Avg Forecast"]
            dow_max = dow["Avg Forecast"].max(skipna=True)
            fig = go.Figure()
            for _, row in dow.iterrows():
                bar_c = TEAL if row["Day"] in ["Saturday", "Sunday"] else "#64748b"
                val   = row["Avg Forecast"] if not pd.isna(row["Avg Forecast"]) else 0
                label = f"{val:.0f}" if not pd.isna(row["Avg Forecast"]) else "—"
                fig.add_trace(_bar(row["Day"], val, bar_c, label))
            fig.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                font=dict(family="Sora", color=TEXT_C),
                showlegend=False, height=340,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis=dict(**_axis("Avg Forecast (units)"), range=[0, (dow_max or 1) * 1.15]),
                xaxis=dict(**_axis("Day of Week", gridded=False),
                           categoryorder="array", categoryarray=order),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Weekend chart needs 'date' column in forecast output.")

    with tabs[2]:
        if "event_flag" in fore.columns:
            evt     = sample.groupby("event_flag")[f].mean().reset_index()
            evt_max = evt[f].max() if not evt.empty else 1
            evt["Day Type"] = evt["event_flag"].map({1: "Event Day 🎉", 0: "Normal Day"})
            fig = go.Figure()
            for _, row in evt.iterrows():
                bar_c = TEAL if str(row["event_flag"]) == "1" else "#64748b"
                fig.add_trace(_bar(row["Day Type"], row[f], bar_c, f"{row[f]:.1f}"))
            fig.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                font=dict(family="Sora", color=TEXT_C),
                showlegend=False, height=340,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis=dict(**_axis("Avg Forecast (units)"), range=[0, evt_max * 1.15]),
                xaxis=_axis("Day Type", gridded=False),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Event data not found in output CSVs.")

        if "date" in fore.columns:
            df2 = fore.dropna(subset=["date"]).copy()
            df2["month"] = df2["date"].dt.month
            wed   = df2[df2["month"].isin([11, 12, 1, 2])]
            other = df2[~df2["month"].isin([11, 12, 1, 2])]
            if not wed.empty and not other.empty:
                st.markdown('<div class="section-label">💍 Wedding Season vs Rest of Year</div>',
                            unsafe_allow_html=True)
                comp = pd.DataFrame({
                    "Period":     ["Wedding Season (Nov–Feb)", "Rest of Year"],
                    "Avg Demand": [wed[f].mean(),              other[f].mean()],
                    "color":      [TEAL,                        "#64748b"],
                })
                comp_max = comp["Avg Demand"].max()
                fig2 = go.Figure()
                for _, row in comp.iterrows():
                    fig2.add_trace(_bar(row["Period"], row["Avg Demand"], row["color"],
                                        f"{row['Avg Demand']:.1f}"))
                fig2.update_layout(
                    paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                    font=dict(family="Sora", color=TEXT_C),
                    showlegend=False, height=310,
                    margin=dict(l=10, r=10, t=20, b=10),
                    yaxis=dict(**_axis("Avg Demand (units)"), range=[0, comp_max * 1.15]),
                    xaxis=_axis("Period", gridded=False),
                )
                st.plotly_chart(fig2, use_container_width=True)


# ── Entry point ──────────────────────────────────────────────────────────────

def show_admin_dashboard():
    inject_css()
    start_hourly_alerts()
    nav_items = ["📊 Overview", "📈 Forecast", "⚠️ Insights & Alerts", "📊 Business Insights"]
    selected, filters = render_sidebar(nav_items, default="📊 Overview")
    if   selected == "📊 Overview":           render_overview(filters)
    elif selected == "📈 Forecast":           render_forecast(filters)
    elif selected == "⚠️ Insights & Alerts":  render_insights(filters)
    elif selected == "📊 Business Insights":  render_business_insights(filters)