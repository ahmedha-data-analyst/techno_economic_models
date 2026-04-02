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
}

# Streamlit enforces a minimum text area height of 68px.
COMPACT_TEXT_AREA_HEIGHT = 68
PROJECT_CURRENCY_SYMBOL = "£"
PROJECT_CURRENCY_LABEL = "GBP (£)"
PROJECT_CURRENCY_RATE_LABEL = "GBP/yr"

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

# -------------------------------------------------------------------------
# TECHNOLOGY CATALOGUE
# -------------------------------------------------------------------------
# Each component spec contains: rating metadata + capex_items, opex_items,
# footprint_items, output_items.  Formulas are evaluated with `rating` in scope.
# -------------------------------------------------------------------------
TECH_CATALOGUE = {
    "Hydrogen Production": {
        "Electrolyser": {
            "PEM Electrolyser": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Rated electrical input capacity of the electrolyser (MW)",
                "capex_items": [
                    {"name": "PEM Stack",           "formula": "rating * 700_000",            "note": "£700k/MW — industry benchmark 2024"},
                    {"name": "Balance of Plant",    "formula": "rating * 700_000 * 0.20",     "note": "20% of stack CAPEX"},
                    {"name": "Installation",        "formula": "rating * 700_000 * 0.05",     "note": "5% of stack CAPEX"},
                ],
                "opex_items": [
                    {"name": "Stack O&M",           "opex_type": "Cost (£/yr)",  "formula": "rating * 700_000 * 0.01",   "unit": "£/yr",   "note": "1% p.a. of stack CAPEX"},
                    {"name": "Grid Parasitic Power","opex_type": "Power (kW)",   "formula": "rating * 50",               "unit": "kW",     "note": "50 kW parasitic per MW rated"},
                    {"name": "Process Water",       "opex_type": "Water (L/hr)", "formula": "rating * 10_000",           "unit": "L/hr",   "note": "~10 L water per kg H2 at full load"},
                ],
                "footprint_items": [
                    {"name": "Electrolyser skid",  "formula": "rating * 100", "note": "100 m²/MW — containerised skid"},
                ],
                "output_items": [
                    {"name": "Green H2 production","output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_PRODUCTION,    "formula": "rating * 1_000 / 53.0 * 8_760",            "unit": "kg/yr",    "note": "53 kWh/kg, 8,760 hrs/yr full load"},
                    {"name": "H2 Revenue",         "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,         "formula": "rating * 1_000 / 53.0 * 8_760 * 7.0",      "unit": "GBP/yr",   "note": "£7/kg H2 indicative price"},
                    {"name": "CO2 Avoided",        "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,     "formula": "rating * 1_000 / 53.0 * 8_760 * 6.29 / 1_000", "unit": "t CO2/yr", "note": "6.29 kg CO2 per kg grey H2 displaced"},
                ],
            },
            "Alkaline Electrolyser": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Rated electrical input capacity of the electrolyser (MW)",
                "capex_items": [
                    {"name": "Alkaline Stack",      "formula": "rating * 550_000",           "note": "£550k/MW — alkaline is lower cost than PEM"},
                    {"name": "Balance of Plant",    "formula": "rating * 550_000 * 0.15",    "note": "15% of stack CAPEX"},
                    {"name": "Installation",        "formula": "rating * 550_000 * 0.05",    "note": "5% of stack CAPEX"},
                ],
                "opex_items": [
                    {"name": "Stack O&M",           "opex_type": "Cost (£/yr)",  "formula": "rating * 550_000 * 0.015",  "unit": "£/yr",   "note": "1.5% p.a. — alkaline requires more maintenance"},
                    {"name": "Grid Parasitic Power","opex_type": "Power (kW)",   "formula": "rating * 40",               "unit": "kW",     "note": "40 kW parasitic per MW rated"},
                    {"name": "Process Water",       "opex_type": "Water (L/hr)", "formula": "rating * 11_000",           "unit": "L/hr",   "note": "~11 L water per kg H2 at full load"},
                ],
                "footprint_items": [
                    {"name": "Electrolyser skid",  "formula": "rating * 130",  "note": "130 m²/MW — larger footprint than PEM"},
                ],
                "output_items": [
                    {"name": "Green H2 production","output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_PRODUCTION,    "formula": "rating * 1_000 / 55.0 * 8_760",            "unit": "kg/yr",    "note": "55 kWh/kg, 8,760 hrs/yr full load"},
                    {"name": "H2 Revenue",         "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,         "formula": "rating * 1_000 / 55.0 * 8_760 * 7.0",      "unit": "GBP/yr",   "note": "£7/kg H2 indicative price"},
                    {"name": "CO2 Avoided",        "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,     "formula": "rating * 1_000 / 55.0 * 8_760 * 6.29 / 1_000", "unit": "t CO2/yr", "note": "6.29 kg CO2 per kg grey H2 displaced"},
                ],
            },
        },
        "Compressor": {
            "H2 Compressor (350 bar)": {
                "rating_unit": "kg/hr",
                "rating_default": 10.0,
                "rating_min": 1.0,
                "rating_max": 500.0,
                "rating_step": 1.0,
                "rating_help": "Throughput capacity of the compressor (kg H2/hr)",
                "capex_items": [
                    {"name": "Compressor unit",    "formula": "rating * 10_000",  "note": "£10k per kg/hr throughput"},
                    {"name": "Installation",       "formula": "rating * 10_000 * 0.05", "note": "5% of unit CAPEX"},
                ],
                "opex_items": [
                    {"name": "Compressor O&M",     "opex_type": "Cost (£/yr)",  "formula": "rating * 10_000 * 0.01",  "unit": "£/yr",  "note": "1% p.a. of CAPEX"},
                    {"name": "Compression Power",  "opex_type": "Power (kW)",   "formula": "rating * 3",              "unit": "kW",    "note": "3 kWh per kg H2 compressed to 350 bar"},
                ],
                "footprint_items": [
                    {"name": "Compressor skid",    "formula": "rating * 5",     "note": "5 m² per kg/hr capacity"},
                ],
                "output_items": [
                    {"name": "Compressed H2",      "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 8_760", "unit": "kg/yr", "note": "Throughput at full-time operation"},
                ],
            },
            "H2 Compressor (700 bar)": {
                "rating_unit": "kg/hr",
                "rating_default": 10.0,
                "rating_min": 1.0,
                "rating_max": 500.0,
                "rating_step": 1.0,
                "rating_help": "Throughput capacity of the compressor (kg H2/hr)",
                "capex_items": [
                    {"name": "Compressor unit",    "formula": "rating * 16_000",  "note": "£16k per kg/hr — high pressure compressor"},
                    {"name": "Installation",       "formula": "rating * 16_000 * 0.05", "note": "5% of unit CAPEX"},
                ],
                "opex_items": [
                    {"name": "Compressor O&M",     "opex_type": "Cost (£/yr)",  "formula": "rating * 16_000 * 0.015", "unit": "£/yr",  "note": "1.5% p.a. — higher pressure = more wear"},
                    {"name": "Compression Power",  "opex_type": "Power (kW)",   "formula": "rating * 6",              "unit": "kW",    "note": "6 kWh per kg H2 compressed to 700 bar"},
                ],
                "footprint_items": [
                    {"name": "Compressor skid",    "formula": "rating * 7",     "note": "7 m² per kg/hr capacity"},
                ],
                "output_items": [
                    {"name": "Compressed H2",      "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_H2_COMPRESSION, "formula": "rating * 8_760", "unit": "kg/yr", "note": "Throughput at full-time operation"},
                ],
            },
        },
    },
    "Renewable Generation": {
        "Solar PV": {
            "Ground-Mounted Solar PV": {
                "rating_unit": "MWp",
                "rating_default": 2.0,
                "rating_min": 0.1,
                "rating_max": 200.0,
                "rating_step": 0.5,
                "rating_help": "Peak power output capacity of the solar array (MWp)",
                "capex_items": [
                    {"name": "Solar panels & inverters", "formula": "rating * 600_000",  "note": "£600k/MWp installed"},
                    {"name": "Grid connection",          "formula": "50_000",            "note": "£50k flat connection cost"},
                    {"name": "Civil works",              "formula": "rating * 600_000 * 0.08", "note": "8% of panel CAPEX"},
                ],
                "opex_items": [
                    {"name": "Solar O&M",           "opex_type": "Cost (£/yr)",  "formula": "rating * 600_000 * 0.01",  "unit": "£/yr",   "note": "1% p.a. of CAPEX"},
                    {"name": "Land lease",          "opex_type": "Cost (£/yr)",  "formula": "rating * 5_000",           "unit": "£/yr",   "note": "£5k/MWp/yr typical UK agricultural lease"},
                ],
                "footprint_items": [
                    {"name": "Solar field area",    "formula": "rating * 10_000",   "note": "10,000 m²/MWp including row spacing"},
                ],
                "output_items": [
                    {"name": "Annual generation",  "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 1_100",     "unit": "MWh/yr",  "note": "1,100 equivalent full-load hours — UK average"},
                    {"name": "Generation Revenue", "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,          "formula": "rating * 1_100 * 50", "unit": "GBP/yr",  "note": "£50/MWh indicative PPA rate"},
                ],
            },
        },
        "Wind Turbine": {
            "Onshore Wind Turbine": {
                "rating_unit": "MW",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.5,
                "rating_help": "Nameplate capacity of the wind turbine (MW)",
                "capex_items": [
                    {"name": "Wind turbine",       "formula": "rating * 1_000_000",         "note": "£1M/MW nameplate"},
                    {"name": "Balance of Plant",   "formula": "rating * 1_000_000 * 0.10",  "note": "10% of turbine CAPEX"},
                    {"name": "Grid connection",    "formula": "rating * 50_000",             "note": "£50k/MW grid connection"},
                ],
                "opex_items": [
                    {"name": "Wind turbine O&M",   "opex_type": "Cost (£/yr)",  "formula": "rating * 1_000_000 * 0.01", "unit": "£/yr",  "note": "1% p.a. of CAPEX"},
                    {"name": "Land lease",         "opex_type": "Cost (£/yr)",  "formula": "rating * 8_000",            "unit": "£/yr",  "note": "£8k/MW/yr typical UK wind lease"},
                ],
                "footprint_items": [
                    {"name": "Turbine base pad",   "formula": "rating * 500",  "note": "500 m²/MW turbine base (not exclusion zone)"},
                ],
                "output_items": [
                    {"name": "Annual generation",  "output_type": "Product",  "output_subtype": OUTPUT_SUBTYPE_POWER_GENERATION, "formula": "rating * 2_600",       "unit": "MWh/yr",  "note": "2,600 equivalent full-load hours — UK onshore avg"},
                    {"name": "Generation Revenue", "output_type": "Revenue",  "output_subtype": OUTPUT_SUBTYPE_REVENUE,          "formula": "rating * 2_600 * 50",   "unit": "GBP/yr",  "note": "£50/MWh indicative PPA rate"},
                    {"name": "CO2 Avoided",        "output_type": "Saving",   "output_subtype": OUTPUT_SUBTYPE_CO2_AVOIDED,      "formula": "rating * 2_600 * 0.233","unit": "t CO2/yr","note": "0.233 t CO2/MWh UK grid intensity displaced"},
                ],
            },
        },
    },
    "Storage": {
        "Hydrogen Storage": {
            "Tube Trailer (Type 1)": {
                "rating_unit": "kg",
                "rating_default": 250.0,
                "rating_min": 10.0,
                "rating_max": 5000.0,
                "rating_step": 50.0,
                "rating_help": "H2 storage capacity of the tube trailer (kg)",
                "capex_items": [
                    {"name": "Tube trailer unit",  "formula": "rating * 500",  "note": "£500/kg H2 storage capacity"},
                ],
                "opex_items": [
                    {"name": "Storage O&M",        "opex_type": "Cost (£/yr)", "formula": "rating * 500 * 0.01", "unit": "£/yr", "note": "1% p.a. of CAPEX"},
                ],
                "footprint_items": [
                    {"name": "Trailer bay",        "formula": "30",  "note": "30 m² per trailer unit (fixed)"},
                ],
                "output_items": [
                    {"name": "H2 storage capacity","output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_STORAGE, "formula": "rating", "unit": "kg", "note": "Max H2 storable at one time"},
                ],
            },
            "Compressed Tank (350 bar)": {
                "rating_unit": "kg",
                "rating_default": 100.0,
                "rating_min": 10.0,
                "rating_max": 10000.0,
                "rating_step": 50.0,
                "rating_help": "H2 storage capacity of the pressure vessel (kg)",
                "capex_items": [
                    {"name": "Pressure vessel",    "formula": "rating * 800",  "note": "£800/kg H2 for 350 bar vessel"},
                    {"name": "Valve / pipework",   "formula": "rating * 800 * 0.05", "note": "5% of vessel CAPEX"},
                ],
                "opex_items": [
                    {"name": "Tank O&M",           "opex_type": "Cost (£/yr)", "formula": "rating * 800 * 0.01", "unit": "£/yr", "note": "1% p.a. of CAPEX"},
                ],
                "footprint_items": [
                    {"name": "Tank pad",           "formula": "rating * 0.15", "note": "0.15 m²/kg — compact vessel installation"},
                ],
                "output_items": [
                    {"name": "H2 storage capacity","output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_H2_STORAGE, "formula": "rating", "unit": "kg", "note": "Max H2 storable at one time"},
                ],
            },
        },
    },
    "Water Treatment": {
        "Purification": {
            "Reverse Osmosis Unit": {
                "rating_unit": "m³/hr",
                "rating_default": 1.0,
                "rating_min": 0.1,
                "rating_max": 100.0,
                "rating_step": 0.1,
                "rating_help": "Water treatment throughput (m³/hr)",
                "capex_items": [
                    {"name": "RO unit (fixed)",    "formula": "50_000",             "note": "£50k fixed for skid and controls"},
                    {"name": "RO unit (variable)", "formula": "rating * 5_000",     "note": "£5k per m³/hr additional capacity"},
                ],
                "opex_items": [
                    {"name": "RO O&M",             "opex_type": "Cost (£/yr)",  "formula": "(50_000 + rating * 5_000) * 0.02",  "unit": "£/yr",  "note": "2% p.a. of CAPEX — membrane replacement"},
                    {"name": "RO Power",           "opex_type": "Power (kW)",   "formula": "rating * 0.5",                      "unit": "kW",    "note": "0.5 kW per m³/hr throughput"},
                    {"name": "RO Water loss",      "opex_type": "Water (L/hr)", "formula": "rating * 200",                      "unit": "L/hr",  "note": "200 L/hr reject stream per m³/hr treated"},
                ],
                "footprint_items": [
                    {"name": "RO skid",            "formula": "20",  "note": "20 m² fixed for standard RO skid"},
                ],
                "output_items": [
                    {"name": "Purified water",     "output_type": "Product", "output_subtype": OUTPUT_SUBTYPE_WATER_OUTPUT, "formula": "rating * 800", "unit": "L/hr", "note": "~80% recovery rate"},
                ],
            },
        },
    },
    "Balance of Plant": {
        "Site Infrastructure": {
            "Control Room / SCADA": {
                "rating_unit": "kW (facility load)",
                "rating_default": 50.0,
                "rating_min": 5.0,
                "rating_max": 500.0,
                "rating_step": 5.0,
                "rating_help": "Total facility electrical load this SCADA system supervises (kW)",
                "capex_items": [
                    {"name": "Control room & SCADA", "formula": "30_000", "note": "£30k fixed cost for containerised control room"},
                ],
                "opex_items": [
                    {"name": "SCADA maintenance",  "opex_type": "Cost (£/yr)", "formula": "5_000",  "unit": "£/yr", "note": "£5k/yr fixed maintenance and software licence"},
                    {"name": "Control room power", "opex_type": "Power (kW)",  "formula": "20",     "unit": "kW",   "note": "20 kW constant power draw"},
                ],
                "footprint_items": [
                    {"name": "Control room",       "formula": "25", "note": "25 m² fixed — standard portacabin / container"},
                ],
                "output_items": [],
            },
            "Site Fencing & Civil Works": {
                "rating_unit": "m²",
                "rating_default": 500.0,
                "rating_min": 50.0,
                "rating_max": 50000.0,
                "rating_step": 50.0,
                "rating_help": "Total site area to be fenced and prepared (m²)",
                "capex_items": [
                    {"name": "Fencing",            "formula": "rating * 15",  "note": "£15/m² perimeter estimate"},
                    {"name": "Civil / groundworks","formula": "rating * 35",  "note": "£35/m² for hardstanding and drainage"},
                ],
                "opex_items": [
                    {"name": "Site maintenance",   "opex_type": "Cost (£/yr)", "formula": "rating * 2",  "unit": "£/yr", "note": "£2/m²/yr for grass cutting, fencing repair, etc."},
                ],
                "footprint_items": [
                    {"name": "Site area",          "formula": "rating", "note": "Pass-through: the rated area is the footprint"},
                ],
                "output_items": [],
            },
        },
    },
}


# -------------------------------------------------------------------------
# SESSION STATE HELPERS
# -------------------------------------------------------------------------
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

    # Remove legacy project-level currency settings. Project Builder uses GBP throughout.
    for project in st.session_state["pb_projects"].values():
        project.pop("currency", None)
        project.setdefault("created_at", date.today().isoformat())
        _migrate_legacy_project_records(project)


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _fmt_currency(value: float, decimals: int = 0) -> str:
    return f"{PROJECT_CURRENCY_SYMBOL}{format(value, f',.{decimals}f')}"


def _fmt_currency_millions(value: float, decimals: int = 2) -> str:
    return f"{PROJECT_CURRENCY_SYMBOL}{format(value / 1e6, f',.{decimals}f')}M"


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
        "locations": {},
    }
    st.session_state["pb_active_project"] = pid
    return pid


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


def _create_location(project_id: str, name: str, description: str) -> str:
    lid = "loc_" + _short_id()
    st.session_state["pb_projects"][project_id]["locations"][lid] = {
        "id": lid,
        "name": name.strip() or "Unnamed Location",
        "description": description,
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

    active_pid = st.session_state["pb_active_project"]
    active_index = 0
    if active_pid and active_pid in project_ids:
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
        st.sidebar.markdown(
            f'<p style="color:{HS_GREY};font-size:0.78rem;margin-top:6px;line-height:1.5;">'
            f'All financial values in Project Builder use fixed {PROJECT_CURRENCY_LABEL} benchmark assumptions.</p>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Create Project", key="pb_create_proj_btn"):
            if new_name.strip():
                _create_project(new_name, new_desc)
                st.rerun()
            else:
                st.sidebar.error("Please enter a project name.")
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
            project["project_life_years"] = st.sidebar.slider(
                "Project life (years)", 5, 30, project["project_life_years"], key="pb_proj_life"
            )
            project["discount_rate_pct"] = st.sidebar.number_input(
                "Discount rate (%)", 1.0, 20.0, project["discount_rate_pct"], 0.5, key="pb_disc_rate"
            )
            project["inflation_rate_pct"] = st.sidebar.number_input(
                "Inflation rate (%)", 0.0, 10.0, project["inflation_rate_pct"], 0.5, key="pb_inf_rate"
            )

            st.sidebar.markdown("---")
            if st.sidebar.button("Delete this project", key="pb_del_proj_btn"):
                _delete_project(selected_project_id)
                st.rerun()

            return project

    return None


# =========================================================================
# TAB 1 — PROJECT OVERVIEW
# =========================================================================
def _render_tab_overview(project: dict) -> None:
    agg = _aggregate_project_cofo(project)

    # KPI row 1
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total CAPEX", _fmt_currency_millions(agg["total_capex"]))
    m2.metric("Annual OPEX (cost)", f"{_fmt_currency(agg['total_opex_cost'])}/yr")
    m3.metric("Power Demand", f"{agg['total_opex_power_kw']:,.1f} kW")
    m4.metric("Water Demand", f"{agg['total_opex_water_l_hr']:,.0f} L/hr")
    m5.metric("Total Footprint", f"{agg['total_footprint_m2']:,.0f} m²")
    m6.metric("H2 Production", f"{agg['total_h2_kg_yr'] / 1000:,.1f} t/yr")

    # KPI row 2
    m7, m8, m9, m10, m11, m12 = st.columns(6)
    m7.metric("Annual Revenue", f"{_fmt_currency(agg['total_revenue_yr'])}/yr")
    m8.metric("CO2 Saved", f"{agg['total_co2_t_yr']:,.1f} t/yr")
    m9.metric("Power Generated", f"{agg['total_power_mwh_yr']:,.0f} MWh/yr")
    m10.metric("Locations", str(agg["location_count"]))
    m11.metric("Technology Items", str(agg["tech_item_count"]))
    payback_str = "N/A"
    if agg["total_opex_cost"] > 0 and agg["total_revenue_yr"] > agg["total_opex_cost"]:
        payback_yr = agg["total_capex"] / (agg["total_revenue_yr"] - agg["total_opex_cost"])
        payback_str = f"{payback_yr:.1f} yrs"
    m12.metric("Simple Payback", payback_str)

    st.markdown("---")

    # Project details + location summary side by side
    col_left, col_right = st.columns([1, 2])

    with col_left:
        with st.expander("Project Details", expanded=True):
            new_name = st.text_input("Project name", value=project["name"], key=f"pb_edit_proj_name_{project['id']}")
            new_desc = st.text_area("Description", value=project["description"], key=f"pb_edit_proj_desc_{project['id']}", height=80)
            st.caption(f"Financial values on this page use fixed {PROJECT_CURRENCY_LABEL} benchmark assumptions.")
            if st.button("Save Changes", key=f"pb_save_proj_{project['id']}"):
                project["name"] = new_name.strip() or project["name"]
                project["description"] = new_desc
                st.success("Project details saved.")

    with col_right:
        st.markdown(f'<p class="hs-section-header">Location Summary</p>', unsafe_allow_html=True)
        df_locs = _build_location_summary_dataframe(project)
        if not df_locs.empty:
            st.dataframe(df_locs, use_container_width=True, hide_index=True)
        else:
            st.info("No locations added yet. Go to the Locations tab to add your first location.")

    # COFO breakdown bar chart
    st.markdown("---")
    st.markdown(f'<p class="hs-section-header">COFO Breakdown by Location</p>', unsafe_allow_html=True)

    if agg["tech_item_count"] == 0:
        st.info("Add technology items to locations to see the COFO breakdown.")
        return

    # Build per-location CAPEX data for stacked bar
    loc_names = [loc["name"] for loc in project["locations"].values()]
    capex_by_category: dict[str, list] = {cat: [0.0] * len(loc_names) for cat in TECH_CATALOGUE}

    for i, loc in enumerate(project["locations"].values()):
        for item in loc["technology_items"].values():
            cat = item["category"]
            for rec in item["cofo_records"]:
                if rec["cofo_type"] == "CAPEX":
                    if cat in capex_by_category:
                        capex_by_category[cat][i] += rec["value"]

    col_ov1, col_ov2 = st.columns(2)

    with col_ov1:
        fig_capex_loc = go.Figure()
        for cat, values in capex_by_category.items():
            if sum(values) > 0:
                fig_capex_loc.add_bar(
                    x=values,
                    y=loc_names,
                    name=cat,
                    orientation="h",
                    marker_color=CATEGORY_COLOURS.get(cat, HS_GREY),
                )
        fig_capex_loc.update_layout(
            barmode="stack",
            title="CAPEX by Location & Technology Category",
            xaxis_title=PROJECT_CURRENCY_LABEL,
            yaxis=dict(autorange="reversed"),
            height=max(250, 80 * len(loc_names)),
        )
        st.plotly_chart(apply_chart_theme(fig_capex_loc), use_container_width=True, key="pb_chart_capex_loc")
        st.caption("Total upfront capital cost per location, broken down by technology category. Hover over each segment to see the value.")

    with col_ov2:
        # COFO type donut
        cofo_vals = [
            agg["total_capex"],
            agg["total_opex_cost"] * project["project_life_years"],
            agg["total_footprint_m2"] * 1000,  # scaled to make visible; explained in caption
        ]
        cofo_labels = [
            "CAPEX",
            f"Lifetime OPEX (×{project['project_life_years']}yr)",
            f"Footprint (×{PROJECT_CURRENCY_SYMBOL}1k/m²)",
        ]
        cofo_colors = [COFO_COLOURS["CAPEX"], COFO_COLOURS["OPEX"], COFO_COLOURS["Footprint"]]

        fig_cofo_donut = go.Figure(go.Pie(
            labels=cofo_labels,
            values=[v for v in cofo_vals if v > 0],
            hole=0.55,
            marker=dict(colors=[c for c, v in zip(cofo_colors, cofo_vals) if v > 0]),
            textinfo="label+percent",
            textfont=dict(color=HS_WHITE, size=11),
        ))
        fig_cofo_donut.update_layout(
            title="Project Cost Structure",
            showlegend=True,
        )
        st.plotly_chart(apply_chart_theme(fig_cofo_donut), use_container_width=True, key="pb_chart_cofo_donut")
        st.caption("Project cost structure: CAPEX (one-off) vs lifetime OPEX (annualised over project life). Footprint is indexed to £1k/m² to make it comparable in scale — it is not a monetary cost.")


# =========================================================================
# TAB 2 — LOCATIONS
# =========================================================================
def _render_tab_locations(project: dict) -> None:
    col_list, col_detail = st.columns([1, 2])

    with col_list:
        st.markdown(f'<p class="hs-section-header">Locations in this project</p>', unsafe_allow_html=True)

        locs = project["locations"]
        if locs:
            for loc_id, loc in locs.items():
                n_items = len(loc["technology_items"])
                with st.expander(f"{loc['name']} — {n_items} item(s)", expanded=False):
                    new_loc_name = st.text_input(
                        "Location name", value=loc["name"], key=f"pb_loc_name_{loc_id}"
                    )
                    new_loc_desc = st.text_area(
                        "Description",
                        value=loc["description"],
                        key=f"pb_loc_desc_{loc_id}",
                        height=COMPACT_TEXT_AREA_HEIGHT,
                    )
                    save_col, del_col = st.columns(2)
                    with save_col:
                        if st.button("Save", key=f"pb_save_loc_{loc_id}"):
                            loc["name"] = new_loc_name.strip() or loc["name"]
                            loc["description"] = new_loc_desc
                            st.success("Saved.")
                    with del_col:
                        if st.button("Delete", key=f"pb_del_loc_{loc_id}"):
                            if n_items == 0:
                                _delete_location(project["id"], loc_id)
                                st.rerun()
                            else:
                                st.warning(f"Remove all {n_items} technology items first.")
        else:
            st.info("No locations yet.")

        st.markdown("---")
        st.markdown(f'<p class="hs-section-header">Add New Location</p>', unsafe_allow_html=True)
        new_loc_name_inp = st.text_input("Location name", key="pb_new_loc_name", placeholder="e.g. Quayside Block A")
        new_loc_desc_inp = st.text_area(
            "Description (optional)",
            key="pb_new_loc_desc",
            height=COMPACT_TEXT_AREA_HEIGHT,
        )
        if st.button("Add Location", key="pb_add_loc_btn"):
            if new_loc_name_inp.strip():
                _create_location(project["id"], new_loc_name_inp, new_loc_desc_inp)
                st.rerun()
            else:
                st.error("Please enter a location name.")

    with col_detail:
        st.markdown(f'<p class="hs-section-header">Location Detail</p>', unsafe_allow_html=True)

        if not locs:
            st.info("Add a location on the left to see its detail here.")
            return

        location_ids = list(locs.keys())
        inspect_lid = st.selectbox(
            "Select location to inspect",
            location_ids,
            key="pb_inspect_loc_id",
            format_func=lambda location_id: locs[location_id]["name"],
        )
        if inspect_lid not in locs:
            return

        inspect_loc = locs[inspect_lid]
        tech_items = inspect_loc["technology_items"]

        # Location KPIs
        capex = opex_c = power = water = footprint = 0.0
        for item in tech_items.values():
            for rec in item["cofo_records"]:
                if rec["cofo_type"] == "CAPEX":
                    capex += rec["value"]
                elif rec["cofo_type"] == "OPEX":
                    opex_type_key = _record_opex_type_key(rec)
                    if opex_type_key == OPEX_TYPE_COST:
                        opex_c += rec["value"]
                    elif opex_type_key == OPEX_TYPE_POWER:
                        power += rec["value"]
                    elif opex_type_key == OPEX_TYPE_WATER:
                        water += rec["value"]
                elif rec["cofo_type"] == "Footprint":
                    footprint += rec["value"]

        km1, km2, km3, km4, km5 = st.columns(5)
        km1.metric("Tech Items", str(len(tech_items)))
        km2.metric("CAPEX", _fmt_currency(capex))
        km3.metric("OPEX (GBP/yr)", _fmt_currency(opex_c))
        km4.metric("Power (kW)", f"{power:,.1f}")
        km5.metric("Footprint (m²)", f"{footprint:,.0f}")

        st.markdown("---")
        df_tech = _build_tech_summary_dataframe({"locations": {inspect_lid: inspect_loc}})
        if not df_tech.empty:
            st.dataframe(df_tech.drop(columns=["Location"]), use_container_width=True, hide_index=True)
        else:
            st.info("No technology items at this location. Add items in the Technology Build tab.")


# =========================================================================
# TAB 3 — TECHNOLOGY BUILD
# =========================================================================
def _render_tab_technology(project: dict) -> None:
    locs = project["locations"]

    if not locs:
        st.info("Add at least one location in the Locations tab first.")
        return

    location_ids = list(locs.keys())
    working_lid = st.selectbox(
        "Working location",
        location_ids,
        key="pb_tech_location_id",
        format_func=lambda location_id: locs[location_id]["name"],
        help="Select which location to add or manage technology items for.",
    )
    if working_lid not in locs:
        return

    working_loc = locs[working_lid]
    tech_items = working_loc["technology_items"]

    st.markdown(f'<p class="hs-section-header">Technology at {working_loc["name"]}</p>', unsafe_allow_html=True)

    if tech_items:
        df_existing = _build_tech_summary_dataframe({"locations": {working_lid: working_loc}})
        if not df_existing.empty:
            st.dataframe(df_existing.drop(columns=["Location"]), use_container_width=True, hide_index=True)

        # Remove item
        item_ids = list(tech_items.keys())
        col_sel, col_del = st.columns([3, 1])
        with col_sel:
            selected_item_id = st.selectbox(
                "Select item to view / remove",
                [None] + item_ids,
                key=f"pb_select_tech_item_id_{working_lid}",
                format_func=lambda tech_id: "— select —" if tech_id is None else tech_items[tech_id]["display_name"],
            )
        with col_del:
            st.markdown("<br>", unsafe_allow_html=True)
            if selected_item_id is not None and st.button("Remove selected", key=f"pb_remove_item_{working_lid}"):
                _remove_tech_item(project["id"], working_lid, selected_item_id)
                st.rerun()

        # COFO detail expander
        if selected_item_id in tech_items:
            sel_item = tech_items[selected_item_id]
            with st.expander(f"COFO Records — {sel_item['display_name']}", expanded=False):
                if sel_item["cofo_records"]:
                    df_cofo = pd.DataFrame([{
                        "COFO Type": r["cofo_type"],
                        "Item Name": r["item_name"],
                        "OPEX/Output Type": _record_opex_type_label(r) if r["cofo_type"] == "OPEX" else r["output_subtype"] or "—",
                        "Value": f"{r['value']:,.2f}",
                        "Unit": r["unit"],
                        "Auto-Calc": "Yes" if r["is_auto_calculated"] else "No",
                        "Note": r["source_note"],
                    } for r in sel_item["cofo_records"]])
                    st.dataframe(df_cofo, use_container_width=True, hide_index=True)
                else:
                    st.info("No COFO records for this item.")

    st.markdown("---")

    # ---- ADD TECHNOLOGY EXPANDER ----
    add_expanded = len(tech_items) == 0
    with st.expander("+ Add Technology Item", expanded=add_expanded):
        source_type = st.radio(
            "Source",
            ["From Catalogue", "Manual entry"],
            horizontal=True,
            key=f"pb_add_source_{working_lid}",
        )

        # ================================================================
        # FROM CATALOGUE
        # ================================================================
        if source_type == "From Catalogue":
            categories = list(TECH_CATALOGUE.keys())
            selected_cat = st.selectbox("Category", categories, key="pb_cat_select")

            types = list(TECH_CATALOGUE[selected_cat].keys())
            selected_type = st.selectbox("Type", types, key="pb_type_select")

            components = list(TECH_CATALOGUE[selected_cat][selected_type].keys())
            selected_comp = st.selectbox("Component", components, key="pb_comp_select")

            spec = TECH_CATALOGUE[selected_cat][selected_type][selected_comp]

            st.markdown(
                f'<div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};'
                f'border-radius:4px;padding:14px 18px;margin:10px 0;">'
                f'<p style="color:{HS_GREY};font-size:0.82rem;margin:0;">Rating input: '
                f'<b style="color:{HS_WHITE};">{spec["rating_unit"]}</b> &nbsp;—&nbsp; {spec["rating_help"]}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            rating_val = st.number_input(
                f"Rating ({spec['rating_unit']})",
                min_value=spec["rating_min"],
                max_value=spec["rating_max"],
                value=spec["rating_default"],
                step=spec["rating_step"],
                key="pb_rating_input",
            )

            # Live preview
            preview_records, preview_errors = calculate_cofo_records(spec, rating_val)
            if preview_errors:
                st.error("Formula errors:\n" + "\n".join(f"- {err}" for err in preview_errors))
            if preview_records:
                st.markdown(f'<p class="hs-section-header">Auto-calculated COFO preview</p>', unsafe_allow_html=True)
                preview_df = pd.DataFrame([{
                    "COFO Type": r["cofo_type"],
                    "Item": r["item_name"],
                    "Type": _record_opex_type_label(r) if r["cofo_type"] == "OPEX" else r["output_subtype"] or "—",
                    "Value": f"{r['value']:,.2f}",
                    "Unit": r["unit"],
                } for r in preview_records])
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

            default_display_name = f"{selected_comp} ({rating_val} {spec['rating_unit']})"
            display_name = st.text_input(
                "Display name (editable)", value=default_display_name, key="pb_tech_display_name"
            )
            notes = st.text_area(
                "Notes (optional)",
                key="pb_tech_notes",
                height=COMPACT_TEXT_AREA_HEIGHT,
            )

            if st.button("Add to Location", key="pb_add_tech_catalogue_btn"):
                if not display_name.strip():
                    st.error("Please enter a display name.")
                elif preview_errors:
                    st.error("This component contains formula errors and cannot be added until they are fixed.")
                else:
                    cofo_records, cofo_errors = calculate_cofo_records(spec, rating_val)
                    if cofo_errors:
                        st.error("This component contains formula errors and cannot be added until they are fixed.")
                        return
                    new_item = {
                        "id": "tech_" + _short_id(),
                        "display_name": display_name.strip(),
                        "category": selected_cat,
                        "type_": selected_type,
                        "component": selected_comp,
                        "rating_value": rating_val,
                        "rating_unit": spec["rating_unit"],
                        "notes": notes,
                        "cofo_records": cofo_records,
                    }
                    _add_tech_item(project["id"], working_lid, new_item)
                    st.success(f"Added: {display_name}")
                    st.rerun()

        # ================================================================
        # MANUAL ENTRY
        # ================================================================
        else:
            pending_manual_cofo = _get_pending_manual_cofo(project["id"], working_lid)
            st.info("Use manual entry to add custom technology items not in the catalogue. Add one COFO record at a time.")

            manual_name = st.text_input("Item display name", key="pb_manual_item_name", placeholder="e.g. Custom heat exchanger")
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                manual_cat = st.selectbox("Category", list(TECH_CATALOGUE.keys()) + ["Other"], key="pb_manual_cat")
                manual_type = st.text_input("Type", key="pb_manual_type", placeholder="e.g. Heat Recovery")
            with c_m2:
                manual_comp = st.text_input("Component", key="pb_manual_comp", placeholder="e.g. Plate Heat Exchanger")
                manual_rating = st.text_input("Rating (value + unit)", key="pb_manual_rating", placeholder="e.g. 500 kW")

            st.markdown(f'<p class="hs-section-header">Add COFO Record</p>', unsafe_allow_html=True)
            cofo_type_sel = st.selectbox("COFO Type", ["CAPEX", "OPEX", "Footprint", "Output"], key="pb_manual_cofo_type")

            cofo_item_name = st.text_input("Item name", key="pb_manual_cofo_item_name", placeholder="e.g. Heat exchanger unit")

            new_cofo: dict = {
                "id": _short_id(),
                "cofo_type": cofo_type_sel,
                "item_name": cofo_item_name,
                "opex_type": "",
                "output_type": "",
                "output_subtype": "",
                "value": 0.0,
                "unit": "",
                "is_auto_calculated": False,
                "source_formula": "",
                "source_note": "Manual entry",
            }

            if cofo_type_sel == "CAPEX":
                new_cofo["value"] = st.number_input("CAPEX value (£)", min_value=0.0, step=1000.0, key="pb_manual_capex_val")
                new_cofo["unit"] = "£"

            elif cofo_type_sel == "OPEX":
                opex_type_sel = st.selectbox(
                    "OPEX type",
                    [OPEX_TYPE_COST, OPEX_TYPE_POWER, OPEX_TYPE_WATER, OPEX_TYPE_OTHER],
                    key="pb_manual_opex_type",
                    format_func=lambda type_key: _opex_type_label(type_key),
                )
                new_cofo["opex_type_key"] = opex_type_sel
                new_cofo["opex_type"] = _opex_type_label(opex_type_sel)
                new_cofo["value"] = st.number_input("Value", min_value=0.0, step=0.1, key="pb_manual_opex_val")
                new_cofo["unit"] = st.text_input("Unit", value=_opex_unit_for_key(opex_type_sel), key="pb_manual_opex_unit")

            elif cofo_type_sel == "Footprint":
                new_cofo["value"] = st.number_input("Footprint area (m²)", min_value=0.0, step=1.0, key="pb_manual_foot_val")
                new_cofo["unit"] = "m²"

            elif cofo_type_sel == "Output":
                output_type_sel = st.selectbox("Output type", ["Product", "Revenue", "Saving"], key="pb_manual_out_type")
                output_subtype_sel = st.selectbox(
                    "Output subtype",
                    [
                        OUTPUT_SUBTYPE_H2_PRODUCTION,
                        OUTPUT_SUBTYPE_H2_COMPRESSION,
                        OUTPUT_SUBTYPE_H2_STORAGE,
                        OUTPUT_SUBTYPE_POWER_GENERATION,
                        OUTPUT_SUBTYPE_WATER_OUTPUT,
                        OUTPUT_SUBTYPE_REVENUE,
                        OUTPUT_SUBTYPE_CO2_AVOIDED,
                        "NOx (kg/yr)",
                        "SOx (kg/yr)",
                        "Other",
                    ],
                    key="pb_manual_out_subtype"
                )
                new_cofo["output_type"] = output_type_sel
                new_cofo["output_subtype"] = output_subtype_sel
                new_cofo["value"] = st.number_input("Value", min_value=0.0, step=0.1, key="pb_manual_out_val")
                new_cofo["unit"] = st.text_input("Unit", key="pb_manual_out_unit")

            if st.button("Add COFO Record", key="pb_manual_add_cofo_btn"):
                if not cofo_item_name.strip():
                    st.error("Please enter an item name.")
                elif new_cofo["value"] == 0.0:
                    st.warning("Value is 0 — record added anyway.")
                    pending_manual_cofo.append(new_cofo)
                else:
                    pending_manual_cofo.append(new_cofo)
                    st.success(f"COFO record '{cofo_item_name}' added to pending list.")

            if pending_manual_cofo:
                st.markdown(f'<p class="hs-section-header">Pending COFO records</p>', unsafe_allow_html=True)
                pending_df = pd.DataFrame([{
                    "COFO Type": r["cofo_type"],
                    "Item": r["item_name"],
                    "Type": _record_opex_type_label(r) if r["cofo_type"] == "OPEX" else r["output_subtype"] or "—",
                    "Value": f"{r['value']:,.2f}",
                    "Unit": r["unit"],
                } for r in pending_manual_cofo])
                st.dataframe(pending_df, use_container_width=True, hide_index=True)

                col_save, col_clear = st.columns(2)
                with col_save:
                    if st.button("Save Technology Item", key="pb_manual_save_btn"):
                        if not manual_name.strip():
                            st.error("Please enter a display name for the technology item.")
                        else:
                            rating_str = manual_rating.strip() if manual_rating else "—"
                            rating_val_manual = 0.0
                            rating_unit_manual = rating_str
                            try:
                                parts = rating_str.split()
                                if parts:
                                    rating_val_manual = float(parts[0])
                                    rating_unit_manual = " ".join(parts[1:]) if len(parts) > 1 else "—"
                            except (ValueError, IndexError):
                                pass

                            new_manual_item = {
                                "id": "tech_" + _short_id(),
                                "display_name": manual_name.strip(),
                                "category": manual_cat,
                                "type_": manual_type or "—",
                                "component": manual_comp or "—",
                                "rating_value": rating_val_manual,
                                "rating_unit": rating_unit_manual,
                                "notes": "",
                                "cofo_records": list(pending_manual_cofo),
                            }
                            _add_tech_item(project["id"], working_lid, new_manual_item)
                            _clear_pending_manual_cofo(project["id"], working_lid)
                            st.success(f"Technology item '{manual_name}' saved.")
                            st.rerun()
                with col_clear:
                    if st.button("Clear pending records", key="pb_manual_clear_btn"):
                        _clear_pending_manual_cofo(project["id"], working_lid)
                        st.rerun()


# =========================================================================
# TAB 4 — CATALOGUE REFERENCE
# =========================================================================
def _render_tab_catalogue() -> None:
    st.markdown(f'<p class="hs-section-header">Technology Catalogue</p>', unsafe_allow_html=True)
    st.caption("Browse available components and their default cost/output formulas. Use the preview to see calculated values at any rating.")

    col_browse, col_detail = st.columns([1, 2])

    with col_browse:
        cat_options = list(TECH_CATALOGUE.keys())
        browse_cat = st.selectbox("Category", cat_options, key="pb_cat_browse")
        type_options = list(TECH_CATALOGUE[browse_cat].keys())
        browse_type = st.selectbox("Type", type_options, key="pb_type_browse")
        comp_options = list(TECH_CATALOGUE[browse_cat][browse_type].keys())
        browse_comp = st.selectbox("Component", comp_options, key="pb_comp_browse")

    with col_detail:
        spec = TECH_CATALOGUE[browse_cat][browse_type][browse_comp]

        st.markdown(
            f'<div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};'
            f'border-radius:4px;padding:14px 18px;margin-bottom:12px;">'
            f'<p style="color:{HS_GREEN};font-weight:700;font-size:0.9rem;margin:0 0 6px 0;">'
            f'{browse_comp}</p>'
            f'<p style="color:{HS_GREY};font-size:0.82rem;margin:0;">'
            f'Category: {browse_cat} &nbsp;|&nbsp; Type: {browse_type}<br>'
            f'Rating unit: <b style="color:{HS_WHITE};">{spec["rating_unit"]}</b></p>'
            f'</div>',
            unsafe_allow_html=True,
        )

        preview_rating = st.number_input(
            f"Preview at rating ({spec['rating_unit']})",
            min_value=spec["rating_min"],
            max_value=spec["rating_max"],
            value=spec["rating_default"],
            step=spec["rating_step"],
            key="pb_cat_preview_rating",
        )

        preview_records, preview_errors = calculate_cofo_records(spec, preview_rating)
        if preview_errors:
            st.error("Formula errors:\n" + "\n".join(f"- {err}" for err in preview_errors))
        if preview_records:
            preview_df = pd.DataFrame([{
                "COFO Type": r["cofo_type"],
                "Item": r["item_name"],
                "OPEX/Output Type": _record_opex_type_label(r) if r["cofo_type"] == "OPEX" else r["output_subtype"] or "—",
                f"Value at {preview_rating} {spec['rating_unit']}": f"{r['value']:,.2f}",
                "Unit": r["unit"],
                "Formula": r["source_formula"],
                "Basis": r["source_note"],
            } for r in preview_records])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
        elif not preview_errors:
            st.info("No COFO records defined for this component.")


# =========================================================================
# TAB 5 — RESULTS & ANALYSIS
# =========================================================================
def _render_tab_analysis(project: dict) -> None:
    agg = _aggregate_project_cofo(project)

    if agg["tech_item_count"] == 0:
        st.info("Add technology items to locations to see analysis charts.")
        return

    proj_life = project["project_life_years"]
    inflation = project["inflation_rate_pct"] / 100.0

    # ---- ROW A: CAPEX charts ----
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        # CAPEX by location × category (stacked bar)
        loc_names = [loc["name"] for loc in project["locations"].values()]
        capex_by_cat: dict[str, list] = {cat: [0.0] * len(loc_names) for cat in TECH_CATALOGUE}

        for i, loc in enumerate(project["locations"].values()):
            for item in loc["technology_items"].values():
                cat = item["category"]
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "CAPEX" and cat in capex_by_cat:
                        capex_by_cat[cat][i] += rec["value"]

        fig_capex = go.Figure()
        for cat, vals in capex_by_cat.items():
            if sum(vals) > 0:
                fig_capex.add_bar(
                    x=vals, y=loc_names, name=cat, orientation="h",
                    marker_color=CATEGORY_COLOURS.get(cat, HS_GREY),
                    text=[_fmt_currency(v) if v > 0 else "" for v in vals],
                    textposition="inside", textfont=dict(color=HS_WHITE, size=10),
                )
        fig_capex.update_layout(
            barmode="stack",
            title=f"CAPEX by Location — Total {_fmt_currency(agg['total_capex'])}",
            xaxis_title=PROJECT_CURRENCY_LABEL,
            yaxis=dict(autorange="reversed"),
            height=max(300, 80 * len(loc_names)),
        )
        st.plotly_chart(apply_chart_theme(fig_capex), use_container_width=True, key="pb_chart_analysis_capex")
        st.caption("Total upfront capital investment per location. Hover over each segment for the category-level value.")

    with col_a2:
        # CAPEX vs lifetime OPEX waterfall comparison
        lifetime_opex_cost = agg["total_opex_cost"] * proj_life
        fig_waterfall = go.Figure(go.Bar(
            x=["Total CAPEX", f"Lifetime OPEX\n({proj_life} yrs)", "Total Lifetime Cost"],
            y=[agg["total_capex"], lifetime_opex_cost, agg["total_capex"] + lifetime_opex_cost],
            marker_color=[COFO_COLOURS["CAPEX"], COFO_COLOURS["OPEX"], HS_WHITE],
            text=[
                _fmt_currency_millions(agg["total_capex"]),
                _fmt_currency_millions(lifetime_opex_cost),
                _fmt_currency_millions(agg["total_capex"] + lifetime_opex_cost),
            ],
            textposition="outside",
            textfont=dict(color=HS_WHITE),
        ))
        fig_waterfall.update_layout(
            title="CAPEX vs Lifetime OPEX Cost",
            yaxis_title=PROJECT_CURRENCY_LABEL,
            showlegend=False,
        )
        st.plotly_chart(apply_chart_theme(fig_waterfall), use_container_width=True, key="pb_chart_analysis_waterfall")
        st.caption(f"One-off capital cost vs the total cost of operating the project over {proj_life} years. Shows whether CAPEX or OPEX dominates the overall cost structure.")

    st.markdown("---")

    # ---- ROW B: OPEX breakdown ----
    col_b1, col_b2 = st.columns(2)

    with col_b1:
        # OPEX cost (£/yr) by technology item — sorted
        opex_items_list = []
        for loc in project["locations"].values():
            for item in loc["technology_items"].values():
                item_opex = sum(r["value"] for r in item["cofo_records"]
                                if r["cofo_type"] == "OPEX" and _record_opex_type_key(r) == OPEX_TYPE_COST)
                if item_opex > 0:
                    opex_items_list.append((f"{loc['name']} / {item['display_name']}", item_opex))

        if opex_items_list:
            opex_items_list.sort(key=lambda x: x[1])
            opex_labels = [x[0] for x in opex_items_list]
            opex_vals = [x[1] for x in opex_items_list]
            fig_opex_bar = go.Figure(go.Bar(
                x=opex_vals, y=opex_labels, orientation="h",
                marker=dict(
                    color=opex_vals,
                    colorscale=[[0, HS_GREEN_DARK], [1, HS_GREEN]],
                    showscale=False,
                ),
                text=[_fmt_currency(v) for v in opex_vals],
                textposition="outside",
                textfont=dict(color=HS_WHITE, size=10),
            ))
            fig_opex_bar.update_layout(
                title="Annual OPEX Cost by Technology Item",
                xaxis_title=PROJECT_CURRENCY_RATE_LABEL,
                yaxis=dict(autorange="reversed"),
                margin=dict(l=220),
                height=max(300, 55 * len(opex_items_list)),
            )
            st.plotly_chart(apply_chart_theme(fig_opex_bar), use_container_width=True, key="pb_chart_opex_items")
            st.caption("Annual operating cost (GBP/yr) for each technology item. Longer bars are the biggest contributors to running costs.")
        else:
            st.info("No OPEX cost records to display.")

    with col_b2:
        # OPEX breakdown by type: Cost / Power / Water
        opex_cost_total = agg["total_opex_cost"]
        opex_power_total = agg["total_opex_power_kw"]
        opex_water_total = agg["total_opex_water_l_hr"]

        fig_opex_types = go.Figure()
        fig_opex_types.add_bar(
            name=f"Cost ({PROJECT_CURRENCY_RATE_LABEL})",
            x=[_opex_type_label(OPEX_TYPE_COST)],
            y=[opex_cost_total],
            marker_color=COFO_COLOURS["OPEX"],
            yaxis="y1",
            text=[_fmt_currency(opex_cost_total)],
            textposition="outside",
            textfont=dict(color=HS_WHITE),
        )
        fig_opex_types.add_bar(
            name="Power (kW)",
            x=["Power (kW)"],
            y=[opex_power_total],
            marker_color=HS_GREEN,
            yaxis="y2",
            text=[f"{opex_power_total:,.1f} kW"],
            textposition="outside",
            textfont=dict(color=HS_WHITE),
        )
        fig_opex_types.add_bar(
            name="Water (L/hr)",
            x=["Water (L/hr)"],
            y=[opex_water_total],
            marker_color="#2196a0",
            yaxis="y2",
            text=[f"{opex_water_total:,.0f} L/hr"],
            textposition="outside",
            textfont=dict(color=HS_WHITE),
        )
        fig_opex_types.update_layout(
            title="OPEX by Resource Type",
            yaxis=dict(title=dict(text=PROJECT_CURRENCY_RATE_LABEL, font=dict(color=COFO_COLOURS["OPEX"]))),
            yaxis2=dict(title=dict(text="kW / L/hr", font=dict(color=HS_GREEN)),
                        overlaying="y", side="right"),
            barmode="group",
        )
        st.plotly_chart(apply_chart_theme(fig_opex_types), use_container_width=True, key="pb_chart_opex_types")
        st.caption("Three types of OPEX: money (GBP/yr cost), power demand (kW), and water demand (L/hr). Power and water are on the right axis because they use different units to cost.")

    st.markdown("---")

    # ---- ROW C: Outputs ----
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        # Outputs by subtype — horizontal grouped bar
        output_rows: list[dict] = []
        for loc in project["locations"].values():
            for item in loc["technology_items"].values():
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "Output":
                        output_rows.append({
                            "subtype": rec["output_subtype"],
                            "value": rec["value"],
                            "output_type": rec["output_type"],
                            "item": item["display_name"],
                        })

        if output_rows:
            output_df = pd.DataFrame(output_rows)
            agg_out = output_df.groupby("subtype")["value"].sum().reset_index()
            agg_out = agg_out.sort_values("value", ascending=True)

            output_colours = {
                OUTPUT_SUBTYPE_H2_PRODUCTION:  HS_GREEN,
                OUTPUT_SUBTYPE_H2_COMPRESSION: HS_GREEN_DARK,
                OUTPUT_SUBTYPE_H2_STORAGE:     "#6ea8fe",
                OUTPUT_SUBTYPE_POWER_GENERATION: "#499823",
                OUTPUT_SUBTYPE_WATER_OUTPUT:   "#2196a0",
                OUTPUT_SUBTYPE_REVENUE:        "#a7d730",
                OUTPUT_SUBTYPE_CO2_AVOIDED:    "#4caf84",
                "NOx (kg/yr)":     "#d4a017",
                "SOx (kg/yr)":     "#e05c5c",
            }

            fig_outputs = go.Figure(go.Bar(
                x=agg_out["value"],
                y=agg_out["subtype"],
                orientation="h",
                marker_color=[output_colours.get(s, HS_GREY) for s in agg_out["subtype"]],
                text=[f"{v:,.1f}" for v in agg_out["value"]],
                textposition="outside",
                textfont=dict(color=HS_WHITE, size=10),
            ))
            fig_outputs.update_layout(
                title="Outputs and Capacities by Type",
                xaxis_title="Annual value (native units)",
                margin=dict(l=140),
                height=max(250, 55 * len(agg_out)),
            )
            st.plotly_chart(apply_chart_theme(fig_outputs), use_container_width=True, key="pb_chart_outputs")
            st.caption("All outputs and capacity-style records aggregated across the project. Each row uses its own native unit (kg, MWh, GBP, t CO2) — values cannot be directly compared across rows, but they do show the scale of each project stream.")
        else:
            st.info("No output records. Add technology from the catalogue to see outputs.")

    with col_c2:
        # Revenue vs OPEX cost by location
        loc_rev = {}
        loc_opex = {}
        for loc in project["locations"].values():
            loc_rev[loc["name"]] = 0.0
            loc_opex[loc["name"]] = 0.0
            for item in loc["technology_items"].values():
                for rec in item["cofo_records"]:
                    if rec["cofo_type"] == "Output" and rec["output_subtype"] == OUTPUT_SUBTYPE_REVENUE:
                        loc_rev[loc["name"]] += rec["value"]
                    elif rec["cofo_type"] == "OPEX" and _record_opex_type_key(rec) == OPEX_TYPE_COST:
                        loc_opex[loc["name"]] += rec["value"]

        if any(v > 0 for v in {**loc_rev, **loc_opex}.values()):
            fig_rev_opex = go.Figure()
            fig_rev_opex.add_bar(
                name="Annual Revenue (GBP/yr)",
                x=list(loc_rev.keys()),
                y=list(loc_rev.values()),
                marker_color=HS_GREEN,
                text=[_fmt_currency(v) for v in loc_rev.values()],
                textposition="outside",
                textfont=dict(color=HS_WHITE),
            )
            fig_rev_opex.add_bar(
                name="Annual OPEX Cost (GBP/yr)",
                x=list(loc_opex.keys()),
                y=list(loc_opex.values()),
                marker_color=HS_GREY,
                text=[_fmt_currency(v) for v in loc_opex.values()],
                textposition="outside",
                textfont=dict(color=HS_WHITE),
            )
            fig_rev_opex.update_layout(
                barmode="group",
                title="Revenue vs OPEX Cost by Location",
                yaxis_title=PROJECT_CURRENCY_RATE_LABEL,
            )
            st.plotly_chart(apply_chart_theme(fig_rev_opex), use_container_width=True, key="pb_chart_rev_opex")
            st.caption("Revenue vs operating cost for each location. Green bars above grey bars mean a location is covering its own running costs. A location with no green bar has no revenue-generating outputs.")
        else:
            st.info("No revenue or cost data available for comparison.")

    st.markdown("---")

    # ---- ROW D: Indicative project cash flow (full width) ----
    st.markdown(f'<p class="hs-section-header">Indicative Project Cash Flow</p>', unsafe_allow_html=True)

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

    # Find payback
    payback_yr = None
    for y in range(1, proj_life + 1):
        if cumulative_cf[y] >= 0:
            payback_yr = y
            break

    fig_cf = go.Figure()
    fig_cf.add_bar(
        x=years[1:], y=annual_revenue[1:],
        name="Annual Revenue", marker_color=HS_GREEN,
    )
    fig_cf.add_bar(
        x=years[1:], y=-annual_opex_cost[1:],
        name="Annual OPEX Cost", marker_color=HS_GREY,
    )
    bar_colors_cum = ["#a7d730" if v >= 0 else "#e05c5c" for v in cumulative_cf]
    fig_cf.add_scatter(
        x=years, y=cumulative_cf,
        name="Cumulative Net Cash Flow",
        mode="lines+markers",
        line=dict(color=HS_WHITE, width=2, dash="dot"),
        marker=dict(color=bar_colors_cum, size=7),
        yaxis="y",
    )
    fig_cf.add_hline(y=0, line_color=HS_GREY, line_dash="dash", line_width=1)
    if payback_yr:
        fig_cf.add_vline(
            x=payback_yr,
            line_color=HS_GREEN,
            line_dash="dot",
            annotation_text=f"Payback Yr {payback_yr}",
            annotation_font_color=HS_GREEN,
        )
    fig_cf.update_layout(
        barmode="relative",
        title="Indicative Project Cash Flow (pre-tax, no degradation)",
        xaxis_title="Year",
        yaxis_title=PROJECT_CURRENCY_LABEL,
        height=380,
    )
    st.plotly_chart(apply_chart_theme(fig_cf), use_container_width=True, key="pb_chart_cashflow")
    st.caption(
        f"Simplified indicative cash flow over {proj_life} years. Green bars = annual revenue, grey bars = annual OPEX cost. "
        f"The dotted line is the running cumulative cash position starting from -{_fmt_currency(agg['total_capex'])} CAPEX at year 0. "
        f"This model does not include tax, degradation, or debt — use the dedicated models (Green OffPort, Industrial, Utility Scale) for full financial analysis."
    )

    st.markdown("---")

    # ---- Data tables ----
    with st.expander("Full COFO Records Table", expanded=False):
        df_full = _build_full_cofo_dataframe(project)
        if not df_full.empty:
            st.dataframe(df_full, use_container_width=True, hide_index=True)
        else:
            st.info("No COFO records yet.")

    with st.expander("Location Summary Table", expanded=False):
        df_loc_sum = _build_location_summary_dataframe(project)
        if not df_loc_sum.empty:
            st.dataframe(df_loc_sum, use_container_width=True, hide_index=True)
        else:
            st.info("No locations with technology items yet.")

    with st.expander("Technology Item Summary", expanded=False):
        df_tech_sum = _build_tech_summary_dataframe(project)
        if not df_tech_sum.empty:
            st.dataframe(df_tech_sum, use_container_width=True, hide_index=True)
        else:
            st.info("No technology items yet.")


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
    st.info(
        "No project is active. Use the sidebar on the left to create a new project — "
        "give it a name and click **Create Project** to begin."
    )
    st.markdown(
        f"""
        <div style="background:{HS_BG_CARD};border-left:4px solid {HS_GREEN};border-radius:6px;
        padding:22px 26px;margin-top:18px;max-width:700px;">
        <p style="color:{HS_GREEN};font-weight:700;font-size:0.9rem;text-transform:uppercase;
        letter-spacing:0.07em;margin:0 0 10px 0;">How the Project Builder works</p>
        <p style="color:#e8e8e8;font-size:0.92rem;line-height:1.7;margin:0;">
        <b style="color:{HS_WHITE};">1. Create a project</b> — give it a name.<br>
        <b style="color:{HS_WHITE};">2. Add locations</b> — a project can have multiple sites or areas (e.g. Quayside, Substation, Storage Yard).<br>
        <b style="color:{HS_WHITE};">3. Add technology items</b> to each location — choose from the catalogue
        (electrolyser, solar, compressor, storage, etc.) or enter custom items manually.<br>
        <b style="color:{HS_WHITE};">4. Set the rating</b> (e.g. 2 MW) — CAPEX, OPEX, footprint, and outputs are
        auto-calculated using industry benchmark formulas.<br>
        <b style="color:{HS_WHITE};">5. Review Results</b> — see total project CAPEX, annual OPEX, energy and
        water demands, outputs, revenue, and an indicative cash flow in the Analysis tab.<br><br>
        All financial values in Project Builder are shown in fixed {PROJECT_CURRENCY_LABEL} terms.
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

st.markdown("---")

tab_overview, tab_locs, tab_tech, tab_cat, tab_analysis = st.tabs([
    "Project Overview",
    "Locations",
    "Technology Build",
    "Catalogue Reference",
    "Results & Analysis",
])

with tab_overview:
    _render_tab_overview(active_project)

with tab_locs:
    _render_tab_locations(active_project)

with tab_tech:
    _render_tab_technology(active_project)

with tab_cat:
    _render_tab_catalogue()

with tab_analysis:
    _render_tab_analysis(active_project)
