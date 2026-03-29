import streamlit as st
import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.graph_objects as go

from utils import (
    LOGO_PATH,
    inject_hydrostar_css,
    render_sidebar_header,
    render_page_header,
    apply_chart_theme,
    simulate_8760_profiles,
    HS_GREEN,
    HS_GREY,
)

st.set_page_config(
    page_title="HydroStar — Utility Scale",
    layout="wide",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None,
)

inject_hydrostar_css()
render_sidebar_header()

# -------------------------------------------------------------------------
# SIDEBAR: FINANCING PARAMETERS
# -------------------------------------------------------------------------
st.sidebar.markdown(
    f'<p class="hs-section-header">Financing Parameters</p>',
    unsafe_allow_html=True,
)
grant_pct = st.sidebar.slider("Government Grant (%)", 0, 50, 20) / 100
loan_pct = st.sidebar.slider("Debt Leverage — Loan (%)", 0, 80, 60) / 100
project_life = st.sidebar.slider("Project Life (Years)", 10, 25, 20)

# -------------------------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------------------------
render_page_header(
    "Utility Scale — Project Finance & Hybrid Power",
    "Large-scale solar and hybrid power project finance with debt amortization",
)

# -------------------------------------------------------------------------
# INPUTS
# -------------------------------------------------------------------------
with st.expander("System Sizing & Power Configuration", expanded=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f'<p class="hs-section-header">Generation</p>', unsafe_allow_html=True)
        sys_solar_mw = st.number_input("Solar PV capacity (MW)", min_value=0.0, value=23.0, step=1.0)

    with c2:
        st.markdown(f'<p class="hs-section-header">Electrolyser</p>', unsafe_allow_html=True)
        sys_elec_mw = st.number_input("Electrolyser capacity (MW)", min_value=0.1, value=11.0, step=0.5)

    with c3:
        st.markdown(f'<p class="hs-section-header">Supplementary Power</p>', unsafe_allow_html=True)
        use_nuclear = st.checkbox(
            "Purchase overnight off-peak power (e.g. Nuclear @ £40/MWh)",
            value=True,
            help="Adds 12 hours/day of off-peak grid power to supplement solar generation.",
        )
        st.markdown(
            f'<p style="color:{HS_GREY};font-size:0.86rem;margin-top:8px;line-height:1.5;">'
            f'Off-peak rate: <b style="color:#fff;">£40/MWh</b> — fixed assumption</p>',
            unsafe_allow_html=True,
        )

# -------------------------------------------------------------------------
# CALCULATIONS
# -------------------------------------------------------------------------
sim = simulate_8760_profiles(sys_solar_mw, 0, sys_elec_mw, 55.0)
solar_h2 = sim["Annual_H2_kg"]
night_h2 = ((sys_elec_mw * 1000 * 365 * 12) / 55.0) if use_nuclear else 0
total_h2 = solar_h2 + night_h2

gross_capex = (sys_solar_mw * 650000 * 1.15) + (sys_elec_mw * 450000 * 1.15) + 2000000
grant_amount = gross_capex * grant_pct
net_capex_after_grant = gross_capex - grant_amount

loan_principal = net_capex_after_grant * loan_pct
equity_required = net_capex_after_grant - loan_principal

loan_term = 15
loan_rate = 0.05
annual_pmt = npf.pmt(loan_rate, loan_term, -loan_principal) if loan_principal > 0 else 0

night_power_cost = (night_h2 * 55.0 / 1000) * 40.0 if use_nuclear else 0
opex = (gross_capex * 0.02) + night_power_cost
revenue = total_h2 * 5.0

# -------------------------------------------------------------------------
# KPI METRICS
# -------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    f'<p class="hs-section-header">Project Financing Structure</p>',
    unsafe_allow_html=True,
)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Gross CAPEX", f"£{gross_capex / 1e6:.2f} M")
m2.metric("Grant Received", f"£{grant_amount / 1e6:.2f} M")
m3.metric("Debt (Loan)", f"£{loan_principal / 1e6:.2f} M")
m4.metric("Equity Required", f"£{equity_required / 1e6:.2f} M")

m5, m6, m7, m8 = st.columns(4)
m5.metric("Solar H2 (annual)", f"{solar_h2 / 1000:.1f} t/yr")
m6.metric("Off-peak H2 (annual)", f"{night_h2 / 1000:.1f} t/yr")
m7.metric("Total H2 (annual)", f"{total_h2 / 1000:.1f} t/yr")
m8.metric("Annual Loan Payment", f"£{annual_pmt / 1e6:.2f} M" if loan_principal > 0 else "N/A")

st.markdown("---")

# -------------------------------------------------------------------------
# CASH FLOW CHART
# -------------------------------------------------------------------------
df_cf = pd.DataFrame(index=np.arange(1, project_life + 1))
df_cf["Revenue"] = revenue
df_cf["OPEX"] = -opex
df_cf["EBITDA"] = df_cf["Revenue"] + df_cf["OPEX"]
df_cf["Debt Service"] = 0.0
df_cf.loc[1:loan_term, "Debt Service"] = -annual_pmt
df_cf["Net Equity Cash Flow"] = df_cf["EBITDA"] + df_cf["Debt Service"]
df_cf.loc[1, "Net Equity Cash Flow"] -= equity_required

fig = go.Figure()
fig.add_trace(go.Bar(
    x=df_cf.index, y=df_cf["EBITDA"],
    name="EBITDA", marker_color="#499823",
))
fig.add_trace(go.Bar(
    x=df_cf.index, y=df_cf["Debt Service"],
    name="Debt Service (Loan Payment)", marker_color="#c0392b",
))
fig.add_trace(go.Scatter(
    x=df_cf.index, y=df_cf["Net Equity Cash Flow"].cumsum(),
    mode="lines+markers", name="Cumulative Net Cash Flow",
    line=dict(color="#a7d730", width=3),
    marker=dict(size=5),
))
fig.update_layout(
    barmode="relative",
    title=f"{project_life}-Year Levered Cash Flow",
    xaxis_title="Year",
    yaxis_title="GBP (£)",
)
st.plotly_chart(apply_chart_theme(fig), use_container_width=True)

# -------------------------------------------------------------------------
# DETAILED TABLE
# -------------------------------------------------------------------------
st.subheader("Annual Cash Flow Detail")
df_cf_display = df_cf.copy().reset_index().rename(columns={"index": "Year"})
df_cf_display["Cumulative Net Cash Flow"] = df_cf["Net Equity Cash Flow"].cumsum().values
st.dataframe(
    df_cf_display.style.format({
        "Revenue": "£{:,.0f}",
        "OPEX": "£{:,.0f}",
        "EBITDA": "£{:,.0f}",
        "Debt Service": "£{:,.0f}",
        "Net Equity Cash Flow": "£{:,.0f}",
        "Cumulative Net Cash Flow": "£{:,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
