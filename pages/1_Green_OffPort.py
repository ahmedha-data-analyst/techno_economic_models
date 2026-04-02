import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from utils import (
    LOGO_PATH,
    inject_hydrostar_css,
    render_sidebar_header,
    render_page_header,
    apply_chart_theme,
    HS_GREEN,
    HS_GREY,
    load_sif_hourly_profiles,
    get_generation_capacity_warning,
    run_sif_green_offport_physics,
    run_sif_green_offport_utilities,
    run_sif_green_offport_costs,
    run_sif_green_offport_cashflow,
)

st.set_page_config(
    page_title="HydroStar — Green OffPort",
    layout="wide",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None,
)

inject_hydrostar_css()
render_sidebar_header()

# -------------------------------------------------------------------------
# SIDEBAR: PROJECT PARAMETERS
# -------------------------------------------------------------------------
st.sidebar.markdown(
    f'<p class="hs-section-header">Project Parameters</p>',
    unsafe_allow_html=True,
)
project_life = st.sidebar.slider("Project Life (Years)", 10, 25, 20)
discount_rate = st.sidebar.number_input("Discount Rate / WACC (%)", 1.0, 15.0, 8.0, 0.5) / 100
inflation_rate = st.sidebar.number_input("Annual Inflation (%)", 0.0, 10.0, 3.5, 0.5) / 100
degradation = st.sidebar.number_input("Annual Degradation (%)", 0.0, 5.0, 0.25, 0.05) / 100

# -------------------------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------------------------
render_page_header(
    "Green OffPort (Portside)",
    "Portside green hydrogen production — hourly solar, wind, and grid generation profiles",
)

# -------------------------------------------------------------------------
# WORKBOOK CHECK
# -------------------------------------------------------------------------
try:
    load_sif_hourly_profiles()
except Exception as exc:
    st.error(str(exc))
    st.stop()

