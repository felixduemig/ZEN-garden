"""
Build script for the Crystal Ball RC model.
Creates: 6_cb_rc_model
Nodes: CH, DE, AT
96 time steps = 4 meteorological seasons × 24 hours (median per hour-of-day within season)
"""

import pandas as pd
import numpy as np
import os
import json
import shutil

# =====================================================================
# PATHS & SETTINGS
# =====================================================================
CB_PATH  = r"C:\Users\felix\Documents\GitHub\ZEN-garden\ZEN-models\data\Crystal_Ball"
OUT_PATH = r"C:\Users\felix\Documents\GitHub\ZEN-garden\6_cb_rc_model"

NODES    = ["CH", "DE", "AT"]
EDGES    = ["CH-AT", "AT-CH", "CH-DE", "DE-CH", "DE-AT", "AT-DE"]

REF_YEAR  = 2023
OPT_YEARS = 8
INTERVAL  = 2
# Optimized years: 2023, 2025, 2027, 2029, 2031, 2033, 2035, 2037
CAPEX_YEARS = list(range(REF_YEAR, 2051))  # 2023..2050

# =====================================================================
# STEP 1 – REPRESENTATIVE 96 TIME STEPS
# =====================================================================
# Non-leap year calendar (Crystal Ball data starts Jan 1 = hour 0)
_MS = {'Jan':    0, 'Feb':  744, 'Mar': 1416, 'Apr': 2160,
       'May': 2880, 'Jun': 3624, 'Jul': 4344, 'Aug': 5088,
       'Sep': 5832, 'Oct': 6552, 'Nov': 7296, 'Dec': 8016}
_ML = {'Jan':744, 'Feb':672, 'Mar':744, 'Apr':720, 'May':744,
       'Jun':720, 'Jul':744, 'Aug':744, 'Sep':720,
       'Oct':744, 'Nov':720, 'Dec':744}

def _month_hours(m):
    return np.arange(_MS[m], _MS[m] + _ML[m])

# Meteorological seasons (DJF/MAM/JJA/SON)
SEASON_HOURS = {
    'Winter': np.concatenate([_month_hours(m) for m in ['Dec','Jan','Feb']]),
    'Spring': np.concatenate([_month_hours(m) for m in ['Mar','Apr','May']]),
    'Summer': np.concatenate([_month_hours(m) for m in ['Jun','Jul','Aug']]),
    'Autumn': np.concatenate([_month_hours(m) for m in ['Sep','Oct','Nov']]),
}
SEASON_ORDER = ['Winter','Spring','Summer','Autumn']


def to_96ts(arr_8760):
    """
    Convert an 8760-length array to 96 representative time steps.
    For each of the 4 seasons and each hour-of-day (0-23):
      representative value = median over all matching hours in that season.
    Output order: [W_h0, W_h1, ..., W_h23, Sp_h0, ..., Su_h23, Au_h0, ..., Au_h23]
    """
    arr = np.asarray(arr_8760, dtype=float)
    assert len(arr) >= 8760, f"Expected ≥8760 values, got {len(arr)}"
    arr = arr[:8760]
    result = []
    for season in SEASON_ORDER:
        hrs = SEASON_HOURS[season]
        for h in range(24):
            subset = arr[hrs[hrs % 24 == h]]
            result.append(float(np.median(subset)))
    return np.array(result)


# =====================================================================
# STEP 2 – CAPACITY EXISTING AGGREGATION
# =====================================================================
def sum_cap_existing(df, node, ref_year, lifetime):
    """Sum all vintage entries for node that are still alive at ref_year."""
    cutoff = ref_year - lifetime
    mask = (df['node'] == node) & (df['year_construction'] >= cutoff)
    return float(df.loc[mask, 'capacity_existing'].sum())


# =====================================================================
# STEP 3 – LOAD CRYSTAL BALL DATA
# =====================================================================
print("Loading Crystal Ball 8760 h data …")
elec_8760  = pd.read_csv(f"{CB_PATH}/set_carriers/electricity/demand.csv", index_col=0)
heat_8760  = pd.read_csv(f"{CB_PATH}/set_carriers/heat/demand.csv",        index_col=0)
wind_8760  = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/wind_onshore/max_load.csv",
    index_col=0)
pv_8760    = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/photovoltaics/max_load.csv",
    index_col=0)

