import streamlit as st
from pathlib import Path
from utils import (
    LOGO_PATH,
    APP_DIR,
    inject_hydrostar_css,
    render_sidebar_header,
    render_page_header,
    HS_GREEN,
    HS_GREEN_DARK,
    HS_BG_CARD,
    HS_GREY,
    HS_BG_DARK,
)

st.set_page_config(
    page_title="HydroStar Digital Twin",
    layout="wide",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None,
)

inject_hydrostar_css()
render_sidebar_header()

st.sidebar.markdown(
    f'<p style="color:{HS_GREY};font-size:0.80rem;margin-top:2px;line-height:1.4;">'
    f'Select a model from the navigation above to begin your analysis.</p>',
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------
# EXTRA CSS FOR HOME PAGE ONLY
# -------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    .hs-card {{
        background-color: {HS_BG_CARD};
        border-left: 4px solid {HS_GREEN};
        border-radius: 6px;
        padding: 24px 22px 24px 22px;
        display: flex;
        flex-direction: column;
        height: 100%;
        box-sizing: border-box;
    }}
    .hs-card-title {{
        color: {HS_GREEN};
        font-weight: 700;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin: 0 0 10px 0;
    }}
    .hs-card-body {{
        color: #e8e8e8;
        font-size: 0.92rem;
        line-height: 1.65;
        margin: 0 0 12px 0;
        flex-grow: 1;
    }}
    .hs-card-sub {{
        color: {HS_GREY};
        font-size: 0.82rem;
        line-height: 1.6;
        margin: 0;
        border-top: 1px solid #4a505a;
        padding-top: 10px;
    }}
    .hs-step {{
        background-color: {HS_BG_DARK};
        border-radius: 4px;
        padding: 16px 18px;
        margin-bottom: 10px;
        display: flex;
        align-items: flex-start;
        gap: 16px;
    }}
    .hs-step-num {{
        background-color: {HS_GREEN};
        color: {HS_BG_DARK};
        font-weight: 800;
        font-size: 0.88rem;
        border-radius: 50%;
        min-width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        margin-top: 1px;
    }}
    .hs-step-text {{
        color: #e8e8e8;
        font-size: 0.92rem;
        line-height: 1.6;
    }}
    .hs-step-label {{
        color: {HS_GREEN};
        font-weight: 700;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================================
# HEADER
# =========================================================================
render_page_header("HydroStar Digital Twin", "Techno-Economic Analysis Platform")

st.markdown("---")

# =========================================================================
# ABOUT HYDROSTAR & TECHNOLOGY IMAGE
# =========================================================================
st.markdown(
    f'<h2 style="color:#ffffff;font-size:1.2rem;font-weight:700;margin-bottom:10px;">About HydroStar</h2>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <p style="color:#e8e8e8;font-size:0.95rem;line-height:1.75;max-width:920px;margin-bottom:20px;">
    HydroStar is a green hydrogen technology company that designs and deploys hardware across the green
    hydrogen value chain, including hydrogen production, purification, compression, and storage. Its
    membraneless electrolyser eliminates the need for membranes and precious metals, significantly
    reducing system complexity, cost, and supply-chain risk compared with conventional electrolysis
    technologies. The figure below displays HydroStar's key technology features.
    </p>
    """,
    unsafe_allow_html=True,
)

electrolyser_img = APP_DIR / "features_nextgen_electrolyser.webp"
if electrolyser_img.exists():
    st.image(str(electrolyser_img), use_container_width=True)
else:
    st.info("Technology overview image not found.")

st.markdown("---")

# =========================================================================
# THREE MODEL CARDS
# =========================================================================
st.markdown(
    f'<h2 style="color:#ffffff;font-size:1.2rem;font-weight:700;margin-bottom:16px;">Available Models</h2>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    st.markdown(
        f"""
        <div class="hs-card">
            <p class="hs-card-title">Green OffPort (Portside)</p>
            <p class="hs-card-body">
                Models green hydrogen production at a portside facility using real hourly
                solar, wind, and grid generation profiles. Covers the full project from
                power input through to hydrogen delivery.
            </p>
            <p class="hs-card-sub">
                Outputs: LCOH &bull; CAPEX / OPEX breakdown &bull; Annual H2 production &bull;
                Pre- and post-tax IRR &bull; NPV &bull; Payback period &bull;
                Monthly physics and utility profiles
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="hs-card">
            <p class="hs-card-title">Industrial (Babcock)</p>
            <p class="hs-card-body">
                Quantifies the economic case for replacing diesel with green hydrogen in
                an industrial setting. Stacks value from diesel displacement, carbon credits,
                oxygen revenue, and wastewater treatment savings.
            </p>
            <p class="hs-card-sub">
                Outputs: Gross and effective LCOH &bull; Annual value stack &bull;
                Diesel displaced &bull; CO2 avoided &bull; IRR &bull; NPV &bull;
                After-tax cash flow table
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="hs-card">
            <p class="hs-card-title">Utility Scale (Project Finance)</p>
            <p class="hs-card-body">
                Project finance model for large-scale solar and hybrid hydrogen plants.
                Structures the capital stack with government grants, debt, and equity,
                and models optional off-peak power purchases to improve utilisation.
            </p>
            <p class="hs-card-sub">
                Outputs: CAPEX structure &bull; Grant and debt sizing &bull;
                Annual EBITDA &bull; Debt amortisation &bull;
                Levered equity cash flow &bull; Cumulative returns
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# =========================================================================
# HOW TO USE
# =========================================================================
st.markdown(
    f'<h2 style="color:#ffffff;font-size:1.2rem;font-weight:700;margin-bottom:16px;">How to Use This Tool</h2>',
    unsafe_allow_html=True,
)

left, right = st.columns(2, gap="large")

with left:
    st.markdown(
        f"""
        <div class="hs-step">
            <div class="hs-step-num">1</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Select a model</span> from the sidebar on the left.
                Each model represents a different hydrogen use case.
                Click the name of the model you want to analyse.
            </div>
        </div>
        <div class="hs-step">
            <div class="hs-step-num">2</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Review and adjust the inputs.</span>
                Every input comes pre-filled with realistic default values so you can see results
                immediately. Open each section (click the heading to expand it) and change any
                values to match your specific project.
            </div>
        </div>
        <div class="hs-step">
            <div class="hs-step-num">3</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Set project-level parameters</span> in the
                left sidebar: project life, discount rate, inflation, and degradation.
                These apply across the entire model and update results instantly.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        f"""
        <div class="hs-step">
            <div class="hs-step-num">4</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Read the key metrics</span> at the top of the results
                section. These headline numbers (LCOH, IRR, NPV, payback) update automatically
                every time you change an input — no button to press.
            </div>
        </div>
        <div class="hs-step">
            <div class="hs-step-num">5</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Explore the output tabs</span> below the metrics
                for detailed charts and tables. Tabs cover physics, utilities, CAPEX/OPEX
                breakdown, cash flow, and monthly outputs depending on the model.
            </div>
        </div>
        <div class="hs-step">
            <div class="hs-step-num">6</div>
            <div class="hs-step-text">
                <span class="hs-step-label">Export data</span> from any table by hovering
                over it and clicking the download icon that appears in the top-right corner
                of the table. Charts can be saved using the camera icon on hover.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    f'<p style="color:{HS_GREY};font-size:0.75rem;text-align:center;">HydroStar Europe Ltd. &nbsp;|&nbsp; Confidential</p>',
    unsafe_allow_html=True,
)