# -------------------------------------------------------------------------
# INPUTS — grouped in expanders
# -------------------------------------------------------------------------
with st.expander("Production & Generation Assets", expanded=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f'<p class="hs-section-header">Production</p>', unsafe_allow_html=True)
        ownership = st.selectbox(
            "Ownership model",
            ["Owned", "Bought under PPA"],
            help="Owned: CAPEX for generation assets is included. PPA: no generation CAPEX, electricity cost applied instead.",
        )
        production_method = st.selectbox(
            "Production method",
            ["Solar only", "Wind only", "Solar and wind", "Grid only"],
        )
        electrolyser_mw = st.number_input(
            "Electrolyser size (MW)", min_value=0.1, max_value=50.0, value=1.0, step=0.1,
            help="Rated capacity of the electrolyser stack.",
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Generation Capacities</p>', unsafe_allow_html=True)
        solar_mw = st.number_input(
            "Solar farm capacity (MW)", min_value=0.0, max_value=50.0, value=2.0, step=0.5,
        )
        wind_mw = st.number_input(
            "Wind turbine capacity (MW)", min_value=0.0, max_value=50.0, value=1.0, step=0.5,
        )
        grid_mw = st.number_input(
            "Grid connection capacity (MW)", min_value=0.0, max_value=50.0, value=1.0, step=0.5,
        )

    with c3:
        st.markdown(f'<p class="hs-section-header">Electrolyser Efficiency</p>', unsafe_allow_html=True)
        efficiency_kwh_per_kg = st.number_input(
            "Electrolyser efficiency (kWh/kg H2)", min_value=40.0, max_value=70.0, value=53.0, step=0.5,
            help="Energy consumption per kg of hydrogen produced.",
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<p style="color:{HS_GREY};font-size:0.86rem;line-height:1.5;">Rated output at full load: '
            f'<b style="color:#fff;">{electrolyser_mw * 1000 / efficiency_kwh_per_kg:.1f} kg H2/hr</b></p>',
            unsafe_allow_html=True,
        )

with st.expander("Utilities & Site Configuration", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f'<p class="hs-section-header">Utilities</p>', unsafe_allow_html=True)
        water_source = st.selectbox(
            "Water source",
            ["Highly pure", "Tap water", "Rainwater"],
            help="Highly pure requires water purification unit (CAPEX + energy). Rainwater/tap are lower cost.",
        )
        compression = st.selectbox(
            "Compression level",
            ["None", "Low (100 bar)", "Medium (350 bar)", "High (700 bar)"],
        )
        storage_days = st.number_input(
            "Onsite storage (days of max production)", min_value=0.0, max_value=30.0, value=1.0, step=0.5,
            help="Number of days of maximum daily H2 production to hold in storage.",
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Site Logistics</p>', unsafe_allow_html=True)
        tube_trailer_required = st.selectbox(
            "40ft tube trailer required?", ["No", "Yes"],
            help="Adds £250,000 to CAPEX if required.",
        )
        transportation_required = st.selectbox(
            "Transportation required?", ["No", "Yes"],
            help="Adds £0.75/kg H2 to annual OPEX if required.",
        )
        number_of_operators = st.number_input(
            "Number of operators", min_value=0, max_value=20, value=0, step=1,
            help="Each operator adds £30,000/yr to OPEX.",
        )

with st.expander("Costs", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f'<p class="hs-section-header">Site & Capital Costs</p>', unsafe_allow_html=True)
        grid_connection_cost = st.number_input(
            "Grid connection cost (£)", min_value=0.0, value=0.0, step=1000.0,
        )
        land_cost = st.number_input(
            "Land purchase (£)", min_value=0.0, value=0.0, step=1000.0,
        )
        installation_cost = st.number_input(
            "Installation costs (£)", min_value=0.0, value=30000.0, step=1000.0,
        )
        licensing_cost = st.number_input(
            "Licensing, permitting & planning (£)", min_value=0.0, value=30000.0, step=1000.0,
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Recurring & Financial</p>', unsafe_allow_html=True)
        rent_cost = st.number_input(
            "Annual rent (£/yr)", min_value=0.0, value=4000.0, step=100.0,
        )
        tax_rate = st.number_input(
            "Corporation tax rate (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0,
        ) / 100.0
        renewable_electricity_cost = st.number_input(
            "Renewables electricity cost (£/MWh)", min_value=0.0, value=80.0, step=1.0,
            help="Used for PPA stack electricity cost.",
        )
        grid_electricity_cost = st.number_input(
            "Grid electricity cost (£/MWh)", min_value=0.0, value=150.0, step=1.0,
            help="Used for compression and purification electricity.",
        )
        water_cost = st.number_input(
            "Water cost (£/m3)", min_value=0.0, value=1.93, step=0.01,
        )

with st.expander("Revenue", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f'<p class="hs-section-header">Hydrogen Sales</p>', unsafe_allow_html=True)
        sale_price = st.number_input(
            "Hydrogen sale price (£/kg)", min_value=0.0, value=7.0, step=0.25,
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Carbon Credits</p>', unsafe_allow_html=True)
        include_carbon_credits = st.selectbox("Include carbon credits?", ["No", "Yes"])
        carbon_credit_price = st.number_input(
            "Carbon credit price (£/tonne CO2)", min_value=0.0, value=75.0, step=1.0,
        )

# -------------------------------------------------------------------------
# VALIDATION WARNING
# -------------------------------------------------------------------------
generation_warning = get_generation_capacity_warning(
    production_method=production_method,
    solar_mw=solar_mw,
    wind_mw=wind_mw,
    grid_mw=grid_mw,
)
if generation_warning:
    st.warning(generation_warning)

# -------------------------------------------------------------------------
# CALCULATIONS
# -------------------------------------------------------------------------
physics = run_sif_green_offport_physics(
    production_method=production_method,
    solar_mw=solar_mw,
    wind_mw=wind_mw,
    grid_mw=grid_mw,
    electrolyser_mw=electrolyser_mw,
    efficiency_kwh_per_kg=efficiency_kwh_per_kg,
)

utilities = run_sif_green_offport_utilities(
    hourly_actual_h2_kg=physics["hourly_actual_h2_kg"],
    water_source=water_source,
    compression=compression,
)

costs = run_sif_green_offport_costs(
    ownership=ownership,
    production_method=production_method,
    solar_mw=solar_mw,
    wind_mw=wind_mw,
    electrolyser_mw=electrolyser_mw,
    grid_connection_cost=grid_connection_cost,
    land_cost=land_cost,
    installation_cost=installation_cost,
    licensing_cost=licensing_cost,
    water_source=water_source,
    compression=compression,
    tube_trailer_required=tube_trailer_required,
    transportation_required=transportation_required,
    number_of_operators=number_of_operators,
    storage_days=storage_days,
    rent_cost=rent_cost,
    physics=physics,
    utilities=utilities,
    renewable_electricity_cost_mwh=renewable_electricity_cost,
    grid_electricity_cost_mwh=grid_electricity_cost,
    water_cost_m3=water_cost,
)

cashflow = run_sif_green_offport_cashflow(
    project_life=project_life,
    inflation_rate=inflation_rate,
    degradation_rate=degradation,
    tax_rate=tax_rate,
    discount_rate=discount_rate,
    depreciation_rate=0.18,
    sale_price_per_kg=sale_price,
    include_carbon_credits=include_carbon_credits,
    carbon_credit_price_per_tonne=carbon_credit_price,
    annual_actual_h2_kg=physics["annual_actual_h2_kg"],
    costs=costs,
)

# Old (commented) approach
 npv_costs = costs["total_capex"] + sum(
     costs["total_annual_opex"] / ((1 + discount_rate) ** year)
     for year in range(1, project_life + 1)
 )

npv_h2 = sum(
    physics["annual_actual_h2_kg"] * ((1 - degradation) ** (year - 1)) / ((1 + discount_rate) ** year)
    for year in range(1, project_life + 1)
)
lcoh = npv_costs / npv_h2 if npv_h2 > 0 else float("nan")

# -------------------------------------------------------------------------
# KPI METRICS
# -------------------------------------------------------------------------
st.markdown("---")
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("LCOH", f"£{lcoh:,.2f}/kg")
m2.metric("Total CAPEX", f"£{costs['total_capex'] / 1e6:,.2f} M")
m3.metric("Annual H2 (actual)", f"{physics['annual_actual_h2_kg'] / 1000:,.2f} t")
m4.metric("Annual H2 (theoretical)", f"{physics['annual_theoretical_h2_kg'] / 1000:,.2f} t")
m5.metric("Pre-tax IRR", f"{npv_costs}%")
m6.metric("Post-tax IRR", f"{npv_h2}%")

m7, m8, m9, m10, m11, m12 = st.columns(6)
m7.metric("Payback Period", f"{cashflow['payback_period']} years")
m8.metric("NPV", f"£{cashflow['npv'] / 1e6:,.2f} M")
m9.metric("Annual Water Demand", f"{utilities['annual_water_demand_m3']:,.1f} m3")
m10.metric("Purification Demand", f"{utilities['annual_purification_kwh'] / 1000:,.2f} MWh")
m11.metric("Compression Demand", f"{utilities['annual_compression_kwh'] / 1000:,.2f} MWh")
m12.metric("Actual / Theoretical", f"{physics['utilisation_vs_theoretical'] * 100:,.2f}%")

st.markdown("---")

# -------------------------------------------------------------------------
# OUTPUT TABS
# -------------------------------------------------------------------------
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Physics", "Utilities", "CAPEX / OPEX", "Cash Flow", "Monthly Outputs"])

with tab1:
    col_a, col_b = st.columns(2)

    with col_a:
        df_monthly_h2 = pd.DataFrame({
            "Month": month_names,
            "Actual H2 (kg)": physics["monthly_actual_h2_kg"],
            "Theoretical H2 (kg)": physics["monthly_theoretical_h2_kg"],
        })
        fig_h2 = px.bar(
            df_monthly_h2,
            x="Month",
            y=["Actual H2 (kg)", "Theoretical H2 (kg)"],
            barmode="group",
            title="Monthly Hydrogen Production",
            color_discrete_sequence=["#a7d730", "#499823"],
        )
        st.plotly_chart(apply_chart_theme(fig_h2), use_container_width=True)

    with col_b:
        df_power = pd.DataFrame({
            "Day": np.arange(1, 366),
            "Daily total power (kWh)": physics["daily_power_kwh"],
            "Daily actual H2 (kg)": physics["daily_actual_h2_kg"],
        })
        fig_power = px.line(
            df_power,
            x="Day",
            y=["Daily total power (kWh)", "Daily actual H2 (kg)"],
            title="Daily Power and Hydrogen Output",
            color_discrete_sequence=["#a7d730", "#499823"],
        )
        st.plotly_chart(apply_chart_theme(fig_power), use_container_width=True)

with tab2:
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        df_utils = pd.DataFrame({
            "Utility": ["Water demand", "Purification electricity", "Compression electricity"],
            "Annual value": [
                utilities["annual_water_demand_m3"],
                utilities["annual_purification_kwh"] / 1000.0,
                utilities["annual_compression_kwh"] / 1000.0,
            ],
            "Unit": ["m3", "MWh", "MWh"],
        })
        st.dataframe(df_utils, use_container_width=True, hide_index=True)

    with col_u2:
        df_monthly_utils = pd.DataFrame({
            "Month": month_names,
            "Water demand (m3)": utilities["monthly_water_demand_l"] / 1000.0,
            "Purification electricity (MWh)": utilities["monthly_purification_kwh"] / 1000.0,
            "Compression electricity (MWh)": utilities["monthly_compression_kwh"] / 1000.0,
        })
        fig_utils = px.bar(
            df_monthly_utils,
            x="Month",
            y=["Water demand (m3)", "Purification electricity (MWh)", "Compression electricity (MWh)"],
            barmode="group",
            title="Monthly Utility Requirements",
            color_discrete_sequence=["#a7d730", "#499823", "#8c919a"],
        )
        st.plotly_chart(apply_chart_theme(fig_utils), use_container_width=True)

with tab3:
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        capex_items = {k: v for k, v in costs["capex_breakdown"].items() if v > 0}
        if capex_items:
            fig_capex = px.pie(
                names=list(capex_items.keys()),
                values=list(capex_items.values()),
                title="CAPEX Breakdown",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Greens_r,
            )
            st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True)

    with col_c2:
        opex_items = {k: v for k, v in costs["opex_breakdown"].items() if v > 0}
        if opex_items:
            fig_opex = px.pie(
                names=list(opex_items.keys()),
                values=list(opex_items.values()),
                title="Year 1 OPEX Breakdown",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Greens_r,
            )
            st.plotly_chart(apply_chart_theme(fig_opex), use_container_width=True)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.dataframe(
            pd.DataFrame({
                "CAPEX item": list(costs["capex_breakdown"].keys()),
                "Value (£)": [f"£{v:,.0f}" for v in costs["capex_breakdown"].values()],
            }),
            use_container_width=True,
            hide_index=True,
        )
    with col_t2:
        st.dataframe(
            pd.DataFrame({
                "OPEX item": list(costs["opex_breakdown"].keys()),
                "Year 1 value (£)": [f"£{v:,.0f}" for v in costs["opex_breakdown"].values()],
            }),
            use_container_width=True,
            hide_index=True,
        )

with tab4:
    df_cf = cashflow["cashflow_df"]

    fig_cf = go.Figure()
    fig_cf.add_bar(
        x=df_cf["Year"],
        y=df_cf["Equity free cash flow"],
        name="Equity Free Cash Flow",
        marker_color="#499823",
    )
    fig_cf.add_scatter(
        x=df_cf["Year"],
        y=df_cf["Cumulative cash flow"],
        mode="lines+markers",
        name="Cumulative Cash Flow",
        line=dict(color="#a7d730", width=2),
        marker=dict(color="#a7d730", size=5),
    )
    fig_cf.update_layout(title="Cash Flow and Cumulative Payback Profile")
    st.plotly_chart(apply_chart_theme(fig_cf), use_container_width=True)

    st.dataframe(df_cf, use_container_width=True, hide_index=True)

with tab5:
    df_monthly = pd.DataFrame({
        "Month": month_names,
        "Power available (kWh)": physics["monthly_power_kwh"],
        "Theoretical H2 (kg)": physics["monthly_theoretical_h2_kg"],
        "Actual H2 (kg)": physics["monthly_actual_h2_kg"],
        "Water demand (m3)": utilities["monthly_water_demand_l"] / 1000.0,
        "Purification electricity (MWh)": utilities["monthly_purification_kwh"] / 1000.0,
        "Compression electricity (MWh)": utilities["monthly_compression_kwh"] / 1000.0,
    })
    st.dataframe(df_monthly, use_container_width=True, hide_index=True)