print("Computing 96 representative time steps …")
elec_96  = {n: to_96ts(elec_8760[n].values) for n in NODES}
heat_96  = {n: to_96ts(heat_8760[n].values) for n in NODES}
wind_96  = {n: to_96ts(wind_8760[n].values) for n in NODES}
pv_96    = {n: to_96ts(pv_8760[n].values)   for n in NODES}

print("Reading capacity_existing vintages …")
wind_df = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/wind_onshore/capacity_existing.csv")
pv_df   = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/photovoltaics/capacity_existing.csv")
hp_df   = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/heat_pump/capacity_existing.csv")
ngb_df  = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_conversion_technologies/natural_gas_boiler/capacity_existing.csv")
ngs_df  = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_storage_technologies/natural_gas_storage/capacity_existing.csv")
ngs_e_df = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_storage_technologies/natural_gas_storage/capacity_existing_energy.csv")
ngp_df  = pd.read_csv(
    f"{CB_PATH}/set_technologies/set_transport_technologies/natural_gas_pipeline/capacity_existing.csv")

# Technology lifetimes (years)
LIFETIMES = {
    'wind_onshore':       25,
    'photovoltaics':      30,
    'heat_pump':          19,
    'natural_gas_boiler': 21,
    'natural_gas_storage': 100,
    'natural_gas_pipeline': 60,
}

wind_cap  = {n: sum_cap_existing(wind_df,  n, REF_YEAR, LIFETIMES['wind_onshore'])       for n in NODES}
pv_cap    = {n: sum_cap_existing(pv_df,    n, REF_YEAR, LIFETIMES['photovoltaics'])       for n in NODES}
hp_cap    = {n: sum_cap_existing(hp_df,    n, REF_YEAR, LIFETIMES['heat_pump'])           for n in NODES}
ngb_cap   = {n: sum_cap_existing(ngb_df,   n, REF_YEAR, LIFETIMES['natural_gas_boiler'])  for n in NODES}
ngs_cap   = {n: sum_cap_existing(ngs_df,   n, REF_YEAR, LIFETIMES['natural_gas_storage']) for n in NODES}
ngs_ecap  = {n: float(ngs_e_df[ngs_e_df['node'] == n]['capacity_existing_energy'].sum())  for n in NODES}

# NG pipeline capacity for our 6 edges
def ngp_cap_edge(edge):
    row = ngp_df[ngp_df['edge'] == edge]
    if len(row) == 0:
        return 0.0
    return float(row['capacity_existing'].sum())

ngp_cap = {e: ngp_cap_edge(e) for e in EDGES}

# Generic baseload:
# capacity[n] = mean(elec_demand_96[n]) − mean(pv_96[n]) × pv_cap[n] − mean(wind_96[n]) × wind_cap[n]
baseload_cap = {}
for n in NODES:
    avg_d  = float(np.mean(elec_96[n]))
    avg_pv = float(np.mean(pv_96[n]))   * pv_cap[n]
    avg_w  = float(np.mean(wind_96[n])) * wind_cap[n]
    baseload_cap[n] = max(avg_d - avg_pv - avg_w, 0.0)

print("\n-- Computed capacities (GW) --")
for n in NODES:
    print(f"  {n}: elec_avg={np.mean(elec_96[n]):.2f}  "
          f"wind={wind_cap[n]:.3f}  pv={pv_cap[n]:.3f}  "
          f"hp={hp_cap[n]:.3f}  ngb={ngb_cap[n]:.3f}  "
          f"baseload={baseload_cap[n]:.3f}")
print(f"  NG pipeline: {ngp_cap}")
print(f"  NG storage (GW): {ngs_cap}")
print(f"  NG storage energy (GWh): {ngs_ecap}")

# =====================================================================
# STEP 4 – CREATE DIRECTORY STRUCTURE
# =====================================================================
DIRS = [
    "energy_system",
    "set_carriers/electricity",
    "set_carriers/heat",
    "set_carriers/natural_gas",
    "set_technologies/set_conversion_technologies/heat_pump",
    "set_technologies/set_conversion_technologies/natural_gas_boiler",
    "set_technologies/set_conversion_technologies/photovoltaics",
    "set_technologies/set_conversion_technologies/wind_onshore",
    "set_technologies/set_conversion_technologies/generic_baseload",
    "set_technologies/set_conversion_technologies/generic_heat_baseload",
    "set_technologies/set_storage_technologies/natural_gas_storage",
    "set_technologies/set_transport_technologies/natural_gas_pipeline",
]
for d in DIRS:
    os.makedirs(os.path.join(OUT_PATH, d), exist_ok=True)

