"""
app.py — Streamlit entry point
Handles routing: Login → Admin Dashboard or Data Reviewer Dashboard
"""

import streamlit as st

st.set_page_config(
    page_title="SmartDemand | Williams Sonoma",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── session state defaults ─────────────────────────────────────────────────────
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("role", None)
st.session_state.setdefault("username", None)

# ── pre-import all pages once (cached by Python's module system) ───────────────
from frontend.pages.login import show_login
from frontend.pages.admin_dashboard import show_admin_dashboard
from frontend.pages.data_reviewer import show_reviewer_dashboard

# ── routing ────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    show_login()
elif st.session_state.role == "admin":
    show_admin_dashboard()
elif st.session_state.role == "reviewer":
    show_reviewer_dashboard()