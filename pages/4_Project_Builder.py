import uuid
import math
from datetime import date
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
    load_sif_hourly_profiles,
    get_generation_capacity_warning,
    run_sif_green_offport_physics,
    run_sif_green_offport_utilities,
    run_sif_green_offport_costs,
    run_sif_green_offport_cashflow,
    HS_GREEN,
    HS_GREEN_DARK,
    HS_BG_CARD,
    HS_BG_DARK,
    HS_GREY,
    HS_WHITE,
)

# -------------------------------------------------------------------------
# COFO TYPE COLOURS
# -------------------------------------------------------------------------
COFO_COLOURS = {
    "CAPEX":     "#a7d730",
    "OPEX":      "#8c4fc8",
    "Footprint": "#d4a017",
    "Output":    "#4caf84",
}

CATEGORY_COLOURS = {
    "Hydrogen Production": "#a7d730",
    "Renewable Generation": "#499823",
    "Storage":              "#4caf84",
    "Water Treatment":      "#2196a0",
    "Balance of Plant":     "#8c919a",
    "Green OffPort":        "#a7d730",
}

# Streamlit enforces a minimum text area height of 68px.
COMPACT_TEXT_AREA_HEIGHT = 68
PROJECT_CURRENCY_SYMBOL = "£"
PROJECT_CURRENCY_LABEL = "GBP (£)"
PROJECT_CURRENCY_RATE_LABEL = "GBP/yr"
GREEN_OFFPORT_SOURCE_KIND = "green_offport"
GREEN_OFFPORT_CATEGORY = "Green OffPort"
GREEN_OFFPORT_TYPE = "SIF Green OffPort"
GREEN_OFFPORT_COMPONENT = "Green OffPort Scenario"
SOURCE_GREEN_OFFPORT = "Green OffPort model"
SOURCE_CATALOGUE_ADVANCED = "From Catalogue (Advanced)"
SOURCE_MANUAL_ADVANCED = "Manual entry (Advanced)"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

OUTPUT_SUBTYPE_H2_PRODUCTION = "H2 production (kg/yr)"
OUTPUT_SUBTYPE_H2_COMPRESSION = "H2 compression capacity (kg/yr)"
OUTPUT_SUBTYPE_H2_STORAGE = "H2 storage capacity (kg)"
OUTPUT_SUBTYPE_POWER_GENERATION = "Power generation (MWh/yr)"
OUTPUT_SUBTYPE_WATER_OUTPUT = "Water output (L/hr)"
OUTPUT_SUBTYPE_REVENUE = "Revenue (GBP/yr)"
OUTPUT_SUBTYPE_CO2_AVOIDED = "CO2 avoided (t/yr)"

OPEX_TYPE_COST = "cost_gbp_per_year"
OPEX_TYPE_POWER = "power_kw"
OPEX_TYPE_WATER = "water_l_per_hr"
OPEX_TYPE_OTHER = "other"

OPEX_TYPE_LABELS = {
    OPEX_TYPE_COST: "Cost (GBP/yr)",
    OPEX_TYPE_POWER: "Power (kW)",
    OPEX_TYPE_WATER: "Water (L/hr)",
    OPEX_TYPE_OTHER: "Other",
}

OPEX_TYPE_DEFAULT_UNITS = {
    OPEX_TYPE_COST: "GBP/yr",
    OPEX_TYPE_POWER: "kW",
    OPEX_TYPE_WATER: "L/hr",
    OPEX_TYPE_OTHER: "",
}

GREEN_OFFPORT_PROJECT_DEFAULTS = {
    "degradation_rate_pct": 0.25,
    "tax_rate_pct": 25.0,
    "depreciation_rate_pct": 18.0,
    "h2_sale_price_gbp_per_kg": 7.0,
    "include_carbon_credits": "No",
    "carbon_credit_price_gbp_per_tonne": 75.0,
}