def p(*parts):
    return os.path.join(OUT_PATH, *parts)

def cp(src, *dst):
    shutil.copy2(src, p(*dst))

def write_json(data, *parts):
    with open(p(*parts), 'w') as f:
        json.dump(data, f, indent=4)

def read_json(path):
    with open(path) as f:
        return json.load(f)

# =====================================================================
# STEP 5 – system.json
# =====================================================================
write_json({
    "set_conversion_technologies": [
        "generic_baseload", "generic_heat_baseload", "photovoltaics", "wind_onshore",
        "heat_pump", "natural_gas_boiler"
    ],
    "set_storage_technologies":  ["natural_gas_storage"],
    "set_transport_technologies": ["natural_gas_pipeline"],
    "set_nodes": NODES,
    "reference_year":  REF_YEAR,
    "unaggregated_time_steps_per_year": 96,
    "aggregated_time_steps_per_year":   96,
    "conduct_time_series_aggregation":  False,
    "optimized_years":         OPT_YEARS,
    "interval_between_years":  INTERVAL,
    "use_rolling_horizon":     False,
    "years_in_rolling_horizon": 1,
}, "system.json")

# =====================================================================
# STEP 6 – energy_system
# =====================================================================
for fname in ["base_units.json", "unit_definitions.txt", "attributes.json"]:
    src = f"{CB_PATH}/energy_system/{fname}"
    if os.path.exists(src):
        cp(src, "energy_system", fname)

# Node coordinates (centroid of each country, from Crystal Ball)
NODE_COORDS = {
    "CH": (8.286928794895285,  46.73678128684938),
    "DE": (10.426171427430804, 51.08304539800482),
    "AT": (13.797778364631036, 47.631858269895794),
}
pd.DataFrame({
    "node": NODES,
    "lon":  [NODE_COORDS[n][0] for n in NODES],
    "lat":  [NODE_COORDS[n][1] for n in NODES],
}).to_csv(p("energy_system", "set_nodes.csv"), index=False)

pd.DataFrame({
    "edge":      EDGES,
    "node_from": [e.split("-")[0] for e in EDGES],
    "node_to":   [e.split("-")[1] for e in EDGES],
}).to_csv(p("energy_system", "set_edges.csv"), index=False)

# =====================================================================
# STEP 7 – Carriers
# =====================================================================

# --- electricity ---
cp(f"{CB_PATH}/set_carriers/electricity/attributes.json",
   "set_carriers", "electricity", "attributes.json")
(pd.DataFrame({"time": range(96), **{n: elec_96[n] for n in NODES}})
    .to_csv(p("set_carriers", "electricity", "demand.csv"), index=False))

# --- heat ---
cp(f"{CB_PATH}/set_carriers/heat/attributes.json",
   "set_carriers", "heat", "attributes.json")
(pd.DataFrame({"time": range(96), **{n: heat_96[n] for n in NODES}})
    .to_csv(p("set_carriers", "heat", "demand.csv"), index=False))

# --- natural_gas ---
cp(f"{CB_PATH}/set_carriers/natural_gas/attributes.json",
   "set_carriers", "natural_gas", "attributes.json")
ng_avail_raw = pd.read_csv(f"{CB_PATH}/set_carriers/natural_gas/availability_import.csv")
ng_avail_d   = dict(zip(ng_avail_raw["node"], ng_avail_raw["availability_import"]))
# CH not in CB data → reasonable default (~35 TWh/year ≈ 4.2 GW average)
if "CH" not in ng_avail_d:
    ng_avail_d["CH"] = 4.2
(pd.DataFrame({"node": NODES,
               "availability_import": [ng_avail_d[n] for n in NODES]})
    .to_csv(p("set_carriers", "natural_gas", "availability_import.csv"), index=False))
cp(f"{CB_PATH}/set_carriers/natural_gas/price_import_yearly_variation.csv",
   "set_carriers", "natural_gas", "price_import_yearly_variation.csv")

# =====================================================================
# HELPER – write CAPEX / OPEX as wide matrix (year, CH, DE, AT)
# =====================================================================
def write_wide(src_csv, dest_path, years):
    """Read a single-column (year → value) CSV and write wide (year, CH, DE, AT)."""
    df  = pd.read_csv(src_csv, index_col="year")
    col = df.columns[0]
    s   = df[col]
    out = pd.DataFrame({"year": years})
    for n in NODES:
        out[n] = out["year"].map(s)
    out.to_csv(dest_path, index=False)

