import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
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
)

st.set_page_config(
    page_title="HydroStar — Industrial (Babcock)",
    layout="wide",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None,
)

inject_hydrostar_css()
render_sidebar_header()

# -------------------------------------------------------------------------
# SIDEBAR: PROJECT FINANCIAL PARAMETERS
# -------------------------------------------------------------------------
st.sidebar.markdown(
    f'<p class="hs-section-header">Project Parameters</p>',
    unsafe_allow_html=True,
)
project_life_local = st.sidebar.number_input("Project Life (Years)", min_value=1, value=20, step=1)
discount_rate_local = st.sidebar.number_input("Discount Rate (%)", min_value=0.0, value=10.0, step=0.5) / 100
inflation_rate_local = st.sidebar.number_input("Inflation Rate (%)", min_value=0.0, value=3.5, step=0.5) / 100
degradation_local = st.sidebar.number_input("Production Degradation (%)", min_value=0.0, value=0.25, step=0.05) / 100
tax_rate = st.sidebar.number_input("Corporation Tax Rate (%)", min_value=0.0, value=25.0, step=1.0) / 100

# -------------------------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------------------------
render_page_header(
    "Industrial Value Stack Model",
    "Diesel displacement and by-product value stack for industrial hydrogen applications",
)

# -------------------------------------------------------------------------
# INPUTS — grouped in expanders
# -------------------------------------------------------------------------
with st.expander("Electrolyser & Operations", expanded=True):
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f'<p class="hs-section-header">Electrolyser</p>', unsafe_allow_html=True)
        elec_mw = st.number_input("Electrolyser capacity (MW)", min_value=0.1, value=1.0, step=0.1)
        availability = st.number_input(
            "Operating availability (%)",
            min_value=0.0, max_value=1.0, value=0.90, step=0.01, format="%.2f",
            help="Fraction of 8,760 hours the plant runs annually.",
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Efficiency</p>', unsafe_allow_html=True)
        efficiency_kwh_per_kg = 50.0  # fixed constant per workbook
        st.markdown(
            f'<p style="color:{HS_GREY};font-size:0.86rem;">Electrolyser efficiency</p>'
            f'<p style="color:#fff;font-size:1.15rem;font-weight:700;margin:2px 0 10px 0;">50.0 kWh/kg H2</p>',
            unsafe_allow_html=True,
        )
        annual_operating_hours_preview = 8760 * availability
        st.markdown(
            f'<p style="color:{HS_GREY};font-size:0.86rem;">Operating hours/year</p>'
            f'<p style="color:#fff;font-size:1.15rem;font-weight:700;margin:2px 0 0 0;">{annual_operating_hours_preview:,.0f} hrs</p>',
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(f'<p class="hs-section-header">Stack Replacement</p>', unsafe_allow_html=True)
        stack_replacement_cost = st.number_input(
            "Stack replacement cost (£)", min_value=0.0, value=30000.0, step=1000.0,
        )
        stack_life_years = st.number_input(
            "Stack life (Years)", min_value=0.1, value=1.5, step=0.1,
        )

with st.expander("Market Prices", expanded=True):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f'<p class="hs-section-header">Fuel</p>', unsafe_allow_html=True)
        diesel_price = st.number_input("Diesel price (£/L)", min_value=0.0, value=1.31, step=0.01)

    with c2:
        st.markdown(f'<p class="hs-section-header">Electricity</p>', unsafe_allow_html=True)
        electricity_price = st.number_input("Electricity price (£/MWh)", min_value=0.0, value=75.0, step=1.0)

    with c3:
        st.markdown(f'<p class="hs-section-header">Oxygen</p>', unsafe_allow_html=True)
        o2_price = st.number_input("O2 price (£/tonne)", min_value=0.0, value=100.0, step=1.0)

    with c4:
        st.markdown(f'<p class="hs-section-header">Carbon</p>', unsafe_allow_html=True)
        carbon_price = st.number_input("Carbon credit price (£/tCO2e)", min_value=0.0, value=58.19, step=0.01)

with st.expander("By-Products & Wastewater", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f'<p class="hs-section-header">Oxygen</p>', unsafe_allow_html=True)
        oxygen_yield = st.number_input(
            "O2 yield (kg O2 / kg H2)", min_value=0.0, value=8.0, step=0.1,
        )
        oxygen_used_pct = st.number_input(
            "O2 used on-site (%)",
            min_value=0.0, max_value=1.0, value=0.0, step=0.05, format="%.2f",
            help="Fraction consumed on-site. Remainder is sold.",
        )

    with c2:
        st.markdown(f'<p class="hs-section-header">Wastewater</p>', unsafe_allow_html=True)
        wastewater_lph = st.number_input(
            "Wastewater rate (L/hr)", min_value=0.0, value=200.0, step=10.0,
        )

# -------------------------------------------------------------------------
# CONSTANTS (workbook)
# -------------------------------------------------------------------------
diesel_energy_kwh_per_l = 10.7
diesel_engine_eff = 1.0
fuel_cell_eff = 1.0
diesel_emissions_kgco2_per_l = 2.68

electrolyser_capex_rate = 550000.0
bop_pct_of_electrolyser = 0.15
compressor_capex_rate = 10000.0
chiller_unit_cost = 250000.0
storage_unit_cost = 7319.0
storage_units_required = 5
installation_cost = 40000.0
licensing_cost = 40000.0

equipment_om_pct = 0.02
operator_cost = 30000.0
water_cost = 0.0

tanker_capacity_m3 = 30.0
standing_charge_per_visit = 22.0
haulage_cost_per_m3 = 10.0
treatment_gate_fee_per_m3 = 15.27

# -------------------------------------------------------------------------
# CALCULATIONS
# -------------------------------------------------------------------------
annual_operating_hours = 8760 * availability
annual_electricity_mwh = elec_mw * annual_operating_hours
annual_h2 = (annual_electricity_mwh * 1000) / efficiency_kwh_per_kg

diesel_avoided = (annual_h2 * 33.33 * fuel_cell_eff) / (diesel_engine_eff * diesel_energy_kwh_per_l)
annual_diesel_value = diesel_avoided * diesel_price
annual_co2_avoided_t = (diesel_avoided * diesel_emissions_kgco2_per_l) / 1000
annual_carbon_value = annual_co2_avoided_t * carbon_price

wastewater_m3 = (annual_operating_hours * wastewater_lph) / 1000
tankering_visits = np.ceil(wastewater_m3 / tanker_capacity_m3) if wastewater_m3 > 0 else 0
fixed_admin_levy = (tankering_visits * standing_charge_per_visit) / wastewater_m3 if wastewater_m3 > 0 else 0
all_in_avoided_cost_per_m3 = haulage_cost_per_m3 + treatment_gate_fee_per_m3 + fixed_admin_levy
annual_wastewater_value = wastewater_m3 * all_in_avoided_cost_per_m3

oxygen_sold_pct = 1 - oxygen_used_pct
annual_o2_tonnes = (annual_h2 * oxygen_yield / 1000) * oxygen_sold_pct
annual_o2_value = annual_o2_tonnes * o2_price

annual_carbon_output_t = annual_h2 * 5.13 / 1000

production_kg_per_hr = annual_h2 / annual_operating_hours if annual_operating_hours > 0 else 0

electrolyser_capex = electrolyser_capex_rate * elec_mw
bop_capex = electrolyser_capex * bop_pct_of_electrolyser
compressor_capex = compressor_capex_rate * production_kg_per_hr
chiller_capex = chiller_unit_cost
storage_capex = storage_units_required * storage_unit_cost
total_capex = (
    electrolyser_capex + bop_capex + compressor_capex + chiller_capex
    + storage_capex + installation_cost + licensing_cost
)

electrolyser_om = electrolyser_capex * equipment_om_pct
compressor_om = compressor_capex * equipment_om_pct
chiller_om = chiller_capex * equipment_om_pct
storage_om = storage_capex * equipment_om_pct
electrode_deg_om = stack_replacement_cost / stack_life_years if stack_life_years > 0 else 0
electricity_cost = annual_electricity_mwh * electricity_price

annual_opex = (
    electrolyser_om + compressor_om + chiller_om + storage_om
    + electrode_deg_om + electricity_cost + water_cost + operator_cost
)

years = np.arange(project_life_local)
production_multiplier = ((1 + inflation_rate_local) ** years) * ((1 - degradation_local) ** years)
discount_factors = 1 / ((1 + discount_rate_local) ** years)

annual_h2_series = annual_h2 * ((1 - degradation_local) ** years)
discounted_h2_series = annual_h2_series * discount_factors

diesel_series = annual_diesel_value * production_multiplier
carbon_series = annual_carbon_value * production_multiplier
wastewater_series = annual_wastewater_value * production_multiplier
oxygen_series = annual_o2_value * production_multiplier
opex_series = annual_opex * ((1 + inflation_rate_local) ** years)

pv_h2 = annual_h2_series[0] + npf.npv(discount_rate_local, annual_h2_series[1:]) if project_life_local > 0 else 0
pv_opex = opex_series[0] + npf.npv(discount_rate_local, opex_series[1:]) if project_life_local > 0 else 0
pv_capex = total_capex
pv_total_costs = pv_capex + pv_opex
gross_lcoh = pv_total_costs / pv_h2 if pv_h2 > 0 else 0

pv_wastewater = wastewater_series[0] + npf.npv(discount_rate_local, wastewater_series[1:]) if project_life_local > 0 else 0
pv_carbon = carbon_series[0] + npf.npv(discount_rate_local, carbon_series[1:]) if project_life_local > 0 else 0
pv_oxygen = oxygen_series[0] + npf.npv(discount_rate_local, oxygen_series[1:]) if project_life_local > 0 else 0

pv_total_credits = pv_wastewater + pv_carbon + pv_oxygen
net_pv_lifetime_cost = pv_total_costs - pv_total_credits
effective_lcoh = net_pv_lifetime_cost / pv_h2 if pv_h2 > 0 else 0

benefits_series = diesel_series + carbon_series + wastewater_series
expenses_series = opex_series
ebitda_series = benefits_series - expenses_series

depreciation_annual = total_capex / project_life_local if project_life_local > 0 else 0
taxable_income_series = ebitda_series - depreciation_annual
taxes_paid_series = np.where(taxable_income_series > 0, taxable_income_series * tax_rate, 0.0)
after_tax_fcf_series = ebitda_series - taxes_paid_series

cash_flows = np.insert(after_tax_fcf_series, 0, -total_capex)
project_irr = npf.irr(cash_flows)
project_npv = npf.npv(discount_rate_local, cash_flows[1:]) + cash_flows[0]

cumulative_after_tax_cf = np.cumsum(cash_flows)
payback_candidates = np.where(cumulative_after_tax_cf >= 0)[0]
payback_year = int(payback_candidates[0]) if len(payback_candidates) > 0 else None

annual_customer_value = annual_diesel_value + annual_carbon_value + annual_wastewater_value
total_credits_savings_per_kg = gross_lcoh - effective_lcoh if pv_h2 > 0 else 0
diesel_equivalent_cost = annual_diesel_value / annual_h2 if annual_h2 > 0 else 0
green_premium = effective_lcoh - diesel_equivalent_cost
annual_green_premium_cost = green_premium * annual_h2
annual_total_value_stack = annual_customer_value + annual_o2_value
annual_net_customer_value_after_opex = annual_total_value_stack - annual_opex

# -------------------------------------------------------------------------
# KPI METRICS
# -------------------------------------------------------------------------
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Gross LCOH", f"£{gross_lcoh:.2f} / kg")
m2.metric("Total Credits & Savings", f"£{total_credits_savings_per_kg:.2f} / kg")
m3.metric("Effective H2 Cost", f"£{effective_lcoh:.2f} / kg")
m4.metric("Annual H2 Production", f"{annual_h2 / 1000:.1f} t/yr")

m5, m6, m7, m8 = st.columns(4)
m5.metric("Annual Customer Value", f"£{annual_customer_value:,.0f} / yr")
m6.metric("Annual O2 Revenue", f"£{annual_o2_value:,.0f} / yr")
m7.metric("Diesel Equivalent Cost", f"£{diesel_equivalent_cost:.2f} / kg")
m8.metric("Green Premium", f"£{green_premium:.2f} / kg")

m9, m10, m11, m12 = st.columns(4)
m9.metric("Annual Green Premium Cost", f"£{annual_green_premium_cost:,.0f} / yr")
m10.metric("Annual CO2 Avoided", f"{annual_co2_avoided_t:,.1f} tCO2/yr")
m11.metric("IRR", f"{project_irr * 100:.2f}%" if pd.notna(project_irr) else "N/A")
m12.metric("NPV", f"£{project_npv:,.0f}")

st.markdown(
    f"""
    <div style="background:#3a3f49;border-left:3px solid #499823;border-radius:4px;padding:12px 18px;margin:12px 0;font-size:0.88rem;color:#cccccc;line-height:1.8;">
    <b style="color:#fff;">Total CAPEX:</b> £{total_capex:,.0f} &nbsp;&nbsp;|&nbsp;&nbsp;
    <b style="color:#fff;">Annual OPEX:</b> £{annual_opex:,.0f} &nbsp;&nbsp;|&nbsp;&nbsp;
    <b style="color:#fff;">Payback:</b> {payback_year if payback_year is not None else 'No payback within model life'} years &nbsp;&nbsp;|&nbsp;&nbsp;
    <b style="color:#fff;">Wastewater avoided cost:</b> £{all_in_avoided_cost_per_m3:.2f}/m3 &nbsp;&nbsp;|&nbsp;&nbsp;
    <b style="color:#fff;">Diesel displaced:</b> {diesel_avoided:,.0f} L/yr
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# -------------------------------------------------------------------------
# CHARTS
# -------------------------------------------------------------------------
colA, colB = st.columns(2)

with colA:
    value_stack_labels = [
        "OPEX (Cost)", "Diesel Savings", "Wastewater Savings",
        "Carbon Credits", "Oxygen Revenue", "Net Annual Value",
    ]
    value_stack_values = [
        -annual_opex, annual_diesel_value, annual_wastewater_value,
        annual_carbon_value, annual_o2_value, annual_net_customer_value_after_opex,
    ]
    fig_value = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "relative", "total"],
        x=value_stack_labels,
        y=value_stack_values,
        connector={"line": {"color": "#4a505a"}},
        increasing={"marker": {"color": "#a7d730"}},
        decreasing={"marker": {"color": "#c0392b"}},
        totals={"marker": {"color": "#499823"}},
    ))
    fig_value.update_layout(
        title="Annual Operating Cost vs Revenue / Savings Stack (£)",
        yaxis_title="GBP (£)",
    )
    st.plotly_chart(apply_chart_theme(fig_value), use_container_width=True)

with colB:
    lcoh_labels = ["Gross LCOH", "Wastewater Savings", "Carbon Credits", "Oxygen Revenue", "Effective LCOH"]
    lcoh_values = [
        gross_lcoh,
        -(pv_wastewater / pv_h2 if pv_h2 > 0 else 0),
        -(pv_carbon / pv_h2 if pv_h2 > 0 else 0),
        -(pv_oxygen / pv_h2 if pv_h2 > 0 else 0),
        effective_lcoh,
    ]
    fig_lcoh = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "total"],
        x=lcoh_labels,
        y=lcoh_values,
        connector={"line": {"color": "#4a505a"}},
        increasing={"marker": {"color": "#a7d730"}},
        decreasing={"marker": {"color": "#c0392b"}},
        totals={"marker": {"color": "#499823"}},
    ))
    fig_lcoh.update_layout(title="LCOH Waterfall (£/kg)", yaxis_title="£ / kg")
    st.plotly_chart(apply_chart_theme(fig_lcoh), use_container_width=True)

colC, colD = st.columns(2)

with colC:
    capex_breakdown = pd.DataFrame({
        "Category": [
            "Electrolyser", "Balance of Plant", "Compressor",
            "Chiller", "Storage", "Installation", "Licensing",
        ],
        "Value": [
            electrolyser_capex, bop_capex, compressor_capex,
            chiller_capex, storage_capex, installation_cost, licensing_cost,
        ],
    })
    fig_capex = px.pie(
        capex_breakdown, names="Category", values="Value",
        title="CAPEX Breakdown", hole=0.4,
        color_discrete_sequence=px.colors.sequential.Greens_r,
    )
    st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True)

with colD:
    opex_breakdown = pd.DataFrame({
        "Category": [
            "Electricity", "Electrolyser O&M", "Compressor O&M",
            "Chiller O&M", "Storage O&M", "Electrode Degradation", "Operator", "Water",
        ],
        "Value": [
            electricity_cost, electrolyser_om, compressor_om,
            chiller_om, storage_om, electrode_deg_om, operator_cost, water_cost,
        ],
    })
    fig_opex = px.pie(
        opex_breakdown, names="Category", values="Value",
        title="Annual OPEX Breakdown", hole=0.4,
        color_discrete_sequence=px.colors.sequential.Greens_r,
    )
    st.plotly_chart(apply_chart_theme(fig_opex), use_container_width=True)

cf_df = pd.DataFrame({
    "Year": np.arange(0, project_life_local + 1),
    "Net Cash Flow": cash_flows,
    "Cumulative Cash Flow": cumulative_after_tax_cf,
})

fig_cf = go.Figure()
fig_cf.add_trace(go.Bar(
    x=cf_df["Year"], y=cf_df["Net Cash Flow"],
    name="After-Tax Cash Flow", marker_color="#499823",
))
fig_cf.add_trace(go.Scatter(
    x=cf_df["Year"], y=cf_df["Cumulative Cash Flow"],
    mode="lines+markers", name="Cumulative Cash Flow",
    line=dict(color="#a7d730", width=2), marker=dict(size=5),
))
fig_cf.update_layout(title="Project Cash Flow Profile", xaxis_title="Year", yaxis_title="GBP (£)")
st.plotly_chart(apply_chart_theme(fig_cf), use_container_width=True)

total_value_series = benefits_series + oxygen_series
cumulative_total_value = np.cumsum(total_value_series)
cumulative_costs = np.concatenate(([-total_capex], -total_capex + np.cumsum(expenses_series)))

cv_df = pd.DataFrame({
    "Year": np.arange(0, project_life_local + 1),
    "Cum. Total Value": np.concatenate(([0.0], cumulative_total_value)),
    "Cum. Costs": cumulative_costs,
})

fig_cv = go.Figure()
fig_cv.add_trace(go.Scatter(
    x=cv_df["Year"], y=cv_df["Cum. Total Value"],
    mode="lines+markers", name="Cum. Total Value",
    line=dict(color="#a7d730", width=2),
))
fig_cv.add_trace(go.Scatter(
    x=cv_df["Year"], y=cv_df["Cum. Costs"],
    mode="lines+markers", name="Cum. Costs",
    line=dict(color="#c0392b", width=2, dash="dash"),
))
fig_cv.update_layout(
    title=f"Cumulative Value — {project_life_local}-Year Projection (£)",
    xaxis_title="Year", yaxis_title="GBP (£)",
)
st.plotly_chart(apply_chart_theme(fig_cv), use_container_width=True)

# -------------------------------------------------------------------------
# DETAILED TABLE
# -------------------------------------------------------------------------
year_labels = np.arange(project_life_local)
detail_df = pd.DataFrame({
    "Year": year_labels,
    "Annual H2 (kg)": annual_h2_series,
    "Diesel Savings (£)": diesel_series,
    "Carbon Credits (£)": carbon_series,
    "Wastewater Savings (£)": wastewater_series,
    "Oxygen Revenue (£)": oxygen_series,
    "Benefits ex O2 (£)": benefits_series,
    "OPEX (£)": expenses_series,
    "EBITDA (£)": ebitda_series,
    "Taxable Income (£)": taxable_income_series,
    "Taxes Paid (£)": taxes_paid_series,
    "After-Tax FCF (£)": after_tax_fcf_series,
})

st.subheader("Detailed Annual Model Table")
st.dataframe(
    detail_df.style.format({
        "Annual H2 (kg)": "{:,.0f}",
        "Diesel Savings (£)": "£{:,.0f}",
        "Carbon Credits (£)": "£{:,.0f}",
        "Wastewater Savings (£)": "£{:,.0f}",
        "Oxygen Revenue (£)": "£{:,.0f}",
        "Benefits ex O2 (£)": "£{:,.0f}",
        "OPEX (£)": "£{:,.0f}",
        "EBITDA (£)": "£{:,.0f}",
        "Taxable Income (£)": "£{:,.0f}",
        "Taxes Paid (£)": "£{:,.0f}",
        "After-Tax FCF (£)": "£{:,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
