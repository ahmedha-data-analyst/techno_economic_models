import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"
WORKBOOK_PATH = APP_DIR / "SIF technoeconomic model.xlsx"

# -------------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------------
MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

WATER_RATIO_MAP = {
    "Highly pure": 6.0,
    "Tap water": 1.0,
    "Rainwater": 1.0,
}

PURIFICATION_KWH_PER_M3_MAP = {
    "Highly pure": 3.0,
    "Tap water": 0.0,
    "Rainwater": 0.0,
}

COMPRESSION_KWH_PER_KG_MAP = {
    "None": 0.0,
    "Low (100 bar)": 1.0,
    "Medium (350 bar)": 3.0,
    "High (700 bar)": 6.0,
}

# -------------------------------------------------------------------------
# BRANDING & THEMING
# -------------------------------------------------------------------------
HS_GREEN       = "#a7d730"
HS_GREEN_DARK  = "#499823"
HS_BG          = "#30343c"
HS_BG_DARK     = "#23262d"
HS_BG_CARD     = "#3a3f49"
HS_GREY        = "#8c919a"
HS_WHITE       = "#ffffff"


def inject_hydrostar_css() -> None:
    st.markdown(
        f"""
        <style>
        /* ---- Global background & text ---- */
        .stApp {{
            background-color: {HS_BG};
            color: {HS_WHITE};
        }}

        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {{
            background-color: {HS_BG_DARK};
        }}
        [data-testid="stSidebar"] * {{
            color: {HS_WHITE} !important;
        }}
        [data-testid="stSidebarNav"] a[aria-selected="true"] span {{
            color: {HS_GREEN} !important;
            font-weight: 700;
        }}

        /* ---- Headings ---- */
        h1, h2, h3 {{
            color: {HS_WHITE} !important;
        }}
        h1 span, h2 span, h3 span {{
            color: {HS_WHITE} !important;
        }}

        /* ---- Metric cards ---- */
        [data-testid="stMetric"] {{
            background-color: {HS_BG_CARD};
            border-left: 3px solid {HS_GREEN};
            padding: 12px 16px;
            border-radius: 4px;
        }}
        [data-testid="stMetricLabel"] {{
            color: {HS_GREY} !important;
            font-size: 0.82rem !important;
            font-weight: 500 !important;
            letter-spacing: 0.02em;
        }}
        [data-testid="stMetricValue"] {{
            color: {HS_WHITE} !important;
            font-size: 1.35rem !important;
            font-weight: 700 !important;
        }}

        /* ---- Tabs ---- */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {HS_BG_DARK};
            border-radius: 4px 4px 0 0;
            gap: 2px;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: {HS_GREY} !important;
            background-color: transparent;
            border-radius: 4px 4px 0 0;
            padding: 8px 18px;
        }}
        .stTabs [aria-selected="true"] {{
            color: {HS_GREEN} !important;
            font-weight: 700;
            border-bottom: 2px solid {HS_GREEN} !important;
        }}
        .stTabs [data-baseweb="tab-highlight"] {{
            background-color: {HS_GREEN} !important;
        }}

        /* ---- Expanders ---- */
        [data-testid="stExpander"] summary {{
            color: {HS_GREEN} !important;
            font-weight: 600;
            font-size: 1.0rem;
        }}
        [data-testid="stExpander"] {{
            background-color: {HS_BG_CARD};
            border: 1px solid #4a505a;
            border-radius: 4px;
            margin-bottom: 10px;
        }}

        /* ---- Input widgets ---- */
        [data-testid="stNumberInput"] label,
        [data-testid="stSelectbox"] label,
        [data-testid="stSlider"] label,
        [data-testid="stCheckbox"] label {{
            color: {HS_GREY} !important;
            font-size: 0.88rem !important;
            font-weight: 400;
        }}
        .stNumberInput input, .stTextInput input {{
            background-color: {HS_BG_DARK} !important;
            color: {HS_WHITE} !important;
            border: 1px solid #4a505a !important;
            border-radius: 4px;
        }}
        div[data-baseweb="select"] > div {{
            background-color: {HS_BG_DARK} !important;
            color: {HS_WHITE} !important;
            border: 1px solid #4a505a !important;
        }}

        /* ---- Buttons ---- */
        .stButton > button {{
            background-color: {HS_GREEN};
            color: {HS_BG};
            border: none;
            border-radius: 4px;
            font-weight: 700;
        }}
        .stButton > button:hover {{
            background-color: {HS_GREEN_DARK};
            color: {HS_WHITE};
        }}

        /* ---- Dataframe ---- */
        [data-testid="stDataFrame"] {{
            background-color: {HS_BG_CARD};
        }}
        [data-testid="stDataFrame"] th {{
            background-color: {HS_BG_DARK} !important;
            color: {HS_GREEN} !important;
        }}

        /* ---- Warning / error / info ---- */
        [data-testid="stAlert"] {{
            border-radius: 4px;
        }}

        /* ---- Horizontal rule ---- */
        hr {{
            border-color: {HS_GREEN_DARK};
            opacity: 0.35;
        }}

        /* ---- Section header style ---- */
        .hs-section-header {{
            color: {HS_GREEN};
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            margin-bottom: 8px;
            border-bottom: 1px solid {HS_GREEN_DARK};
            padding-bottom: 5px;
        }}

        /* ---- Hide Streamlit branding ---- */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_chart_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(42,46,54,0.7)",
        font=dict(color=HS_WHITE, family="sans-serif"),
        title_font=dict(color=HS_GREEN, size=14),
        legend=dict(
            bgcolor="rgba(35,38,45,0.8)",
            bordercolor="#4a505a",
            borderwidth=1,
            font=dict(color=HS_WHITE),
        ),
        xaxis=dict(
            gridcolor="#3a3f49",
            zerolinecolor="#4a505a",
            tickfont=dict(color=HS_GREY),
        ),
        yaxis=dict(
            gridcolor="#3a3f49",
            zerolinecolor="#4a505a",
            tickfont=dict(color=HS_GREY),
        ),
    )
    return fig


def render_sidebar_header():
    st.sidebar.markdown("---")


def render_page_header(title: str, subtitle: str = "") -> None:
    """
    Renders a professional branded header card at the top of every page,
    containing the HydroStar logo on the left and the page title on the right.
    """
    import base64

    logo_html = ""
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        logo_html = (
            f'<img class="hs-header-logo" src="data:image/png;base64,{logo_b64}" '
            f'style="width:auto;object-fit:contain;flex-shrink:0;" />'
        )

    subtitle_html = (
        f'<p class="hs-header-subtitle" style="color:{HS_GREY};font-weight:400;margin:6px 0 0 0;">{subtitle}</p>'
        if subtitle else ""
    )

    st.markdown(
        f"""
        <style>
        .hs-header-card {{
            display: flex;
            align-items: center;
            gap: 36px;
            background: linear-gradient(90deg, {HS_BG_DARK} 0%, {HS_BG_CARD} 100%);
            border-left: 8px solid {HS_GREEN};
            border-radius: 6px;
            padding: 28px 44px;
            margin-bottom: 20px;
        }}
        .hs-header-logo {{
            height: 112px;
        }}
        .hs-header-divider {{
            border-left: 1px solid #4a505a;
            padding-left: 36px;
        }}
        .hs-header-title {{
            color: {HS_WHITE};
            font-size: 2.9rem;
            font-weight: 800;
            margin: 0;
            line-height: 1.2;
            letter-spacing: -0.01em;
        }}
        .hs-header-subtitle {{
            font-size: 1.64rem;
        }}

        /* ---- Tablet (≤900px) ---- */
        @media (max-width: 900px) {{
            .hs-header-card {{
                gap: 22px;
                padding: 20px 24px;
            }}
            .hs-header-logo {{
                height: 72px;
            }}
            .hs-header-divider {{
                padding-left: 22px;
            }}
            .hs-header-title {{
                font-size: 1.9rem;
            }}
            .hs-header-subtitle {{
                font-size: 1.05rem;
                margin-top: 4px !important;
            }}
        }}

        /* ---- Mobile (≤600px) ---- */
        @media (max-width: 600px) {{
            .hs-header-card {{
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
                padding: 16px 18px;
                border-left-width: 5px;
            }}
            .hs-header-logo {{
                height: 48px;
            }}
            .hs-header-divider {{
                border-left: none;
                padding-left: 0;
            }}
            .hs-header-title {{
                font-size: 1.4rem;
                letter-spacing: 0;
            }}
            .hs-header-subtitle {{
                font-size: 0.88rem;
                margin-top: 3px !important;
            }}
        }}
        </style>
        <div class="hs-header-card">
            {logo_html}
            <div class="hs-header-divider">
                <p class="hs-header-title">{title}</p>
                {subtitle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------------
# SCENARIO 1 HELPERS
# -------------------------------------------------------------------------

@st.cache_resource
def load_sif_hourly_profiles():
    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            "SIF technoeconomic model.xlsx was not found in the app directory."
        )

    xl = pd.ExcelFile(WORKBOOK_PATH)

    def extract_365x24(sheet_name: str) -> np.ndarray:
        df = pd.read_excel(
            WORKBOOK_PATH,
            sheet_name=sheet_name,
            header=None,
            skiprows=2,
            usecols=range(2, 26),
            nrows=365,
        )
        return df.fillna(0.0).to_numpy(dtype=float)

    sheet_names = set(xl.sheet_names)
    if {"Solar 1MW", "Wind 1MW", "Grid 1MW"}.issubset(sheet_names):
        return {
            "solar_kw": extract_365x24("Solar 1MW"),
            "wind_kw": extract_365x24("Wind 1MW"),
            "grid_kw": extract_365x24("Grid 1MW"),
            "profiles_are_scaled": False,
        }

    if {"Solar scaled", "Wind scaled", "Grid scaled"}.issubset(sheet_names):
        return {
            "solar_kw": extract_365x24("Solar scaled"),
            "wind_kw": extract_365x24("Wind scaled"),
            "grid_kw": extract_365x24("Grid scaled"),
            "profiles_are_scaled": True,
        }

    raise ValueError(
        "Workbook is missing the expected source profile sheets."
    )


def _monthly_sums_from_daily(daily_array: np.ndarray) -> np.ndarray:
    monthly = []
    start_idx = 0
    for days in MONTH_LENGTHS:
        monthly.append(float(np.sum(daily_array[start_idx:start_idx + days])))
        start_idx += days
    return np.array(monthly, dtype=float)


def get_generation_capacity_warning(
    production_method: str,
    solar_mw: float,
    wind_mw: float,
    grid_mw: float,
) -> str | None:
    if production_method == "Solar only" and solar_mw <= 0:
        return "Solar-only production is selected, but solar capacity is 0 MW."
    if production_method == "Wind only" and wind_mw <= 0:
        return "Wind-only production is selected, but wind capacity is 0 MW."
    if production_method == "Grid only" and grid_mw <= 0:
        return "Grid-only production is selected, but grid capacity is 0 MW."
    if production_method == "Solar and wind" and solar_mw <= 0 and wind_mw <= 0:
        return "Solar and wind production is selected, but both renewable capacities are 0 MW."
    return None


def run_sif_green_offport_physics(
    production_method: str,
    solar_mw: float,
    wind_mw: float,
    grid_mw: float,
    electrolyser_mw: float,
    efficiency_kwh_per_kg: float = 53.0,
):
    profiles = load_sif_hourly_profiles()

    if profiles["profiles_are_scaled"]:
        solar_kw = profiles["solar_kw"]
        wind_kw = profiles["wind_kw"]
        grid_kw = profiles["grid_kw"]
    else:
        solar_kw = profiles["solar_kw"] * solar_mw
        wind_kw = profiles["wind_kw"] * wind_mw
        grid_kw = profiles["grid_kw"] * grid_mw

    if production_method == "Solar only":
        total_power_kw = solar_kw
    elif production_method == "Wind only":
        total_power_kw = wind_kw
    elif production_method == "Solar and wind":
        total_power_kw = solar_kw + wind_kw
    elif production_method == "Grid only":
        total_power_kw = grid_kw
    else:
        total_power_kw = grid_kw

    electrolyser_capacity_kw = electrolyser_mw * 1000.0
    electrolyser_max_kg_per_hr = electrolyser_capacity_kw / efficiency_kwh_per_kg

    theoretical_h2_kg = total_power_kw / efficiency_kwh_per_kg
    actual_h2_kg = np.minimum(total_power_kw, electrolyser_capacity_kw) / efficiency_kwh_per_kg

    daily_power_kwh = total_power_kw.sum(axis=1)
    daily_theoretical_h2_kg = theoretical_h2_kg.sum(axis=1)
    daily_actual_h2_kg = actual_h2_kg.sum(axis=1)

    monthly_power_kwh = _monthly_sums_from_daily(daily_power_kwh)
    monthly_theoretical_h2_kg = _monthly_sums_from_daily(daily_theoretical_h2_kg)
    monthly_actual_h2_kg = _monthly_sums_from_daily(daily_actual_h2_kg)

    annual_power_kwh = float(total_power_kw.sum())
    annual_theoretical_h2_kg = float(theoretical_h2_kg.sum())
    annual_actual_h2_kg = float(actual_h2_kg.sum())
    annual_curtailed_kwh = float(((theoretical_h2_kg - actual_h2_kg) * efficiency_kwh_per_kg).sum())
    utilisation_vs_theoretical = (
        annual_actual_h2_kg / annual_theoretical_h2_kg if annual_theoretical_h2_kg > 0 else 0.0
    )
    max_daily_h2_kg = float(daily_actual_h2_kg.max()) if len(daily_actual_h2_kg) > 0 else 0.0
    full_load_utilisation = (
        float(np.minimum(total_power_kw, electrolyser_capacity_kw).sum()) / (electrolyser_capacity_kw * 8760.0)
        if electrolyser_capacity_kw > 0 else 0.0
    )

    return {
        "hourly_total_power_kw": total_power_kw,
        "hourly_theoretical_h2_kg": theoretical_h2_kg,
        "hourly_actual_h2_kg": actual_h2_kg,
        "daily_power_kwh": daily_power_kwh,
        "daily_theoretical_h2_kg": daily_theoretical_h2_kg,
        "daily_actual_h2_kg": daily_actual_h2_kg,
        "monthly_power_kwh": monthly_power_kwh,
        "monthly_theoretical_h2_kg": monthly_theoretical_h2_kg,
        "monthly_actual_h2_kg": monthly_actual_h2_kg,
        "annual_power_kwh": annual_power_kwh,
        "annual_theoretical_h2_kg": annual_theoretical_h2_kg,
        "annual_actual_h2_kg": annual_actual_h2_kg,
        "annual_curtailed_kwh": annual_curtailed_kwh,
        "utilisation_vs_theoretical": utilisation_vs_theoretical,
        "full_load_utilisation": full_load_utilisation,
        "electrolyser_capacity_kw": electrolyser_capacity_kw,
        "electrolyser_max_kg_per_hr": electrolyser_max_kg_per_hr,
        "max_daily_h2_kg": max_daily_h2_kg,
    }


def run_sif_green_offport_utilities(
    hourly_actual_h2_kg: np.ndarray,
    water_source: str,
    compression: str,
):
    water_ratio = WATER_RATIO_MAP[water_source]
    purification_kwh_per_m3 = PURIFICATION_KWH_PER_M3_MAP[water_source]
    compression_kwh_per_kg = COMPRESSION_KWH_PER_KG_MAP[compression]

    hourly_water_demand_l = hourly_actual_h2_kg * 10.0 * water_ratio
    hourly_purification_kwh = (hourly_water_demand_l / 1000.0) * purification_kwh_per_m3
    hourly_compression_kwh = hourly_actual_h2_kg * compression_kwh_per_kg

    daily_water_demand_l = hourly_water_demand_l.sum(axis=1)
    daily_purification_kwh = hourly_purification_kwh.sum(axis=1)
    daily_compression_kwh = hourly_compression_kwh.sum(axis=1)

    monthly_water_demand_l = _monthly_sums_from_daily(daily_water_demand_l)
    monthly_purification_kwh = _monthly_sums_from_daily(daily_purification_kwh)
    monthly_compression_kwh = _monthly_sums_from_daily(daily_compression_kwh)

    annual_water_demand_l = float(hourly_water_demand_l.sum())
    annual_water_demand_m3 = annual_water_demand_l / 1000.0
    annual_purification_kwh = float(hourly_purification_kwh.sum())
    annual_compression_kwh = float(hourly_compression_kwh.sum())

    return {
        "hourly_water_demand_l": hourly_water_demand_l,
        "hourly_purification_kwh": hourly_purification_kwh,
        "hourly_compression_kwh": hourly_compression_kwh,
        "daily_water_demand_l": daily_water_demand_l,
        "daily_purification_kwh": daily_purification_kwh,
        "daily_compression_kwh": daily_compression_kwh,
        "monthly_water_demand_l": monthly_water_demand_l,
        "monthly_purification_kwh": monthly_purification_kwh,
        "monthly_compression_kwh": monthly_compression_kwh,
        "annual_water_demand_l": annual_water_demand_l,
        "annual_water_demand_m3": annual_water_demand_m3,
        "annual_purification_kwh": annual_purification_kwh,
        "annual_compression_kwh": annual_compression_kwh,
    }


def run_sif_green_offport_costs(
    ownership: str,
    production_method: str,
    solar_mw: float,
    wind_mw: float,
    electrolyser_mw: float,
    grid_connection_cost: float,
    land_cost: float,
    installation_cost: float,
    licensing_cost: float,
    water_source: str,
    compression: str,
    tube_trailer_required: str,
    transportation_required: str,
    number_of_operators: int,
    storage_days: float,
    rent_cost: float,
    physics: dict,
    utilities: dict,
    renewable_electricity_cost_mwh: float,
    grid_electricity_cost_mwh: float,
    water_cost_m3: float,
):
    owned = ownership == "Owned"
    includes_solar = production_method in ["Solar only", "Solar and wind"]
    includes_wind = production_method in ["Wind only", "Solar and wind"]

    solar_capex = solar_mw * 600000.0 if owned and includes_solar else 0.0
    solar_bop = solar_capex * 0.10 if owned and includes_solar else 0.0

    wind_capex = wind_mw * 1000000.0 if owned and includes_wind else 0.0
    wind_bop = wind_capex * 0.10 if owned and includes_wind else 0.0

    grid_connection_capex = grid_connection_cost if owned else 0.0

    electrolyser_capex = electrolyser_mw * 700000.0
    bop_capex = electrolyser_capex * 0.10

    compressor_capex = physics["electrolyser_max_kg_per_hr"] * 10000.0 if compression != "None" else 0.0
    storage_capex = physics["max_daily_h2_kg"] * storage_days * 200.0
    water_unit_capex = 50000.0 if water_source == "Highly pure" else 0.0
    tube_trailer_capex = 250000.0 if tube_trailer_required == "Yes" else 0.0

    capex_breakdown = {
        "Solar panels": solar_capex,
        "Solar BOP": solar_bop,
        "Wind turbines": wind_capex,
        "Wind turbine BOP": wind_bop,
        "Grid connection": grid_connection_capex,
        "Electrolyser": electrolyser_capex,
        "Balance of Plant": bop_capex,
        "Compressor": compressor_capex,
        "Storage tanks": storage_capex,
        "Water purification unit": water_unit_capex,
        "40ft tube trailer": tube_trailer_capex,
        "Land purchase": land_cost,
        "Installation costs": installation_cost,
        "Licensing, permitting, planning": licensing_cost,
    }
    total_capex = float(sum(capex_breakdown.values()))

    annual_actual_h2_kg = physics["annual_actual_h2_kg"]

    opex_breakdown = {
        "Solar O&M": solar_capex * 0.01,
        "Wind turbine O&M": wind_capex * 0.01,
        "Electrolyser O&M": electrolyser_capex * 0.01,
        "Compressors O&M": compressor_capex * 0.01,
        "Storage O&M": storage_capex * 0.01,
        "Stack electricity": 0.0 if owned else (annual_actual_h2_kg * 33.33) * (renewable_electricity_cost_mwh / 1000.0),
        "Compression electricity": utilities["annual_compression_kwh"] * (grid_electricity_cost_mwh / 1000.0),
        "Purification electricity": utilities["annual_purification_kwh"] * (grid_electricity_cost_mwh / 1000.0),
        "Water usage": 0.0 if water_source == "Rainwater" else utilities["annual_water_demand_m3"] * water_cost_m3,
        "Transportation cost": annual_actual_h2_kg * 0.75 if transportation_required == "Yes" else 0.0,
        "Rent": rent_cost,
        "Insurance": 25000.0,
        "Operators salaries": number_of_operators * 30000.0,
    }
    total_annual_opex = float(sum(opex_breakdown.values()))

    return {
        "capex_breakdown": capex_breakdown,
        "total_capex": total_capex,
        "opex_breakdown": opex_breakdown,
        "total_annual_opex": total_annual_opex,
    }


def run_sif_green_offport_cashflow(
    project_life: int,
    inflation_rate: float,
    degradation_rate: float,
    tax_rate: float,
    discount_rate: float,
    depreciation_rate: float,
    sale_price_per_kg: float,
    include_carbon_credits: str,
    carbon_credit_price_per_tonne: float,
    annual_actual_h2_kg: float,
    costs: dict,
):
    years = np.arange(0, project_life + 1)

    base_stack_electricity = costs["opex_breakdown"]["Stack electricity"]
    base_compression_electricity = costs["opex_breakdown"]["Compression electricity"]
    base_purification_electricity = costs["opex_breakdown"]["Purification electricity"]
    base_water_usage = costs["opex_breakdown"]["Water usage"]

    base_om_cost = (
        costs["opex_breakdown"]["Solar O&M"]
        + costs["opex_breakdown"]["Wind turbine O&M"]
        + costs["opex_breakdown"]["Electrolyser O&M"]
        + costs["opex_breakdown"]["Compressors O&M"]
        + costs["opex_breakdown"]["Storage O&M"]
    )

    base_further_expenses = (
        costs["opex_breakdown"]["Rent"]
        + costs["opex_breakdown"]["Insurance"]
        + costs["opex_breakdown"]["Operators salaries"]
        + costs["opex_breakdown"]["Transportation cost"]
    )

    stack_electricity = np.zeros(project_life + 1)
    compression_electricity = np.zeros(project_life + 1)
    purification_electricity = np.zeros(project_life + 1)
    water_usage = np.zeros(project_life + 1)
    annual_electricity_cost = np.zeros(project_life + 1)
    om_cost = np.zeros(project_life + 1)
    further_expenses = np.zeros(project_life + 1)
    annual_expenses = np.zeros(project_life + 1)

    green_h2_production = np.zeros(project_life + 1)
    h2_revenue = np.zeros(project_life + 1)
    carbon_credit_revenue = np.zeros(project_life + 1)
    ebitda = np.zeros(project_life + 1)

    depreciation_remaining = np.zeros(project_life + 1)
    annual_depreciation = np.zeros(project_life + 1)
    taxable_income = np.zeros(project_life + 1)
    cumulative_taxable_income = np.zeros(project_life + 1)
    taxes_paid = np.zeros(project_life + 1)
    interest = np.zeros(project_life + 1)
    debt_service = np.zeros(project_life + 1)
    equity_fcf = np.zeros(project_life + 1)

    total_capex = costs["total_capex"]

    for y in range(1, project_life + 1):
        op_year_index = y - 1

        stack_electricity[y] = base_stack_electricity * ((1 + inflation_rate) ** op_year_index)
        compression_electricity[y] = base_compression_electricity * ((1 - degradation_rate) ** op_year_index)
        purification_electricity[y] = base_purification_electricity * ((1 - degradation_rate) ** op_year_index)
        water_usage[y] = base_water_usage * ((1 - degradation_rate) ** op_year_index)

        annual_electricity_cost[y] = (
            stack_electricity[y]
            + compression_electricity[y]
            + purification_electricity[y]
            + water_usage[y]
        )

        om_cost[y] = base_om_cost * ((1 + inflation_rate) ** op_year_index)
        further_expenses[y] = base_further_expenses * ((1 + inflation_rate) ** op_year_index)
        annual_expenses[y] = annual_electricity_cost[y] + om_cost[y] + further_expenses[y]

        green_h2_production[y] = annual_actual_h2_kg * ((1 - degradation_rate) ** op_year_index)
        h2_revenue[y] = green_h2_production[y] * sale_price_per_kg

        if include_carbon_credits == "Yes":
            carbon_credit_revenue[y] = green_h2_production[y] * 6.29 / 1000.0 * carbon_credit_price_per_tonne
        else:
            carbon_credit_revenue[y] = 0.0

        ebitda[y] = h2_revenue[y] + carbon_credit_revenue[y] - annual_expenses[y]

    ebitda[0] = -total_capex

    depreciation_remaining[0] = total_capex
    for y in range(1, project_life + 1):
        depreciation_remaining[y] = depreciation_remaining[y - 1] * (1 - depreciation_rate)
        annual_depreciation[y] = depreciation_remaining[y - 1] - depreciation_remaining[y]

        taxable_income[y] = ebitda[y] - annual_depreciation[y] - interest[y]
        cumulative_taxable_income[y] = cumulative_taxable_income[y - 1] + taxable_income[y]
        taxes_paid[y] = taxable_income[y] * tax_rate if cumulative_taxable_income[y] > 0 else 0.0
        equity_fcf[y] = ebitda[y] - taxes_paid[y] - debt_service[y]

    equity_fcf[0] = -total_capex

    cumulative_cash_flow = np.cumsum(equity_fcf)
    payback_period = int((cumulative_cash_flow[1:] < 0).sum())

    ebitda_irr = npf.irr(ebitda) * 100.0 if len(ebitda) > 1 else np.nan
    equity_after_tax_irr = npf.irr(equity_fcf) * 100.0 if len(equity_fcf) > 1 else np.nan
    npv = npf.npv(discount_rate, equity_fcf[1:]) + equity_fcf[0]

    cashflow_df = pd.DataFrame({
        "Year": years,
        "Stack electricity": stack_electricity,
        "Compression electricity": compression_electricity,
        "Purification electricity": purification_electricity,
        "Water demand cost": water_usage,
        "Annual electricity cost": annual_electricity_cost,
        "O&M cost": om_cost,
        "Further expenses": further_expenses,
        "Annual expenses": annual_expenses,
        "Green H2 production (kg)": green_h2_production,
        "Hydrogen revenue": h2_revenue,
        "Carbon credit revenue": carbon_credit_revenue,
        "EBITDA": ebitda,
        "Depreciation remaining": depreciation_remaining,
        "Annual depreciation": annual_depreciation,
        "Taxable income": taxable_income,
        "Cumulative taxable income": cumulative_taxable_income,
        "Taxes paid": taxes_paid,
        "Interest": interest,
        "Debt service": debt_service,
        "Equity free cash flow": equity_fcf,
        "Cumulative cash flow": cumulative_cash_flow,
    })

    return {
        "cashflow_df": cashflow_df,
        "ebitda_irr": ebitda_irr,
        "equity_after_tax_irr": equity_after_tax_irr,
        "npv": npv,
        "payback_period": payback_period,
    }


# -------------------------------------------------------------------------
# SCENARIO 3 HELPER
# -------------------------------------------------------------------------

def simulate_8760_profiles(solar_mw, wind_mw, electrolyser_mw, efficiency_kwh_kg=53.0):
    hours = np.arange(8760)

    daily_cycle = np.clip(np.sin(2 * np.pi * (hours - 6) / 24), 0, 1)
    seasonal_cycle = 0.5 + 0.5 * np.sin(2 * np.pi * (hours - 2160) / 8760)
    solar_kw = solar_mw * 1000 * daily_cycle * seasonal_cycle * 0.7

    rng = np.random.default_rng(42)
    wind_kw = wind_mw * 1000 * np.clip(
        (np.sin(2 * np.pi * hours / 168) + rng.normal(0, 0.5, 8760)),
        0,
        1,
    ) * 0.4

    total_power_kw = solar_kw + wind_kw
    electrolyser_capacity_kw = electrolyser_mw * 1000

    power_used_kw = np.minimum(total_power_kw, electrolyser_capacity_kw)
    curtailed_power_kw = total_power_kw - power_used_kw
    h2_produced_kg = power_used_kw / efficiency_kwh_kg

    return {
        "Annual_H2_kg": np.sum(h2_produced_kg),
        "Annual_Power_Used_kWh": np.sum(power_used_kw),
        "Annual_Curtailed_kWh": np.sum(curtailed_power_kw),
        "Utilisation_Factor": np.sum(power_used_kw) / (electrolyser_capacity_kw * 8760) if electrolyser_mw > 0 else 0,
    }
