import streamlit as st
import pandas as pd
import numpy as np
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
discount_rate = st.sidebar.number_input("Discount Rate / WACC (%)", 1.0, 15.0, 10.0, 0.5) / 100
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

_cf_df = cashflow["cashflow_df"]
npv_costs = costs["total_capex"] + sum(
    _cf_df.loc[_cf_df["Year"] == year, "Annual expenses"].iloc[0]
    for year in range(1, project_life + 1)
)
npv_h2 = sum(
    physics["annual_actual_h2_kg"] * ((1 - degradation) ** (year - 1))
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
m5.metric("Pre-tax IRR", f"{cashflow['ebitda_irr']:,.2f}%")
m6.metric("Post-tax IRR", f"{cashflow['equity_after_tax_irr']:,.2f}%")

m7, m8, m9, m10, m11, m12 = st.columns(6)
m7.metric("Payback Period", f"{cashflow['payback_period']} years")
m8.metric("NPV", f"£{cashflow['npv'] / 1e6:,.2f} M")
m9.metric("Annual Water Demand", f"{utilities['annual_water_demand_m3']:,.1f} m3")
m10.metric("Purification Demand", f"{utilities['annual_purification_kwh'] / 1000:,.2f} MWh")
m11.metric("Compression Demand", f"{utilities['annual_compression_kwh'] / 1000:,.2f} MWh")
m12.metric("Actual / Theoretical", f"{physics['utilisation_vs_theoretical'] * 100:,.2f}%")

# m13, m14, _, _, _, _ = st.columns(6)
# m13.metric("Lifetime Costs", f"£{npv_costs / 1e6:,.2f} M")
# m14.metric("Lifetime H2", f"{npv_h2 / 1000:,.1f} t")

st.markdown("---")
# -------------------------------------------------------------------------
# OUTPUT TABS
# -------------------------------------------------------------------------
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Physics", "Utilities", "CAPEX / OPEX", "Cash Flow", "Monthly Outputs"])

# =========================================================================
# TAB 1 — PHYSICS
# =========================================================================
with tab1:

    # --- Row 1: Monthly H2 production (stacked actual + curtailed) & daily H2 ---
    col_a, col_b = st.columns(2)

    with col_a:
        monthly_curtailed = physics["monthly_theoretical_h2_kg"] - physics["monthly_actual_h2_kg"]
        df_monthly_h2 = pd.DataFrame({
            "Month": month_names,
            "Actual H2 (kg)": physics["monthly_actual_h2_kg"],
            "Curtailed / unused (kg)": monthly_curtailed,
        })
        fig_h2 = go.Figure()
        fig_h2.add_bar(
            x=df_monthly_h2["Month"], y=df_monthly_h2["Actual H2 (kg)"],
            name="Actual H2 produced", marker_color="#a7d730",
        )
        fig_h2.add_bar(
            x=df_monthly_h2["Month"], y=df_monthly_h2["Curtailed / unused (kg)"],
            name="Curtailed / electrolyser limit", marker_color="#4a505a",
        )
        fig_h2.update_layout(
            barmode="stack",
            title="Monthly H2 Production — Actual vs Curtailed",
            yaxis_title="kg H2",
        )
        st.plotly_chart(apply_chart_theme(fig_h2), use_container_width=True, key="fig_h2")

    with col_b:
        # Daily actual H2 output only — clean single series
        fig_daily_h2 = go.Figure()
        fig_daily_h2.add_scatter(
            x=np.arange(1, 366),
            y=physics["daily_actual_h2_kg"],
            mode="lines",
            name="Daily H2 (kg)",
            line=dict(color="#a7d730", width=1),
            fill="tozeroy",
            fillcolor="rgba(167,215,48,0.15)",
        )
        fig_daily_h2.update_layout(
            title="Daily Actual H2 Output (full year)",
            xaxis_title="Day of year",
            yaxis_title="kg H2",
        )
        st.plotly_chart(apply_chart_theme(fig_daily_h2), use_container_width=True, key="fig_daily_h2")

    # --- Row 2: Daily power heatmap & electrolyser utilisation by month ---
    col_c, col_d = st.columns(2)

    with col_c:
        # Reshape daily power into 52 weeks × 7 days heatmap (trim to 364 days)
        daily_power = physics["daily_power_kwh"][:364]
        heatmap_data = daily_power.reshape(52, 7)
        fig_heatmap = go.Figure(go.Heatmap(
            z=heatmap_data,
            x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            y=[f"W{w+1}" for w in range(52)],
            colorscale=[[0, "#23262d"], [0.5, "#499823"], [1.0, "#a7d730"]],
            showscale=True,
            colorbar=dict(title="kWh", tickfont=dict(color="#8c919a")),
        ))
        fig_heatmap.update_layout(
            title="Power Generation Heatmap (Week × Day)",
            xaxis_title="Day of week",
            yaxis_title="Week of year",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(apply_chart_theme(fig_heatmap), use_container_width=True, key="fig_heatmap")

    with col_d:
        # Monthly electrolyser utilisation (actual H2 / theoretical H2 per month)
        monthly_util = np.where(
            physics["monthly_theoretical_h2_kg"] > 0,
            physics["monthly_actual_h2_kg"] / physics["monthly_theoretical_h2_kg"] * 100,
            0.0,
        )
        fig_util = go.Figure()
        fig_util.add_bar(
            x=month_names,
            y=monthly_util,
            marker_color=["#a7d730" if v >= 95 else "#499823" if v >= 70 else "#8c919a" for v in monthly_util],
            name="Utilisation (%)",
        )
        fig_util.add_hline(
            y=float(np.mean(monthly_util)),
            line_dash="dash",
            line_color="#ffffff",
            annotation_text=f"Avg {float(np.mean(monthly_util)):.1f}%",
            annotation_font_color="#ffffff",
        )
        fig_util.update_layout(
            title="Monthly Electrolyser Utilisation (Actual / Theoretical)",
            yaxis_title="%",
            yaxis=dict(range=[0, 105]),
        )
        st.plotly_chart(apply_chart_theme(fig_util), use_container_width=True, key="fig_util")

    # --- Row 3: Full-year hourly heatmap of actual H2 production ---
    st.markdown(f'<p class="hs-section-header">Hourly H2 Production Profile — Full Year</p>', unsafe_allow_html=True)
    hourly_h2 = physics["hourly_actual_h2_kg"]  # shape (365, 24)
    fig_hourly = go.Figure(go.Heatmap(
        z=hourly_h2,
        x=[f"{h:02d}:00" for h in range(24)],
        y=[f"Day {d+1}" for d in range(365)],
        colorscale=[[0, "#23262d"], [0.4, "#499823"], [1.0, "#a7d730"]],
        showscale=True,
        colorbar=dict(title="kg H2/hr", tickfont=dict(color="#8c919a")),
    ))
    fig_hourly.update_layout(
        title="Hourly H2 Production — Day of Year vs Hour of Day",
        xaxis_title="Hour of day",
        yaxis_title="Day of year",
        height=450,
        yaxis=dict(autorange="reversed", tickfont=dict(color="#8c919a")),
    )
    st.plotly_chart(apply_chart_theme(fig_hourly), use_container_width=True, key="fig_hourly")


# =========================================================================
# TAB 2 — UTILITIES
# =========================================================================
with tab2:

    # --- Row 1: Monthly water demand & monthly electricity demand (separate axes) ---
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        fig_water = go.Figure()
        fig_water.add_bar(
            x=month_names,
            y=utilities["monthly_water_demand_l"] / 1000.0,
            name="Water demand (m³)",
            marker_color="#a7d730",
        )
        fig_water.update_layout(
            title="Monthly Water Demand",
            yaxis_title="m³",
        )
        st.plotly_chart(apply_chart_theme(fig_water), use_container_width=True, key="fig_water")

    with col_u2:
        fig_elec = go.Figure()
        fig_elec.add_bar(
            x=month_names,
            y=utilities["monthly_purification_kwh"] / 1000.0,
            name="Purification (MWh)",
            marker_color="#499823",
        )
        fig_elec.add_bar(
            x=month_names,
            y=utilities["monthly_compression_kwh"] / 1000.0,
            name="Compression (MWh)",
            marker_color="#a7d730",
        )
        fig_elec.update_layout(
            barmode="stack",
            title="Monthly Electricity Demand — Purification & Compression",
            yaxis_title="MWh",
        )
        st.plotly_chart(apply_chart_theme(fig_elec), use_container_width=True, key="fig_elec")

    # --- Row 2: Water demand intensity (m³ per kg H2) & cumulative water ---
    col_u3, col_u4 = st.columns(2)

    with col_u3:
        # Water intensity: m³ per tonne H2 produced per month
        monthly_h2_t = physics["monthly_actual_h2_kg"] / 1000.0
        monthly_water_m3 = utilities["monthly_water_demand_l"] / 1000.0
        water_intensity = np.where(monthly_h2_t > 0, monthly_water_m3 / monthly_h2_t, 0.0)
        fig_intensity = go.Figure()
        fig_intensity.add_scatter(
            x=month_names,
            y=water_intensity,
            mode="lines+markers",
            name="m³ water / tonne H2",
            line=dict(color="#a7d730", width=2),
            marker=dict(color="#a7d730", size=7),
        )
        fig_intensity.update_layout(
            title="Water Intensity (m³ per tonne H2)",
            yaxis_title="m³ / t H2",
        )
        st.plotly_chart(apply_chart_theme(fig_intensity), use_container_width=True, key="fig_intensity")

    with col_u4:
        # Cumulative water demand across the year
        cumulative_water = np.cumsum(utilities["monthly_water_demand_l"] / 1000.0)
        fig_cum_water = go.Figure()
        fig_cum_water.add_scatter(
            x=month_names,
            y=cumulative_water,
            mode="lines+markers",
            name="Cumulative water (m³)",
            line=dict(color="#499823", width=2),
            fill="tozeroy",
            fillcolor="rgba(73,152,35,0.15)",
            marker=dict(color="#499823", size=7),
        )
        fig_cum_water.update_layout(
            title="Cumulative Annual Water Demand",
            yaxis_title="m³",
        )
        st.plotly_chart(apply_chart_theme(fig_cum_water), use_container_width=True, key="fig_cum_water")

    # --- Row 3: Annual utility summary table ---
    st.markdown(f'<p class="hs-section-header">Annual Utility Summary</p>', unsafe_allow_html=True)
    df_utils_summary = pd.DataFrame({
        "Utility": ["Water demand", "Purification electricity", "Compression electricity",
                    "Total auxiliary electricity"],
        "Annual value": [
            f"{utilities['annual_water_demand_m3']:,.1f}",
            f"{utilities['annual_purification_kwh'] / 1000.0:,.2f}",
            f"{utilities['annual_compression_kwh'] / 1000.0:,.2f}",
            f"{(utilities['annual_purification_kwh'] + utilities['annual_compression_kwh']) / 1000.0:,.2f}",
        ],
        "Unit": ["m³", "MWh", "MWh", "MWh"],
    })
    st.dataframe(df_utils_summary, use_container_width=True, hide_index=True)


# =========================================================================
# TAB 3 — CAPEX / OPEX
# =========================================================================
with tab3:

    # --- Row 1: Horizontal bar charts (much easier to read than pie for many items) ---
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        capex_items = {k: v for k, v in costs["capex_breakdown"].items() if v > 0}
        if capex_items:
            fig_capex = go.Figure(go.Bar(
                x=list(capex_items.values()),
                y=list(capex_items.keys()),
                orientation="h",
                marker=dict(
                    color=list(capex_items.values()),
                    colorscale=[[0, "#499823"], [1, "#a7d730"]],
                    showscale=False,
                ),
                text=[f"£{v:,.0f}" for v in capex_items.values()],
                textposition="outside",
                textfont=dict(color="#ffffff", size=11),
            ))
            fig_capex.update_layout(
                title=f"CAPEX Breakdown  —  Total £{costs['total_capex']:,.0f}",
                xaxis_title="£",
                yaxis=dict(autorange="reversed"),
                margin=dict(l=180),
                height=380,
            )
            st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True, key="fig_capex")

    with col_c2:
        opex_items = {k: v for k, v in costs["opex_breakdown"].items() if v > 0}
        if opex_items:
            fig_opex = go.Figure(go.Bar(
                x=list(opex_items.values()),
                y=list(opex_items.keys()),
                orientation="h",
                marker=dict(
                    color=list(opex_items.values()),
                    colorscale=[[0, "#499823"], [1, "#a7d730"]],
                    showscale=False,
                ),
                text=[f"£{v:,.0f}" for v in opex_items.values()],
                textposition="outside",
                textfont=dict(color="#ffffff", size=11),
            ))
            fig_opex.update_layout(
                title=f"Year 1 OPEX Breakdown  —  Total £{costs['total_annual_opex']:,.0f}",
                xaxis_title="£",
                yaxis=dict(autorange="reversed"),
                margin=dict(l=210),
                height=380,
            )
            st.plotly_chart(apply_chart_theme(fig_opex), use_container_width=True, key="fig_opex")

    # --- Row 2: OPEX evolution over project life (inflation + degradation effects) ---
    df_cf_costs = cashflow["cashflow_df"][cashflow["cashflow_df"]["Year"] >= 1]
    col_c3, col_c4 = st.columns(2)

    with col_c3:
        fig_opex_trend = go.Figure()
        fig_opex_trend.add_scatter(
            x=df_cf_costs["Year"],
            y=df_cf_costs["Annual electricity cost"],
            name="Electricity cost",
            mode="lines",
            stackgroup="one",
            line=dict(color="#499823"),
            fillcolor="rgba(73,152,35,0.6)",
        )
        fig_opex_trend.add_scatter(
            x=df_cf_costs["Year"],
            y=df_cf_costs["O&M cost"],
            name="O&M cost",
            mode="lines",
            stackgroup="one",
            line=dict(color="#a7d730"),
            fillcolor="rgba(167,215,48,0.6)",
        )
        fig_opex_trend.add_scatter(
            x=df_cf_costs["Year"],
            y=df_cf_costs["Further expenses"],
            name="Rent / insurance / operators",
            mode="lines",
            stackgroup="one",
            line=dict(color="#8c919a"),
            fillcolor="rgba(140,145,154,0.6)",
        )
        fig_opex_trend.update_layout(
            title="OPEX Evolution Over Project Life",
            xaxis_title="Year",
            yaxis_title="£ / year",
        )
        st.plotly_chart(apply_chart_theme(fig_opex_trend), use_container_width=True, key="fig_opex_trend")

    with col_c4:
        # CAPEX vs lifetime OPEX waterfall-style comparison
        lifetime_opex = float(df_cf_costs["Annual expenses"].sum())
        fig_lifetime = go.Figure(go.Bar(
            x=["Total CAPEX", "Lifetime OPEX", "Lifetime Costs"],
            y=[costs["total_capex"], lifetime_opex, costs["total_capex"] + lifetime_opex],
            marker_color=["#499823", "#a7d730", "#ffffff"],
            text=[
                f"£{costs['total_capex'] / 1e6:.2f}M",
                f"£{lifetime_opex / 1e6:.2f}M",
                f"£{(costs['total_capex'] + lifetime_opex) / 1e6:.2f}M",
            ],
            textposition="outside",
            textfont=dict(color="#ffffff"),
        ))
        fig_lifetime.update_layout(
            title="CAPEX vs Lifetime OPEX vs Total Lifetime Cost",
            yaxis_title="£",
            showlegend=False,
        )
        st.plotly_chart(apply_chart_theme(fig_lifetime), use_container_width=True, key="fig_lifetime")

    # --- Row 3: Itemised tables with totals ---
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        capex_vals = list(costs["capex_breakdown"].values())
        capex_keys = list(costs["capex_breakdown"].keys())
        st.dataframe(
            pd.DataFrame({
                "CAPEX item": capex_keys + ["TOTAL"],
                "Value (£)": [f"£{v:,.0f}" for v in capex_vals] + [f"£{costs['total_capex']:,.0f}"],
            }),
            use_container_width=True,
            hide_index=True,
        )
    with col_t2:
        opex_vals = list(costs["opex_breakdown"].values())
        opex_keys = list(costs["opex_breakdown"].keys())
        st.dataframe(
            pd.DataFrame({
                "OPEX item": opex_keys + ["TOTAL (Year 1)"],
                "Year 1 value (£)": [f"£{v:,.0f}" for v in opex_vals] + [f"£{costs['total_annual_opex']:,.0f}"],
            }),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================================
# TAB 4 — CASH FLOW
# =========================================================================
with tab4:
    df_cf = cashflow["cashflow_df"]
    df_ops = df_cf[df_cf["Year"] >= 1]

    # --- Row 1: Revenue vs Expenses stacked + FCF line ---
    fig_rev = go.Figure()
    fig_rev.add_bar(
        x=df_ops["Year"],
        y=df_ops["Hydrogen revenue"],
        name="H2 revenue",
        marker_color="#a7d730",
    )
    if df_ops["Carbon credit revenue"].sum() > 0:
        fig_rev.add_bar(
            x=df_ops["Year"],
            y=df_ops["Carbon credit revenue"],
            name="Carbon credit revenue",
            marker_color="#499823",
        )
    fig_rev.add_bar(
        x=df_ops["Year"],
        y=-df_ops["Annual expenses"],
        name="Annual expenses",
        marker_color="#8c919a",
    )
    fig_rev.add_bar(
        x=df_ops["Year"],
        y=-df_ops["Taxes paid"],
        name="Taxes paid",
        marker_color="#4a505a",
    )
    fig_rev.add_scatter(
        x=df_ops["Year"],
        y=df_ops["Equity free cash flow"],
        name="Equity FCF",
        mode="lines+markers",
        line=dict(color="#ffffff", width=2, dash="dot"),
        marker=dict(color="#ffffff", size=5),
    )
    fig_rev.update_layout(
        barmode="relative",
        title="Annual Revenue vs Expenses & Equity Free Cash Flow",
        xaxis_title="Year",
        yaxis_title="£",
    )
    st.plotly_chart(apply_chart_theme(fig_rev), use_container_width=True, key="fig_rev")

    # --- Row 2: Cumulative cash flow with payback annotation + depreciation ---
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        payback_yr = cashflow["payback_period"]
        fig_cum = go.Figure()
        # Colour bars green above zero, red below
        bar_colors = ["#a7d730" if v >= 0 else "#e05c5c" for v in df_cf["Cumulative cash flow"]]
        fig_cum.add_bar(
            x=df_cf["Year"],
            y=df_cf["Cumulative cash flow"],
            name="Cumulative cash flow",
            marker_color=bar_colors,
        )
        fig_cum.add_hline(y=0, line_color="#ffffff", line_dash="dash", line_width=1)
        if 0 < payback_yr <= project_life:
            fig_cum.add_vline(
                x=payback_yr,
                line_color="#a7d730",
                line_dash="dot",
                annotation_text=f"Payback Yr {payback_yr}",
                annotation_font_color="#a7d730",
                annotation_position="top right",
            )
        fig_cum.update_layout(
            title="Cumulative Cash Flow & Payback",
            xaxis_title="Year",
            yaxis_title="£",
        )
        st.plotly_chart(apply_chart_theme(fig_cum), use_container_width=True, key="fig_cum")

    with col_f2:
        fig_dep = go.Figure()
        fig_dep.add_scatter(
            x=df_ops["Year"],
            y=df_ops["Depreciation remaining"],
            name="Book value remaining",
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(73,152,35,0.2)",
            line=dict(color="#499823", width=2),
        )
        fig_dep.add_bar(
            x=df_ops["Year"],
            y=df_ops["Annual depreciation"],
            name="Annual depreciation charge",
            marker_color="#a7d730",
            opacity=0.7,
        )
        fig_dep.update_layout(
            title="Asset Depreciation Profile (18% Reducing Balance)",
            xaxis_title="Year",
            yaxis_title="£",
        )
        st.plotly_chart(apply_chart_theme(fig_dep), use_container_width=True, key="fig_dep")

    # --- Row 3: Taxable income and taxes paid ---
    col_f3, col_f4 = st.columns(2)

    with col_f3:
        fig_tax = go.Figure()
        fig_tax.add_bar(
            x=df_ops["Year"],
            y=df_ops["Taxable income"],
            name="Taxable income",
            marker_color=["#a7d730" if v >= 0 else "#e05c5c" for v in df_ops["Taxable income"]],
        )
        fig_tax.add_scatter(
            x=df_ops["Year"],
            y=df_ops["Cumulative taxable income"],
            name="Cumulative taxable income",
            mode="lines+markers",
            line=dict(color="#ffffff", width=2, dash="dot"),
            marker=dict(size=4),
        )
        fig_tax.add_hline(y=0, line_color="#8c919a", line_dash="dash", line_width=1)
        fig_tax.update_layout(
            title="Taxable Income & Loss Carry-Forward",
            xaxis_title="Year",
            yaxis_title="£",
        )
        st.plotly_chart(apply_chart_theme(fig_tax), use_container_width=True, key="fig_tax")

    with col_f4:
        fig_h2_prod = go.Figure()
        fig_h2_prod.add_scatter(
            x=df_ops["Year"],
            y=df_ops["Green H2 production (kg)"] / 1000.0,
            name="H2 production (t)",
            mode="lines+markers",
            fill="tozeroy",
            fillcolor="rgba(167,215,48,0.15)",
            line=dict(color="#a7d730", width=2),
            marker=dict(size=5),
        )
        fig_h2_prod.update_layout(
            title="Annual H2 Production Over Project Life (with degradation)",
            xaxis_title="Year",
            yaxis_title="tonnes H2",
        )
        st.plotly_chart(apply_chart_theme(fig_h2_prod), use_container_width=True, key="fig_h2_prod")

    # --- Key cashflow table (subset of most useful columns) ---
    st.markdown(f'<p class="hs-section-header">Cash Flow Summary Table</p>', unsafe_allow_html=True)
    df_cf_display = df_cf[[
        "Year", "Green H2 production (kg)", "Hydrogen revenue", "Annual expenses",
        "EBITDA", "Annual depreciation", "Taxes paid", "Equity free cash flow", "Cumulative cash flow",
    ]].copy()
    for col in df_cf_display.columns[1:]:
        df_cf_display[col] = df_cf_display[col].map(lambda x: f"£{x:,.0f}")
    st.dataframe(df_cf_display, use_container_width=True, hide_index=True)


# =========================================================================
# TAB 5 — MONTHLY OUTPUTS
# =========================================================================
with tab5:

    # --- Row 1: Power available vs H2 produced monthly ---
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        fig_monthly_power = go.Figure()
        fig_monthly_power.add_bar(
            x=month_names,
            y=physics["monthly_power_kwh"] / 1000.0,
            name="Power available (MWh)",
            marker_color="#8c919a",
            opacity=0.8,
        )
        fig_monthly_power.add_scatter(
            x=month_names,
            y=physics["monthly_actual_h2_kg"],
            name="Actual H2 (kg)",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color="#a7d730", width=2),
            marker=dict(size=7),
        )
        fig_monthly_power.update_layout(
            title="Monthly Power Available vs H2 Produced",
            yaxis=dict(title=dict(text="MWh", font=dict(color="#8c919a"))),
            yaxis2=dict(title=dict(text="kg H2", font=dict(color="#a7d730")), overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99),
        )
        st.plotly_chart(apply_chart_theme(fig_monthly_power), use_container_width=True, key="fig_monthly_power")

    with col_m2:
        # Monthly curtailment as % of theoretical
        monthly_curtail_pct = np.where(
            physics["monthly_theoretical_h2_kg"] > 0,
            (physics["monthly_theoretical_h2_kg"] - physics["monthly_actual_h2_kg"])
            / physics["monthly_theoretical_h2_kg"] * 100,
            0.0,
        )
        fig_curtail = go.Figure()
        fig_curtail.add_bar(
            x=month_names,
            y=monthly_curtail_pct,
            marker_color=["#e05c5c" if v > 5 else "#499823" for v in monthly_curtail_pct],
            name="Curtailment %",
        )
        fig_curtail.update_layout(
            title="Monthly Curtailment (% of Theoretical H2 Lost)",
            yaxis_title="%",
            yaxis=dict(range=[0, max(float(monthly_curtail_pct.max()) * 1.2, 5)]),
        )
        st.plotly_chart(apply_chart_theme(fig_curtail), use_container_width=True, key="fig_curtail")

    # --- Row 2: Monthly water & electricity side by side ---
    col_m3, col_m4 = st.columns(2)

    with col_m3:
        fig_m_water = go.Figure()
        fig_m_water.add_bar(
            x=month_names,
            y=utilities["monthly_water_demand_l"] / 1000.0,
            name="Water demand (m³)",
            marker_color="#a7d730",
        )
        fig_m_water.update_layout(title="Monthly Water Demand", yaxis_title="m³")
        st.plotly_chart(apply_chart_theme(fig_m_water), use_container_width=True, key="fig_m_water")

    with col_m4:
        fig_m_elec = go.Figure()
        fig_m_elec.add_bar(
            x=month_names,
            y=utilities["monthly_purification_kwh"] / 1000.0,
            name="Purification (MWh)",
            marker_color="#499823",
        )
        fig_m_elec.add_bar(
            x=month_names,
            y=utilities["monthly_compression_kwh"] / 1000.0,
            name="Compression (MWh)",
            marker_color="#a7d730",
        )
        fig_m_elec.update_layout(
            barmode="stack",
            title="Monthly Auxiliary Electricity (Purification + Compression)",
            yaxis_title="MWh",
        )
        st.plotly_chart(apply_chart_theme(fig_m_elec), use_container_width=True, key="fig_m_elec")

    # --- Full monthly data table ---
    st.markdown(f'<p class="hs-section-header">Full Monthly Data Table</p>', unsafe_allow_html=True)
    df_monthly = pd.DataFrame({
        "Month": month_names,
        "Power available (MWh)": (physics["monthly_power_kwh"] / 1000.0).round(1),
        "Theoretical H2 (kg)": physics["monthly_theoretical_h2_kg"].round(0).astype(int),
        "Actual H2 (kg)": physics["monthly_actual_h2_kg"].round(0).astype(int),
        "Curtailment (%)": monthly_curtail_pct.round(2),
        "Water demand (m³)": (utilities["monthly_water_demand_l"] / 1000.0).round(1),
        "Purification electricity (MWh)": (utilities["monthly_purification_kwh"] / 1000.0).round(2),
        "Compression electricity (MWh)": (utilities["monthly_compression_kwh"] / 1000.0).round(2),
    })
    st.dataframe(df_monthly, use_container_width=True, hide_index=True)