# =====================================================================
# STEP 8 – PHOTOVOLTAICS
# =====================================================================
cb_pv  = f"{CB_PATH}/set_technologies/set_conversion_technologies/photovoltaics"
out_pv = p("set_technologies", "set_conversion_technologies", "photovoltaics")

cp(f"{cb_pv}/attributes.json", "set_technologies", "set_conversion_technologies",
   "photovoltaics", "attributes.json")

write_wide(f"{cb_pv}/capex_specific_conversion.csv",
           f"{out_pv}/capex_specific_conversion.csv", CAPEX_YEARS)
write_wide(f"{cb_pv}/opex_specific_fixed.csv",
           f"{out_pv}/opex_specific_fixed.csv", CAPEX_YEARS)

(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [pv_cap[n] for n in NODES]})
    .to_csv(f"{out_pv}/capacity_existing.csv", index=False))

pv_lim_raw  = pd.read_csv(f"{cb_pv}/capacity_limit.csv")
pv_lim_d    = dict(zip(pv_lim_raw["node"], pv_lim_raw["capacity_limit"]))
(pd.DataFrame({"node": NODES,
               "capacity_limit": [pv_lim_d[n] for n in NODES]})
    .to_csv(f"{out_pv}/capacity_limit.csv", index=False))

(pd.DataFrame({"time": range(96), **{n: pv_96[n] for n in NODES}})
    .to_csv(f"{out_pv}/max_load.csv", index=False))

# =====================================================================
# STEP 9 – WIND ONSHORE
# =====================================================================
cb_w  = f"{CB_PATH}/set_technologies/set_conversion_technologies/wind_onshore"
out_w = p("set_technologies", "set_conversion_technologies", "wind_onshore")

cp(f"{cb_w}/attributes.json", "set_technologies", "set_conversion_technologies",
   "wind_onshore", "attributes.json")
write_wide(f"{cb_w}/capex_specific_conversion.csv",
           f"{out_w}/capex_specific_conversion.csv", CAPEX_YEARS)
write_wide(f"{cb_w}/opex_specific_fixed.csv",
           f"{out_w}/opex_specific_fixed.csv", CAPEX_YEARS)
(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [wind_cap[n] for n in NODES]})
    .to_csv(f"{out_w}/capacity_existing.csv", index=False))

wind_lim_raw = pd.read_csv(f"{cb_w}/capacity_limit.csv")
wind_lim_d   = dict(zip(wind_lim_raw["node"], wind_lim_raw["capacity_limit"]))
(pd.DataFrame({"node": NODES,
               "capacity_limit": [wind_lim_d[n] for n in NODES]})
    .to_csv(f"{out_w}/capacity_limit.csv", index=False))
(pd.DataFrame({"time": range(96), **{n: wind_96[n] for n in NODES}})
    .to_csv(f"{out_w}/max_load.csv", index=False))

# =====================================================================
# STEP 10 – HEAT PUMP
# =====================================================================
cb_hp  = f"{CB_PATH}/set_technologies/set_conversion_technologies/heat_pump"
out_hp = p("set_technologies", "set_conversion_technologies", "heat_pump")

cp(f"{cb_hp}/attributes.json", "set_technologies", "set_conversion_technologies",
   "heat_pump", "attributes.json")
write_wide(f"{cb_hp}/capex_specific_conversion.csv",
           f"{out_hp}/capex_specific_conversion.csv", CAPEX_YEARS)
write_wide(f"{cb_hp}/opex_specific_fixed.csv",
           f"{out_hp}/opex_specific_fixed.csv", CAPEX_YEARS)
(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [hp_cap[n] for n in NODES]})
    .to_csv(f"{out_hp}/capacity_existing.csv", index=False))

# =====================================================================
# STEP 11 – NATURAL GAS BOILER
# =====================================================================
cb_ngb  = f"{CB_PATH}/set_technologies/set_conversion_technologies/natural_gas_boiler"
out_ngb = p("set_technologies", "set_conversion_technologies", "natural_gas_boiler")

cp(f"{cb_ngb}/attributes.json", "set_technologies", "set_conversion_technologies",
   "natural_gas_boiler", "attributes.json")
write_wide(f"{cb_ngb}/capex_specific_conversion.csv",
           f"{out_ngb}/capex_specific_conversion.csv", CAPEX_YEARS)
