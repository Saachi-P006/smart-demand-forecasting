import streamlit as st
from frontend.auth import verify_login


@st.cache_data(show_spinner=False)
def _get_login_css() -> str:
    """
    Build the CSS+left-panel HTML exactly once and cache it for the
    lifetime of the server process. Subsequent reruns skip this entirely.
    """
    return """
    <!-- Preconnect so the browser opens the font socket immediately -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link
      href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Cormorant+Garamond:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap"
      rel="stylesheet"
    >

    <style>
    /* ─── RESET EVERY STREAMLIT WRAPPER ─────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    html, body { height: 100vh !important; overflow: hidden !important; }

    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlock"],
    .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        gap: 0 !important;
    }

    [data-testid="stApp"],
    [data-testid="stAppViewContainer"] {
        height: 100vh !important;
        overflow: hidden !important;
        background: #0f0f0f !important;
    }

    #MainMenu, footer, header { visibility: hidden !important; }

    /* ─── PUSH STREAMLIT'S MAIN AREA RIGHT ──────────── */
    [data-testid="stMain"] {
        margin-left: 40% !important;
        width: 60% !important;
        height: 100vh !important;
        overflow: hidden !important;
        background: #0f0f0f !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
    }

    [data-testid="stMainBlockContainer"] {
        width: 100% !important;
        max-width: 100% !important;
        height: 100vh !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    [data-testid="stVerticalBlock"] {
        width: 100% !important;
        max-width: 380px !important;
        padding: 0 !important;
        gap: 12px !important;
    }

    /* ─── LEFT PANEL — FIXED ────────────────────────── */
    .left-panel {
        position: fixed;
        top: 0; left: 0;
        width: 40%;
        height: 100vh;
        background:
            linear-gradient(160deg, rgba(8,6,4,0.58) 0%, rgba(18,12,6,0.76) 100%),
            url("https://images.unsplash.com/photo-1556911220-bff31c812dba?w=1200&q=80")
            center center / cover no-repeat;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 52px 48px;
        z-index: 10;
    }

    .left-panel::after {
        content: '';
        position: absolute;
        top: 72px; bottom: 72px; right: 0;
        width: 1px;
        background: linear-gradient(to bottom,
            transparent 0%,
            rgba(196,160,100,0.5) 35%,
            rgba(196,160,100,0.5) 65%,
            transparent 100%);
    }

    .left-logo {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.68rem;
        letter-spacing: 0.32em;
        color: rgba(255,255,255,0.4);
        text-transform: uppercase;
        animation: fadeUp 0.9s ease both;
    }

    .left-headline {
        font-family: 'Playfair Display', serif;
        font-size: clamp(2.2rem, 3.2vw, 3.2rem);
        font-weight: 700;
        line-height: 1.12;
        color: #fff;
        animation: fadeUp 0.9s 0.15s ease both;
    }

    .left-headline em { font-style: italic; color: #c4a064; }

    .left-tagline {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1rem;
        font-weight: 300;
        color: rgba(255,255,255,0.45);
        letter-spacing: 0.04em;
        margin-top: 14px;
        animation: fadeUp 0.9s 0.3s ease both;
    }

    .left-footer {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.66rem;
        letter-spacing: 0.14em;
        color: rgba(255,255,255,0.22);
        text-transform: uppercase;
        animation: fadeUp 0.9s 0.45s ease both;
    }

    /* ─── FORM ELEMENTS ─────────────────────────────── */
    .form-eyebrow {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.67rem;
        letter-spacing: 0.28em;
        color: #c4a064;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .form-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.3rem;
        font-weight: 700;
        color: #f0ece4;
        line-height: 1.15;
        margin-bottom: 4px;
    }

    .form-subtitle {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1rem;
        font-weight: 300;
        color: rgba(240,236,228,0.38);
        margin-bottom: 24px;
        letter-spacing: 0.03em;
    }

    .gold-divider {
        width: 38px;
        height: 1px;
        background: linear-gradient(to right, #c4a064, transparent);
        margin-bottom: 22px;
    }

    .role-label {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.67rem;
        letter-spacing: 0.22em;
        color: rgba(240,236,228,0.28);
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    /* ─── INPUTS ────────────────────────────────────── */
    div[data-testid="stTextInput"] label {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.67rem !important;
        letter-spacing: 0.2em !important;
        color: rgba(240,236,228,0.38) !important;
        text-transform: uppercase !important;
    }

    div[data-testid="stTextInput"] input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(196,160,100,0.18) !important;
        border-radius: 4px !important;
        color: #f0ece4 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 12px 15px !important;
        transition: border-color 0.3s, background 0.3s, box-shadow 0.3s !important;
    }

    div[data-testid="stTextInput"] input:focus {
        background: rgba(196,160,100,0.05) !important;
        border-color: #c4a064 !important;
        box-shadow: 0 0 0 3px rgba(196,160,100,0.1) !important;
        outline: none !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(240,236,228,0.16) !important;
    }

    /* ─── BUTTONS ───────────────────────────────────── */
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.24em !important;
        text-transform: uppercase !important;
        border-radius: 4px !important;
        padding: 13px 20px !important;
        width: 100% !important;
        transition: all 0.25s ease !important;
    }

    div[data-testid="stButton"] > button {
        background: transparent !important;
        border: 1px solid rgba(196,160,100,0.32) !important;
        color: #c4a064 !important;
    }

    div[data-testid="stButton"] > button:hover {
        background: rgba(196,160,100,0.08) !important;
        border-color: #c4a064 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(196,160,100,0.12) !important;
    }

    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #c4a064 0%, #a07840 100%) !important;
        color: #0d0d0d !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 18px rgba(196,160,100,0.22) !important;
    }

    div[data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(135deg, #d4b074 0%, #b08850 100%) !important;
        box-shadow: 0 8px 28px rgba(196,160,100,0.3) !important;
        transform: translateY(-1px) !important;
    }

    .back-wrap div[data-testid="stButton"] > button {
        background: transparent !important;
        border: none !important;
        color: rgba(240,236,228,0.28) !important;
        font-size: 0.66rem !important;
        padding: 8px 0 !important;
        width: auto !important;
        box-shadow: none !important;
        letter-spacing: 0.16em !important;
    }

    .back-wrap div[data-testid="stButton"] > button:hover {
        color: #c4a064 !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* ─── MISC ──────────────────────────────────────── */
    div[data-testid="stAlert"] {
        background: rgba(220,80,80,0.08) !important;
        border: 1px solid rgba(220,80,80,0.2) !important;
        border-radius: 4px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.78rem !important;
        color: rgba(240,180,180,0.85) !important;
    }

    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }

    [data-testid="stVerticalBlock"] > div {
        gap: 0 !important;
        padding: 0 !important;
    }

    /* ─── ANIMATIONS ────────────────────────────────── */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    </style>

    <div class="left-panel">
        <div class="left-logo">Demand Intelligence Platform</div>
        <div>
            <div class="left-headline">
                Precision<br>Forecasting,<br><em>Beautifully</em><br>Delivered.
            </div>
            <div class="left-tagline">Data-driven clarity for every decision.</div>
        </div>
        <div class="left-footer">Williams Sonoma &nbsp;·&nbsp; &copy; 2025</div>
    </div>
    """


