"""
frontend/pages/data_reviewer.py
Tabular prediction review — proper visible text, inline edit/comment, teal action buttons.
Sidebar color untouched. All text visible. Edit triggers comment section per row.
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from frontend.components.sidebar import render_sidebar

OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "output")
REVIEW_CSV   = os.path.join(OUTPUT_DIR, "reviewer_edits.csv")
FORECAST_CSV = os.path.join(OUTPUT_DIR, "demand_forecast_output.csv")

ROWS_PER_PAGE = 15


# ─────────────────────────────────────────────────────────────────────────────
# CSS — light main area, sidebar untouched, all text forced visible
# ─────────────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

    #MainMenu, footer { visibility: hidden; }

    /* ── Main content area ── */
    [data-testid="stAppViewContainer"] > .main {
        background: #f4f6fa !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    [data-testid="stMain"] {
        background: #f4f6fa !important;
    }

    /* ── Force ALL text in main area to be visible dark ── */
    [data-testid="stMain"] p,
    [data-testid="stMain"] span,
    [data-testid="stMain"] div,
    [data-testid="stMain"] label,
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3,
    [data-testid="stMain"] li,
    [data-testid="stMain"] td,
    [data-testid="stMain"] th {
        color: #1a1f2e !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    /* ── Page header ── */
    .page-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }
    .page-sub {
        font-size: 0.83rem;
        color: #64748b !important;
        font-weight: 400;
        margin-bottom: 1.5rem;
    }

    /* ── Summary stat chips ── */
    .stat-row {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        margin-bottom: 1.2rem;
    }
    .stat-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.38rem 0.9rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1.5px solid;
        white-space: nowrap;
    }
    .chip-total    { background:#fff; border-color:#cbd5e1; color:#334155 !important; }
    .chip-pending  { background:#fef9ec; border-color:#fcd34d; color:#92400e !important; }
    .chip-approved { background:#f0fdf4; border-color:#6ee7b7; color:#065f46 !important; }
    .chip-edited   { background:#eff6ff; border-color:#93c5fd; color:#1d4ed8 !important; }
    .chip-rejected { background:#fff1f2; border-color:#fda4af; color:#be123c !important; }

    /* ── Table wrapper ── */
    .tbl-wrap {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin-bottom: 1.2rem;
    }
    .tbl-wrap table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.83rem;
    }
    .tbl-wrap thead tr {
        background: #0f172a;
    }
    .tbl-wrap thead th {
        padding: 0.75rem 1rem;
        text-align: left;
        font-weight: 600;
        font-size: 0.75rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #94a3b8 !important;
        border: none;
        white-space: nowrap;
    }
    .tbl-wrap tbody tr {
        border-bottom: 1px solid #f1f5f9;
        transition: background 0.12s;
    }
    .tbl-wrap tbody tr:last-child { border-bottom: none; }
    .tbl-wrap tbody tr:hover { background: #f8fafc; }
    .tbl-wrap tbody td {
        padding: 0.7rem 1rem;
        color: #1e293b !important;
        vertical-align: middle;
    }

    /* ── Flag badges ── */
    .flag-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        margin: 1px 2px;
        white-space: nowrap;
    }
    .flag-spike    { background:#fef2f2; color:#dc2626 !important; border:1px solid #fca5a5; }
    .flag-drop     { background:#eff6ff; color:#2563eb !important; border:1px solid #93c5fd; }
    .flag-event    { background:#f5f3ff; color:#7c3aed !important; border:1px solid #c4b5fd; }
    .flag-other    { background:#f8fafc; color:#475569 !important; border:1px solid #cbd5e1; }

    /* ── Status badges ── */
    .status-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .s-pending  { background:#fef9ec; color:#92400e !important; border:1px solid #fcd34d; }
    .s-approved { background:#f0fdf4; color:#065f46 !important; border:1px solid #6ee7b7; }
    .s-edited   { background:#eff6ff; color:#1d4ed8 !important; border:1px solid #93c5fd; }
    .s-rejected { background:#fff1f2; color:#be123c !important; border:1px solid #fda4af; }

    /* ── Teal action buttons ── */
    [data-testid="stButton"] > button {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        padding: 0.38rem 1rem !important;
        border-radius: 8px !important;
        border: none !important;
        cursor: pointer !important;
        transition: all 0.15s !important;
    }
    /* Approve buttons — teal */
    [data-testid="stButton"]:has(button[key*="approve"]) > button,
    button[kind="secondary"][key*="approve"] {
        background: linear-gradient(135deg, #0d9488, #0f766e) !important;
        color: #ffffff !important;
    }
    /* Edit/toggle buttons — slate */
    [data-testid="stButton"]:has(button[key*="edit"]) > button {
        background: linear-gradient(135deg, #334155, #1e293b) !important;
        color: #ffffff !important;
    }
    /* Save buttons — teal dark */
    [data-testid="stButton"]:has(button[key*="save"]) > button {
        background: linear-gradient(135deg, #0f766e, #065f46) !important;
        color: #ffffff !important;
    }
    /* Cancel buttons — slate light */
    [data-testid="stButton"]:has(button[key*="cancel"]) > button {
        background: #e2e8f0 !important;
        color: #475569 !important;
    }
    /* Default fallback — teal for all unmarked buttons */
    [data-testid="stButton"] > button {
        background: linear-gradient(135deg, #0d9488, #0f766e) !important;
        color: #ffffff !important;
    }
    [data-testid="stButton"] > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(13,148,136,0.3) !important;
    }

    /* ── Edit panel ── */
    .edit-panel {
        background: #f8fafc;
        border: 1.5px solid #0d9488;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin: 0.2rem 0 0.5rem 0;
    }
    .edit-panel-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #0d9488 !important;
        margin-bottom: 0.5rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .prev-comment {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 0.4rem 0.7rem;
        font-size: 0.76rem;
        color: #475569 !important;
        margin-bottom: 0.4rem;
        font-style: italic;
    }

    /* ── Streamlit widget text fixes ── */
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] * {
        color: #1e293b !important;
        background: #ffffff !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    [data-testid="stTextArea"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stSelectbox"] label {
        color: #475569 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
    }
    /* Metric text */
    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-family: 'DM Mono', monospace !important;
    }
    [data-testid="stMetricLabel"] {
        color: #64748b !important;
    }

    /* ── Pagination ── */
    .pag-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        padding: 0.6rem 0;
    }
    .pag-info {
        font-size: 0.8rem;
        color: #64748b !important;
        font-weight: 500;
    }

    /* ── Selectbox filter ── */
    [data-testid="stSelectbox"] > div > div {
        background: #ffffff !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSelectbox"] svg { color: #64748b !important; }

    /* ── Info/warning boxes ── */
    [data-testid="stAlert"] {
        background: #f0fdf4 !important;
        color: #065f46 !important;
        border-color: #6ee7b7 !important;
    }

    /* ── Success flash ── */
    .flash-ok {
        background: #f0fdf4;
        border: 1px solid #6ee7b7;
        border-radius: 7px;
        padding: 0.35rem 0.8rem;
        font-size: 0.77rem;
        font-weight: 600;
        color: #065f46 !important;
        display: inline-block;
        margin-top: 0.2rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_forecast() -> pd.DataFrame:
    try:
        needed = {"product_id","store_id","date","city","predicted_units","adjusted_demand","reason_flags"}
        df = pd.read_csv(FORECAST_CSV, usecols=lambda c: c in needed)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=15, show_spinner=False)
def load_reviews() -> dict:
    try:
        df = pd.read_csv(REVIEW_CSV)
        out = {}
        for _, row in df.iterrows():
            key = (str(row.get("product_id","")), str(row.get("store_id","")), str(row.get("date","")))
            out[key] = {
                "status":         row.get("status","pending"),
                "adjusted_units": row.get("adjusted_units", row.get("predicted_units", 0)),
                "notes":          str(row.get("reviewer_notes", row.get("notes","")) or ""),
                "reviewed_by":    row.get("reviewed_by",""),
                "reviewed_at":    row.get("reviewed_at",""),
            }
        return out
    except Exception:
        return {}


def save_review(pid, sid, date, predicted, adjusted, status, notes, reviewer):
    new_row = {
        "product_id": pid, "store_id": sid, "date": str(date),
        "predicted_units": predicted, "adjusted_units": adjusted,
        "status": status, "reviewer_notes": notes,
        "reviewed_by": reviewer,
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        df = pd.read_csv(REVIEW_CSV) if os.path.exists(REVIEW_CSV) else pd.DataFrame()
        if all(c in df.columns for c in ["product_id","store_id","date"]):
            mask = ((df["product_id"].astype(str)==str(pid)) &
                    (df["store_id"].astype(str)==str(sid)) &
                    (df["date"].astype(str)==str(date)))
            df = df[~mask]
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(REVIEW_CSV, index=False)
        load_reviews.clear()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


def apply_filters(df, filters):
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
        df = df[(df["date"] >= s) & (df["date"] <= e)]
    return df


def parse_flags(flag_str: str) -> str:
    """Convert raw reason_flags string to HTML badge(s)."""
    if not flag_str or flag_str.lower() in ("nan", "none", ""):
        return '<span style="color:#94a3b8;font-size:0.75rem;">—</span>'
    badges = []
    fl = flag_str.lower()
    if any(k in fl for k in ["spike","sudden spike","surge"]):
        badges.append('<span class="flag-badge flag-spike">📈 Sudden Spike</span>')
    if any(k in fl for k in ["drop","sudden drop","decline"]):
        badges.append('<span class="flag-badge flag-drop">📉 Sudden Drop</span>')
    if any(k in fl for k in ["event","festival","holiday","conflict"]):
        badges.append('<span class="flag-badge flag-event">🗓 Event Conflict</span>')
    if not badges:
        short = flag_str[:40] + ("…" if len(flag_str) > 40 else "")
        badges.append(f'<span class="flag-badge flag-other">{short}</span>')
    return "".join(badges)


def status_badge(status: str) -> str:
    cls_map = {
        "pending":  ("s-pending",  "⏳ Pending"),
        "approved": ("s-approved", "✅ Approved"),
        "edited":   ("s-edited",   "✏️ Edited"),
        "rejected": ("s-rejected", "❌ Rejected"),
    }
    cls, label = cls_map.get(status, ("s-pending", "⏳ Pending"))
    return f'<span class="status-badge {cls}">{label}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def show_reviewer_dashboard():
    inject_css()

    nav_items = ["🔍 Prediction Review", "📋 My Reviews"]
    selected, filters = render_sidebar(nav_items, default="🔍 Prediction Review")

    st.markdown('<div class="page-title">Data Reviewer</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Approve or edit ML demand predictions before admin sees them</div>', unsafe_allow_html=True)

    with st.spinner("Loading forecast data…"):
        forecast_df = load_forecast()

    if forecast_df.empty:
        st.warning("No forecast data found. Run `python main.py` first.")
        return

    reviews  = load_reviews()
    filtered = apply_filters(forecast_df.copy(), filters)

    # ── Summary counts ──
    all_keys   = {(str(r[0]), str(r[1]), str(r[2])) for r in
                  filtered[["product_id","store_id","date"]].itertuples(index=False)}
    approved_n = sum(1 for k in all_keys if reviews.get(k,{}).get("status")=="approved")
    edited_n   = sum(1 for k in all_keys if reviews.get(k,{}).get("status")=="edited")
    rejected_n = sum(1 for k in all_keys if reviews.get(k,{}).get("status")=="rejected")
    pending_n  = len(all_keys) - approved_n - edited_n - rejected_n

    st.markdown(f"""
    <div class="stat-row">
        <span class="stat-chip chip-total">📦 Total: <b>{len(filtered):,}</b></span>
        <span class="stat-chip chip-pending">⏳ Pending: <b>{pending_n:,}</b></span>
        <span class="stat-chip chip-approved">✅ Approved: <b>{approved_n}</b></span>
        <span class="stat-chip chip-edited">✏️ Edited: <b>{edited_n}</b></span>
        <span class="stat-chip chip-rejected">❌ Rejected: <b>{rejected_n}</b></span>
    </div>
    """, unsafe_allow_html=True)

    if selected == "🔍 Prediction Review":
        _render_table(filtered, reviews, filters)
    else:
        _render_my_reviews(reviews)


# ─────────────────────────────────────────────────────────────────────────────
# Prediction Review — tabular with inline edit/comment
# ─────────────────────────────────────────────────────────────────────────────

def _render_table(df, reviews, filters):
    fc_col = next((c for c in ["predicted_units","adjusted_demand"] if c in df.columns), None)
    if fc_col is None:
        st.error("No predicted_units / adjusted_demand column found in forecast CSV.")
        return

    # Status filter
    col_f, _ = st.columns([2, 5])
    with col_f:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "⏳ Pending", "✅ Approved", "✏️ Edited", "❌ Rejected"],
            key="sf_sel"
        )

    # Build display list
    display_rows = []
    for row_idx, row in enumerate(df.itertuples(index=False)):
        pid    = str(getattr(row, "product_id", "N/A"))
        sid    = str(getattr(row, "store_id",   "N/A"))
        dt     = str(getattr(row, "date",        "N/A"))
        key    = (pid, sid, dt)
        rev    = reviews.get(key, {})
        status = rev.get("status", "pending")

        if status_filter != "All":
            target = status_filter.split(" ", 1)[1].lower()
            if status != target:
                continue
        display_rows.append((row_idx, row, rev, key, status))

    if not display_rows:
        st.info("No predictions match the current filter.")
        return

    # Pagination
    ROWS_PER_PAGE = 15
    if "reviewer_page" not in st.session_state:
        st.session_state.reviewer_page = 0
    total_pages = max(1, (len(display_rows) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    if st.session_state.reviewer_page >= total_pages:
        st.session_state.reviewer_page = 0
    page      = st.session_state.reviewer_page
    page_rows = display_rows[page * ROWS_PER_PAGE:(page + 1) * ROWS_PER_PAGE]

    reviewer = st.session_state.get("username", "")

    # ── Table header ──
    st.markdown("""
    <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Product ID</th>
          <th>Store</th>
          <th>Location</th>
          <th>Date</th>
          <th>Predicted Demand</th>
          <th>Reason Flags</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
    </table>
    </div>
    """, unsafe_allow_html=True)

    # ── Rows ── (rendered with Streamlit columns for interactive buttons)
    for i, (row_idx, row, rev, key, status) in enumerate(page_rows):
        pid   = getattr(row, "product_id", "N/A")
        sid   = getattr(row, "store_id",   "N/A")
        dt    = getattr(row, "date",        "N/A")
        city  = getattr(row, "city",        "—") if hasattr(row, "city") else "—"
        pred  = getattr(row, fc_col, 0)
        flags = str(getattr(row, "reason_flags", "") or "") if hasattr(row, "reason_flags") else ""
        uid   = str(row_idx)
        row_n = page * ROWS_PER_PAGE + i + 1

        notes_key  = f"__notes_{uid}"
        edit_key   = f"__edit_open_{uid}"
        saved_key  = f"__saved_{uid}"

        if notes_key not in st.session_state:
            st.session_state[notes_key] = str(rev.get("notes", "") or "")
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        # ── Static row HTML ──
        try:
            pred_disp = f"{float(pred):,.0f}"
        except Exception:
            pred_disp = str(pred)

        st.markdown(f"""
        <div style="background:#fff; border:1px solid #e2e8f0; border-radius:10px;
                    padding:0.6rem 1rem; margin-bottom:0.3rem;
                    display:flex; align-items:center; gap:0; flex-wrap:nowrap;">
          <div style="width:3%; color:#94a3b8; font-size:0.75rem; font-weight:600;">{row_n}</div>
          <div style="width:10%; font-family:'DM Mono',monospace; font-size:0.82rem;
                      font-weight:600; color:#0f172a;">{pid}</div>
          <div style="width:8%;  font-size:0.82rem; color:#334155;">{sid}</div>
          <div style="width:12%; font-size:0.82rem; color:#334155;">{city}</div>
          <div style="width:11%; font-size:0.78rem; color:#64748b;">{dt}</div>
          <div style="width:12%; font-family:'DM Mono',monospace; font-size:0.85rem;
                      font-weight:700; color:#0f172a;">{pred_disp}</div>
          <div style="width:28%;">{parse_flags(flags)}</div>
          <div style="width:10%;">{status_badge(status)}</div>
          <!-- actions rendered below via Streamlit columns -->
        </div>
        """, unsafe_allow_html=True)

        # ── Action buttons in Streamlit columns (for interactivity) ──
        a1, a2, a3 = st.columns([1.2, 1.2, 6])

        with a1:
            if st.button("✅ Approve", key=f"approve_{uid}"):
                if save_review(pid, sid, dt, pred, pred, "approved",
                               st.session_state[notes_key], reviewer):
                    st.session_state[saved_key] = "Approved"
                    st.session_state[edit_key]  = False
                    st.rerun()

        with a2:
            label = "🔼 Close" if st.session_state[edit_key] else "✏️ Edit"
            if st.button(label, key=f"edit_{uid}"):
                st.session_state[edit_key] = not st.session_state[edit_key]
                st.rerun()

        # ── Inline edit / comment panel ──
        if st.session_state[edit_key]:
            with st.container():
                st.markdown('<div class="edit-panel">', unsafe_allow_html=True)
                st.markdown('<div class="edit-panel-title">✏️ Edit & Comment</div>',
                            unsafe_allow_html=True)

                # Show previous comment if any
                prev = rev.get("notes", "")
                if prev and str(prev) not in ("", "nan", "None"):
                    st.markdown(
                        f'<div class="prev-comment">Previous note: {prev}</div>',
                        unsafe_allow_html=True
                    )

                ec1, ec2 = st.columns([1, 2])
                with ec1:
                    adj_val = st.number_input(
                        "Adjusted Units",
                        value=float(rev.get("adjusted_units", pred) or pred),
                        min_value=0.0, step=1.0,
                        key=f"adj_{uid}"
                    )
                with ec2:
                    comment = st.text_area(
                        "Reviewer Comment",
                        value=st.session_state[notes_key],
                        placeholder="e.g. Diwali spike expected — increasing by 20 units. Conflict with regional festival flagged.",
                        height=90,
                        key=f"comment_{uid}"
                    )
                    st.session_state[notes_key] = comment

                s1, s2, _ = st.columns([1.2, 1, 5])
                with s1:
                    if st.button("💾 Save Edit", key=f"save_{uid}"):
                        if save_review(pid, sid, dt, pred, adj_val, "edited", comment, reviewer):
                            st.session_state[saved_key] = f"Saved · {adj_val:.0f} units"
                            st.session_state[edit_key]  = False
                            st.rerun()
                with s2:
                    if st.button("Cancel", key=f"cancel_{uid}"):
                        st.session_state[edit_key] = False
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

        # Flash saved message
        if st.session_state.get(saved_key):
            st.markdown(
                f'<div class="flash-ok">✅ {st.session_state[saved_key]}</div>',
                unsafe_allow_html=True
            )
            st.session_state[saved_key] = None

        st.markdown("<div style='height:0.15rem'></div>", unsafe_allow_html=True)

    # ── Pagination ──
    pg1, pg2, pg3 = st.columns([1, 3, 1])
    with pg1:
        if page > 0:
            if st.button("← Prev", key="pg_prev"):
                st.session_state.reviewer_page -= 1
                st.rerun()
    with pg2:
        st.markdown(
            f'<div class="pag-info" style="text-align:center;">'
            f'Page {page+1} of {total_pages} &nbsp;·&nbsp; '
            f'Showing {len(page_rows)} of {len(display_rows)} rows</div>',
            unsafe_allow_html=True
        )
    with pg3:
        if page < total_pages - 1:
            if st.button("Next →", key="pg_next"):
                st.session_state.reviewer_page += 1
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# My Reviews tab
# ─────────────────────────────────────────────────────────────────────────────

def _render_my_reviews(reviews):
    reviewer = st.session_state.get("username", "")
    my = {k: v for k, v in reviews.items() if v.get("reviewed_by") == reviewer}

    if not my:
        st.info("You haven't reviewed any predictions yet. Head to 'Prediction Review' to start.")
        return

    rows = []
    for (pid, sid, date), rev in my.items():
        rows.append({
            "Product ID":     pid,
            "Store":          sid,
            "Date":           date,
            "Adj. Units":     rev.get("adjusted_units", ""),
            "Status":         rev.get("status", "").title(),
            "Comment":        rev.get("notes", ""),
            "Reviewed At":    rev.get("reviewed_at", ""),
        })

    st.markdown("### My Review History")
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        height=500
    )