write_wide(f"{cb_ngb}/opex_specific_fixed.csv",
           f"{out_ngb}/opex_specific_fixed.csv", CAPEX_YEARS)
(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [ngb_cap[n] for n in NODES]})
    .to_csv(f"{out_ngb}/capacity_existing.csv", index=False))

# =====================================================================
# STEP 12 – GENERIC BASELOAD
# =====================================================================
out_gb = p("set_technologies", "set_conversion_technologies", "generic_baseload")

gb_attrs = {
    "capacity_addition_min":        {"default_value": 0,     "unit": "GW"},
    "capacity_addition_max":        {"default_value": 0,     "unit": "GW"},   # no new invest
    "capacity_addition_unbounded":  {"default_value": 0,     "unit": "GW"},
    "capacity_existing":            {"default_value": 0,     "unit": "GW"},
    "capacity_limit":               {"default_value": 0,     "unit": "GW"},
    "min_load":                     {"default_value": 0,     "unit": "1"},
    "max_load":                     {"default_value": 1,     "unit": "1"},
    "lifetime":                     {"default_value": 40,    "unit": "1"},
    "opex_specific_variable":       {"default_value": 0.0,   "unit": "Euro/MWh"},
    "carbon_intensity_technology":  {"default_value": 0,     "unit": "kilotons/GWh"},
    "construction_time":            {"default_value": 0,     "unit": "1"},
    "capacity_investment_existing": {"default_value": 0,     "unit": "GW"},
    "opex_specific_fixed":          {"default_value": 0,     "unit": "Euro/kW"},
    "max_diffusion_rate":           {"default_value": 0,     "unit": "1"},
    "capex_specific_conversion":    {"default_value": 0,     "unit": "Euro/kW"},
    "reference_carrier":            {"default_value": ["electricity"]},
    "input_carrier":                {"default_value": []},
    "output_carrier":               {"default_value": ["electricity"]},
    "conversion_factor":            {"": {"default_value": 1.0, "unit": "GWh/GWh"}},
}
write_json(gb_attrs, "set_technologies", "set_conversion_technologies",
           "generic_baseload", "attributes.json")

(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [baseload_cap[n] for n in NODES]})
    .to_csv(f"{out_gb}/capacity_existing.csv", index=False))

# =====================================================================
# STEP 12b – GENERIC HEAT BASELOAD
# Covers the residual heat demand that HP + NGB cannot satisfy at peak.
# Sized to peak_heat_demand_96[n] - hp_cap[n] - ngb_cap[n], clamped to ≥ 0.
# No new investment allowed (capacity_addition_max = 0).
# =====================================================================
out_ghb = p("set_technologies", "set_conversion_technologies", "generic_heat_baseload")

heat_baseload_cap = {}
for n in NODES:
    peak_heat = float(np.max(heat_96[n]))           # peak over 96 representative hours
    heat_baseload_cap[n] = max(peak_heat - hp_cap[n] - ngb_cap[n], 0.0)

ghb_attrs = {
    "capacity_addition_min":        {"default_value": 0,     "unit": "GW"},
    "capacity_addition_max":        {"default_value": 0,     "unit": "GW"},   # no new invest
    "capacity_addition_unbounded":  {"default_value": 0,     "unit": "GW"},
    "capacity_existing":            {"default_value": 0,     "unit": "GW"},
    "capacity_limit":               {"default_value": 0,     "unit": "GW"},
    "min_load":                     {"default_value": 0,     "unit": "1"},
    "max_load":                     {"default_value": 1,     "unit": "1"},
    "lifetime":                     {"default_value": 40,    "unit": "1"},
    "opex_specific_variable":       {"default_value": 0.0,   "unit": "Euro/MWh"},
    "carbon_intensity_technology":  {"default_value": 0,     "unit": "kilotons/GWh"},
    "construction_time":            {"default_value": 0,     "unit": "1"},
    "capacity_investment_existing": {"default_value": 0,     "unit": "GW"},
    "opex_specific_fixed":          {"default_value": 0,     "unit": "Euro/kW"},
    "max_diffusion_rate":           {"default_value": 0,     "unit": "1"},
    "capex_specific_conversion":    {"default_value": 0,     "unit": "Euro/kW"},
    "reference_carrier":            {"default_value": ["heat"]},
    "input_carrier":                {"default_value": []},
    "output_carrier":               {"default_value": ["heat"]},
    "conversion_factor":            {"": {"default_value": 1.0, "unit": "GWh/GWh"}},
}
write_json(ghb_attrs, "set_technologies", "set_conversion_technologies",
           "generic_heat_baseload", "attributes.json")

