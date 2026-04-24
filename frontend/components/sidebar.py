import streamlit as st
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
RAW_DIR    = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

TEAL  = "#0d9488"
SLATE = "#0f172a"


def render_sidebar(nav_items: list, default: str = None) -> tuple:

    st.markdown(f"""
    <style>

    /* ───────── Sidebar Background ───────── */
    [data-testid="stSidebar"] {{
        background: {SLATE};
        border-right: 1px solid #1e293b;
    }}

    /* ───────── KEEP TOGGLE BUTTON VISIBLE ───────── */
    button[kind="header"] {{
        opacity: 1 !important;
        visibility: visible !important;
        display: flex !important;
    }}

    /* Hide ONLY shortcut text (keep arrow icon) */
    button[kind="header"] div[data-testid="collapsedControl"] p {{
        display: none !important;
    }}

    /* ───────── Sidebar Text ───────── */
    [data-testid="stSidebar"] * {{
        color: #f1f5f9 !important;
        font-family: 'DM Sans', sans-serif !important;
    }}

    /* ───────── Brand ───────── */
    .sb-brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 25px;
    }}

    .sb-name {{
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.02em;
    }}

    .sb-sub {{
        font-size: 12px;
        opacity: 0.7;
    }}

    /* ───────── Section Title ───────── */
    .sb-sec {{
        font-size: 11px;
        text-transform: uppercase;
        margin-top: 18px;
        margin-bottom: 10px;
        display: block;
        opacity: 0.6;
        letter-spacing: 0.08em;
    }}

    /* ───────── Nav Buttons ───────── */
    .stButton > button {{
        width: 100%;
        margin-bottom: 10px;
        padding: 0.5rem;
        border-radius: 8px;
        border: 1px solid #1e293b;
        background: #020617;
        color: #e2e8f0;
        font-weight: 500;
        transition: all 0.2s ease;
    }}

    .stButton > button:hover {{
        background: {TEAL};
        color: white;
        border-color: {TEAL};
        transform: translateX(3px);
    }}

    /* ───────── Logout Button ───────── */
    .stButton > button[kind="secondary"] {{
        background: #7f1d1d;
        border: none;
    }}

    .stButton > button[kind="secondary"]:hover {{
        background: #b91c1c;
    }}

    /* ───────── Divider ───────── */
    hr {{
        border: none;
        border-top: 1px solid #1e293b;
        margin: 15px 0;
    }}

    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:

        # ───────── Brand ─────────
        st.markdown("""
        <div class="sb-brand">
            <div style="font-size:22px;">🏺</div>
            <div>
                <div class="sb-name">SmartDemand</div>
                <div class="sb-sub">Williams Sonoma</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ───────── User Info ─────────
        st.markdown(
            f'<div style="margin-bottom:15px;">👤 {st.session_state.get("username","User")} '
            f'· {st.session_state.get("role","").title()}</div>',
            unsafe_allow_html=True
        )

        # ───────── Navigation ─────────
        st.markdown('<span class="sb-sec">Navigation</span>', unsafe_allow_html=True)

        selected = default if default in nav_items else nav_items[0]

        for item in nav_items:
            if st.button(item, key=f"nav_{item}"):
                selected = item

        st.markdown("---")

        # ───────── Logout ─────────
        if st.button("🚪 Logout", key="sidebar_logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    return selected, {}