# -------------------------------------------------------------------------
# TECHNOLOGY CATALOGUE
# -------------------------------------------------------------------------
# Each component spec contains: rating metadata + capex_items, opex_items,
# footprint_items, output_items.  Formulas are evaluated with `rating` in scope.
# -------------------------------------------------------------------------
TECH_CATALOGUE = {
    # =========================================================================
    # HYDROGEN PRODUCTION
    # All electrolyser costs are sourced directly from the SIF technoeconomic
    # model (Costs sheet).  Efficiency = 53 kWh/kg, water demand = 10 L/kg H2
    # (direct), x6 for highly-pure pre-treatment (SIF Parameters sheet).
    # CO2 saving = 6.29 kg CO2 per kg H2 (displacing grey H2, SIF Parameters).
    # H2 sale price £7/kg (SIF Control sheet default).
    # =========================================================================
    "Hydrogen Production": {
        "Electrolyser": {
            # ---------------------------------------------------------------
            # HydroStar NextGen — membraneless, no precious metals.
            # £600k/MW from SIF Costs sheet (column I, row 9).
            # BOP 10% of stack CAPEX (SIF model row 10).
            # O&M 1% p.a. of electrolyser CAPEX (SIF Costs row 28: £7k on £700k → 1%).
            # ---------------------------------------------------------------
            "HydroStar NextGen Electrolyser": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Rated electrical input capacity of the HydroStar NextGen membraneless electrolyser (MW)",
                "capex_items": [
                    {"name": "NextGen Stack",           "formula": "rating * 600_000",           "note": "£600k/MW — HydroStar NextGen (SIF Costs sheet, col I)"},
                    {"name": "Balance of Plant",        "formula": "rating * 600_000 * 0.10",    "note": "10% of stack CAPEX (SIF Costs row 10)"},
                    {"name": "Installation & commissioning", "formula": "30_000",                "note": "£30k fixed installation (SIF Control row 20 default)"},
                    {"name": "Licensing & permitting",  "formula": "30_000",                     "note": "£30k fixed licensing/permitting/planning (SIF Control row 21)"},
                ],
                "opex_items": [
                    {"name": "Electrolyser O&M",        "opex_type": "Cost (£/yr)",  "formula": "rating * 600_000 * 0.01",     "unit": "GBP/yr", "note": "1% p.a. of stack CAPEX (SIF Costs row 28)"},
                    {"name": "Annual insurance",        "opex_type": "Cost (£/yr)",  "formula": "25_000",                      "unit": "GBP/yr", "note": "£25k/yr fixed insurance (SIF Costs row 39)"},
                    {"name": "Process water (direct)",  "opex_type": "Water (L/hr)", "formula": "rating * 1_000 / 53.0 * 10.0","unit": "L/hr",   "note": "10 L/kg H2 direct water demand (SIF Parameters row 4)"},
                ],
                "footprint_items": [
                    {"name": "Electrolyser skid",       "formula": "rating * 80",    "note": "80 m²/MW — NextGen compact containerised skid"},
                ],
                "output_items": [
                    {"name": "Green H2 production",  "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_PRODUCTION, "formula": "rating * 1_000 / 53.0 * 8_760",                 "unit": "kg/yr",    "note": "53 kWh/kg at full load, 8,760 hrs/yr (SIF Parameters row 2)"},
                    {"name": "H2 Revenue",           "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,       "formula": "rating * 1_000 / 53.0 * 8_760 * 7.0",           "unit": "GBP/yr",   "note": "£7/kg H2 indicative sale price (SIF Control row 28)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,   "formula": "rating * 1_000 / 53.0 * 8_760 * 6.29 / 1_000",  "unit": "t CO2/yr", "note": "6.29 kg CO2/kg H2 grey H2 displaced (SIF Parameters row 31)"},
                ],
            },
            # ---------------------------------------------------------------
            # PEM Electrolyser — £1M/MW from SIF Costs sheet (col J, row 9).
            # ---------------------------------------------------------------
            "PEM Electrolyser": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Rated electrical input capacity of the PEM electrolyser (MW)",
                "capex_items": [
                    {"name": "PEM Stack",               "formula": "rating * 1_000_000",         "note": "£1M/MW — PEM electrolyser (SIF Costs sheet, col J)"},
                    {"name": "Balance of Plant",        "formula": "rating * 1_000_000 * 0.10",  "note": "10% of stack CAPEX (SIF Costs row 10)"},
                    {"name": "Installation & commissioning", "formula": "30_000",                "note": "£30k fixed installation (SIF Control row 20 default)"},
                    {"name": "Licensing & permitting",  "formula": "30_000",                     "note": "£30k fixed licensing/permitting/planning (SIF Control row 21)"},
                ],
                "opex_items": [
                    {"name": "Electrolyser O&M",        "opex_type": "Cost (£/yr)",  "formula": "rating * 1_000_000 * 0.01",   "unit": "GBP/yr", "note": "1% p.a. of stack CAPEX (SIF Costs row 28)"},
                    {"name": "Annual insurance",        "opex_type": "Cost (£/yr)",  "formula": "25_000",                      "unit": "GBP/yr", "note": "£25k/yr fixed insurance (SIF Costs row 39)"},
                    {"name": "Process water (direct)",  "opex_type": "Water (L/hr)", "formula": "rating * 1_000 / 53.0 * 10.0","unit": "L/hr",   "note": "10 L/kg H2 direct water demand (SIF Parameters row 4)"},
                ],
                "footprint_items": [
                    {"name": "Electrolyser skid",       "formula": "rating * 100",   "note": "100 m²/MW — standard PEM containerised skid"},
                ],
                "output_items": [
                    {"name": "Green H2 production",  "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_PRODUCTION, "formula": "rating * 1_000 / 53.0 * 8_760",                 "unit": "kg/yr",    "note": "53 kWh/kg at full load, 8,760 hrs/yr (SIF Parameters row 2)"},
                    {"name": "H2 Revenue",           "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,       "formula": "rating * 1_000 / 53.0 * 8_760 * 7.0",           "unit": "GBP/yr",   "note": "£7/kg H2 indicative sale price (SIF Control row 28)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,   "formula": "rating * 1_000 / 53.0 * 8_760 * 6.29 / 1_000",  "unit": "t CO2/yr", "note": "6.29 kg CO2/kg H2 grey H2 displaced (SIF Parameters row 31)"},
                ],
            },
            # ---------------------------------------------------------------
            # Alkaline Electrolyser — lower CAPEX but lower efficiency.
            # £550k/MW industry benchmark; O&M 1.5% due to caustic maintenance.
            # ---------------------------------------------------------------
            "Alkaline Electrolyser": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 200.0,
                "rating_step": 0.1,
                "rating_help": "Rated electrical input capacity of the alkaline electrolyser (MW)",
                "capex_items": [
                    {"name": "Alkaline Stack",          "formula": "rating * 550_000",           "note": "£550k/MW — alkaline lower cost than PEM; industry benchmark"},
                    {"name": "Balance of Plant",        "formula": "rating * 550_000 * 0.10",    "note": "10% of stack CAPEX (consistent with SIF model BOP rate)"},
                    {"name": "Installation & commissioning", "formula": "30_000",                "note": "£30k fixed (SIF Control row 20)"},
                    {"name": "Licensing & permitting",  "formula": "30_000",                     "note": "£30k fixed (SIF Control row 21)"},
                ],
                "opex_items": [
                    {"name": "Electrolyser O&M",        "opex_type": "Cost (£/yr)",  "formula": "rating * 550_000 * 0.015",    "unit": "GBP/yr", "note": "1.5% p.a. — alkaline caustic electrolyte requires more maintenance"},
                    {"name": "Annual insurance",        "opex_type": "Cost (£/yr)",  "formula": "25_000",                      "unit": "GBP/yr", "note": "£25k/yr fixed insurance (SIF Costs row 39)"},
                    {"name": "Process water (direct)",  "opex_type": "Water (L/hr)", "formula": "rating * 1_000 / 55.0 * 10.0","unit": "L/hr",   "note": "10 L/kg H2; 55 kWh/kg efficiency (slightly lower than PEM)"},
                ],
                "footprint_items": [
                    {"name": "Electrolyser skid",       "formula": "rating * 130",   "note": "130 m²/MW — larger footprint due to caustic circulation system"},
                ],
                "output_items": [
                    {"name": "Green H2 production",  "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_PRODUCTION, "formula": "rating * 1_000 / 55.0 * 8_760",                 "unit": "kg/yr",    "note": "55 kWh/kg efficiency at full load, 8,760 hrs/yr"},
                    {"name": "H2 Revenue",           "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,       "formula": "rating * 1_000 / 55.0 * 8_760 * 7.0",           "unit": "GBP/yr",   "note": "£7/kg H2 indicative sale price (SIF Control row 28)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,   "formula": "rating * 1_000 / 55.0 * 8_760 * 6.29 / 1_000",  "unit": "t CO2/yr", "note": "6.29 kg CO2/kg H2 (SIF Parameters row 31)"},
                ],
            },
        },
        # -------------------------------------------------------------------
        # COMPRESSOR
        # £10k/kg/hr throughput (SIF Costs sheet row 11).
        # O&M 1% of CAPEX (SIF Costs row 29: £1,887 on £188,679 → 1%).
        # Power: 1 kWh/kg (100 bar), 3 kWh/kg (350 bar), 6 kWh/kg (700 bar)
        # — from SIF Parameters sheet rows 25–28.
        # -------------------------------------------------------------------
        "Compressor": {
            "H2 Compressor — Low (100 bar)": {
                "rating_unit": "kg/hr",
                "rating_default": 19.0,
                "rating_min": 1.0,
                "rating_max": 1000.0,
                "rating_step": 1.0,
                "rating_help": "Throughput capacity of the compressor (kg H2/hr). Typical: 1 MW electrolyser → ~19 kg/hr.",
                "capex_items": [
                    {"name": "Compressor unit",         "formula": "rating * 10_000",            "note": "£10k/kg/hr — SIF Costs sheet row 11"},
                    {"name": "Pipework & valves",       "formula": "rating * 10_000 * 0.05",     "note": "5% of unit CAPEX for interconnecting pipework"},
                ],
                "opex_items": [
                    {"name": "Compressor O&M",          "opex_type": "Cost (£/yr)",  "formula": "rating * 10_000 * 0.01",      "unit": "GBP/yr", "note": "1% p.a. of CAPEX (SIF Costs row 29)"},
                    {"name": "Compression power",       "opex_type": "Power (kW)",   "formula": "rating * 1.0",                "unit": "kW",     "note": "1 kWh/kg H2 to 100 bar (SIF Parameters row 28)"},
                ],
                "footprint_items": [
                    {"name": "Compressor skid",         "formula": "rating * 3",     "note": "3 m²/kg/hr — compact low-pressure skid"},
                ],
                "output_items": [
                    {"name": "Compressed H2 capacity",  "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 8_760", "unit": "kg/yr", "note": "Annual throughput at continuous full-load operation"},
                ],
            },
            "H2 Compressor — Medium (350 bar)": {
                "rating_unit": "kg/hr",
                "rating_default": 19.0,
                "rating_min": 1.0,
                "rating_max": 1000.0,
                "rating_step": 1.0,
                "rating_help": "Throughput capacity of the compressor (kg H2/hr). Typical: 1 MW electrolyser → ~19 kg/hr.",
                "capex_items": [
                    {"name": "Compressor unit",         "formula": "rating * 10_000",            "note": "£10k/kg/hr — SIF Costs sheet row 11"},
                    {"name": "Pipework & valves",       "formula": "rating * 10_000 * 0.05",     "note": "5% of unit CAPEX for interconnecting pipework"},
                ],
                "opex_items": [
                    {"name": "Compressor O&M",          "opex_type": "Cost (£/yr)",  "formula": "rating * 10_000 * 0.01",      "unit": "GBP/yr", "note": "1% p.a. of CAPEX (SIF Costs row 29)"},
                    {"name": "Compression power",       "opex_type": "Power (kW)",   "formula": "rating * 3.0",                "unit": "kW",     "note": "3 kWh/kg H2 to 350 bar (SIF Parameters row 27)"},
                ],
                "footprint_items": [
                    {"name": "Compressor skid",         "formula": "rating * 5",     "note": "5 m²/kg/hr — medium-pressure skid"},
                ],
                "output_items": [
                    {"name": "Compressed H2 capacity",  "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 8_760", "unit": "kg/yr", "note": "Annual throughput at continuous full-load operation"},
                ],
            },
            "H2 Compressor — High (700 bar)": {
                "rating_unit": "kg/hr",
                "rating_default": 19.0,
                "rating_min": 1.0,
                "rating_max": 500.0,
                "rating_step": 1.0,
                "rating_help": "Throughput capacity of the compressor (kg H2/hr). Used for vehicle refuelling (700 bar).",
                "capex_items": [
                    {"name": "Compressor unit",         "formula": "rating * 10_000 * 1.6",      "note": "£16k/kg/hr — high-pressure compressor premium over SIF base"},
                    {"name": "Pipework & valves",       "formula": "rating * 10_000 * 1.6 * 0.05", "note": "5% of unit CAPEX"},
                ],
                "opex_items": [
                    {"name": "Compressor O&M",          "opex_type": "Cost (£/yr)",  "formula": "rating * 10_000 * 1.6 * 0.015","unit": "GBP/yr", "note": "1.5% p.a. — higher wear at 700 bar"},
                    {"name": "Compression power",       "opex_type": "Power (kW)",   "formula": "rating * 6.0",                "unit": "kW",     "note": "6 kWh/kg H2 to 700 bar (SIF Parameters row 25)"},
                ],
                "footprint_items": [
                    {"name": "Compressor skid",         "formula": "rating * 7",     "note": "7 m²/kg/hr — larger high-pressure skid"},
                ],
                "output_items": [
                    {"name": "Compressed H2 capacity",  "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 8_760", "unit": "kg/yr", "note": "Annual throughput at continuous full-load operation"},
                ],
            },
        },
    },

    # =========================================================================
    # RENEWABLE GENERATION
    # Solar: £600k/MWp from SIF Costs row 3.  BOP 10% (row 4 note: 'more
    # specific costing' suggested but 10% is the model default).
    # Wind: £1M/MW (SIF Costs row 5), BOP 10% (row 6).
    # O&M: Solar 1% (row 26 = 0, but utils.py uses 1%), Wind 1% (row 27: £10k
    # on £1M = 1%).  Grid electricity cost £0.15/kWh (SIF Costs row 33).
    # Solar full-load hours: 1,100 hrs/yr (UK average, consistent with SIF
    # profiles).  Wind: 2,600 hrs/yr (UK onshore, consistent with SIF).
    # =========================================================================
    "Renewable Generation": {
        "Solar PV": {
            # ---------------------------------------------------------------
            # Ground-Mounted Solar PV — standard utility-scale bifacial panels.
            # ---------------------------------------------------------------
            "Ground-Mounted Solar PV": {
                "rating_unit": "MWp",
                "rating_default": 2.0,
                "rating_min": 0.1,
                "rating_max": 200.0,
                "rating_step": 0.5,
                "rating_help": "Peak installed capacity of the solar array (MWp DC)",
                "capex_items": [
                    {"name": "Solar panels & inverters","formula": "rating * 600_000",           "note": "£600k/MWp — SIF Costs sheet row 3"},
                    {"name": "Balance of Plant",        "formula": "rating * 600_000 * 0.10",    "note": "10% of panel CAPEX: cabling, mounting, substation (SIF Costs row 4)"},
                    {"name": "Civil works & groundworks","formula": "rating * 600_000 * 0.05",   "note": "5% of panel CAPEX for access roads, drainage, cable trenching"},
                    {"name": "Grid connection",         "formula": "50_000",                     "note": "£50k fixed grid connection cost"},
                ],
                "opex_items": [
                    {"name": "Solar O&M",               "opex_type": "Cost (£/yr)",  "formula": "rating * 600_000 * 0.01",     "unit": "GBP/yr", "note": "1% p.a. of CAPEX — panel cleaning, inverter maintenance, monitoring"},
                    {"name": "Land lease",              "opex_type": "Cost (£/yr)",  "formula": "rating * 5_000",              "unit": "GBP/yr", "note": "£5k/MWp/yr — typical UK solar agricultural lease rate"},
                    {"name": "Site insurance",          "opex_type": "Cost (£/yr)",  "formula": "rating * 1_500",              "unit": "GBP/yr", "note": "£1.5k/MWp/yr all-risks insurance"},
                ],
                "footprint_items": [
                    {"name": "Solar field area",        "formula": "rating * 10_000", "note": "10,000 m²/MWp including inter-row spacing (ground coverage ratio ~35%)"},
                ],
                "output_items": [
                    {"name": "Annual generation",    "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 1_100",        "unit": "MWh/yr",  "note": "1,100 full-load hours/yr — UK average (consistent with SIF Solar 1MW profile)"},
                    {"name": "PPA Revenue",          "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,          "formula": "rating * 1_100 * 80",    "unit": "GBP/yr",  "note": "£80/MWh — SIF Control row: renewables electricity cost used as indicative PPA floor"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,      "formula": "rating * 1_100 * 0.233", "unit": "t CO2/yr","note": "0.233 t CO2/MWh UK grid carbon intensity (DESNZ 2024)"},
                ],
            },
            # ---------------------------------------------------------------
            # Rooftop / Car Park Solar PV — lower yield, no land cost.
            # ---------------------------------------------------------------
            "Rooftop / Car Park Solar PV": {
                "rating_unit": "MWp",
                "rating_default": 0.5,
                "rating_min": 0.01,
                "rating_max": 20.0,
                "rating_step": 0.1,
                "rating_help": "Peak installed capacity of rooftop or car park canopy solar (MWp DC)",
                "capex_items": [
                    {"name": "Solar panels & inverters","formula": "rating * 750_000",           "note": "£750k/MWp — rooftop premium over ground-mount (higher install cost)"},
                    {"name": "Structural mounting",     "formula": "rating * 750_000 * 0.08",    "note": "8% of panel CAPEX: roof penetration, purlins, fixings"},
                    {"name": "Grid connection (LV)",    "formula": "15_000",                     "note": "£15k fixed low-voltage metering and protection"},
                ],
                "opex_items": [
                    {"name": "Solar O&M",               "opex_type": "Cost (£/yr)",  "formula": "rating * 750_000 * 0.012",    "unit": "GBP/yr", "note": "1.2% p.a. — rooftop slightly higher due to access difficulty"},
                    {"name": "Site insurance",          "opex_type": "Cost (£/yr)",  "formula": "rating * 2_000",              "unit": "GBP/yr", "note": "£2k/MWp/yr all-risks insurance"},
                ],
                "footprint_items": [
                    {"name": "Roof / canopy area",      "formula": "rating * 6_500",  "note": "6,500 m²/MWp — higher packing density than ground-mount"},
                ],
                "output_items": [
                    {"name": "Annual generation",    "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 900",          "unit": "MWh/yr",  "note": "900 full-load hours/yr — UK rooftop (lower than ground-mount due to fixed tilt)"},
                    {"name": "Behind-the-meter saving", "output_type": "Revenue", "output_subtype": OUTPUT_SUBTYPE_REVENUE,        "formula": "rating * 900 * 150",     "unit": "GBP/yr",  "note": "£150/MWh grid electricity displaced at £150/MWh (SIF Control row)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,      "formula": "rating * 900 * 0.233",   "unit": "t CO2/yr","note": "0.233 t CO2/MWh UK grid carbon intensity"},
                ],
            },
        },
        "Wind Turbine": {
            # ---------------------------------------------------------------
            # Onshore Wind Turbine — £1M/MW (SIF Costs row 5), BOP 10% (row 6).
            # O&M 1% (SIF Costs row 27: £10k on £1M wind CAPEX).
            # Wind 2,600 full-load hours — consistent with SIF Wind 1MW profile.
            # ---------------------------------------------------------------
            "Onshore Wind Turbine": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.5,
                "rating_help": "Nameplate capacity per turbine (MW). Typical UK onshore: 3–5 MW per unit.",
                "capex_items": [
                    {"name": "Wind turbine (supply & erect)", "formula": "rating * 1_000_000",      "note": "£1M/MW nameplate — SIF Costs sheet row 5"},
                    {"name": "Balance of Plant",             "formula": "rating * 1_000_000 * 0.10","note": "10% of turbine CAPEX: roads, cabling, substation (SIF Costs row 6)"},
                    {"name": "Grid connection",              "formula": "rating * 50_000",           "note": "£50k/MW grid connection — varies significantly by proximity"},
                ],
                "opex_items": [
                    {"name": "Wind turbine O&M",    "opex_type": "Cost (£/yr)",  "formula": "rating * 1_000_000 * 0.01",   "unit": "GBP/yr", "note": "1% p.a. of turbine CAPEX — SIF Costs row 27 (£10k/MW)"},
                    {"name": "Land lease",          "opex_type": "Cost (£/yr)",  "formula": "rating * 8_000",              "unit": "GBP/yr", "note": "£8k/MW/yr — typical UK wind farm lease rate"},
                    {"name": "Site insurance",      "opex_type": "Cost (£/yr)",  "formula": "rating * 5_000",              "unit": "GBP/yr", "note": "£5k/MW/yr all-risks insurance"},
                ],
                "footprint_items": [
                    {"name": "Turbine base & hardstanding", "formula": "rating * 500", "note": "500 m²/MW for turbine base pad and crane hardstanding (not exclusion zone)"},
                ],
                "output_items": [
                    {"name": "Annual generation",    "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 2_600",        "unit": "MWh/yr",  "note": "2,600 full-load hours/yr — UK onshore average (consistent with SIF Wind 1MW profile)"},
                    {"name": "PPA Revenue",          "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,          "formula": "rating * 2_600 * 80",    "unit": "GBP/yr",  "note": "£80/MWh indicative PPA rate (SIF renewables electricity cost)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,      "formula": "rating * 2_600 * 0.233", "unit": "t CO2/yr","note": "0.233 t CO2/MWh UK grid carbon intensity displaced"},
                ],
            },
            # ---------------------------------------------------------------
            # Small Wind Turbine — community / industrial scale (<500 kW).
            # ---------------------------------------------------------------
            "Small Wind Turbine (<500 kW)": {
                "rating_unit": "kW",
                "rating_default": 100.0,
                "rating_min": 10.0,
                "rating_max": 500.0,
                "rating_step": 10.0,
                "rating_help": "Nameplate capacity of the small wind turbine (kW). Typical industrial: 50–250 kW.",
                "capex_items": [
                    {"name": "Small wind turbine",   "formula": "rating * 1_500",              "note": "£1.5k/kW — small turbines carry a unit-size premium over utility scale"},
                    {"name": "Foundation & civil",   "formula": "rating * 1_500 * 0.12",       "note": "12% of turbine cost — smaller foundations but proportionally higher"},
                    {"name": "Grid connection (LV)", "formula": "10_000",                       "note": "£10k fixed low-voltage connection"},
                ],
                "opex_items": [
                    {"name": "Turbine O&M",          "opex_type": "Cost (£/yr)",  "formula": "rating * 1_500 * 0.02",       "unit": "GBP/yr", "note": "2% p.a. — small turbines relatively higher maintenance per kW"},
                    {"name": "Land lease",           "opex_type": "Cost (£/yr)",  "formula": "rating * 8",                  "unit": "GBP/yr", "note": "£8/kW/yr land lease"},
                ],
                "footprint_items": [
                    {"name": "Turbine base pad",     "formula": "rating * 0.5",   "note": "0.5 m²/kW base pad"},
                ],
                "output_items": [
                    {"name": "Annual generation",    "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 2_600 / 1000",  "unit": "MWh/yr",  "note": "2,600 full-load hours/yr (same as utility scale for same site wind resource)"},
                    {"name": "Revenue / saving",     "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,          "formula": "rating * 2_600 / 1000 * 150", "unit": "GBP/yr","note": "£150/MWh grid electricity displaced or sold (SIF grid electricity cost)"},
                    {"name": "CO2 Avoided",          "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,      "formula": "rating * 2_600 / 1000 * 0.233","unit": "t CO2/yr","note": "0.233 t CO2/MWh"},
                ],
            },
        },
        "Grid Connection": {
            # ---------------------------------------------------------------
            # Grid Connection (PPA / Import) — represents a grid feed used to
            # supplement renewable generation.  Cost based on SIF model: grid
            # electricity £150/MWh (SIF Control row, grid_electricity_cost
            # default); stack electricity for PPA £80/MWh.
            # ---------------------------------------------------------------
            "Grid Electricity Connection": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 50.0,
                "rating_step": 0.1,
                "rating_help": "Contracted grid import capacity (MW). Used to supplement renewables or power ancillary loads.",
                "capex_items": [
                    {"name": "Grid connection infrastructure", "formula": "rating * 50_000",  "note": "£50k/MW — connection cost to DNO; varies by proximity to substation"},
                    {"name": "Protection & metering",          "formula": "15_000",           "note": "£15k fixed for grid protection relay and smart metering"},
                ],
                "opex_items": [
                    {"name": "Electricity cost (grid)",   "opex_type": "Cost (£/yr)",  "formula": "rating * 1_000 * 8_760 * 0.5 * 0.15",  "unit": "GBP/yr", "note": "50% utilisation × 8,760 hr × £150/MWh (SIF Control row grid electricity cost)"},
                    {"name": "Standing charge",           "opex_type": "Cost (£/yr)",  "formula": "rating * 5_000",                        "unit": "GBP/yr", "note": "£5k/MW/yr network standing charge / capacity charge"},
                ],
                "footprint_items": [
                    {"name": "Switchgear / metering kiosk", "formula": "20", "note": "20 m² fixed for grid connection kiosk"},
                ],
                "output_items": [
                    {"name": "Grid power available",  "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 8_760 * 0.5", "unit": "MWh/yr", "note": "50% utilisation estimate — grid power available to facility"},
                ],
            },
        },
    },

    # =========================================================================
    # STORAGE
    # H2 storage: £200/kg (SIF Costs sheet row 12).
    # O&M: 1% p.a. (SIF Costs row 30: £906 on £90,566 → 1%).
    # 40ft tube trailer: £250k fixed (SIF Costs row 14).
    # =========================================================================
    "Storage": {
        "Hydrogen Storage": {
            # ---------------------------------------------------------------
            # H2 Storage Tank — generic vessel, £200/kg (SIF Costs row 12).
            # Sized as days of max production × max daily output.
            # ---------------------------------------------------------------
            "H2 Storage Tank": {
                "rating_unit": "kg",
                "rating_default": 500.0,
                "rating_min": 10.0,
                "rating_max": 50_000.0,
                "rating_step": 50.0,
                "rating_help": "H2 storage capacity (kg). Tip: 1 MW electrolyser at 53 kWh/kg produces ~452 kg/day max.",
                "capex_items": [
                    {"name": "Storage vessel(s)",   "formula": "rating * 200",                "note": "£200/kg H2 capacity — SIF Costs sheet row 12"},
                    {"name": "Valves & pipework",   "formula": "rating * 200 * 0.05",         "note": "5% of vessel CAPEX for interconnecting pipework and isolation valves"},
                    {"name": "Pressure safety & venting", "formula": "rating * 200 * 0.03",   "note": "3% of vessel CAPEX for PRV, vent stack, and safety systems"},
                ],
                "opex_items": [
                    {"name": "Storage O&M",         "opex_type": "Cost (£/yr)",  "formula": "rating * 200 * 0.01",         "unit": "GBP/yr", "note": "1% p.a. of CAPEX — SIF Costs row 30"},
                ],
                "footprint_items": [
                    {"name": "Tank pad & bund",     "formula": "rating * 0.20",  "note": "0.2 m²/kg capacity including bunding and access clearance"},
                ],
                "output_items": [
                    {"name": "H2 storage capacity", "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_STORAGE, "formula": "rating", "unit": "kg", "note": "Max H2 storable at one time"},
                ],
            },
            # ---------------------------------------------------------------
            # 40ft Tube Trailer — £250k fixed unit (SIF Costs row 14).
            # ---------------------------------------------------------------
            "40ft Tube Trailer": {
                "rating_unit": "units",
                "rating_default": 1.0,
                "rating_min": 1.0,
                "rating_max": 20.0,
                "rating_step": 1.0,
                "rating_help": "Number of 40ft tube trailers. Each holds ~250–350 kg H2 at ~200 bar.",
                "capex_items": [
                    {"name": "40ft tube trailer",   "formula": "rating * 250_000",            "note": "£250k per trailer — SIF Costs sheet row 14"},
                ],
                "opex_items": [
                    {"name": "Trailer O&M",         "opex_type": "Cost (£/yr)",  "formula": "rating * 250_000 * 0.01",     "unit": "GBP/yr", "note": "1% p.a. of CAPEX for inspection, valve maintenance, and certification"},
                ],
                "footprint_items": [
                    {"name": "Trailer bay(s)",      "formula": "rating * 60",    "note": "60 m² per trailer bay including manoeuvring clearance"},
                ],
                "output_items": [
                    {"name": "H2 storage capacity", "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_STORAGE, "formula": "rating * 300", "unit": "kg", "note": "~300 kg H2 per trailer at 200 bar (mid-range estimate)"},
                ],
            },
        },
        "Battery Storage": {
            # ---------------------------------------------------------------
            # Battery Energy Storage System (BESS) — grid-scale lithium-ion.
            # Smooths renewable output and enables time-shifting for electrolyser.
            # ---------------------------------------------------------------
            "Battery BESS (Lithium-Ion)": {
                "rating_unit": "MWh",
                "rating_default": 2.0,
                "rating_min": 0.1,
                "rating_max": 500.0,
                "rating_step": 0.5,
                "rating_help": "Usable energy storage capacity (MWh). Typical ratio: 1–2 MWh per MW electrolyser for buffer smoothing.",
                "capex_items": [
                    {"name": "Battery modules & BMS",   "formula": "rating * 200_000",         "note": "£200k/MWh — utility-scale BESS 2024 benchmark (BEIS)"},
                    {"name": "Inverter & controls",     "formula": "rating * 200_000 * 0.15",  "note": "15% of module cost for PCS, controls, grid interface"},
                    {"name": "Civil & containment",     "formula": "rating * 200_000 * 0.05",  "note": "5% civil works for pad, firewall, drainage"},
                ],
                "opex_items": [
                    {"name": "BESS O&M",                "opex_type": "Cost (£/yr)",  "formula": "rating * 200_000 * 0.01",     "unit": "GBP/yr", "note": "1% p.a. of CAPEX — monitoring, thermal management, cell replacement reserve"},
                ],
                "footprint_items": [
                    {"name": "BESS container pad",      "formula": "rating * 15",    "note": "15 m²/MWh — standard 40ft container footprint per 2 MWh"},
                ],
                "output_items": [],
            },
        },
    },

    # =========================================================================
    # WATER TREATMENT
    # Water purification unit: £50k fixed (SIF Costs row 13).
    # Purification power: 3 kWh/m³ for highly pure, 0 for tap/rainwater
    # (SIF Parameters rows 10, 15, 20).
    # Direct water demand: 10 L/kg H2 (SIF Parameters row 4).
    # Highly-pure pre-treatment ratio: 6× (SIF Parameters row 11) → 60 L/kg.
    # Water cost: £1.93/m³ (SIF Costs row 35).
    # =========================================================================
    "Water Treatment": {
        "Purification": {
            # ---------------------------------------------------------------
            # Highly-Pure Water Purification Unit (RO + DI) — for use with
            # electrolysers requiring ultrapure feed water.
            # £50k fixed (SIF Costs row 13).  3 kWh/m³ (SIF Parameters row 10).
            # Water demand ratio 6× (SIF Parameters row 11): needs 60 L/kg H2.
            # ---------------------------------------------------------------
            "Highly-Pure Water Purification Unit": {
                "rating_unit": "m³/hr",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Treated water throughput (m³/hr). For 1 MW electrolyser: ~19 kg/hr H2 × 60 L/kg = 1.14 m³/hr required.",
                "capex_items": [
                    {"name": "Purification unit (fixed)",    "formula": "50_000",               "note": "£50k fixed unit cost — SIF Costs sheet row 13"},
                    {"name": "Purification unit (variable)", "formula": "rating * 10_000",       "note": "£10k/m³/hr for capacity above 1 m³/hr (pipework, additional membranes)"},
                ],
                "opex_items": [
                    {"name": "Purification O&M",    "opex_type": "Cost (£/yr)",  "formula": "(50_000 + rating * 10_000) * 0.02", "unit": "GBP/yr", "note": "2% p.a. of CAPEX — membrane replacement, resin, chemicals"},
                    {"name": "Purification power",  "opex_type": "Power (kW)",   "formula": "rating * 3.0",                      "unit": "kW",     "note": "3 kWh/m³ — SIF Parameters row 10 (highly pure)"},
                    {"name": "Raw water consumption","opex_type": "Water (L/hr)", "formula": "rating * 1_250",                    "unit": "L/hr",   "note": "~80% recovery: 1 m³/hr treated needs ~1.25 m³/hr raw"},
                ],
                "footprint_items": [
                    {"name": "Purification skid",   "formula": "25",             "note": "25 m² fixed for standard RO+DI skid (containerised)"},
                ],
                "output_items": [
                    {"name": "Purified water output","output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_WATER_OUTPUT, "formula": "rating * 1_000", "unit": "L/hr", "note": "Treated water output at rated throughput"},
                ],
            },
            # ---------------------------------------------------------------
            # Tap / Rainwater Pre-filter — simple filtration only.
            # No purification electricity needed (SIF Parameters row 15/20: 0).
            # Water demand ratio 1× (SIF Parameters rows 16, 21).
            # ---------------------------------------------------------------
            "Tap / Rainwater Pre-filter": {
                "rating_unit": "m³/hr",
                "rating_default": 0.5,
                "rating_min": 0.1,
                "rating_max": 50.0,
                "rating_step": 0.1,
                "rating_help": "Filtered water throughput (m³/hr). For 1 MW electrolyser: ~19 kg/hr H2 × 10 L/kg = 0.19 m³/hr required.",
                "capex_items": [
                    {"name": "Pre-filter skid",     "formula": "8_000",                        "note": "£8k fixed for simple sediment / carbon block filter skid"},
                    {"name": "Pipework & fittings", "formula": "rating * 2_000",               "note": "£2k/m³/hr for pipework connections"},
                ],
                "opex_items": [
                    {"name": "Filter media replacement", "opex_type": "Cost (£/yr)", "formula": "(8_000 + rating * 2_000) * 0.10", "unit": "GBP/yr", "note": "10% p.a. — frequent cartridge/media replacement for simple filters"},
                    {"name": "Raw water cost",       "opex_type": "Cost (£/yr)",  "formula": "rating * 8_760 * 1.93 / 1_000",     "unit": "GBP/yr", "note": "Water at £1.93/m³ (SIF Costs row 35) × throughput × 8,760 hr/yr"},
                ],
                "footprint_items": [
                    {"name": "Filter skid",         "formula": "5",              "note": "5 m² fixed for compact pre-filter unit"},
                ],
                "output_items": [
                    {"name": "Filtered water output","output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_WATER_OUTPUT, "formula": "rating * 1_000", "unit": "L/hr", "note": "Filtered tap or rainwater at rated throughput"},
                ],
            },
        },
        "Wastewater": {
            # ---------------------------------------------------------------
            # Wastewater Treatment / Oxygen Recovery — electrolysis by-product
            # oxygen can be sold or used for wastewater treatment.
            # ---------------------------------------------------------------
            "Oxygen Recovery System": {
                "rating_unit": "kg H2/hr",
                "rating_default": 19.0,
                "rating_min": 1.0,
                "rating_max": 500.0,
                "rating_step": 1.0,
                "rating_help": "Rated at the H2 production rate of the upstream electrolyser (kg H2/hr). O2 produced = 8× H2 by mass.",
                "capex_items": [
                    {"name": "O2 capture & buffer tank",  "formula": "rating * 2_000",         "note": "£2k/kg/hr H2 equivalent — O2 collection manifold and buffer vessel"},
                    {"name": "O2 compressor / dryer",     "formula": "rating * 1_500",         "note": "£1.5k/kg/hr H2 — drying and light compression for pipeline quality O2"},
                ],
                "opex_items": [
                    {"name": "O2 system O&M",       "opex_type": "Cost (£/yr)",  "formula": "(rating * 2_000 + rating * 1_500) * 0.02", "unit": "GBP/yr", "note": "2% p.a. of CAPEX"},
                    {"name": "O2 system power",     "opex_type": "Power (kW)",   "formula": "rating * 0.5",                              "unit": "kW",     "note": "~0.5 kW/kg/hr H2 for O2 handling equipment"},
                ],
                "footprint_items": [
                    {"name": "O2 handling area",    "formula": "rating * 2",     "note": "2 m²/kg H2/hr production rate"},
                ],
                "output_items": [
                    {"name": "Oxygen output",       "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_WATER_OUTPUT, "formula": "rating * 8 * 8_760", "unit": "kg O2/yr", "note": "O2 produced = ~8 kg per kg H2 by electrolysis stoichiometry"},
                    {"name": "O2 Revenue",          "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,     "formula": "rating * 8 * 8_760 * 0.05", "unit": "GBP/yr", "note": "£0.05/kg O2 indicative — industrial O2 price varies widely"},
                ],
            },
        },
    },

    # =========================================================================
    # BALANCE OF PLANT
    # Costs from SIF model: installation £30k (row 20), licensing £30k (row 21),
    # rent £4k/yr (row 22/38), insurance £25k/yr (row 39),
    # operator salary £30k/person/yr (row 40),
    # transport £0.75/kg H2 (row 36).
    # =========================================================================
    "Balance of Plant": {
        "Site Infrastructure": {
            # ---------------------------------------------------------------
            # Control Room & SCADA — fixed cost for site supervision.
            # ---------------------------------------------------------------
            "Control Room & SCADA": {
                "rating_unit": "kW (facility load)",
                "rating_default": 1_000.0,
                "rating_min": 50.0,
                "rating_max": 100_000.0,
                "rating_step": 50.0,
                "rating_help": "Total facility electrical load supervised by this SCADA system (kW). Size relative to electrolyser MW.",
                "capex_items": [
                    {"name": "Control room building/container", "formula": "30_000",             "note": "£30k fixed — portacabin or 20ft container (SIF: installation cost basis)"},
                    {"name": "SCADA hardware & commissioning",  "formula": "rating * 5",         "note": "£5/kW supervised — PLC, sensors, comms, factory acceptance testing"},
                ],
                "opex_items": [
                    {"name": "SCADA licence & maintenance", "opex_type": "Cost (£/yr)", "formula": "5_000",   "unit": "GBP/yr", "note": "£5k/yr software licence and on-site calibration visits"},
                    {"name": "Control room power",          "opex_type": "Power (kW)",  "formula": "15",      "unit": "kW",     "note": "15 kW continuous: lighting, HVAC, IT equipment"},
                ],
                "footprint_items": [
                    {"name": "Control room",                "formula": "25",             "note": "25 m² — standard 20ft container or portacabin"},
                ],
                "output_items": [],
            },
            # ---------------------------------------------------------------
            # Site Fencing & Civil Works
            # ---------------------------------------------------------------
            "Site Fencing & Civil Works": {
                "rating_unit": "m²",
                "rating_default": 500.0,
                "rating_min": 50.0,
                "rating_max": 100_000.0,
                "rating_step": 50.0,
                "rating_help": "Total site area to be fenced and prepared (m²)",
                "capex_items": [
                    {"name": "Perimeter fencing",         "formula": "rating ** 0.5 * 4 * 15",  "note": "£15/m perimeter × 4 sides of a square site"},
                    {"name": "Hardstanding & drainage",   "formula": "rating * 35",              "note": "£35/m² for hardstanding, drainage, and access road"},
                    {"name": "Security lighting & CCTV",  "formula": "10_000",                   "note": "£10k fixed for perimeter lighting and CCTV system"},
                ],
                "opex_items": [
                    {"name": "Site maintenance",          "opex_type": "Cost (£/yr)", "formula": "rating * 2",  "unit": "GBP/yr", "note": "£2/m²/yr for grass cutting, fencing repair, gully emptying"},
                    {"name": "Site rent",                 "opex_type": "Cost (£/yr)", "formula": "4_000",        "unit": "GBP/yr", "note": "£4k/yr annual rent default (SIF Costs row 38 / Control row 22)"},
                ],
                "footprint_items": [
                    {"name": "Site area",                 "formula": "rating",         "note": "Pass-through: the rated area is the site footprint"},
                ],
                "output_items": [],
            },
            # ---------------------------------------------------------------
            # Grid Connection (Site-Level)
            # ---------------------------------------------------------------
            "Site Grid Connection": {
                "rating_unit": "MVA",
                "rating_default": 1.5,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Site-level grid connection capacity (MVA). Typically 10–20% more than total facility load.",
                "capex_items": [
                    {"name": "DNO connection works",      "formula": "rating * 80_000",          "note": "£80k/MVA — indicative DNO reinforcement and cable; highly site-specific"},
                    {"name": "Site HV substation",        "formula": "rating * 40_000",          "note": "£40k/MVA for on-site transformer, switchgear, and protection"},
                    {"name": "Protection & metering",     "formula": "20_000",                   "note": "£20k fixed for protection relay, revenue meter, SCADA integration"},
                ],
                "opex_items": [
                    {"name": "Grid standing charge",      "opex_type": "Cost (£/yr)", "formula": "rating * 8_000",   "unit": "GBP/yr", "note": "£8k/MVA/yr network access and capacity charges"},
                    {"name": "Substation maintenance",    "opex_type": "Cost (£/yr)", "formula": "rating * 40_000 * 0.01", "unit": "GBP/yr", "note": "1% p.a. of substation CAPEX for maintenance and inspection"},
                ],
                "footprint_items": [
                    {"name": "HV substation compound",   "formula": "150",            "note": "150 m² fixed for outdoor HV switchgear and transformer compound"},
                ],
                "output_items": [],
            },
        },
        "Site Staffing": {
            # ---------------------------------------------------------------
            # Operations Staff — £30k/person/yr (SIF Costs row 40).
            # ---------------------------------------------------------------
            "Site Operators": {
                "rating_unit": "FTE",
                "rating_default": 2.0,
                "rating_min": 0.0,
                "rating_max": 50.0,
                "rating_step": 1.0,
                "rating_help": "Number of full-time equivalent site operators. Small H2 plants: 1–3 operators. SIF default: 0 (unmanned).",
                "capex_items": [],
                "opex_items": [
                    {"name": "Operator salaries",         "opex_type": "Cost (£/yr)", "formula": "rating * 30_000",  "unit": "GBP/yr", "note": "£30k/person/yr — SIF Costs row 40 / Control row 16"},
                ],
                "footprint_items": [],
                "output_items": [],
            },
            # ---------------------------------------------------------------
            # Annual Insurance — fixed or MW-scaled.
            # SIF Costs row 39: £25k fixed.
            # ---------------------------------------------------------------
            "Site Insurance": {
                "rating_unit": "MW (total installed)",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 200.0,
                "rating_step": 0.1,
                "rating_help": "Total installed capacity of the site (MW) to scale insurance. SIF default: £25k/yr fixed.",
                "capex_items": [],
                "opex_items": [
                    {"name": "All-risks insurance",       "opex_type": "Cost (£/yr)", "formula": "25_000 + rating * 3_000", "unit": "GBP/yr", "note": "£25k fixed + £3k/MW — SIF base £25k (row 39) plus capacity uplift"},
                ],
                "footprint_items": [],
                "output_items": [],
            },
        },
        "Hydrogen Logistics": {
            # ---------------------------------------------------------------
            # H2 Transportation — £0.75/kg H2 delivered (SIF Costs row 36).
            # ---------------------------------------------------------------
            "H2 Transportation (Road)": {
                "rating_unit": "kg H2/yr",
                "rating_default": 165_000.0,
                "rating_min": 1_000.0,
                "rating_max": 10_000_000.0,
                "rating_step": 1_000.0,
                "rating_help": "Annual H2 delivered by road (kg/yr). Typical: 1 MW electrolyser at 53 kWh/kg = ~165,000 kg/yr full-load.",
                "capex_items": [],
                "opex_items": [
                    {"name": "Road transportation",       "opex_type": "Cost (£/yr)", "formula": "rating * 0.75",    "unit": "GBP/yr", "note": "£0.75/kg H2 — SIF Costs row 36 / Control row 23 transport cost"},
                ],
                "footprint_items": [],
                "output_items": [],
            },
            # ---------------------------------------------------------------
            # H2 Dispensing / Refuelling Station — for vehicle refuelling.
            # ---------------------------------------------------------------
            "H2 Dispensing / Refuelling Station": {
                "rating_unit": "kg/day",
                "rating_default": 100.0,
                "rating_min": 10.0,
                "rating_max": 2_000.0,
                "rating_step": 10.0,
                "rating_help": "Daily H2 dispensing capacity (kg/day). Small station: 100 kg/day; medium: 500 kg/day.",
                "capex_items": [
                    {"name": "Dispensing equipment",     "formula": "rating * 1_500",           "note": "£1.5k/kg/day — dispenser nozzles, flow meters, cooling"},
                    {"name": "Safety systems & signage", "formula": "rating * 1_500 * 0.10",    "note": "10% of dispenser CAPEX for H2 sensors, ESD, and site safety signage"},
                    {"name": "Forecourt civil works",    "formula": "50_000",                   "note": "£50k fixed for canopy, hardstanding, drainage"},
                ],
                "opex_items": [
                    {"name": "Dispensing O&M",           "opex_type": "Cost (£/yr)", "formula": "(rating * 1_500 + rating * 1_500 * 0.10) * 0.02 + 50_000 * 0.01", "unit": "GBP/yr", "note": "2% dispenser CAPEX + 1% civil CAPEX p.a."},
                    {"name": "Station power",            "opex_type": "Power (kW)",  "formula": "rating * 0.1",              "unit": "kW",     "note": "0.1 kW/kg/day for cooling, controls, lighting"},
                ],
                "footprint_items": [
                    {"name": "Forecourt area",           "formula": "50 + rating * 0.5", "note": "50 m² fixed + 0.5 m² per kg/day dispensing capacity"},
                ],
                "output_items": [
                    {"name": "H2 dispensed",             "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 365", "unit": "kg/yr", "note": "Annual dispensing at rated daily capacity"},
                    {"name": "Fuelling Revenue",         "output_type": "Revenue", "output_subtype": OUTPUT_SUBTYPE_REVENUE,        "formula": "rating * 365 * 12.0", "unit": "GBP/yr", "note": "£12/kg H2 at retail pump — indicative UK refuelling station price"},
                    {"name": "Diesel / HGV CO2 Avoided", "output_type": "Saving", "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,    "formula": "rating * 365 * 6.29 / 1_000", "unit": "t CO2/yr", "note": "6.29 kg CO2/kg H2 displaced (SIF Parameters row 31)"},
                ],
            },
        },
    },
}


# -------------------------------------------------------------------------
# SESSION STATE HELPERS
# -------------------------------------------------------------------------
def _ensure_project_financial_defaults(project: dict) -> None:
    for key, default_value in GREEN_OFFPORT_PROJECT_DEFAULTS.items():
        project.setdefault(key, default_value)


def _init_session_state() -> None:
    if "pb_projects" not in st.session_state:
        st.session_state["pb_projects"] = {}
    if "pb_active_project" not in st.session_state:
        st.session_state["pb_active_project"] = None
    if "pb_pending_manual_cofo_by_context" not in st.session_state:
        legacy_pending = st.session_state.pop("pb_pending_manual_cofo", [])
        st.session_state["pb_pending_manual_cofo_by_context"] = {}
        if legacy_pending:
            st.session_state["pb_pending_manual_cofo_by_context"]["__legacy__"] = list(legacy_pending)
    elif "pb_pending_manual_cofo" in st.session_state:
        legacy_pending = st.session_state.pop("pb_pending_manual_cofo", [])
        if legacy_pending:
            store = st.session_state["pb_pending_manual_cofo_by_context"]
            store.setdefault("__legacy__", []).extend(legacy_pending)

    # Migrate legacy project records once per project (guarded by a flag so this
    # never runs again on subsequent page reloads for the same project).
    for project in st.session_state["pb_projects"].values():
        project.pop("currency", None)  # currency field was removed; clean up once
        project.setdefault("created_at", date.today().isoformat())
        project.setdefault("inter_site_connections", [])
        _ensure_project_financial_defaults(project)
        if not project.get("_migrated"):
            _migrate_legacy_project_records(project)
            project["_migrated"] = True


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _fmt_currency(value: float, decimals: int = 0) -> str:
    return f"{PROJECT_CURRENCY_SYMBOL}{format(value, f',.{decimals}f')}"


def _fmt_currency_millions(value: float, decimals: int = 2) -> str:
    return f"{PROJECT_CURRENCY_SYMBOL}{format(value / 1e6, f',.{decimals}f')}M"


def _fmt_percent(value: float, decimals: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:,.{decimals}f}%"


def _normalize_opex_type_key(value: str) -> str:
    mapping = {
        OPEX_TYPE_COST: OPEX_TYPE_COST,
        OPEX_TYPE_POWER: OPEX_TYPE_POWER,
        OPEX_TYPE_WATER: OPEX_TYPE_WATER,
        OPEX_TYPE_OTHER: OPEX_TYPE_OTHER,
        "Cost (£/yr)": OPEX_TYPE_COST,
        "Cost (GBP/yr)": OPEX_TYPE_COST,
        "Power (kW)": OPEX_TYPE_POWER,
        "Water (L/hr)": OPEX_TYPE_WATER,
        "Other": OPEX_TYPE_OTHER,
    }
    return mapping.get(value, "")


def _opex_type_label(type_key: str, fallback: str = "") -> str:
    normalized = _normalize_opex_type_key(type_key) or _normalize_opex_type_key(fallback)
    if normalized:
        return OPEX_TYPE_LABELS[normalized]
    return fallback or type_key or "—"


def _opex_unit_for_key(type_key: str) -> str:
    normalized = _normalize_opex_type_key(type_key)
    return OPEX_TYPE_DEFAULT_UNITS.get(normalized, "")


def _record_opex_type_key(record: dict) -> str:
    return _normalize_opex_type_key(record.get("opex_type_key", "")) or _normalize_opex_type_key(record.get("opex_type", ""))


def _record_opex_type_label(record: dict) -> str:
    return _opex_type_label(record.get("opex_type_key", ""), record.get("opex_type", ""))


def _manual_cofo_context_key(project_id: str, location_id: str) -> str:
    return f"{project_id}::{location_id}"


def _get_pending_manual_cofo(project_id: str, location_id: str) -> list:
    store = st.session_state["pb_pending_manual_cofo_by_context"]
    context_key = _manual_cofo_context_key(project_id, location_id)
    if context_key not in store and "__legacy__" in store and len(store) == 1:
        store[context_key] = store.pop("__legacy__")
    return store.setdefault(context_key, [])


def _clear_pending_manual_cofo(project_id: str, location_id: str) -> None:
    st.session_state["pb_pending_manual_cofo_by_context"].pop(
        _manual_cofo_context_key(project_id, location_id),
        None,
    )


def _migrate_legacy_output_record(record: dict) -> None:
    if record.get("cofo_type") != "Output":
        return

    item_name = record.get("item_name", "")
    old_subtype = record.get("output_subtype", "")

    if old_subtype == "Revenue (£/yr)":
        record["output_subtype"] = OUTPUT_SUBTYPE_REVENUE
        if record.get("unit") == "£/yr":
            record["unit"] = "GBP/yr"
    elif old_subtype == "CO2 (t/yr)":
        record["output_subtype"] = OUTPUT_SUBTYPE_CO2_AVOIDED
    elif old_subtype == "Power (MWh/yr)" and item_name == "Annual generation":
        record["output_subtype"] = OUTPUT_SUBTYPE_POWER_GENERATION
    elif old_subtype == "Water (L/hr)" and item_name == "Purified water":
        record["output_subtype"] = OUTPUT_SUBTYPE_WATER_OUTPUT
    elif old_subtype == "H2 (kg/yr)":
        if item_name == "Green H2 production":
            record["output_subtype"] = OUTPUT_SUBTYPE_H2_PRODUCTION
        elif item_name == "Compressed H2":
            record["output_subtype"] = OUTPUT_SUBTYPE_H2_COMPRESSION
        elif item_name == "H2 storage capacity":
            record["output_subtype"] = OUTPUT_SUBTYPE_H2_STORAGE
            if record.get("unit") == "kg capacity":
                record["unit"] = "kg"


def _migrate_legacy_opex_record(record: dict) -> None:
    if record.get("cofo_type") != "OPEX":
        return

    type_key = _record_opex_type_key(record)
    if not type_key:
        return

    record["opex_type_key"] = type_key
    record["opex_type"] = _opex_type_label(type_key, record.get("opex_type", ""))

    if type_key == OPEX_TYPE_COST and record.get("unit") == "£/yr":
        record["unit"] = "GBP/yr"
    elif not record.get("unit"):
        record["unit"] = _opex_unit_for_key(type_key)


def _migrate_legacy_project_records(project: dict) -> None:
    for location in project.get("locations", {}).values():
        # Ensure all locations have coordinate fields (added in later version)
        location.setdefault("postcode", "")
        location.setdefault("lat", None)
        location.setdefault("lon", None)
        for item in location.get("technology_items", {}).values():
            for record in item.get("cofo_records", []):
                _migrate_legacy_opex_record(record)
                _migrate_legacy_output_record(record)


# -------------------------------------------------------------------------
# FORMULA ENGINE
# -------------------------------------------------------------------------
def _evaluate_formula(formula: str, rating: float) -> float:
    try:
        return float(eval(formula, {"__builtins__": {}}, {"rating": rating, "math": math}))
    except Exception as exc:
        raise ValueError(f"Formula '{formula}' failed at rating {rating}: {exc}") from exc


def calculate_cofo_records(component_spec: dict, rating: float) -> tuple[list, list[str]]:
    records = []
    errors: list[str] = []

    for item in component_spec.get("capex_items", []):
        try:
            val = _evaluate_formula(item["formula"], rating)
        except ValueError as exc:
            errors.append(f"CAPEX / {item['name']}: {exc}")
            continue
        if val != 0.0:
            records.append({
                "id": _short_id(),
                "cofo_type": "CAPEX",
                "item_name": item["name"],
                "opex_type": "",
                "output_type": "",
                "output_subtype": "",
                "value": val,
                "unit": "£",
                "is_auto_calculated": True,
                "source_formula": item["formula"],
                "source_note": item.get("note", ""),
            })

    for item in component_spec.get("opex_items", []):
        try:
            val = _evaluate_formula(item["formula"], rating)
        except ValueError as exc:
            errors.append(f"OPEX / {item['name']}: {exc}")
            continue
        if val != 0.0:
            opex_type_key = _normalize_opex_type_key(item["opex_type"])
            records.append({
                "id": _short_id(),
                "cofo_type": "OPEX",
                "item_name": item["name"],
                "opex_type_key": opex_type_key,
                "opex_type": _opex_type_label(item["opex_type"]),
                "output_type": "",
                "output_subtype": "",
                "value": val,
                "unit": _opex_unit_for_key(opex_type_key) or item.get("unit", ""),
                "is_auto_calculated": True,
                "source_formula": item["formula"],
                "source_note": item.get("note", ""),
            })

    for item in component_spec.get("footprint_items", []):
        try:
            val = _evaluate_formula(item["formula"], rating)
        except ValueError as exc:
            errors.append(f"Footprint / {item['name']}: {exc}")
            continue
        if val != 0.0:
            records.append({
                "id": _short_id(),
                "cofo_type": "Footprint",
                "item_name": item["name"],
                "opex_type": "",
                "output_type": "",
                "output_subtype": "",
                "value": val,
                "unit": "m²",
                "is_auto_calculated": True,
                "source_formula": item["formula"],
                "source_note": item.get("note", ""),
            })

    for item in component_spec.get("output_items", []):
        try:
            val = _evaluate_formula(item["formula"], rating)
        except ValueError as exc:
            errors.append(f"Output / {item['name']}: {exc}")
            continue
        if val != 0.0:
            records.append({
                "id": _short_id(),
                "cofo_type": "Output",
                "item_name": item["name"],
                "opex_type": "",
                "output_type": item["output_type"],
                "output_subtype": item["output_subtype"],
                "value": val,
                "unit": item["unit"],
                "is_auto_calculated": True,
                "source_formula": item["formula"],
                "source_note": item.get("note", ""),
            })

    return records, errors


# -------------------------------------------------------------------------
# GREEN OFFPORT ADAPTER
# -------------------------------------------------------------------------
def _green_offport_project_financials(project: dict) -> dict:
    _ensure_project_financial_defaults(project)
    return {
        "project_life": int(project["project_life_years"]),
        "inflation_rate": float(project["inflation_rate_pct"]) / 100.0,
        "degradation_rate": float(project["degradation_rate_pct"]) / 100.0,
        "tax_rate": float(project["tax_rate_pct"]) / 100.0,
        "discount_rate": float(project["discount_rate_pct"]) / 100.0,
        "depreciation_rate": float(project["depreciation_rate_pct"]) / 100.0,
        "sale_price_per_kg": float(project["h2_sale_price_gbp_per_kg"]),
        "include_carbon_credits": project.get("include_carbon_credits", "No"),
        "carbon_credit_price_per_tonne": float(project["carbon_credit_price_gbp_per_tonne"]),
    }


def _build_green_offport_results(inputs: dict, project: dict) -> dict:
    financials = _green_offport_project_financials(project)
    physics = run_sif_green_offport_physics(
        production_method=inputs["production_method"],
        solar_mw=float(inputs["solar_mw"]),
        wind_mw=float(inputs["wind_mw"]),
        grid_mw=float(inputs["grid_mw"]),
        electrolyser_mw=float(inputs["electrolyser_mw"]),
        efficiency_kwh_per_kg=float(inputs["efficiency_kwh_per_kg"]),
    )
    utilities = run_sif_green_offport_utilities(
        hourly_actual_h2_kg=physics["hourly_actual_h2_kg"],
        water_source=inputs["water_source"],
        compression=inputs["compression"],
    )
    costs = run_sif_green_offport_costs(
        ownership=inputs["ownership"],
        production_method=inputs["production_method"],
        solar_mw=float(inputs["solar_mw"]),
        wind_mw=float(inputs["wind_mw"]),
        electrolyser_mw=float(inputs["electrolyser_mw"]),
        grid_connection_cost=float(inputs["grid_connection_cost"]),
        land_cost=float(inputs["land_cost"]),
        installation_cost=float(inputs["installation_cost"]),
        licensing_cost=float(inputs["licensing_cost"]),
        water_source=inputs["water_source"],
        compression=inputs["compression"],
        tube_trailer_required=inputs["tube_trailer_required"],
        transportation_required=inputs["transportation_required"],
        number_of_operators=int(inputs["number_of_operators"]),
        storage_days=float(inputs["storage_days"]),
        rent_cost=float(inputs["rent_cost"]),
        physics=physics,
        utilities=utilities,
        renewable_electricity_cost_mwh=float(inputs["renewable_electricity_cost_mwh"]),
        grid_electricity_cost_mwh=float(inputs["grid_electricity_cost_mwh"]),
        water_cost_m3=float(inputs["water_cost_m3"]),
    )
    cashflow = run_sif_green_offport_cashflow(
        project_life=financials["project_life"],
        inflation_rate=financials["inflation_rate"],
        degradation_rate=financials["degradation_rate"],
        tax_rate=financials["tax_rate"],
        discount_rate=financials["discount_rate"],
        depreciation_rate=financials["depreciation_rate"],
        sale_price_per_kg=financials["sale_price_per_kg"],
        include_carbon_credits=financials["include_carbon_credits"],
        carbon_credit_price_per_tonne=financials["carbon_credit_price_per_tonne"],
        annual_actual_h2_kg=physics["annual_actual_h2_kg"],
        costs=costs,
    )

    cashflow_df = cashflow["cashflow_df"]
    npv_costs = costs["total_capex"] + float(cashflow_df.loc[cashflow_df["Year"] >= 1, "Annual expenses"].sum())
    npv_h2 = sum(
        physics["annual_actual_h2_kg"] * ((1 - financials["degradation_rate"]) ** (year - 1))
        for year in range(1, financials["project_life"] + 1)
    )
    lcoh = npv_costs / npv_h2 if npv_h2 > 0 else float("nan")

    return {
        "inputs": inputs,
        "financials": financials,
        "physics": physics,
        "utilities": utilities,
        "costs": costs,
        "cashflow": cashflow,
        "lcoh": lcoh,
        "npv_costs": npv_costs,
        "npv_h2": npv_h2,
    }


def _green_offport_record_id(prefix: str, section: str, idx: int, name: str) -> str:
    safe_name = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)[:40].strip("_")
    return f"{prefix}_{section}_{idx}_{safe_name or 'record'}"


def _make_green_offport_cofo_records(results: dict, record_prefix: str = "green_offport") -> list:
    records: list[dict] = []
    costs = results["costs"]
    physics = results["physics"]
    cashflow_df = results["cashflow"]["cashflow_df"]
    year_1 = cashflow_df.loc[cashflow_df["Year"] == 1]
    h2_revenue = float(year_1["Hydrogen revenue"].iloc[0]) if not year_1.empty else 0.0
    carbon_credit_revenue = float(year_1["Carbon credit revenue"].iloc[0]) if not year_1.empty else 0.0
    annual_h2_kg = float(physics["annual_actual_h2_kg"])
    annual_co2_t = annual_h2_kg * 6.29 / 1_000.0

    for idx, (name, value) in enumerate(costs["capex_breakdown"].items(), start=1):
        value = float(value)
        if value == 0.0:
            continue
        records.append({
            "id": _green_offport_record_id(record_prefix, "capex", idx, name),
            "cofo_type": "CAPEX",
            "item_name": name,
            "opex_type": "",
            "output_type": "",
            "output_subtype": "",
            "value": value,
            "unit": "£",
            "is_auto_calculated": True,
            "source_formula": "run_sif_green_offport_costs",
            "source_note": "Green OffPort SIF pipeline CAPEX breakdown",
        })

    for idx, (name, value) in enumerate(costs["opex_breakdown"].items(), start=1):
        value = float(value)
        if value == 0.0:
            continue
        records.append({
            "id": _green_offport_record_id(record_prefix, "opex", idx, name),
            "cofo_type": "OPEX",
            "item_name": name,
            "opex_type_key": OPEX_TYPE_COST,
            "opex_type": OPEX_TYPE_LABELS[OPEX_TYPE_COST],
            "output_type": "",
            "output_subtype": "",
            "value": value,
            "unit": "GBP/yr",
            "is_auto_calculated": True,
            "source_formula": "run_sif_green_offport_costs",
            "source_note": "Green OffPort SIF pipeline Year 1 OPEX breakdown",
        })

    output_specs = [
        ("Actual H2 production", "Product", OUTPUT_SUBTYPE_H2_PRODUCTION, annual_h2_kg, "kg/yr", "run_sif_green_offport_physics"),
        ("H2 Revenue", "Revenue", OUTPUT_SUBTYPE_REVENUE, h2_revenue, "GBP/yr", "run_sif_green_offport_cashflow"),
        ("Carbon credit revenue", "Revenue", OUTPUT_SUBTYPE_REVENUE, carbon_credit_revenue, "GBP/yr", "run_sif_green_offport_cashflow"),
        ("CO2 Avoided", "Saving", OUTPUT_SUBTYPE_CO2_AVOIDED, annual_co2_t, "t CO2/yr", "run_sif_green_offport_cashflow"),
    ]
    for idx, (name, output_type, output_subtype, value, unit, formula) in enumerate(output_specs, start=1):
        value = float(value)
        if value == 0.0:
            continue
        records.append({
            "id": _green_offport_record_id(record_prefix, "output", idx, name),
            "cofo_type": "Output",
            "item_name": name,
            "opex_type": "",
            "output_type": output_type,
            "output_subtype": output_subtype,
            "value": value,
            "unit": unit,
            "is_auto_calculated": True,
            "source_formula": formula,
            "source_note": "Green OffPort SIF pipeline output record",
        })

    return records


def _sync_project_green_offport_items(project: dict) -> None:
    _ensure_project_financial_defaults(project)
    for loc in project.get("locations", {}).values():
        for item in loc.get("technology_items", {}).values():
            if item.get("source_kind") != GREEN_OFFPORT_SOURCE_KIND:
                continue
            try:
                results = _build_green_offport_results(item["green_offport_inputs"], project)
                item["cofo_records"] = _make_green_offport_cofo_records(results, item["id"])
                item.pop("green_offport_error", None)
            except Exception as exc:
                item["green_offport_error"] = str(exc)
                item["cofo_records"] = []


def _collect_green_offport_items(project: dict) -> list[tuple[dict, dict]]:
    items = []
    for loc in project.get("locations", {}).values():
        for item in loc.get("technology_items", {}).values():
            if item.get("source_kind") == GREEN_OFFPORT_SOURCE_KIND:
                items.append((loc, item))
    return items


# -------------------------------------------------------------------------
# STATE MUTATION HELPERS
# -------------------------------------------------------------------------
def _create_project(name: str, description: str) -> str:
    pid = "proj_" + _short_id()
    st.session_state["pb_projects"][pid] = {
        "id": pid,
        "name": name.strip() or "Unnamed Project",
        "description": description,
        "created_at": date.today().isoformat(),
        "project_life_years": 20,
        "discount_rate_pct": 10.0,
        "inflation_rate_pct": 3.5,
        **GREEN_OFFPORT_PROJECT_DEFAULTS,
        "locations": {},
        "inter_site_connections": [],  # list of connection dicts
        "_migrated": True,
    }
    st.session_state["pb_active_project"] = pid
    return pid


def _ensure_valid_sidebar_project_selection(project_ids: list[str], new_project_option: str = "__new__") -> None:
    options = set(project_ids)
    options.add(new_project_option)

    selected_project_id = st.session_state.get("pb_sidebar_project_select_id")
    if selected_project_id in options:
        return

    active_project_id = st.session_state.get("pb_active_project")
    if active_project_id in project_ids:
        st.session_state["pb_sidebar_project_select_id"] = active_project_id
    elif project_ids:
        st.session_state["pb_sidebar_project_select_id"] = project_ids[0]
        st.session_state["pb_active_project"] = project_ids[0]
    else:
        st.session_state["pb_sidebar_project_select_id"] = new_project_option


def _handle_create_project() -> None:
    new_name = st.session_state.get("pb_new_proj_name", "")
    new_desc = st.session_state.get("pb_new_proj_desc", "")

    if not new_name.strip():
        st.session_state["pb_sidebar_create_error"] = "Please enter a project name."
        return

    project_id = _create_project(new_name, new_desc)
    st.session_state["pb_sidebar_project_select_id"] = project_id
    st.session_state["pb_new_proj_name"] = ""
    st.session_state["pb_new_proj_desc"] = ""
    st.session_state.pop("pb_sidebar_create_error", None)


def _delete_project(project_id: str) -> None:
    if project_id in st.session_state["pb_projects"]:
        del st.session_state["pb_projects"][project_id]
    pending_store = st.session_state.get("pb_pending_manual_cofo_by_context", {})
    for key in list(pending_store.keys()):
        if key.startswith(f"{project_id}::"):
            del pending_store[key]
    if st.session_state["pb_active_project"] == project_id:
        remaining = list(st.session_state["pb_projects"].keys())
        st.session_state["pb_active_project"] = remaining[0] if remaining else None


def _handle_delete_project(project_id: str) -> None:
    _delete_project(project_id)
    remaining = list(st.session_state["pb_projects"].keys())
    st.session_state["pb_sidebar_project_select_id"] = remaining[0] if remaining else "__new__"


def _create_location(project_id: str, name: str, description: str) -> str:
    lid = "loc_" + _short_id()
    st.session_state["pb_projects"][project_id]["locations"][lid] = {
        "id": lid,
        "name": name.strip() or "Unnamed Location",
        "description": description,
        "postcode": "",
        "lat": None,
        "lon": None,
        "technology_items": {},
    }
    return lid


def _delete_location(project_id: str, location_id: str) -> None:
    locs = st.session_state["pb_projects"][project_id]["locations"]
    if location_id in locs:
        del locs[location_id]
    _clear_pending_manual_cofo(project_id, location_id)


def _add_tech_item(project_id: str, location_id: str, tech_item: dict) -> None:
    st.session_state["pb_projects"][project_id]["locations"][location_id]["technology_items"][tech_item["id"]] = tech_item


def _remove_tech_item(project_id: str, location_id: str, tech_item_id: str) -> None:
    items = st.session_state["pb_projects"][project_id]["locations"][location_id]["technology_items"]
    if tech_item_id in items:
        del items[tech_item_id]


# -------------------------------------------------------------------------
# AGGREGATION HELPERS
# -------------------------------------------------------------------------
def _aggregate_project_cofo(project: dict) -> dict:
    totals = {
        "total_capex": 0.0,
        "total_opex_cost": 0.0,
        "total_opex_power_kw": 0.0,
        "total_opex_water_l_hr": 0.0,
        "total_footprint_m2": 0.0,
        "total_h2_kg_yr": 0.0,
        "total_revenue_yr": 0.0,
        "total_co2_t_yr": 0.0,
        "total_power_mwh_yr": 0.0,
        "tech_item_count": 0,
        "location_count": 0,
    }
    for loc in project["locations"].values():
        totals["location_count"] += 1
        for item in loc["technology_items"].values():
            totals["tech_item_count"] += 1
            for rec in item["cofo_records"]:
                if rec["cofo_type"] == "CAPEX":
                    totals["total_capex"] += rec["value"]
                elif rec["cofo_type"] == "OPEX":
                    opex_type_key = _record_opex_type_key(rec)
                    if opex_type_key == OPEX_TYPE_COST:
                        totals["total_opex_cost"] += rec["value"]
                    elif opex_type_key == OPEX_TYPE_POWER:
                        totals["total_opex_power_kw"] += rec["value"]
                    elif opex_type_key == OPEX_TYPE_WATER:
                        totals["total_opex_water_l_hr"] += rec["value"]
                elif rec["cofo_type"] == "Footprint":
                    totals["total_footprint_m2"] += rec["value"]
                elif rec["cofo_type"] == "Output":
                    if rec["output_subtype"] == OUTPUT_SUBTYPE_H2_PRODUCTION:
                        totals["total_h2_kg_yr"] += rec["value"]
                    elif rec["output_subtype"] == OUTPUT_SUBTYPE_REVENUE:
                        totals["total_revenue_yr"] += rec["value"]
                    elif rec["output_subtype"] == OUTPUT_SUBTYPE_CO2_AVOIDED:
                        totals["total_co2_t_yr"] += rec["value"]
                    elif rec["output_subtype"] == OUTPUT_SUBTYPE_POWER_GENERATION:
                        totals["total_power_mwh_yr"] += rec["value"]
    return totals


def _build_full_cofo_dataframe(project: dict) -> pd.DataFrame:
    rows = []
    for loc in project["locations"].values():
        for item in loc["technology_items"].values():
            for rec in item["cofo_records"]:
                rows.append({
                    "Location": loc["name"],
                    "Technology Item": item["display_name"],
                    "Category": item["category"],
                    "COFO Type": rec["cofo_type"],
                    "Item Name": rec["item_name"],
                    "OPEX / Output Type": _record_opex_type_label(rec) if rec["cofo_type"] == "OPEX" else rec["output_subtype"] or "—",
                    "Value": rec["value"],
                    "Unit": rec["unit"],
                    "Auto-Calculated": "Yes" if rec["is_auto_calculated"] else "No",
                    "Source Note": rec["source_note"],
                })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _build_location_summary_dataframe(project: dict) -> pd.DataFrame:
    rows = []
    for loc in project["locations"].values():
        capex = opex_cost = opex_power = opex_water = footprint = h2 = revenue = co2 = 0.0
        n_items = len(loc["technology_items"])
        for item in loc["technology_items"].values():
            for rec in item["cofo_records"]:
                if rec["cofo_type"] == "CAPEX":
                    capex += rec["value"]
                elif rec["cofo_type"] == "OPEX":
                    opex_type_key = _record_opex_type_key(rec)
                    if opex_type_key == OPEX_TYPE_COST:
                        opex_cost += rec["value"]
                    elif opex_type_key == OPEX_TYPE_POWER:
                        opex_power += rec["value"]
                    elif opex_type_key == OPEX_TYPE_WATER:
                        opex_water += rec["value"]
                elif rec["cofo_type"] == "Footprint":
                    footprint += rec["value"]
                elif rec["cofo_type"] == "Output":
                    if rec["output_subtype"] == OUTPUT_SUBTYPE_H2_PRODUCTION:
                        h2 += rec["value"]
                    elif rec["output_subtype"] == OUTPUT_SUBTYPE_REVENUE:
                        revenue += rec["value"]
                    elif rec["output_subtype"] == OUTPUT_SUBTYPE_CO2_AVOIDED:
                        co2 += rec["value"]
        rows.append({
            "Location": loc["name"],
            "Tech Items": n_items,
            "CAPEX (GBP)": _fmt_currency(capex),
            "Annual OPEX (GBP/yr)": _fmt_currency(opex_cost),
            "Power Demand (kW)": f"{opex_power:,.1f}",
            "Water Demand (L/hr)": f"{opex_water:,.1f}",
            "Footprint (m²)": f"{footprint:,.0f}",
            "H2 Production (kg/yr)": f"{h2:,.0f}",
            "Revenue (GBP/yr)": _fmt_currency(revenue),
            "CO2 Saved (t/yr)": f"{co2:,.1f}",
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _build_tech_summary_dataframe(project: dict) -> pd.DataFrame:
    rows = []
    for loc in project["locations"].values():
        for item in loc["technology_items"].values():
            capex = opex_cost = opex_power = opex_water = footprint = 0.0
            for rec in item["cofo_records"]:
                if rec["cofo_type"] == "CAPEX":
                    capex += rec["value"]
                elif rec["cofo_type"] == "OPEX":
                    opex_type_key = _record_opex_type_key(rec)
                    if opex_type_key == OPEX_TYPE_COST:
                        opex_cost += rec["value"]
                    elif opex_type_key == OPEX_TYPE_POWER:
                        opex_power += rec["value"]
                    elif opex_type_key == OPEX_TYPE_WATER:
                        opex_water += rec["value"]
                elif rec["cofo_type"] == "Footprint":
                    footprint += rec["value"]
            rows.append({
                "Location": loc["name"],
                "Item": item["display_name"],
                "Category": item["category"],
                "Type": item["type_"],
                "Component": item["component"],
                f"Rating": f"{item['rating_value']} {item['rating_unit']}",
                "CAPEX (GBP)": _fmt_currency(capex),
                "OPEX (GBP/yr)": _fmt_currency(opex_cost),
                "Power (kW)": f"{opex_power:,.1f}",
                "Water (L/hr)": f"{opex_water:,.1f}",
                "Footprint (m²)": f"{footprint:,.0f}",
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# -------------------------------------------------------------------------
# GEOGRAPHY HELPERS
# -------------------------------------------------------------------------
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two lat/lon points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lookup_postcode(postcode: str) -> tuple[float, float] | None:
    """
    Calls the free postcodes.io API to convert a UK postcode to (lat, lon).
    Returns None if the postcode is invalid or the request fails.
    No API key required — postcodes.io is a free public UK service.
    """
    import urllib.request
    import json
    clean = postcode.strip().upper().replace(" ", "")
    if not clean:
        return None
    url = f"https://api.postcodes.io/postcodes/{clean}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == 200:
            result = data["result"]
            return float(result["latitude"]), float(result["longitude"])
    except Exception:
        pass
    return None


def _build_location_map_df(project: dict) -> pd.DataFrame:
    """Returns a DataFrame with lat/lon/name for all locations that have coordinates."""
    rows = []
    for loc in project["locations"].values():
        if loc.get("lat") is not None and loc.get("lon") is not None:
            rows.append({
                "lat": loc["lat"],
                "lon": loc["lon"],
                "name": loc["name"],
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["lat", "lon", "name"])


def _build_distance_matrix(project: dict) -> pd.DataFrame | None:
    """
    Returns a symmetric distance matrix DataFrame (km) for all located locations.
    Returns None if fewer than 2 locations have coordinates.
    """
    located = [
        loc for loc in project["locations"].values()
        if loc.get("lat") is not None and loc.get("lon") is not None
    ]
    if len(located) < 2:
        return None
    names = [loc["name"] for loc in located]
    n = len(located)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = _haversine_km(
                    located[i]["lat"], located[i]["lon"],
                    located[j]["lat"], located[j]["lon"],
                )
    df = pd.DataFrame(matrix, index=names, columns=names)
    return df


def _calc_connection_costs(project: dict) -> tuple[float, float]:
    """
    Returns (total_connection_capex, total_connection_opex_per_yr) across all
    inter-site connections, using the stored distance and cost-per-km rates.
    Distance is recomputed live from location coordinates so it stays accurate
    if a postcode is changed after the connection was defined.
    """
    locs = project["locations"]
    total_capex = 0.0
    total_opex = 0.0
    for conn in project.get("inter_site_connections", []):
        loc_a = locs.get(conn["loc_id_a"])
        loc_b = locs.get(conn["loc_id_b"])
        if not loc_a or not loc_b:
            continue
        if loc_a.get("lat") is None or loc_b.get("lat") is None:
            continue
        dist_km = _haversine_km(loc_a["lat"], loc_a["lon"], loc_b["lat"], loc_b["lon"])
        total_capex += dist_km * conn.get("capex_per_km", 0.0)
        total_opex  += dist_km * conn.get("opex_per_km_per_yr", 0.0)
    return total_capex, total_opex


# -------------------------------------------------------------------------
# CASH FLOW HELPER
# -------------------------------------------------------------------------
def _build_indicative_cashflow(agg: dict, proj_life: int, inflation: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (years, annual_revenue, annual_opex_cost, cumulative_cf).
    Revenue and OPEX are both escalated by inflation from Year 1.
    Year 0 = -total_capex.
    """
    years = np.arange(0, proj_life + 1)
    annual_revenue = np.zeros(proj_life + 1)
    annual_opex_cost = np.zeros(proj_life + 1)
    for y in range(1, proj_life + 1):
        inf_factor = (1 + inflation) ** (y - 1)
        annual_revenue[y] = agg["total_revenue_yr"] * inf_factor
        annual_opex_cost[y] = agg["total_opex_cost"] * inf_factor
    equity_fcf = np.zeros(proj_life + 1)
    equity_fcf[0] = -agg["total_capex"]
    for y in range(1, proj_life + 1):
        equity_fcf[y] = annual_revenue[y] - annual_opex_cost[y]
    cumulative_cf = np.cumsum(equity_fcf)
    return years, annual_revenue, annual_opex_cost, cumulative_cf


def _find_payback_year(cumulative_cf: np.ndarray) -> int | None:
    """Returns the first year index where cumulative cash flow >= 0, or None."""
    for y in range(1, len(cumulative_cf)):
        if cumulative_cf[y] >= 0:
            return y
    return None


# =========================================================================
# SIDEBAR
# =========================================================================
def _render_sidebar(projects: dict):
    accent = HS_GREEN

    st.sidebar.markdown(
        f'<p style="color:{accent};font-size:0.82rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;'
        f'margin-bottom:8px;border-bottom:1px solid {HS_GREEN_DARK};padding-bottom:5px;">Projects</p>',
        unsafe_allow_html=True,
    )

    project_ids = list(projects.keys())
    new_project_option = "__new__"
    options = project_ids + [new_project_option]
    _ensure_valid_sidebar_project_selection(project_ids, new_project_option)

    active_pid = st.session_state["pb_active_project"]
    active_index = 0
    selected_state = st.session_state.get("pb_sidebar_project_select_id")
    if selected_state in options:
        active_index = options.index(selected_state)
    elif active_pid and active_pid in project_ids:
        active_index = options.index(active_pid)
    elif not project_ids:
        active_index = options.index(new_project_option)

    selected_project_id = st.sidebar.selectbox(
        "Active project",
        options,
        index=active_index,
        key="pb_sidebar_project_select_id",
        format_func=lambda option: "+ New project" if option == new_project_option else projects[option]["name"],
    )

    if selected_project_id == new_project_option:
        st.sidebar.markdown(
            f'<p style="color:{HS_GREY};font-size:0.80rem;margin-top:6px;">Fill in project details below:</p>',
            unsafe_allow_html=True,
        )
        new_name = st.sidebar.text_input("Project name", key="pb_new_proj_name", placeholder="e.g. Aberdeen Port H2")
        new_desc = st.sidebar.text_area(
            "Description (optional)",
            key="pb_new_proj_desc",
            height=COMPACT_TEXT_AREA_HEIGHT,
        )
        st.sidebar.button("Create Project", key="pb_create_proj_btn", on_click=_handle_create_project)
        create_error = st.session_state.get("pb_sidebar_create_error")
        if create_error:
            st.sidebar.error(create_error)
        return None

    else:
        if selected_project_id in projects:
            st.session_state["pb_active_project"] = selected_project_id
            project = projects[selected_project_id]

            st.sidebar.markdown("---")
            st.sidebar.markdown(
                f'<p style="color:{accent};font-size:0.82rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;'
                f'margin-bottom:8px;border-bottom:1px solid {HS_GREEN_DARK};padding-bottom:5px;">Analysis Parameters</p>',
                unsafe_allow_html=True,
            )
            pid = project["id"]
            project["project_life_years"] = st.sidebar.slider(
                "Project life (years)", 5, 30, project["project_life_years"], key=f"pb_proj_life_{pid}"
            )
            project["discount_rate_pct"] = st.sidebar.number_input(
                "Discount rate (%)", 1.0, 20.0, project["discount_rate_pct"], 0.5, key=f"pb_disc_rate_{pid}"
            )
            project["inflation_rate_pct"] = st.sidebar.number_input(
                "Inflation rate (%)", 0.0, 10.0, project["inflation_rate_pct"], 0.5, key=f"pb_inf_rate_{pid}"
            )
            project["degradation_rate_pct"] = st.sidebar.number_input(
                "Annual degradation (%)", 0.0, 5.0, project["degradation_rate_pct"], 0.05, key=f"pb_deg_rate_{pid}"
            )
            project["tax_rate_pct"] = st.sidebar.number_input(
                "Corporation tax rate (%)", 0.0, 100.0, project["tax_rate_pct"], 1.0, key=f"pb_tax_rate_{pid}"
            )
            project["depreciation_rate_pct"] = st.sidebar.number_input(
                "Depreciation rate (%)", 0.0, 100.0, project["depreciation_rate_pct"], 1.0, key=f"pb_dep_rate_{pid}"
            )
            project["h2_sale_price_gbp_per_kg"] = st.sidebar.number_input(
                "Hydrogen sale price (£/kg)", 0.0, 100.0, project["h2_sale_price_gbp_per_kg"], 0.25, key=f"pb_h2_sale_{pid}"
            )
            carbon_options = ["No", "Yes"]
            include_carbon = project.get("include_carbon_credits", "No")
            if include_carbon not in carbon_options:
                include_carbon = "No"
            project["include_carbon_credits"] = st.sidebar.selectbox(
                "Include carbon credits?",
                carbon_options,
                index=carbon_options.index(include_carbon),
                key=f"pb_carbon_include_{pid}",
            )
            project["carbon_credit_price_gbp_per_tonne"] = st.sidebar.number_input(
                "Carbon credit price (£/tonne CO2)",
                0.0,
                1_000.0,
                project["carbon_credit_price_gbp_per_tonne"],
                1.0,
                key=f"pb_carbon_price_{pid}",
            )

            st.sidebar.markdown("---")
            st.sidebar.button(
                "Delete this project",
                key="pb_del_proj_btn",
                on_click=_handle_delete_project,
                args=(selected_project_id,),
            )

            return project

    return None


def _render_green_offport_add_form(project: dict, active_loc_id: str, loc: dict) -> None:
    key_prefix = f"pb_go_{active_loc_id}"
    st.caption(
        "Build a Green OffPort scenario using the same SIF hourly physics, utilities, costs, and cashflow pipeline as the dedicated Green OffPort page."
    )

    workbook_error = None
    try:
        load_sif_hourly_profiles()
    except Exception as exc:
        workbook_error = str(exc)
        st.error(f"Green OffPort workbook unavailable: {workbook_error}")

    with st.expander("Production & Generation Assets", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            ownership = st.selectbox(
                "Ownership model",
                ["Owned", "Bought under PPA"],
                key=f"{key_prefix}_ownership",
                help="Owned: CAPEX for generation assets is included. PPA: no generation CAPEX, electricity cost applied instead.",
            )
            production_method = st.selectbox(
                "Production method",
                ["Solar only", "Wind only", "Solar and wind", "Grid only"],
                key=f"{key_prefix}_production_method",
            )
            electrolyser_mw = st.number_input(
                "Electrolyser size (MW)",
                min_value=0.1,
                max_value=50.0,
                value=1.0,
                step=0.1,
                key=f"{key_prefix}_electrolyser_mw",
                help="Rated capacity of the electrolyser stack.",
            )
            efficiency_kwh_per_kg = st.number_input(
                "Electrolyser efficiency (kWh/kg H2)",
                min_value=40.0,
                max_value=70.0,
                value=53.0,
                step=0.5,
                key=f"{key_prefix}_efficiency",
                help="Energy consumption per kg of hydrogen produced.",
            )
        with c2:
            solar_mw = st.number_input(
                "Solar farm capacity (MW)",
                min_value=0.0,
                max_value=50.0,
                value=2.0,
                step=0.5,
                key=f"{key_prefix}_solar_mw",
            )
            wind_mw = st.number_input(
                "Wind turbine capacity (MW)",
                min_value=0.0,
                max_value=50.0,
                value=1.0,
                step=0.5,
                key=f"{key_prefix}_wind_mw",
            )
            grid_mw = st.number_input(
                "Grid connection capacity (MW)",
                min_value=0.0,
                max_value=50.0,
                value=1.0,
                step=0.5,
                key=f"{key_prefix}_grid_mw",
            )
            st.markdown(
                f'<p style="color:{HS_GREY};font-size:0.86rem;line-height:1.5;">Rated output at full load: '
                f'<b style="color:#fff;">{electrolyser_mw * 1000 / efficiency_kwh_per_kg:.1f} kg H2/hr</b></p>',
                unsafe_allow_html=True,
            )

    with st.expander("Utilities & Site Configuration", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            water_source = st.selectbox(
                "Water source",
                ["Highly pure", "Tap water", "Rainwater"],
                key=f"{key_prefix}_water_source",
                help="Highly pure requires water purification unit (CAPEX + energy). Rainwater/tap are lower cost.",
            )
            compression = st.selectbox(
                "Compression level",
                ["None", "Low (100 bar)", "Medium (350 bar)", "High (700 bar)"],
                key=f"{key_prefix}_compression",
            )
            storage_days = st.number_input(
                "Onsite storage (days of max production)",
                min_value=0.0,
                max_value=30.0,
                value=1.0,
                step=0.5,
                key=f"{key_prefix}_storage_days",
                help="Number of days of maximum daily H2 production to hold in storage.",
            )
        with c2:
            tube_trailer_required = st.selectbox(
                "40ft tube trailer required?",
                ["No", "Yes"],
                key=f"{key_prefix}_tube_trailer",
                help="Adds £250,000 to CAPEX if required.",
            )
            transportation_required = st.selectbox(
                "Transportation required?",
                ["No", "Yes"],
                key=f"{key_prefix}_transportation",
                help="Adds £0.75/kg H2 to annual OPEX if required.",
            )
            number_of_operators = st.number_input(
                "Number of operators",
                min_value=0,
                max_value=20,
                value=0,
                step=1,
                key=f"{key_prefix}_operators",
                help="Each operator adds £30,000/yr to OPEX.",
            )

    with st.expander("Costs", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            grid_connection_cost = st.number_input(
                "Grid connection cost (£)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                key=f"{key_prefix}_grid_connection_cost",
            )
            land_cost = st.number_input(
                "Land purchase (£)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                key=f"{key_prefix}_land_cost",
            )
            installation_cost = st.number_input(
                "Installation costs (£)",
                min_value=0.0,
                value=30000.0,
                step=1000.0,
                key=f"{key_prefix}_installation_cost",
            )
            licensing_cost = st.number_input(
                "Licensing, permitting & planning (£)",
                min_value=0.0,
                value=30000.0,
                step=1000.0,
                key=f"{key_prefix}_licensing_cost",
            )
        with c2:
            rent_cost = st.number_input(
                "Annual rent (£/yr)",
                min_value=0.0,
                value=4000.0,
                step=100.0,
                key=f"{key_prefix}_rent_cost",
            )
            renewable_electricity_cost = st.number_input(
                "Renewables electricity cost (£/MWh)",
                min_value=0.0,
                value=80.0,
                step=1.0,
                key=f"{key_prefix}_renewable_electricity_cost",
                help="Used for PPA stack electricity cost.",
            )
            grid_electricity_cost = st.number_input(
                "Grid electricity cost (£/MWh)",
                min_value=0.0,
                value=150.0,
                step=1.0,
                key=f"{key_prefix}_grid_electricity_cost",
                help="Used for compression and purification electricity.",
            )
            water_cost = st.number_input(
                "Water cost (£/m3)",
                min_value=0.0,
                value=1.93,
                step=0.01,
                key=f"{key_prefix}_water_cost",
            )

    default_display_name = f"Green OffPort - {production_method} ({electrolyser_mw:.1f} MW electrolyser)"
    display_context = (production_method, electrolyser_mw)
    if st.session_state.get(f"{key_prefix}_display_context") != display_context:
        st.session_state[f"{key_prefix}_display_name"] = default_display_name
        st.session_state[f"{key_prefix}_display_context"] = display_context
    display_name = st.text_input("Display name", key=f"{key_prefix}_display_name")

    inputs = {
        "ownership": ownership,
        "production_method": production_method,
        "electrolyser_mw": electrolyser_mw,
        "solar_mw": solar_mw,
        "wind_mw": wind_mw,
        "grid_mw": grid_mw,
        "efficiency_kwh_per_kg": efficiency_kwh_per_kg,
        "water_source": water_source,
        "compression": compression,
        "storage_days": storage_days,
        "tube_trailer_required": tube_trailer_required,
        "transportation_required": transportation_required,
        "number_of_operators": number_of_operators,
        "grid_connection_cost": grid_connection_cost,
        "land_cost": land_cost,
        "installation_cost": installation_cost,
        "licensing_cost": licensing_cost,
        "rent_cost": rent_cost,
        "renewable_electricity_cost_mwh": renewable_electricity_cost,
        "grid_electricity_cost_mwh": grid_electricity_cost,
        "water_cost_m3": water_cost,
    }

    generation_warning = get_generation_capacity_warning(
        production_method=production_method,
        solar_mw=solar_mw,
        wind_mw=wind_mw,
        grid_mw=grid_mw,
    )
    if generation_warning:
        st.warning(generation_warning)

    preview_results = None
    preview_error = workbook_error
    if preview_error is None:
        try:
            preview_results = _build_green_offport_results(inputs, project)
        except Exception as exc:
            preview_error = str(exc)
            st.error(f"Green OffPort calculation failed: {preview_error}")

    if preview_results is not None:
        physics = preview_results["physics"]
        utilities = preview_results["utilities"]
        costs = preview_results["costs"]
        cashflow = preview_results["cashflow"]
        prev_metrics = pd.DataFrame([
            {"Metric": "LCOH", "Value": f"{_fmt_currency(preview_results['lcoh'], 2)}/kg"},
            {"Metric": "Total CAPEX", "Value": _fmt_currency(costs["total_capex"])},
            {"Metric": "Year 1 OPEX", "Value": f"{_fmt_currency(costs['total_annual_opex'])}/yr"},
            {"Metric": "Annual H2 (actual)", "Value": f"{physics['annual_actual_h2_kg'] / 1000:,.2f} t"},
            {"Metric": "Annual H2 (theoretical)", "Value": f"{physics['annual_theoretical_h2_kg'] / 1000:,.2f} t"},
            {"Metric": "Annual water demand", "Value": f"{utilities['annual_water_demand_m3']:,.1f} m3"},
            {"Metric": "Purification demand", "Value": f"{utilities['annual_purification_kwh'] / 1000:,.2f} MWh"},
            {"Metric": "Compression demand", "Value": f"{utilities['annual_compression_kwh'] / 1000:,.2f} MWh"},
            {"Metric": "Pre-tax IRR", "Value": _fmt_percent(cashflow["ebitda_irr"])},
            {"Metric": "Post-tax IRR", "Value": _fmt_percent(cashflow["equity_after_tax_irr"])},
            {"Metric": "NPV", "Value": _fmt_currency_millions(cashflow["npv"])},
            {"Metric": "Payback", "Value": f"{cashflow['payback_period']} years"},
        ])
        st.dataframe(prev_metrics, use_container_width=True, hide_index=True, height=220)

    if st.button(
        "Add Green OffPort scenario",
        key=f"{key_prefix}_add",
        use_container_width=True,
        disabled=preview_results is None or preview_error is not None,
    ):
        if not display_name.strip():
            st.error("Enter a display name.")
        else:
            tech_id = "tech_" + _short_id()
            new_item = {
                "id": tech_id,
                "source_kind": GREEN_OFFPORT_SOURCE_KIND,
                "display_name": display_name.strip(),
                "category": GREEN_OFFPORT_CATEGORY,
                "type_": GREEN_OFFPORT_TYPE,
                "component": GREEN_OFFPORT_COMPONENT,
                "rating_value": electrolyser_mw,
                "rating_unit": "MW",
                "notes": "",
                "green_offport_inputs": inputs,
                "cofo_records": _make_green_offport_cofo_records(preview_results, tech_id),
            }
            _add_tech_item(project["id"], active_loc_id, new_item)
            st.success(f"Added: {display_name}")
            st.rerun()


# =========================================================================
# TAB 1 — BUILD  (locations + technology in one place)
# =========================================================================
# Layout: left panel = location list + add form
#         centre panel = selected location's tech items + remove
#         right panel = add technology form (Green OffPort, catalogue, or manual)
# =========================================================================
def _render_tab_build(project: dict) -> None:
    locs = project["locations"]

    # ---- headline KPIs (compact single row) ----
    agg = _aggregate_project_cofo(project)
    conn_capex, conn_opex = _calc_connection_costs(project)
    total_capex_incl = agg["total_capex"] + conn_capex
    total_opex_incl  = agg["total_opex_cost"] + conn_opex

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total CAPEX",       _fmt_currency_millions(total_capex_incl))
    k2.metric("Annual OPEX",       f"{_fmt_currency(total_opex_incl)}/yr")
    k3.metric("H2 Production",     f"{agg['total_h2_kg_yr']/1000:,.1f} t/yr")
    k4.metric("Annual Revenue",    f"{_fmt_currency(agg['total_revenue_yr'])}/yr")
    k5.metric("Footprint",         f"{agg['total_footprint_m2']:,.0f} m²")
    k6.metric("CO2 Avoided",       f"{agg['total_co2_t_yr']:,.1f} t/yr")
    st.markdown("---")

    # ---- three-panel layout ----
    col_locs, col_items, col_add = st.columns([1, 2, 2])

    # ================================================================
    # LEFT: location list + add location
    # ================================================================
    with col_locs:
        st.markdown(f'<p class="hs-section-header">Locations</p>', unsafe_allow_html=True)

        if not locs:
            st.info("No locations yet. Add one below.")
        else:
            # Which location is selected
            loc_ids = list(locs.keys())
            active_loc_id = st.session_state.get("pb_build_active_loc_id")
            if active_loc_id not in loc_ids:
                active_loc_id = loc_ids[0]
                st.session_state["pb_build_active_loc_id"] = active_loc_id

            for lid, loc in locs.items():
                n_items = len(loc["technology_items"])
                has_coords = loc.get("lat") is not None
                coord_line = f"{loc['lat']:.3f}, {loc['lon']:.3f}" if has_coords else "no coordinates"
                is_selected = lid == active_loc_id

                # Highlight selected location
                border_color = HS_GREEN if is_selected else "#4a505a"
                st.markdown(
                    f'<div style="background:{HS_BG_CARD};border-left:4px solid {border_color};'
                    f'border-radius:4px;padding:10px 12px;margin-bottom:6px;">'
                    f'<p style="color:{HS_WHITE};font-weight:600;font-size:0.9rem;margin:0 0 2px 0;">{loc["name"]}</p>'
                    f'<p style="color:{HS_GREY};font-size:0.78rem;margin:0;">{n_items} item(s) &nbsp;|&nbsp; {coord_line}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Select", key=f"pb_build_sel_{lid}", use_container_width=True):
                    st.session_state["pb_build_active_loc_id"] = lid
                    st.rerun()

        st.markdown("---")
        st.markdown(f'<p class="hs-section-header">Add Location</p>', unsafe_allow_html=True)
        new_loc_name = st.text_input("Name", key="pb_build_new_loc_name", placeholder="e.g. Quayside Block A")

        # Coordinates: postcode lookup or manual
        new_pc = st.text_input("UK Postcode", key="pb_build_new_pc",
                               placeholder="e.g. PL1 2NZ",
                               help="Enter a UK postcode and click Look up, or enter coordinates manually below.")
        new_location_key_nonce = st.session_state.setdefault("pb_build_new_location_key_nonce", 0)
        new_lat_key = f"pb_build_new_lat_inp_{new_location_key_nonce}"
        new_lon_key = f"pb_build_new_lon_inp_{new_location_key_nonce}"
        lu_col, _ = st.columns([1, 1])
        with lu_col:
            if st.button("Look up postcode", key="pb_build_new_pc_lookup", use_container_width=True):
                if new_pc.strip():
                    coords = _lookup_postcode(new_pc.strip())
                    if coords:
                        st.session_state["pb_build_new_lat"] = coords[0]
                        st.session_state["pb_build_new_lon"] = coords[1]
                        st.session_state[new_lat_key] = coords[0]
                        st.session_state[new_lon_key] = coords[1]
                        st.success(f"Found: {coords[0]:.4f}, {coords[1]:.4f}")
                    else:
                        st.error("Postcode not found.")
                else:
                    st.error("Enter a postcode first.")

        lat_col, lon_col = st.columns(2)
        with lat_col:
            new_lat = st.number_input(
                "Latitude", min_value=49.0, max_value=61.0,
                value=float(st.session_state.get("pb_build_new_lat", 54.0)),
                step=0.0001, format="%.5f",
                key=new_lat_key,
                help="UK latitude (49–61)"
            )
        with lon_col:
            new_lon = st.number_input(
                "Longitude", min_value=-8.0, max_value=2.0,
                value=float(st.session_state.get("pb_build_new_lon", -2.0)),
                step=0.0001, format="%.5f",
                key=new_lon_key,
                help="UK longitude (-8 to 2)"
            )

        # Coordinates are considered set if they differ from default placeholders,
        # or if a postcode lookup has populated the session state helpers.
        _coords_set = (
            st.session_state.get("pb_build_new_lat") is not None
            or new_lat != 54.0
            or new_lon != -2.0
        )

        if st.button("Add Location", key="pb_build_add_loc_btn", use_container_width=True):
            if not new_loc_name.strip():
                st.error("Enter a location name.")
            else:
                resolved_lat = new_lat
                resolved_lon = new_lon
                postcode_lookup_failed = False
                if new_pc.strip():
                    coords = _lookup_postcode(new_pc.strip())
                    if coords:
                        resolved_lat, resolved_lon = coords
                    else:
                        postcode_lookup_failed = True

                if postcode_lookup_failed and not _coords_set:
                    st.error("Postcode not found. Check it, click Look up, or enter Latitude and Longitude manually.")
                elif not new_pc.strip() and not _coords_set:
                    st.error("Coordinates required — enter a UK postcode, click Look up, or set Latitude and Longitude manually.")
                else:
                    new_lid = _create_location(project["id"], new_loc_name, "")
                    loc_obj = st.session_state["pb_projects"][project["id"]]["locations"][new_lid]
                    loc_obj["lat"] = resolved_lat
                    loc_obj["lon"] = resolved_lon
                    if new_pc.strip():
                        loc_obj["postcode"] = new_pc.strip().upper()
                    # Reset helpers
                    st.session_state.pop("pb_build_new_lat", None)
                    st.session_state.pop("pb_build_new_lon", None)
                    st.session_state["pb_build_new_location_key_nonce"] = new_location_key_nonce + 1
                    st.session_state["pb_build_active_loc_id"] = new_lid
                    st.rerun()

    # ================================================================
    # CENTRE: selected location's tech items
    # ================================================================
    with col_items:
        active_loc_id = st.session_state.get("pb_build_active_loc_id")
        if not locs or active_loc_id not in locs:
            st.markdown(f'<p class="hs-section-header">Technology Items</p>', unsafe_allow_html=True)
            st.info("Select or add a location on the left.")
        else:
            loc = locs[active_loc_id]
            tech_items = loc["technology_items"]
            st.markdown(
                f'<p class="hs-section-header">Technology at {loc["name"]}</p>',
                unsafe_allow_html=True,
            )

            # Location-level KPIs
            lk_capex = lk_opex = lk_power = lk_water = lk_fp = 0.0
            for item in tech_items.values():
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "CAPEX":
                        lk_capex += rec["value"]
                    elif rec["cofo_type"] == "OPEX":
                        k_ = _record_opex_type_key(rec)
                        if k_ == OPEX_TYPE_COST:   lk_opex  += rec["value"]
                        elif k_ == OPEX_TYPE_POWER: lk_power += rec["value"]
                        elif k_ == OPEX_TYPE_WATER: lk_water += rec["value"]
                    elif rec["cofo_type"] == "Footprint":
                        lk_fp += rec["value"]
            lkm1, lkm2, lkm3 = st.columns(3)
            lkm1.metric("CAPEX",        _fmt_currency(lk_capex))
            lkm2.metric("OPEX/yr",      _fmt_currency(lk_opex))
            lkm3.metric("Footprint",    f"{lk_fp:,.0f} m²")

            st.markdown("<br>", unsafe_allow_html=True)

            if not tech_items:
                st.info("No technology items yet. Use the form on the right to add one.")
            else:
                for tid, item in list(tech_items.items()):
                    item_capex = sum(r["value"] for r in item["cofo_records"] if r["cofo_type"] == "CAPEX")
                    item_opex  = sum(r["value"] for r in item["cofo_records"]
                                     if r["cofo_type"] == "OPEX" and _record_opex_type_key(r) == OPEX_TYPE_COST)
                    with st.expander(
                        f"{item['display_name']}  —  {_fmt_currency(item_capex)} CAPEX",
                        expanded=False,
                    ):
                        ic1, ic2, ic3 = st.columns(3)
                        ic1.markdown(f'<p style="color:{HS_GREY};font-size:0.8rem;margin:0;">Category</p>'
                                     f'<p style="color:{HS_WHITE};font-size:0.88rem;margin:0;">{item["category"]}</p>',
                                     unsafe_allow_html=True)
                        ic2.markdown(f'<p style="color:{HS_GREY};font-size:0.8rem;margin:0;">Rating</p>'
                                     f'<p style="color:{HS_WHITE};font-size:0.88rem;margin:0;">{item["rating_value"]} {item["rating_unit"]}</p>',
                                     unsafe_allow_html=True)
                        ic3.markdown(f'<p style="color:{HS_GREY};font-size:0.8rem;margin:0;">OPEX/yr</p>'
                                     f'<p style="color:{HS_WHITE};font-size:0.88rem;margin:0;">{_fmt_currency(item_opex)}</p>',
                                     unsafe_allow_html=True)
                        if item.get("green_offport_error"):
                            st.error(f"Green OffPort scenario could not be recalculated: {item['green_offport_error']}")
                        # COFO records table
                        if item["cofo_records"]:
                            cofo_rows = []
                            for r in item["cofo_records"]:
                                type_detail = (
                                    _record_opex_type_label(r) if r["cofo_type"] == "OPEX"
                                    else r["output_subtype"] or "—"
                                )
                                cofo_rows.append({
                                    "Type": r["cofo_type"],
                                    "Item": r["item_name"],
                                    "Detail": type_detail,
                                    "Value": f"{r['value']:,.1f}",
                                    "Unit": r["unit"],
                                })
                            st.dataframe(
                                pd.DataFrame(cofo_rows),
                                use_container_width=True,
                                hide_index=True,
                            )
                        if st.button("Remove this item", key=f"pb_build_remove_{tid}", type="secondary"):
                            _remove_tech_item(project["id"], active_loc_id, tid)
                            st.rerun()

            # Location management (edit name / delete) — compact section
            st.markdown("---")
            with st.expander("Edit / delete this location", expanded=False):
                edit_name = st.text_input("Location name", value=loc["name"], key=f"pb_build_edit_name_{active_loc_id}")
                edit_desc = st.text_area("Description", value=loc["description"],
                                         key=f"pb_build_edit_desc_{active_loc_id}", height=COMPACT_TEXT_AREA_HEIGHT)
                sv_col, dl_col = st.columns(2)
                with sv_col:
                    if st.button("Save", key=f"pb_build_save_loc_{active_loc_id}"):
                        loc["name"] = edit_name.strip() or loc["name"]
                        loc["description"] = edit_desc
                        st.success("Saved.")
                with dl_col:
                    if st.button("Delete location", key=f"pb_build_del_loc_{active_loc_id}", type="secondary"):
                        if len(tech_items) == 0:
                            name_del = loc["name"]
                            _delete_location(project["id"], active_loc_id)
                            st.session_state.pop("pb_build_active_loc_id", None)
                            st.success(f"'{name_del}' deleted.")
                            st.rerun()
                        else:
                            st.warning(f"Remove all {len(tech_items)} technology items first.")

    # ================================================================
    # RIGHT: add technology form
    # ================================================================
    with col_add:
        active_loc_id = st.session_state.get("pb_build_active_loc_id")
        if not locs or active_loc_id not in locs:
            st.markdown(f'<p class="hs-section-header">Add Technology</p>', unsafe_allow_html=True)
            st.info("Select a location first.")
        else:
            loc = locs[active_loc_id]
            st.markdown(
                f'<p class="hs-section-header">Add Technology to {loc["name"]}</p>',
                unsafe_allow_html=True,
            )

            source_type = st.radio(
                "Source",
                [SOURCE_GREEN_OFFPORT, SOURCE_CATALOGUE_ADVANCED, SOURCE_MANUAL_ADVANCED],
                horizontal=True,
                key=f"pb_build_source_{active_loc_id}",
            )

            # ---- GREEN OFFPORT MODEL ----
            if source_type == SOURCE_GREEN_OFFPORT:
                _render_green_offport_add_form(project, active_loc_id, loc)

            # ---- FROM CATALOGUE ----
            elif source_type == SOURCE_CATALOGUE_ADVANCED:
                categories = list(TECH_CATALOGUE.keys())
                selected_cat = st.selectbox("Category", categories, key="pb_build_cat")
                types = list(TECH_CATALOGUE[selected_cat].keys())
                selected_type = st.selectbox("Type", types, key="pb_build_type")
                components = list(TECH_CATALOGUE[selected_cat][selected_type].keys())
                selected_comp = st.selectbox("Component", components, key="pb_build_comp")

                spec = TECH_CATALOGUE[selected_cat][selected_type][selected_comp]

                rating_val = st.number_input(
                    f"Rating ({spec['rating_unit']})",
                    min_value=spec["rating_min"],
                    max_value=spec["rating_max"],
                    value=spec["rating_default"],
                    step=spec["rating_step"],
                    key="pb_build_rating",
                    help=spec["rating_help"],
                )

                # Auto-update display name when selection/rating changes
                _new_default = f"{selected_comp} ({rating_val} {spec['rating_unit']})"
                _prev_ctx = st.session_state.get("pb_build_display_name_ctx")
                _cur_ctx = (selected_cat, selected_type, selected_comp, rating_val)
                if _prev_ctx != _cur_ctx:
                    st.session_state["pb_build_display_name"] = _new_default
                    st.session_state["pb_build_display_name_ctx"] = _cur_ctx
                display_name = st.text_input("Display name", key="pb_build_display_name")

                # Live COFO preview
                preview_records, preview_errors = calculate_cofo_records(spec, rating_val)
                if preview_errors:
                    st.error("Formula errors: " + "; ".join(preview_errors))
                if preview_records:
                    st.markdown(
                        f'<p style="color:{HS_GREY};font-size:0.78rem;margin:6px 0 3px 0;">Auto-calculated costs & outputs:</p>',
                        unsafe_allow_html=True,
                    )
                    prev_df = pd.DataFrame([{
                        "Type": r["cofo_type"],
                        "Item": r["item_name"],
                        "Value": f"{r['value']:,.1f}",
                        "Unit": r["unit"],
                    } for r in preview_records])
                    st.dataframe(prev_df, use_container_width=True, hide_index=True, height=180)

                if st.button("Add to location", key="pb_build_add_cat_btn", use_container_width=True,
                             disabled=bool(preview_errors)):
                    if not display_name.strip():
                        st.error("Enter a display name.")
                    else:
                        new_item = {
                            "id": "tech_" + _short_id(),
                            "display_name": display_name.strip(),
                            "category": selected_cat,
                            "type_": selected_type,
                            "component": selected_comp,
                            "rating_value": rating_val,
                            "rating_unit": spec["rating_unit"],
                            "notes": "",
                            "cofo_records": preview_records,
                        }
                        _add_tech_item(project["id"], active_loc_id, new_item)
                        st.success(f"Added: {display_name}")
                        st.rerun()

            # ---- MANUAL ENTRY ----
            elif source_type == SOURCE_MANUAL_ADVANCED:
                pending = _get_pending_manual_cofo(project["id"], active_loc_id)

                st.caption("Build a custom technology item by entering each cost, output, and footprint record below.")

                manual_name = st.text_input("Item display name", key="pb_build_manual_name",
                                            placeholder="e.g. Custom heat exchanger")
                mc1, mc2 = st.columns(2)
                with mc1:
                    manual_cat  = st.selectbox("Category", list(TECH_CATALOGUE.keys()) + ["Other"],
                                               key="pb_build_manual_cat")
                    manual_type = st.text_input("Type", key="pb_build_manual_type", placeholder="e.g. Heat Recovery")
                with mc2:
                    manual_comp   = st.text_input("Component", key="pb_build_manual_comp",
                                                  placeholder="e.g. Plate Heat Exchanger")
                    manual_rating = st.text_input("Rating", key="pb_build_manual_rating",
                                                  placeholder="e.g. 500 kW")

                st.markdown(
                    f'<p style="color:{HS_GREEN};font-size:0.78rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.08em;margin:10px 0 4px 0;">Add a COFO record</p>',
                    unsafe_allow_html=True,
                )

                cofo_type_sel = st.selectbox("Record type", ["CAPEX", "OPEX", "Footprint", "Output"],
                                             key="pb_build_manual_cofo_type")
                cofo_item_name = st.text_input("Record name", key="pb_build_manual_cofo_name",
                                               placeholder="e.g. Heat exchanger unit")

                new_cofo: dict = {
                    "id": _short_id(), "cofo_type": cofo_type_sel,
                    "item_name": cofo_item_name, "opex_type": "", "opex_type_key": "",
                    "output_type": "", "output_subtype": "",
                    "value": 0.0, "unit": "",
                    "is_auto_calculated": False, "source_formula": "", "source_note": "Manual entry",
                }

                if cofo_type_sel == "CAPEX":
                    new_cofo["value"] = st.number_input("Value (£)", min_value=0.0, step=1000.0,
                                                         key="pb_build_manual_capex_val")
                    new_cofo["unit"] = "£"

                elif cofo_type_sel == "OPEX":
                    ot = st.selectbox("OPEX resource type",
                                      [OPEX_TYPE_COST, OPEX_TYPE_POWER, OPEX_TYPE_WATER, OPEX_TYPE_OTHER],
                                      key="pb_build_manual_opex_type",
                                      format_func=_opex_type_label)
                    new_cofo["opex_type_key"] = ot
                    new_cofo["opex_type"] = _opex_type_label(ot)
                    new_cofo["value"] = st.number_input("Value", min_value=0.0, step=0.1,
                                                         key="pb_build_manual_opex_val")
                    new_cofo["unit"] = st.text_input("Unit", value=_opex_unit_for_key(ot),
                                                      key="pb_build_manual_opex_unit")

                elif cofo_type_sel == "Footprint":
                    new_cofo["value"] = st.number_input("Area (m²)", min_value=0.0, step=1.0,
                                                         key="pb_build_manual_foot_val")
                    new_cofo["unit"] = "m²"

                elif cofo_type_sel == "Output":
                    otyp = st.selectbox("Output type", ["Product", "Revenue", "Saving"],
                                        key="pb_build_manual_out_type")
                    osub = st.selectbox("Output subtype",
                                        [OUTPUT_SUBTYPE_H2_PRODUCTION, OUTPUT_SUBTYPE_H2_COMPRESSION,
                                         OUTPUT_SUBTYPE_H2_STORAGE, OUTPUT_SUBTYPE_POWER_GENERATION,
                                         OUTPUT_SUBTYPE_WATER_OUTPUT, OUTPUT_SUBTYPE_REVENUE,
                                         OUTPUT_SUBTYPE_CO2_AVOIDED, "NOx (kg/yr)", "SOx (kg/yr)", "Other"],
                                        key="pb_build_manual_out_sub")
                    new_cofo["output_type"] = otyp
                    new_cofo["output_subtype"] = osub
                    new_cofo["value"] = st.number_input("Value", min_value=0.0, step=0.1,
                                                         key="pb_build_manual_out_val")
                    new_cofo["unit"] = st.text_input("Unit", key="pb_build_manual_out_unit")

                if st.button("Add record", key="pb_build_manual_add_rec", use_container_width=True):
                    if not cofo_item_name.strip():
                        st.error("Enter a record name.")
                    else:
                        pending.append(new_cofo)
                        st.success(f"Record '{cofo_item_name}' added.")
                        st.rerun()

                # Pending records list
                if pending:
                    st.markdown(
                        f'<p style="color:{HS_GREY};font-size:0.78rem;margin:8px 0 3px 0;">'
                        f'{len(pending)} pending record(s):</p>',
                        unsafe_allow_html=True,
                    )
                    for pi, prec in enumerate(pending):
                        p_col, p_del = st.columns([5, 1])
                        with p_col:
                            detail = _record_opex_type_label(prec) if prec["cofo_type"] == "OPEX" \
                                     else prec["output_subtype"] or "—"
                            st.markdown(
                                f'<div style="background:{HS_BG_DARK};border-radius:3px;padding:5px 10px;'
                                f'font-size:0.82rem;color:{HS_WHITE};">'
                                f'<b>{prec["cofo_type"]}</b> — {prec["item_name"]} '
                                f'({detail}) = {prec["value"]:,.1f} {prec["unit"]}</div>',
                                unsafe_allow_html=True,
                            )
                        with p_del:
                            if st.button("X", key=f"pb_build_del_rec_{pi}", help="Remove this record"):
                                pending.pop(pi)
                                st.rerun()

                    save_col, clear_col = st.columns(2)
                    with save_col:
                        if st.button("Save item", key="pb_build_manual_save", use_container_width=True):
                            if not manual_name.strip():
                                st.error("Enter a display name for this item.")
                            else:
                                parts = (manual_rating or "").strip().split()
                                try:
                                    rv = float(parts[0]) if parts else 0.0
                                    ru = " ".join(parts[1:]) if len(parts) > 1 else "—"
                                except ValueError:
                                    rv, ru = 0.0, manual_rating or "—"
                                new_item = {
                                    "id": "tech_" + _short_id(),
                                    "display_name": manual_name.strip(),
                                    "category": manual_cat,
                                    "type_": manual_type or "—",
                                    "component": manual_comp or "—",
                                    "rating_value": rv,
                                    "rating_unit": ru,
                                    "notes": "",
                                    "cofo_records": list(pending),
                                }
                                _add_tech_item(project["id"], active_loc_id, new_item)
                                _clear_pending_manual_cofo(project["id"], active_loc_id)
                                st.success(f"Added: {manual_name}")
                                st.rerun()
                    with clear_col:
                        if st.button("Clear all", key="pb_build_manual_clear", use_container_width=True):
                            _clear_pending_manual_cofo(project["id"], active_loc_id)
                            st.rerun()


# =========================================================================
# TAB 2 — LOCATIONS & MAP
# =========================================================================
def _render_tab_locations_map(project: dict) -> None:
    locs = project["locations"]

    if not locs:
        st.info("Add locations in the Build tab first, then return here to set coordinates and define connections.")
        return

    # ---- Coordinate editor ----
    st.markdown(f'<p class="hs-section-header">Location Coordinates</p>', unsafe_allow_html=True)
    st.caption(
        "Locations added with a valid UK postcode are geocoded automatically. Use Look up to refresh a postcode, or Set to save manual coordinates. "
        "Coordinates are used to calculate distances between sites and to display the project map."
    )

    for loc_id, loc in locs.items():
        has_coords = loc.get("lat") is not None and loc.get("lon") is not None
        coord_status = f"{loc['lat']:.4f}, {loc['lon']:.4f}" if has_coords else "no coordinates"
        st.markdown(
            f'<p style="color:{HS_WHITE};font-weight:600;font-size:0.88rem;margin:12px 0 4px 0;">'
            f'{loc["name"]} &nbsp;<span style="color:{HS_GREY};font-weight:400;font-size:0.8rem;">'
            f'({coord_status})</span></p>',
            unsafe_allow_html=True,
        )
        pc_col, btn_col, lat_col, lon_col, clr_col = st.columns([2, 1, 1, 1, 1])
        with pc_col:
            new_pc = st.text_input("UK Postcode", value=loc.get("postcode", ""),
                                   key=f"pb_map_pc_{loc_id}", placeholder="e.g. PL1 2NZ", label_visibility="collapsed")
        with btn_col:
            if st.button("Look up", key=f"pb_map_lookup_{loc_id}"):
                coords = _lookup_postcode(new_pc)
                if coords:
                    loc["postcode"] = new_pc.strip().upper()
                    loc["lat"], loc["lon"] = coords
                    st.session_state[f"pb_map_lat_{loc_id}"] = coords[0]
                    st.session_state[f"pb_map_lon_{loc_id}"] = coords[1]
                    st.session_state[f"pb_map_coord_signature_{loc_id}"] = coords
                    st.success(f"Set: {coords[0]:.4f}, {coords[1]:.4f}")
                    st.rerun()
                else:
                    st.error(f"Postcode not found.")
        lat_key = f"pb_map_lat_{loc_id}"
        lon_key = f"pb_map_lon_{loc_id}"
        coord_signature_key = f"pb_map_coord_signature_{loc_id}"
        coord_signature = (float(loc["lat"]), float(loc["lon"])) if has_coords else None
        if has_coords and st.session_state.get(coord_signature_key) != coord_signature:
            st.session_state[lat_key] = coord_signature[0]
            st.session_state[lon_key] = coord_signature[1]
            st.session_state[coord_signature_key] = coord_signature
        with lat_col:
            lat_inp = st.number_input("Lat", min_value=49.0, max_value=61.0,
                                      value=float(loc["lat"]) if has_coords else 54.0,
                                      step=0.0001, format="%.5f",
                                      key=lat_key, label_visibility="collapsed",
                                      help="Latitude (49–61 for UK)")
        with lon_col:
            lon_inp = st.number_input("Lon", min_value=-8.0, max_value=2.0,
                                      value=float(loc["lon"]) if has_coords else -2.0,
                                      step=0.0001, format="%.5f",
                                      key=lon_key, label_visibility="collapsed",
                                      help="Longitude (-8 to 2 for UK)")
        with clr_col:
            if st.button("Set", key=f"pb_map_set_{loc_id}"):
                loc["lat"] = lat_inp
                loc["lon"] = lon_inp
                st.session_state[coord_signature_key] = (float(lat_inp), float(lon_inp))
                st.success("Set.")
                st.rerun()

    st.markdown("---")

    # ---- Map + distance matrix ----
    map_df   = _build_location_map_df(project)
    dist_df  = _build_distance_matrix(project)
    located  = len(map_df)

    if located == 0:
        st.info("Enter coordinates for at least one location above to see the project map.")
    else:
        col_map, col_dist = st.columns([3, 2])
        with col_map:
            st.markdown(f'<p class="hs-section-header">Project Map</p>', unsafe_allow_html=True)
            st.map(map_df[["lat", "lon"]], zoom=6, use_container_width=True)
            st.caption(f"{located} located site(s) shown.")
        with col_dist:
            st.markdown(f'<p class="hs-section-header">Straight-Line Distances (km)</p>', unsafe_allow_html=True)
            if dist_df is not None:
                dist_display = dist_df.copy().map(
                    lambda v: "—" if v == 0.0 else f"{v:.1f}"
                )
                st.dataframe(dist_display, use_container_width=True)
                st.caption("Haversine distances. Actual cable or pipe runs will be longer.")
            else:
                st.info("Add coordinates to at least 2 locations to see distances.")

    # ---- Inter-site connections ----
    st.markdown("---")
    st.markdown(f'<p class="hs-section-header">Inter-Site Connections</p>', unsafe_allow_html=True)
    st.caption(
        "Define connections between locations (electricity cable, H2 pipeline, road). "
        "Each connection adds CAPEX and annual OPEX based on the distance between the two sites. "
        "These costs flow through to the project totals."
    )

    connections = project.setdefault("inter_site_connections", [])
    located_locs = {lid: loc for lid, loc in locs.items() if loc.get("lat") is not None}
    loc_id_list  = list(located_locs.keys())

    CONNECTION_TYPES = {
        "Electricity cable (overhead)":   {"capex_per_km": 150_000, "opex_per_km_per_yr": 1_500},
        "Electricity cable (underground)":{"capex_per_km": 400_000, "opex_per_km_per_yr": 2_000},
        "H2 pipeline (low pressure)":     {"capex_per_km": 500_000, "opex_per_km_per_yr": 5_000},
        "H2 pipeline (high pressure)":    {"capex_per_km": 800_000, "opex_per_km_per_yr": 8_000},
        "Road access / haul route":        {"capex_per_km": 200_000, "opex_per_km_per_yr": 3_000},
        "Custom":                          {"capex_per_km": 0,       "opex_per_km_per_yr": 0},
    }

    # Existing connections table
    if connections:
        conn_rows = []
        for i, conn in enumerate(connections):
            la = project["locations"].get(conn["loc_id_a"])
            lb = project["locations"].get(conn["loc_id_b"])
            if not la or not lb or la.get("lat") is None or lb.get("lat") is None:
                continue
            d = _haversine_km(la["lat"], la["lon"], lb["lat"], lb["lon"])
            conn_rows.append({
                "#": i + 1,
                "From": la["name"], "To": lb["name"],
                "Type": conn.get("connection_type", "—"),
                "Distance": f"{d:.2f} km",
                "CAPEX": _fmt_currency(d * conn.get("capex_per_km", 0)),
                "OPEX/yr": _fmt_currency(d * conn.get("opex_per_km_per_yr", 0)),
            })
        if conn_rows:
            st.dataframe(pd.DataFrame(conn_rows), use_container_width=True, hide_index=True)
            del_col, _ = st.columns([2, 4])
            with del_col:
                del_idx = st.selectbox(
                    "Remove connection",
                    [None] + list(range(1, len(conn_rows) + 1)),
                    key="pb_map_del_conn",
                    format_func=lambda x: "— select —" if x is None else f"Connection {x}",
                )
            if del_idx is not None and st.button("Remove", key="pb_map_del_conn_btn"):
                connections.pop(del_idx - 1)
                st.rerun()

    # Add connection form
    if len(loc_id_list) < 2:
        st.info("Add coordinates to at least 2 locations to define connections.")
    else:
        with st.expander("Add a connection", expanded=(len(connections) == 0)):
            ca1, ca2 = st.columns(2)
            with ca1:
                from_id = st.selectbox("From", loc_id_list, key="pb_map_conn_from",
                                       format_func=lambda lid: located_locs[lid]["name"])
            with ca2:
                to_opts = [lid for lid in loc_id_list if lid != from_id]
                to_id = st.selectbox("To", to_opts, key="pb_map_conn_to",
                                     format_func=lambda lid: located_locs[lid]["name"])

            conn_type = st.selectbox("Connection type", list(CONNECTION_TYPES.keys()),
                                     key="pb_map_conn_type")
            defaults = CONNECTION_TYPES[conn_type]
            cr1, cr2 = st.columns(2)
            with cr1:
                capex_rate = st.number_input("CAPEX (£/km)", min_value=0.0,
                                              value=float(defaults["capex_per_km"]), step=10_000.0,
                                              key="pb_map_conn_capex")
            with cr2:
                opex_rate = st.number_input("OPEX (£/km/yr)", min_value=0.0,
                                             value=float(defaults["opex_per_km_per_yr"]), step=100.0,
                                             key="pb_map_conn_opex")

            if from_id and to_id:
                la_ = located_locs[from_id]
                lb_ = located_locs[to_id]
                d_ = _haversine_km(la_["lat"], la_["lon"], lb_["lat"], lb_["lon"])
                st.markdown(
                    f'<div style="background:{HS_BG_CARD};border-left:3px solid {HS_GREEN};'
                    f'border-radius:4px;padding:8px 12px;margin:6px 0;">'
                    f'Distance: <b style="color:{HS_WHITE};">{d_:.2f} km</b>'
                    f'&nbsp;&nbsp;|&nbsp;&nbsp;Est. CAPEX: <b style="color:{HS_GREEN};">{_fmt_currency(d_ * capex_rate)}</b>'
                    f'&nbsp;&nbsp;|&nbsp;&nbsp;Est. OPEX/yr: <b style="color:{HS_GREEN};">{_fmt_currency(d_ * opex_rate)}/yr</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if st.button("Add connection", key="pb_map_add_conn_btn", use_container_width=True):
                connections.append({
                    "id": _short_id(),
                    "loc_id_a": from_id, "loc_id_b": to_id,
                    "connection_type": conn_type,
                    "capex_per_km": capex_rate,
                    "opex_per_km_per_yr": opex_rate,
                })
                st.rerun()

    # Connection totals
    conn_capex_t, conn_opex_t = _calc_connection_costs(project)
    if conn_capex_t > 0 or conn_opex_t > 0:
        ct1, ct2 = st.columns(2)
        ct1.metric("Total Connection CAPEX", _fmt_currency(conn_capex_t))
        ct2.metric("Total Connection OPEX/yr", f"{_fmt_currency(conn_opex_t)}/yr")


def _render_green_offport_scenario_results(project: dict) -> None:
    green_items = _collect_green_offport_items(project)
    if not green_items:
        return

    st.markdown(f'<p class="hs-section-header">Green OffPort SIF Scenario Results</p>', unsafe_allow_html=True)
    st.caption(
        "This section runs the exact Green OffPort SIF pipeline for the selected scenario. "
        "The project-level charts below remain COFO aggregate summaries for all item types."
    )

    if len(green_items) > 1:
        selected_idx = st.selectbox(
            "Green OffPort scenario",
            list(range(len(green_items))),
            key="pb_res_green_offport_selector",
            format_func=lambda idx: f"{green_items[idx][0]['name']} / {green_items[idx][1]['display_name']}",
        )
    else:
        selected_idx = 0

    loc, item = green_items[selected_idx]
    if item.get("green_offport_error"):
        st.error(f"{item['display_name']} could not be recalculated: {item['green_offport_error']}")
        return

    try:
        results = _build_green_offport_results(item["green_offport_inputs"], project)
    except Exception as exc:
        st.error(f"{item['display_name']} could not be recalculated: {exc}")
        return

    physics = results["physics"]
    utilities = results["utilities"]
    costs = results["costs"]
    cashflow = results["cashflow"]
    financials = results["financials"]
    lcoh = results["lcoh"]
    base_key = f"pb_go_res_{item['id']}"

    st.markdown(
        f'<div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};'
        f'border-radius:4px;padding:12px 16px;margin:8px 0 12px 0;">'
        f'<p style="color:{HS_GREEN};font-weight:700;font-size:0.9rem;margin:0 0 4px 0;">{item["display_name"]}</p>'
        f'<p style="color:{HS_GREY};font-size:0.82rem;margin:0;">'
        f'{loc["name"]} &nbsp;|&nbsp; {item["green_offport_inputs"]["production_method"]} &nbsp;|&nbsp; '
        f'{item["green_offport_inputs"]["electrolyser_mw"]} MW electrolyser</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("LCOH", f"{_fmt_currency(lcoh, 2)}/kg")
    m2.metric("Total CAPEX", _fmt_currency_millions(costs["total_capex"]))
    m3.metric("Annual H2 (actual)", f"{physics['annual_actual_h2_kg'] / 1000:,.2f} t")
    m4.metric("Annual H2 (theoretical)", f"{physics['annual_theoretical_h2_kg'] / 1000:,.2f} t")
    m5.metric("Pre-tax IRR", _fmt_percent(cashflow["ebitda_irr"]))
    m6.metric("Post-tax IRR", _fmt_percent(cashflow["equity_after_tax_irr"]))

    m7, m8, m9, m10, m11, m12 = st.columns(6)
    m7.metric("Payback Period", f"{cashflow['payback_period']} years")
    m8.metric("NPV", _fmt_currency_millions(cashflow["npv"]))
    m9.metric("Annual Water Demand", f"{utilities['annual_water_demand_m3']:,.1f} m3")
    m10.metric("Purification Demand", f"{utilities['annual_purification_kwh'] / 1000:,.2f} MWh")
    m11.metric("Compression Demand", f"{utilities['annual_compression_kwh'] / 1000:,.2f} MWh")
    m12.metric("Actual / Theoretical", f"{physics['utilisation_vs_theoretical'] * 100:,.2f}%")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Physics", "Utilities", "CAPEX / OPEX", "Cash Flow", "Monthly Outputs"])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            monthly_curtailed = physics["monthly_theoretical_h2_kg"] - physics["monthly_actual_h2_kg"]
            fig_h2 = go.Figure()
            fig_h2.add_bar(x=MONTH_NAMES, y=physics["monthly_actual_h2_kg"], name="Actual H2 produced", marker_color="#a7d730")
            fig_h2.add_bar(x=MONTH_NAMES, y=monthly_curtailed, name="Curtailed / electrolyser limit", marker_color="#4a505a")
            fig_h2.update_layout(barmode="stack", title="Monthly H2 Production — Actual vs Curtailed", yaxis_title="kg H2")
            st.plotly_chart(apply_chart_theme(fig_h2), use_container_width=True, key=f"{base_key}_fig_h2")
            st.caption("Green bars show hydrogen actually produced each month. Grey shows energy that was available but could not be used because the electrolyser was already at full capacity.")
        with col_b:
            fig_daily_h2 = go.Figure()
            fig_daily_h2.add_scatter(
                x=np.arange(1, 366), y=physics["daily_actual_h2_kg"], mode="lines",
                name="Daily H2 (kg)", line=dict(color="#a7d730", width=1),
                fill="tozeroy", fillcolor="rgba(167,215,48,0.15)",
            )
            fig_daily_h2.update_layout(title="Daily Actual H2 Output (full year)", xaxis_title="Day of year", yaxis_title="kg H2")
            st.plotly_chart(apply_chart_theme(fig_daily_h2), use_container_width=True, key=f"{base_key}_fig_daily_h2")
            st.caption("Each point is one day's total H2 output across the full year — useful for spotting seasonal patterns and low-production periods.")

        col_c, col_d = st.columns(2)
        with col_c:
            daily_power = physics["daily_power_kwh"][:364]
            heatmap_data = daily_power.reshape(52, 7)
            fig_heatmap = go.Figure(go.Heatmap(
                z=heatmap_data, x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                y=[f"W{w+1}" for w in range(52)],
                colorscale=[[0, "#23262d"], [0.5, "#499823"], [1.0, "#a7d730"]],
                showscale=True, colorbar=dict(title="kWh", tickfont=dict(color="#8c919a")),
            ))
            fig_heatmap.update_layout(title="Power Generation Heatmap (Week × Day)", xaxis_title="Day of week", yaxis_title="Week of year", yaxis=dict(autorange="reversed"))
            st.plotly_chart(apply_chart_theme(fig_heatmap), use_container_width=True, key=f"{base_key}_fig_heatmap")
            st.caption("Each cell is one day of the week in one week of the year — brighter green means more power generated.")
        with col_d:
            monthly_util = np.where(
                physics["monthly_theoretical_h2_kg"] > 0,
                physics["monthly_actual_h2_kg"] / physics["monthly_theoretical_h2_kg"] * 100,
                0.0,
            )
            fig_util = go.Figure()
            fig_util.add_bar(
                x=MONTH_NAMES, y=monthly_util,
                marker_color=["#a7d730" if v >= 95 else "#499823" if v >= 70 else "#8c919a" for v in monthly_util],
                name="Utilisation (%)",
            )
            fig_util.add_hline(
                y=float(np.mean(monthly_util)), line_dash="dash", line_color="#ffffff",
                annotation_text=f"Avg {float(np.mean(monthly_util)):.1f}%", annotation_font_color="#ffffff",
            )
            fig_util.update_layout(title="Monthly Electrolyser Utilisation (Actual / Theoretical)", yaxis_title="%", yaxis=dict(range=[0, 105]))
            st.plotly_chart(apply_chart_theme(fig_util), use_container_width=True, key=f"{base_key}_fig_util")
            st.caption("Values below 100% mean the electrolyser was the bottleneck, not the power source.")

        st.markdown(f'<p class="hs-section-header">Hourly H2 Production Profile — Full Year</p>', unsafe_allow_html=True)
        fig_hourly = go.Figure(go.Heatmap(
            z=physics["hourly_actual_h2_kg"],
            x=[f"{h:02d}:00" for h in range(24)],
            y=[f"Day {d+1}" for d in range(365)],
            colorscale=[[0, "#23262d"], [0.4, "#499823"], [1.0, "#a7d730"]],
            showscale=True,
            colorbar=dict(title="kg H2/hr", tickfont=dict(color="#8c919a")),
        ))
        fig_hourly.update_layout(
            title="Hourly H2 Production — Day of Year vs Hour of Day",
            xaxis_title="Hour of day", yaxis_title="Day of year", height=450,
            yaxis=dict(autorange="reversed", tickfont=dict(color="#8c919a")),
        )
        st.plotly_chart(apply_chart_theme(fig_hourly), use_container_width=True, key=f"{base_key}_fig_hourly")
        st.caption("Every hour of every day of the year — brighter green means more H2 produced that hour.")

    with tab2:
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            fig_water = go.Figure()
            fig_water.add_bar(x=MONTH_NAMES, y=utilities["monthly_water_demand_l"] / 1000.0, name="Water demand (m³)", marker_color="#a7d730")
            fig_water.update_layout(title="Monthly Water Demand", yaxis_title="m³")
            st.plotly_chart(apply_chart_theme(fig_water), use_container_width=True, key=f"{base_key}_fig_water")
            st.caption("Total water consumed per month. Higher H2 production months consume proportionally more water.")
        with col_u2:
            fig_elec = go.Figure()
            fig_elec.add_bar(x=MONTH_NAMES, y=utilities["monthly_purification_kwh"] / 1000.0, name="Purification (MWh)", marker_color="#499823")
            fig_elec.add_bar(x=MONTH_NAMES, y=utilities["monthly_compression_kwh"] / 1000.0, name="Compression (MWh)", marker_color="#a7d730")
            fig_elec.update_layout(barmode="stack", title="Monthly Electricity Demand — Purification & Compression", yaxis_title="MWh")
            st.plotly_chart(apply_chart_theme(fig_elec), use_container_width=True, key=f"{base_key}_fig_elec")
            st.caption("Electricity consumed by auxiliary systems, not the electrolyser itself.")

        col_u3, col_u4 = st.columns(2)
        with col_u3:
            monthly_h2_t = physics["monthly_actual_h2_kg"] / 1000.0
            monthly_water_m3 = utilities["monthly_water_demand_l"] / 1000.0
            water_intensity = np.where(monthly_h2_t > 0, monthly_water_m3 / monthly_h2_t, 0.0)
            fig_intensity = go.Figure()
            fig_intensity.add_scatter(
                x=MONTH_NAMES, y=water_intensity, mode="lines+markers", name="m³ water / tonne H2",
                line=dict(color="#a7d730", width=2), marker=dict(color="#a7d730", size=7),
            )
            fig_intensity.update_layout(title="Water Intensity (m³ per tonne H2)", yaxis_title="m³ / t H2")
            st.plotly_chart(apply_chart_theme(fig_intensity), use_container_width=True, key=f"{base_key}_fig_intensity")
            st.caption("How many cubic metres of water are needed per tonne of H2 produced.")
        with col_u4:
            cumulative_water = np.cumsum(utilities["monthly_water_demand_l"] / 1000.0)
            fig_cum_water = go.Figure()
            fig_cum_water.add_scatter(
                x=MONTH_NAMES, y=cumulative_water, mode="lines+markers", name="Cumulative water (m³)",
                line=dict(color="#499823", width=2), fill="tozeroy", fillcolor="rgba(73,152,35,0.15)",
                marker=dict(color="#499823", size=7),
            )
            fig_cum_water.update_layout(title="Cumulative Annual Water Demand", yaxis_title="m³")
            st.plotly_chart(apply_chart_theme(fig_cum_water), use_container_width=True, key=f"{base_key}_fig_cum_water")
            st.caption("Running total of water consumed through the year.")

        st.markdown(f'<p class="hs-section-header">Annual Utility Summary</p>', unsafe_allow_html=True)
        df_utils_summary = pd.DataFrame({
            "Utility": ["Water demand", "Purification electricity", "Compression electricity", "Total auxiliary electricity"],
            "Annual value": [
                f"{utilities['annual_water_demand_m3']:,.1f}",
                f"{utilities['annual_purification_kwh'] / 1000.0:,.2f}",
                f"{utilities['annual_compression_kwh'] / 1000.0:,.2f}",
                f"{(utilities['annual_purification_kwh'] + utilities['annual_compression_kwh']) / 1000.0:,.2f}",
            ],
            "Unit": ["m³", "MWh", "MWh", "MWh"],
        })
        st.dataframe(df_utils_summary, use_container_width=True, hide_index=True)

    with tab3:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            capex_items = {k: v for k, v in costs["capex_breakdown"].items() if v > 0}
            if capex_items:
                fig_capex = go.Figure(go.Bar(
                    x=list(capex_items.values()), y=list(capex_items.keys()), orientation="h",
                    marker=dict(color=list(capex_items.values()), colorscale=[[0, "#499823"], [1, "#a7d730"]], showscale=False),
                    text=[_fmt_currency(v) for v in capex_items.values()],
                    textposition="outside", textfont=dict(color="#ffffff", size=11),
                ))
                fig_capex.update_layout(title=f"CAPEX Breakdown  —  Total {_fmt_currency(costs['total_capex'])}", xaxis_title="£", yaxis=dict(autorange="reversed"), margin=dict(l=180), height=380)
                st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True, key=f"{base_key}_fig_capex")
                st.caption("One-time upfront costs to build the scenario.")
        with col_c2:
            opex_items = {k: v for k, v in costs["opex_breakdown"].items() if v > 0}
            if opex_items:
                fig_opex = go.Figure(go.Bar(
                    x=list(opex_items.values()), y=list(opex_items.keys()), orientation="h",
                    marker=dict(color=list(opex_items.values()), colorscale=[[0, "#499823"], [1, "#a7d730"]], showscale=False),
                    text=[_fmt_currency(v) for v in opex_items.values()],
                    textposition="outside", textfont=dict(color="#ffffff", size=11),
                ))
                fig_opex.update_layout(title=f"Year 1 OPEX Breakdown  —  Total {_fmt_currency(costs['total_annual_opex'])}", xaxis_title="£", yaxis=dict(autorange="reversed"), margin=dict(l=210), height=380)
                st.plotly_chart(apply_chart_theme(fig_opex), use_container_width=True, key=f"{base_key}_fig_opex")
                st.caption("Annual running costs in Year 1.")

        df_cf_costs = cashflow["cashflow_df"][cashflow["cashflow_df"]["Year"] >= 1]
        col_c3, col_c4 = st.columns(2)
        with col_c3:
            fig_opex_trend = go.Figure()
            fig_opex_trend.add_scatter(x=df_cf_costs["Year"], y=df_cf_costs["Annual electricity cost"], name="Electricity cost", mode="lines", stackgroup="one", line=dict(color="#499823"), fillcolor="rgba(73,152,35,0.6)")
            fig_opex_trend.add_scatter(x=df_cf_costs["Year"], y=df_cf_costs["O&M cost"], name="O&M cost", mode="lines", stackgroup="one", line=dict(color="#a7d730"), fillcolor="rgba(167,215,48,0.6)")
            fig_opex_trend.add_scatter(x=df_cf_costs["Year"], y=df_cf_costs["Further expenses"], name="Rent / insurance / operators", mode="lines", stackgroup="one", line=dict(color="#8c919a"), fillcolor="rgba(140,145,154,0.6)")
            fig_opex_trend.update_layout(title="OPEX Evolution Over Project Life", xaxis_title="Year", yaxis_title="£ / year")
            st.plotly_chart(apply_chart_theme(fig_opex_trend), use_container_width=True, key=f"{base_key}_fig_opex_trend")
            st.caption("How annual costs evolve over the project life.")
        with col_c4:
            lifetime_opex = float(df_cf_costs["Annual expenses"].sum())
            fig_lifetime = go.Figure(go.Bar(
                x=["Total CAPEX", "Lifetime OPEX", "Lifetime Costs"],
                y=[costs["total_capex"], lifetime_opex, costs["total_capex"] + lifetime_opex],
                marker_color=["#499823", "#a7d730", "#ffffff"],
                text=[_fmt_currency_millions(costs["total_capex"]), _fmt_currency_millions(lifetime_opex), _fmt_currency_millions(costs["total_capex"] + lifetime_opex)],
                textposition="outside", textfont=dict(color="#ffffff"),
            ))
            fig_lifetime.update_layout(title="CAPEX vs Lifetime OPEX vs Total Lifetime Cost", yaxis_title="£", showlegend=False)
            st.plotly_chart(apply_chart_theme(fig_lifetime), use_container_width=True, key=f"{base_key}_fig_lifetime")
            st.caption("Compares one-off capital cost against total running costs over the full project life.")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            capex_vals = list(costs["capex_breakdown"].values())
            capex_keys = list(costs["capex_breakdown"].keys())
            st.dataframe(pd.DataFrame({
                "CAPEX item": capex_keys + ["TOTAL"],
                "Value (£)": [_fmt_currency(v) for v in capex_vals] + [_fmt_currency(costs["total_capex"])],
            }), use_container_width=True, hide_index=True)
        with col_t2:
            opex_vals = list(costs["opex_breakdown"].values())
            opex_keys = list(costs["opex_breakdown"].keys())
            st.dataframe(pd.DataFrame({
                "OPEX item": opex_keys + ["TOTAL (Year 1)"],
                "Year 1 value (£)": [_fmt_currency(v) for v in opex_vals] + [_fmt_currency(costs["total_annual_opex"])],
            }), use_container_width=True, hide_index=True)

    with tab4:
        df_cf = cashflow["cashflow_df"]
        df_ops = df_cf[df_cf["Year"] >= 1]
        fig_rev = go.Figure()
        fig_rev.add_bar(x=df_ops["Year"], y=df_ops["Hydrogen revenue"], name="H2 revenue", marker_color="#a7d730")
        if df_ops["Carbon credit revenue"].sum() > 0:
            fig_rev.add_bar(x=df_ops["Year"], y=df_ops["Carbon credit revenue"], name="Carbon credit revenue", marker_color="#499823")
        fig_rev.add_bar(x=df_ops["Year"], y=-df_ops["Annual expenses"], name="Annual expenses", marker_color="#8c919a")
        fig_rev.add_bar(x=df_ops["Year"], y=-df_ops["Taxes paid"], name="Taxes paid", marker_color="#4a505a")
        fig_rev.add_scatter(x=df_ops["Year"], y=df_ops["Equity free cash flow"], name="Equity FCF", mode="lines+markers", line=dict(color="#ffffff", width=2, dash="dot"), marker=dict(color="#ffffff", size=5))
        fig_rev.update_layout(barmode="relative", title="Annual Revenue vs Expenses & Equity Free Cash Flow", xaxis_title="Year", yaxis_title="£")
        st.plotly_chart(apply_chart_theme(fig_rev), use_container_width=True, key=f"{base_key}_fig_rev")
        st.caption("Green bars are income, grey/dark bars are costs, and the dotted white line is net cash left each year.")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            payback_yr = cashflow["payback_period"]
            fig_cum = go.Figure()
            bar_colors = ["#a7d730" if v >= 0 else "#e05c5c" for v in df_cf["Cumulative cash flow"]]
            fig_cum.add_bar(x=df_cf["Year"], y=df_cf["Cumulative cash flow"], name="Cumulative cash flow", marker_color=bar_colors)
            fig_cum.add_hline(y=0, line_color="#ffffff", line_dash="dash", line_width=1)
            if 0 < payback_yr <= financials["project_life"]:
                fig_cum.add_vline(x=payback_yr, line_color="#a7d730", line_dash="dot", annotation_text=f"Payback Yr {payback_yr}", annotation_font_color="#a7d730", annotation_position="top right")
            fig_cum.update_layout(title="Cumulative Cash Flow & Payback", xaxis_title="Year", yaxis_title="£")
            st.plotly_chart(apply_chart_theme(fig_cum), use_container_width=True, key=f"{base_key}_fig_cum")
            st.caption("Running total of all cash flows. The dotted green line marks the payback year.")
        with col_f2:
            fig_dep = go.Figure()
            fig_dep.add_scatter(x=df_ops["Year"], y=df_ops["Depreciation remaining"], name="Book value remaining", mode="lines", fill="tozeroy", fillcolor="rgba(73,152,35,0.2)", line=dict(color="#499823", width=2))
            fig_dep.add_bar(x=df_ops["Year"], y=df_ops["Annual depreciation"], name="Annual depreciation charge", marker_color="#a7d730", opacity=0.7)
            fig_dep.update_layout(title=f"Asset Depreciation Profile ({financials['depreciation_rate'] * 100:.0f}% Reducing Balance)", xaxis_title="Year", yaxis_title="£")
            st.plotly_chart(apply_chart_theme(fig_dep), use_container_width=True, key=f"{base_key}_fig_dep")
            st.caption("The green area shows remaining book value; the bars show annual depreciation.")

        col_f3, col_f4 = st.columns(2)
        with col_f3:
            fig_tax = go.Figure()
            fig_tax.add_bar(x=df_ops["Year"], y=df_ops["Taxable income"], name="Taxable income", marker_color=["#a7d730" if v >= 0 else "#e05c5c" for v in df_ops["Taxable income"]])
            fig_tax.add_scatter(x=df_ops["Year"], y=df_ops["Cumulative taxable income"], name="Cumulative taxable income", mode="lines+markers", line=dict(color="#ffffff", width=2, dash="dot"), marker=dict(size=4))
            fig_tax.add_hline(y=0, line_color="#8c919a", line_dash="dash", line_width=1)
            fig_tax.update_layout(title="Taxable Income & Loss Carry-Forward", xaxis_title="Year", yaxis_title="£")
            st.plotly_chart(apply_chart_theme(fig_tax), use_container_width=True, key=f"{base_key}_fig_tax")
            st.caption("Tax is only paid once cumulative taxable income crosses zero.")
        with col_f4:
            fig_h2_prod = go.Figure()
            fig_h2_prod.add_scatter(x=df_ops["Year"], y=df_ops["Green H2 production (kg)"] / 1000.0, name="H2 production (t)", mode="lines+markers", fill="tozeroy", fillcolor="rgba(167,215,48,0.15)", line=dict(color="#a7d730", width=2), marker=dict(size=5))
            fig_h2_prod.update_layout(title="Annual H2 Production Over Project Life (with degradation)", xaxis_title="Year", yaxis_title="tonnes H2")
            st.plotly_chart(apply_chart_theme(fig_h2_prod), use_container_width=True, key=f"{base_key}_fig_h2_prod")
            st.caption("H2 output gradually declines each year due to electrolyser stack degradation.")

        st.markdown(f'<p class="hs-section-header">Cash Flow Summary Table</p>', unsafe_allow_html=True)
        df_cf_display = df_cf[[
            "Year", "Green H2 production (kg)", "Hydrogen revenue", "Annual expenses",
            "EBITDA", "Annual depreciation", "Taxes paid", "Equity free cash flow", "Cumulative cash flow",
        ]].copy()
        for col in df_cf_display.columns[1:]:
            df_cf_display[col] = df_cf_display[col].map(lambda x: f"{x:,.0f}" if col == "Green H2 production (kg)" else _fmt_currency(x))
        st.dataframe(df_cf_display, use_container_width=True, hide_index=True)

    with tab5:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            fig_monthly_power = go.Figure()
            fig_monthly_power.add_bar(x=MONTH_NAMES, y=physics["monthly_power_kwh"] / 1000.0, name="Power available (MWh)", marker_color="#8c919a", opacity=0.8)
            fig_monthly_power.add_scatter(x=MONTH_NAMES, y=physics["monthly_actual_h2_kg"], name="Actual H2 (kg)", mode="lines+markers", yaxis="y2", line=dict(color="#a7d730", width=2), marker=dict(size=7))
            fig_monthly_power.update_layout(title="Monthly Power Available vs H2 Produced", yaxis=dict(title=dict(text="MWh", font=dict(color="#8c919a"))), yaxis2=dict(title=dict(text="kg H2", font=dict(color="#a7d730")), overlaying="y", side="right"), legend=dict(x=0.01, y=0.99))
            st.plotly_chart(apply_chart_theme(fig_monthly_power), use_container_width=True, key=f"{base_key}_fig_monthly_power")
            st.caption("Grey bars show total power available; the green line shows actual H2 produced.")
        with col_m2:
            monthly_curtail_pct = np.where(
                physics["monthly_theoretical_h2_kg"] > 0,
                (physics["monthly_theoretical_h2_kg"] - physics["monthly_actual_h2_kg"]) / physics["monthly_theoretical_h2_kg"] * 100,
                0.0,
            )
            fig_curtail = go.Figure()
            fig_curtail.add_bar(x=MONTH_NAMES, y=monthly_curtail_pct, marker_color=["#e05c5c" if v > 5 else "#499823" for v in monthly_curtail_pct], name="Curtailment %")
            fig_curtail.update_layout(title="Monthly Curtailment (% of Theoretical H2 Lost)", yaxis_title="%", yaxis=dict(range=[0, max(float(monthly_curtail_pct.max()) * 1.2, 5)]))
            st.plotly_chart(apply_chart_theme(fig_curtail), use_container_width=True, key=f"{base_key}_fig_curtail")
            st.caption("Red bars above 5% suggest the electrolyser may be undersized relative to generation capacity.")

        col_m3, col_m4 = st.columns(2)
        with col_m3:
            fig_m_water = go.Figure()
            fig_m_water.add_bar(x=MONTH_NAMES, y=utilities["monthly_water_demand_l"] / 1000.0, name="Water demand (m³)", marker_color="#a7d730")
            fig_m_water.update_layout(title="Monthly Water Demand", yaxis_title="m³")
            st.plotly_chart(apply_chart_theme(fig_m_water), use_container_width=True, key=f"{base_key}_fig_m_water")
            st.caption("Monthly water consumption directly tracks H2 production.")
        with col_m4:
            fig_m_elec = go.Figure()
            fig_m_elec.add_bar(x=MONTH_NAMES, y=utilities["monthly_purification_kwh"] / 1000.0, name="Purification (MWh)", marker_color="#499823")
            fig_m_elec.add_bar(x=MONTH_NAMES, y=utilities["monthly_compression_kwh"] / 1000.0, name="Compression (MWh)", marker_color="#a7d730")
            fig_m_elec.update_layout(barmode="stack", title="Monthly Auxiliary Electricity (Purification + Compression)", yaxis_title="MWh")
            st.plotly_chart(apply_chart_theme(fig_m_elec), use_container_width=True, key=f"{base_key}_fig_m_elec")
            st.caption("Electricity used by auxiliary systems each month.")

        st.markdown(f'<p class="hs-section-header">Full Monthly Data Table</p>', unsafe_allow_html=True)
        df_monthly = pd.DataFrame({
            "Month": MONTH_NAMES,
            "Power available (MWh)": (physics["monthly_power_kwh"] / 1000.0).round(1),
            "Theoretical H2 (kg)": physics["monthly_theoretical_h2_kg"].round(0).astype(int),
            "Actual H2 (kg)": physics["monthly_actual_h2_kg"].round(0).astype(int),
            "Curtailment (%)": monthly_curtail_pct.round(2),
            "Water demand (m³)": (utilities["monthly_water_demand_l"] / 1000.0).round(1),
            "Purification electricity (MWh)": (utilities["monthly_purification_kwh"] / 1000.0).round(2),
            "Compression electricity (MWh)": (utilities["monthly_compression_kwh"] / 1000.0).round(2),
        })
        st.dataframe(df_monthly, use_container_width=True, hide_index=True)

    st.markdown("---")


# =========================================================================
# TAB 3 — RESULTS & ANALYSIS
# =========================================================================
def _render_tab_results(project: dict) -> None:
    agg = _aggregate_project_cofo(project)
    conn_capex, conn_opex = _calc_connection_costs(project)
    agg_incl = dict(agg)
    agg_incl["total_capex"]     = agg["total_capex"] + conn_capex
    agg_incl["total_opex_cost"] = agg["total_opex_cost"] + conn_opex

    if agg_incl["tech_item_count"] == 0:
        st.info("Add technology items in the Build tab to see analysis.")
        return

    proj_life = project["project_life_years"]
    inflation = project["inflation_rate_pct"] / 100.0

    years, annual_revenue, annual_opex_cost, cumulative_cf = _build_indicative_cashflow(
        agg_incl, proj_life, inflation
    )
    payback_yr = _find_payback_year(cumulative_cf)

    _render_green_offport_scenario_results(project)

    # ---- Top KPI row ----
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("Total CAPEX",     _fmt_currency_millions(agg_incl["total_capex"]))
    k2.metric("Annual OPEX",     f"{_fmt_currency(agg_incl['total_opex_cost'])}/yr")
    k3.metric("Annual Revenue",  f"{_fmt_currency(agg_incl['total_revenue_yr'])}/yr")
    k4.metric("H2 Production",   f"{agg_incl['total_h2_kg_yr']/1000:,.1f} t/yr")
    k5.metric("CO2 Avoided",     f"{agg_incl['total_co2_t_yr']:,.1f} t/yr")
    k6.metric("Footprint",       f"{agg_incl['total_footprint_m2']:,.0f} m²")
    k7.metric("Simple Payback",  f"{payback_yr} yrs" if payback_yr else "N/A")

    st.markdown("---")

    # ---- Row A: CAPEX ----
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        loc_names = [loc["name"] for loc in project["locations"].values()]
        capex_categories = list(CATEGORY_COLOURS.keys())
        for loc in project["locations"].values():
            for item in loc["technology_items"].values():
                if item["category"] not in capex_categories:
                    capex_categories.append(item["category"])
        capex_by_cat = {cat: [0.0] * len(loc_names) for cat in capex_categories}
        for i, loc in enumerate(project["locations"].values()):
            for item in loc["technology_items"].values():
                cat = item["category"]
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "CAPEX" and cat in capex_by_cat:
                        capex_by_cat[cat][i] += rec["value"]
        fig_capex = go.Figure()
        for cat, vals in capex_by_cat.items():
            if sum(vals) > 0:
                fig_capex.add_bar(x=vals, y=loc_names, name=cat, orientation="h",
                                  marker_color=CATEGORY_COLOURS.get(cat, HS_GREY),
                                  text=[_fmt_currency(v) if v > 0 else "" for v in vals],
                                  textposition="inside", textfont=dict(color=HS_WHITE, size=10))
        fig_capex.update_layout(
            barmode="stack",
            title=f"CAPEX by Location — Total {_fmt_currency(agg_incl['total_capex'])}",
            xaxis_title=PROJECT_CURRENCY_LABEL,
            yaxis=dict(autorange="reversed"),
            height=max(280, 70 * len(loc_names)),
        )
        st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True, key="pb_res_capex")
        st.caption("One-off capital cost per location, coloured by technology category.")

    with col_a2:
        lifetime_opex = agg_incl["total_opex_cost"] * proj_life
        fig_wf = go.Figure(go.Bar(
            x=["Total CAPEX", f"Lifetime OPEX ({proj_life} yrs)", "Total Lifetime Cost"],
            y=[agg_incl["total_capex"], lifetime_opex, agg_incl["total_capex"] + lifetime_opex],
            marker_color=[COFO_COLOURS["CAPEX"], COFO_COLOURS["OPEX"], HS_WHITE],
            text=[_fmt_currency_millions(agg_incl["total_capex"]),
                  _fmt_currency_millions(lifetime_opex),
                  _fmt_currency_millions(agg_incl["total_capex"] + lifetime_opex)],
            textposition="outside", textfont=dict(color=HS_WHITE),
        ))
        fig_wf.update_layout(title="CAPEX vs Lifetime OPEX", yaxis_title=PROJECT_CURRENCY_LABEL, showlegend=False)
        st.plotly_chart(apply_chart_theme(fig_wf), use_container_width=True, key="pb_res_wf")
        st.caption(f"Shows whether CAPEX or OPEX dominates over the {proj_life}-year project life.")

    st.markdown("---")

    # ---- Row B: OPEX ----
    col_b1, col_b2 = st.columns(2)

    with col_b1:
        opex_list = []
        for loc in project["locations"].values():
            for item in loc["technology_items"].values():
                v = sum(r["value"] for r in item["cofo_records"]
                        if r["cofo_type"] == "OPEX" and _record_opex_type_key(r) == OPEX_TYPE_COST)
                if v > 0:
                    opex_list.append((f"{loc['name']} / {item['display_name']}", v))
        if opex_list:
            opex_list.sort(key=lambda x: x[1])
            fig_opex = go.Figure(go.Bar(
                x=[x[1] for x in opex_list], y=[x[0] for x in opex_list], orientation="h",
                marker=dict(color=[x[1] for x in opex_list],
                            colorscale=[[0, HS_GREEN_DARK], [1, HS_GREEN]], showscale=False),
                text=[_fmt_currency(x[1]) for x in opex_list],
                textposition="outside", textfont=dict(color=HS_WHITE, size=10),
            ))
            fig_opex.update_layout(
                title="Annual OPEX Cost by Item",
                xaxis_title=PROJECT_CURRENCY_RATE_LABEL,
                yaxis=dict(autorange="reversed"),
                margin=dict(l=220),
                height=max(280, 50 * len(opex_list)),
            )
            st.plotly_chart(apply_chart_theme(fig_opex), use_container_width=True, key="pb_res_opex")
            st.caption("Annual running cost per technology item, sorted largest to smallest.")
        else:
            st.info("No OPEX cost records.")

    with col_b2:
        fig_ot = go.Figure()
        fig_ot.add_bar(name="Cost (£/yr)", x=["Cost (£/yr)"], y=[agg_incl["total_opex_cost"]],
                       marker_color=COFO_COLOURS["OPEX"], yaxis="y1",
                       text=[_fmt_currency(agg_incl["total_opex_cost"])],
                       textposition="outside", textfont=dict(color=HS_WHITE))
        fig_ot.add_bar(name="Power (kW)", x=["Power (kW)"], y=[agg["total_opex_power_kw"]],
                       marker_color=HS_GREEN, yaxis="y2",
                       text=[f"{agg['total_opex_power_kw']:,.1f} kW"],
                       textposition="outside", textfont=dict(color=HS_WHITE))
        fig_ot.add_bar(name="Water (L/hr)", x=["Water (L/hr)"], y=[agg["total_opex_water_l_hr"]],
                       marker_color="#2196a0", yaxis="y2",
                       text=[f"{agg['total_opex_water_l_hr']:,.0f} L/hr"],
                       textposition="outside", textfont=dict(color=HS_WHITE))
        fig_ot.update_layout(
            title="OPEX by Resource Type",
            yaxis=dict(title=dict(text=PROJECT_CURRENCY_RATE_LABEL, font=dict(color=COFO_COLOURS["OPEX"]))),
            yaxis2=dict(title=dict(text="kW / L/hr", font=dict(color=HS_GREEN)), overlaying="y", side="right"),
            barmode="group",
        )
        st.plotly_chart(apply_chart_theme(fig_ot), use_container_width=True, key="pb_res_opex_types")
        st.caption("Three types of OPEX: money cost, power demand, and water demand. Cost uses the left axis; power and water use the right axis.")

    st.markdown("---")

    # ---- Row C: Outputs ----
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        out_rows = []
        for loc in project["locations"].values():
            for item in loc["technology_items"].values():
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "Output":
                        out_rows.append({"output_type": rec["output_type"],
                                         "subtype": rec["output_subtype"], "value": rec["value"]})
        if out_rows:
            out_df = pd.DataFrame(out_rows)
            agg_out = out_df.groupby(["output_type", "subtype"])["value"].sum().reset_index()
            type_order = {"Product": 0, "Revenue": 1, "Saving": 2}
            agg_out["_s"] = agg_out["output_type"].map(lambda t: type_order.get(t, 99))
            agg_out = agg_out.sort_values(["_s", "subtype"]).drop(columns=["_s"])
            out_colours = {
                OUTPUT_SUBTYPE_H2_PRODUCTION: HS_GREEN, OUTPUT_SUBTYPE_H2_COMPRESSION: HS_GREEN_DARK,
                OUTPUT_SUBTYPE_H2_STORAGE: "#6ea8fe", OUTPUT_SUBTYPE_POWER_GENERATION: "#499823",
                OUTPUT_SUBTYPE_WATER_OUTPUT: "#2196a0", OUTPUT_SUBTYPE_REVENUE: "#a7d730",
                OUTPUT_SUBTYPE_CO2_AVOIDED: "#4caf84",
            }
            fig_out = go.Figure(go.Bar(
                x=agg_out["value"], y=agg_out["subtype"], orientation="h",
                marker_color=[out_colours.get(s, HS_GREY) for s in agg_out["subtype"]],
                text=[f"{v:,.1f}" for v in agg_out["value"]],
                textposition="outside", textfont=dict(color=HS_WHITE, size=10),
            ))
            fig_out.update_layout(
                title="Annual Outputs by Type",
                xaxis_title="Annual value (native units)",
                margin=dict(l=140),
                height=max(250, 50 * len(agg_out)),
            )
            st.plotly_chart(apply_chart_theme(fig_out), use_container_width=True, key="pb_res_outputs")
            st.caption("All outputs grouped by type (Product / Revenue / Saving). Each row uses its own unit — values are not comparable across rows.")
        else:
            st.info("No output records.")

    with col_c2:
        loc_rev, loc_cost = {}, {}
        for loc in project["locations"].values():
            loc_rev[loc["name"]] = loc_cost[loc["name"]] = 0.0
            for item in loc["technology_items"].values():
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "Output" and rec["output_subtype"] == OUTPUT_SUBTYPE_REVENUE:
                        loc_rev[loc["name"]] += rec["value"]
                    elif rec["cofo_type"] == "OPEX" and _record_opex_type_key(rec) == OPEX_TYPE_COST:
                        loc_cost[loc["name"]] += rec["value"]
        if any(v > 0 for v in {**loc_rev, **loc_cost}.values()):
            fig_rc = go.Figure()
            fig_rc.add_bar(name="Revenue (£/yr)", x=list(loc_rev.keys()), y=list(loc_rev.values()),
                           marker_color=HS_GREEN,
                           text=[_fmt_currency(v) for v in loc_rev.values()],
                           textposition="outside", textfont=dict(color=HS_WHITE))
            fig_rc.add_bar(name="OPEX Cost (£/yr)", x=list(loc_cost.keys()), y=list(loc_cost.values()),
                           marker_color=HS_GREY,
                           text=[_fmt_currency(v) for v in loc_cost.values()],
                           textposition="outside", textfont=dict(color=HS_WHITE))
            fig_rc.update_layout(barmode="group", title="Revenue vs OPEX Cost by Location",
                                 yaxis_title=PROJECT_CURRENCY_RATE_LABEL)
            st.plotly_chart(apply_chart_theme(fig_rc), use_container_width=True, key="pb_res_rev_opex")
            st.caption("Green = annual revenue, grey = annual running cost. Locations where green exceeds grey are cash-flow positive annually.")
        else:
            st.info("No revenue or cost data to compare.")

    st.markdown("---")

    # ---- Cash flow (full width) ----
    st.markdown(f'<p class="hs-section-header">Indicative Project Cash Flow</p>', unsafe_allow_html=True)
    fig_cf = go.Figure()
    fig_cf.add_bar(x=years[1:], y=annual_revenue[1:], name="Annual Revenue", marker_color=HS_GREEN)
    fig_cf.add_bar(x=years[1:], y=-annual_opex_cost[1:], name="Annual OPEX Cost", marker_color=HS_GREY)
    cum_colors = ["#a7d730" if v >= 0 else "#e05c5c" for v in cumulative_cf]
    fig_cf.add_scatter(x=years, y=cumulative_cf, name="Cumulative Cash Flow",
                       mode="lines+markers",
                       line=dict(color=HS_WHITE, width=2, dash="dot"),
                       marker=dict(color=cum_colors, size=7))
    fig_cf.add_hline(y=0, line_color=HS_GREY, line_dash="dash", line_width=1)
    if payback_yr:
        fig_cf.add_vline(x=payback_yr, line_color=HS_GREEN, line_dash="dot",
                         annotation_text=f"Payback Yr {payback_yr}",
                         annotation_font_color=HS_GREEN)
    fig_cf.update_layout(
        barmode="relative",
        title="Indicative Project Cash Flow (pre-tax, no degradation)",
        xaxis_title="Year", yaxis_title=PROJECT_CURRENCY_LABEL, height=380,
    )
    st.plotly_chart(apply_chart_theme(fig_cf), use_container_width=True, key="pb_res_cf")
    st.caption(
        f"Year 0 = -{_fmt_currency(agg_incl['total_capex'])} CAPEX (includes {_fmt_currency(conn_capex)} connection costs). "
        f"Both revenue and OPEX escalate at {project['inflation_rate_pct']:.1f}%/yr. "
        f"In practice, H2 sale prices are often fixed by contract rather than tracking inflation. "
        f"This model excludes tax, degradation, and debt — use the dedicated models for full analysis."
    )

    st.markdown("---")

    # ---- Data tables ----
    with st.expander("Full COFO Records Table", expanded=False):
        df_f = _build_full_cofo_dataframe(project)
        if not df_f.empty:
            st.dataframe(df_f, use_container_width=True, hide_index=True)
        else:
            st.info("No records.")

    with st.expander("Location Summary Table", expanded=False):
        df_l = _build_location_summary_dataframe(project)
        if not df_l.empty:
            st.dataframe(df_l, use_container_width=True, hide_index=True)
        else:
            st.info("No data.")

    with st.expander("Technology Item Summary", expanded=False):
        df_t = _build_tech_summary_dataframe(project)
        if not df_t.empty:
            st.dataframe(df_t, use_container_width=True, hide_index=True)
        else:
            st.info("No data.")


# =========================================================================
# TAB 4 — CATALOGUE REFERENCE  (read-only)
# =========================================================================
def _render_tab_catalogue() -> None:
    st.markdown(f'<p class="hs-section-header">Technology Catalogue</p>', unsafe_allow_html=True)
    st.caption(
        "Browse all available components. Use the preview to see exactly what CAPEX, OPEX, "
        "footprint, and outputs are calculated at any given rating before adding to a project."
    )

    col_browse, col_detail = st.columns([1, 2])

    with col_browse:
        browse_cat  = st.selectbox("Category",  list(TECH_CATALOGUE.keys()),        key="pb_cat_browse")
        browse_type = st.selectbox("Type",       list(TECH_CATALOGUE[browse_cat].keys()), key="pb_type_browse")
        browse_comp = st.selectbox("Component",  list(TECH_CATALOGUE[browse_cat][browse_type].keys()), key="pb_comp_browse")

    with col_detail:
        spec = TECH_CATALOGUE[browse_cat][browse_type][browse_comp]
        st.markdown(
            f'<div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};'
            f'border-radius:4px;padding:14px 18px;margin-bottom:12px;">'
            f'<p style="color:{HS_GREEN};font-weight:700;font-size:0.9rem;margin:0 0 4px 0;">{browse_comp}</p>'
            f'<p style="color:{HS_GREY};font-size:0.82rem;margin:0;">'
            f'{browse_cat} &rarr; {browse_type} &nbsp;|&nbsp; '
            f'Rating unit: <b style="color:{HS_WHITE};">{spec["rating_unit"]}</b></p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        preview_rating = st.number_input(
            f"Preview at rating ({spec['rating_unit']})",
            min_value=spec["rating_min"], max_value=spec["rating_max"],
            value=spec["rating_default"], step=spec["rating_step"],
            key="pb_cat_preview_rating",
        )
        preview_records, preview_errors = calculate_cofo_records(spec, preview_rating)
        if preview_errors:
            st.error("Formula errors: " + "; ".join(preview_errors))
        if preview_records:
            prev_df = pd.DataFrame([{
                "COFO Type": r["cofo_type"],
                "Item": r["item_name"],
                "Detail": _record_opex_type_label(r) if r["cofo_type"] == "OPEX" else r["output_subtype"] or "—",
                f"Value at {preview_rating} {spec['rating_unit']}": f"{r['value']:,.2f}",
                "Unit": r["unit"],
                "Formula": r["source_formula"],
                "Basis": r["source_note"],
            } for r in preview_records])
            st.dataframe(prev_df, use_container_width=True, hide_index=True)
        elif not preview_errors:
            st.info("No COFO records defined for this component.")


# =========================================================================
# MAIN
# =========================================================================
st.set_page_config(
    page_title="HydroStar — Project Builder",
    layout="wide",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None,
)

inject_hydrostar_css()
render_sidebar_header()
_init_session_state()

render_page_header(
    "Project Builder",
    "Multi-site, multi-technology techno-economic project management",
)

active_project = _render_sidebar(st.session_state["pb_projects"])

if active_project is None:
    st.markdown("---")
    st.info("No project active. Use the sidebar to create a new project.")
    st.markdown(
        f"""
        <div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};border-radius:6px;
        padding:22px 26px;margin-top:18px;max-width:700px;">
        <p style="color:{HS_GREEN};font-weight:700;font-size:0.9rem;text-transform:uppercase;
        letter-spacing:0.07em;margin:0 0 10px 0;">How it works</p>
        <p style="color:#e8e8e8;font-size:0.92rem;line-height:1.7;margin:0;">
        <b style="color:{HS_WHITE};">1. Create a project</b> — give it a name in the sidebar.<br>
        <b style="color:{HS_WHITE};">2. Add locations</b> — each location is a distinct site (e.g. Solar Farm, Electrolyser Building, Storage Yard).<br>
        <b style="color:{HS_WHITE};">3. Add technology</b> — use the Green OffPort model by default, or choose advanced catalogue/manual entry for mixed projects.<br>
        <b style="color:{HS_WHITE};">4. Set coordinates</b> — enter postcodes to place sites on the map and calculate inter-site distances.<br>
        <b style="color:{HS_WHITE};">5. Define connections</b> — add cable or pipeline links between sites. Connection costs are included in project totals.<br>
        <b style="color:{HS_WHITE};">6. Review results</b> — see CAPEX, OPEX, revenue, outputs, and an indicative cash flow.
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

_sync_project_green_offport_items(active_project)

st.markdown("---")

tab_build, tab_map, tab_results, tab_catalogue = st.tabs([
    "Build",
    "Locations & Map",
    "Results & Analysis",
    "Catalogue Reference",
])

with tab_build:
    _render_tab_build(active_project)

with tab_map:
    _render_tab_locations_map(active_project)

with tab_results:
    _render_tab_results(active_project)

with tab_catalogue:
    _render_tab_catalogue()