(pd.DataFrame({"node": NODES, "year_construction": [2022]*3,
               "capacity_existing": [heat_baseload_cap[n] for n in NODES]})
    .to_csv(f"{out_ghb}/capacity_existing.csv", index=False))

print(f"\n-- Generic heat baseload (GW) --")
for n in NODES:
    print(f"  {n}: peak_heat={np.max(heat_96[n]):.3f}  "
          f"hp={hp_cap[n]:.3f}  ngb={ngb_cap[n]:.3f}  "
          f"heat_baseload={heat_baseload_cap[n]:.3f}")

# =====================================================================
# STEP 13 – NATURAL GAS STORAGE
# =====================================================================
cb_ngs  = f"{CB_PATH}/set_technologies/set_storage_technologies/natural_gas_storage"
out_ngs = p("set_technologies", "set_storage_technologies", "natural_gas_storage")

ngs_attrs = read_json(f"{cb_ngs}/attributes.json")
# Allow new investment
ngs_attrs["capacity_addition_max"]["default_value"]        = "inf"
ngs_attrs["capacity_addition_max_energy"]["default_value"] = "inf"
write_json(ngs_attrs, "set_technologies", "set_storage_technologies",
           "natural_gas_storage", "attributes.json")

(pd.DataFrame({"node": NODES, "year_construction": [1999]*3,
               "capacity_existing": [ngs_cap[n] for n in NODES]})
    .to_csv(f"{out_ngs}/capacity_existing.csv", index=False))
(pd.DataFrame({"node": NODES, "year_construction": [1999]*3,
               "capacity_existing_energy": [ngs_ecap[n] for n in NODES]})
    .to_csv(f"{out_ngs}/capacity_existing_energy.csv", index=False))

for fname in ["capex_specific_storage.csv", "capex_specific_storage_energy.csv"]:
    src = f"{cb_ngs}/{fname}"
    if os.path.exists(src):
        cp(src, "set_technologies", "set_storage_technologies",
           "natural_gas_storage", fname)

# =====================================================================
# STEP 14 – NATURAL GAS PIPELINE
# =====================================================================
cb_ngp  = f"{CB_PATH}/set_technologies/set_transport_technologies/natural_gas_pipeline"
out_ngp = p("set_technologies", "set_transport_technologies", "natural_gas_pipeline")

cp(f"{cb_ngp}/attributes.json", "set_technologies", "set_transport_technologies",
   "natural_gas_pipeline", "attributes.json")

# Approximate pipeline distances (km)
EDGE_DIST = {
    "CH-AT": 450, "AT-CH": 450,
    "CH-DE": 270, "DE-CH": 270,
    "DE-AT": 650, "AT-DE": 650,
}
(pd.DataFrame({
    "edge":             EDGES,
    "year_construction":[1999] * len(EDGES),
    "capacity_existing":[ngp_cap[e] for e in EDGES],
    "distance":         [EDGE_DIST[e] for e in EDGES],
}).to_csv(f"{out_ngp}/capacity_existing.csv", index=False))

# =====================================================================
# DONE
# =====================================================================
print("\n" + "="*60)
print(f"Model written to: {OUT_PATH}")
print("="*60)
print("\nCapacity existing summary (GW):")
print(f"{'Node':<6} {'elec_avg':>9} {'wind':>8} {'PV':>8} "
      f"{'HP':>8} {'NGB':>8} {'Baseload':>10} {'HeatBL':>8} {'NGS':>8}")
print("-"*80)
for n in NODES:
    print(f"{n:<6} {np.mean(elec_96[n]):>9.2f} {wind_cap[n]:>8.3f} {pv_cap[n]:>8.3f} "
          f"{hp_cap[n]:>8.3f} {ngb_cap[n]:>8.3f} {baseload_cap[n]:>10.3f} "
          f"{heat_baseload_cap[n]:>8.3f} {ngs_cap[n]:>8.3f}")
print()
print("96-step CFs (mean):")
for n in NODES:
    print(f"  {n}: wind={np.mean(wind_96[n]):.3f}  PV={np.mean(pv_96[n]):.3f}")
print()
print("NG pipeline existing (GW):")
for e in EDGES:
    print(f"  {e}: {ngp_cap[e]:.3f} GW")