def show_login():
    # Inject cached CSS + left panel — zero re-computation on reruns
    st.markdown(_get_login_css(), unsafe_allow_html=True)

    st.session_state.setdefault("role_selected", None)

    if not st.session_state.role_selected:
        st.markdown('<div class="form-eyebrow">Welcome back</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-title">Sign In</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-subtitle">Choose your access level to continue</div>', unsafe_allow_html=True)
        st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="role-label">Select your role</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2, gap="small")
        with col1:
            if st.button("⬡  Admin", use_container_width=True, key="btn_admin"):
                st.session_state.role_selected = "admin"
                st.rerun()
        with col2:
            if st.button("◇  Reviewer", use_container_width=True, key="btn_reviewer"):
                st.session_state.role_selected = "reviewer"
                st.rerun()
    else:
        role_display = st.session_state.role_selected.capitalize()
        st.markdown(f'<div class="form-eyebrow">{role_display} Portal</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-title">Enter Your<br>Credentials</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-subtitle">Authorised personnel only</div>', unsafe_allow_html=True)
        st.markdown('<div class="gold-divider"></div>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="your.name@company.com")
            password = st.text_input("Password", type="password", placeholder="••••••••••")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

            if submitted:
                ok, role, name = verify_login(username, password)
                if ok and role == st.session_state.role_selected:
                    st.session_state.authenticated = True
                    st.session_state.role = role
                    st.session_state.username = name
                    st.rerun()
                else:
                    st.error("Invalid credentials or incorrect role selected.")

        st.markdown('<div class="back-wrap">', unsafe_allow_html=True)
        if st.button("← Back to role selection", key="back"):
            st.session_state.role_selected = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)