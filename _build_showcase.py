"""Generator for the showcase dataset 6_showcase_countries (5 EU nodes, 3 years).
Full 8760-h real profiles (CB weather + toy demand) -> internal time-series
aggregation (typical days) at run time. See docs/showcase_model.md."""
import json, os, shutil
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(BASE, "6_showcase_countries")
TPL = os.path.join(BASE, "5_multiple_extended_countries")          # base_units, demand profiles
CB = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball",
                  "set_technologies", "set_conversion_technologies")  # real weather profiles
NODES = ["AT", "CH", "DE", "FR", "IT"]
COORDS = {"AT": (14.5501, 47.5162), "CH": (8.2275, 46.8182), "DE": (10.4541, 51.1657),
          "FR": (2.2137, 46.6033), "IT": (12.4964, 41.9028)}
YEARS = [2025, 2026, 2027]; REFY = 2025

def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True); json.dump(obj, open(path, "w"), indent=2)
def wcsv(path, df):
    os.makedirs(os.path.dirname(path), exist_ok=True); df.to_csv(path, index=False)
def scalar(name, val, unit="1"):
    return {"default_value": val, "unit": unit}

# ---------- real 8760-h profiles ----------
def load_prof(tech):  # CB max_load (capacity factor), 8760 x 5 nodes
    d = pd.read_csv(os.path.join(CB, tech, "max_load.csv"))
    return d[["time"] + NODES].copy()
PROF = {"pv": load_prof("photovoltaics"), "wind": load_prof("wind_onshore"),
        "hydro": load_prof("run-of-river_hydro")}
PROF["pv_half"] = PROF["pv"].copy()                  # clone with exactly half the capacity factor
for _n in NODES:
    PROF["pv_half"][_n] = PROF["pv"][_n] * 0.5
# demand shapes from the (real) extended-toy profiles, normalised to my target peaks
def demand_scaled(carrier, peak):
    raw = pd.read_csv(os.path.join(TPL, "set_carriers", carrier, "demand.csv"))[["time"] + NODES]
    out = {"time": raw["time"]}
    for n in NODES:
        out[n] = peak[n] * raw[n] / raw[n].max()   # keep realistic shape, hit chosen peak
    return pd.DataFrame(out)
ELEC_PEAK = {"AT": 11, "CH": 10, "DE": 75, "FR": 80, "IT": 50}
HEAT_PEAK = {"AT": 14, "CH": 12, "DE": 60, "FR": 45, "IT": 40}
GAS_PRICE = {"AT": 32, "CH": 32, "DE": 30, "FR": 32, "IT": 34}   # ~CB 32 EUR/MWh, slight local spread

# ---------- start clean ----------
if os.path.isdir(DST):
    shutil.rmtree(DST)
os.makedirs(DST)

# ---------- system.json (full year + internal TSA -> typical days) ----------
system = {
    "set_conversion_technologies": ["nuclear", "natural_gas_turbine", "photovoltaics",
                                    "photovoltaics_capex", "photovoltaics_opex",
                                    "photovoltaics_lowcf", "wind_onshore",
                                    "run-of-river_hydro", "natural_gas_boiler", "heat_pump"],
    "set_storage_technologies": ["battery"],
    "set_transport_technologies": ["power_line", "natural_gas_pipeline"],
    "set_nodes": NODES,
    "reference_year": REFY,
    "unaggregated_time_steps_per_year": 8760,        # full chronological year
    "aggregated_time_steps_per_year": 24,            # -> 24 typical hours (hoursPerPeriod=1; enough for storage)
    "conduct_time_series_aggregation": True,
    "optimized_years": 3,
    "interval_between_years": 1,
    "use_rolling_horizon": False,
    "years_in_rolling_horizon": 1,
}
wjson(os.path.join(DST, "system.json"), system)

# ---------- energy_system ----------
es = os.path.join(DST, "energy_system"); os.makedirs(es)
shutil.copy(os.path.join(TPL, "energy_system", "base_units.json"), os.path.join(es, "base_units.json"))
shutil.copy(os.path.join(TPL, "energy_system", "unit_definitions.txt"), os.path.join(es, "unit_definitions.txt"))
wcsv(os.path.join(es, "set_nodes.csv"),
     pd.DataFrame([{"node": n, "lon": COORDS[n][0], "lat": COORDS[n][1]} for n in NODES]))
ADJ = [("AT", "CH"), ("AT", "DE"), ("AT", "IT"), ("CH", "DE"),
       ("CH", "FR"), ("CH", "IT"), ("DE", "FR"), ("FR", "IT")]
erows = []
for a, b in ADJ:
    erows += [{"edge": f"{a}-{b}", "node_from": a, "node_to": b},
              {"edge": f"{b}-{a}", "node_from": b, "node_to": a}]
wcsv(os.path.join(es, "set_edges.csv"), pd.DataFrame(erows))
es_attr = json.load(open(os.path.join(TPL, "energy_system", "attributes.json")))
es_attr["price_carbon_emissions"] = {"default_value": 80.0, "unit": "Euro/tons"}
es_attr["carbon_emissions_budget"] = {"default_value": "inf", "unit": "gigatons"}
wjson(os.path.join(es, "attributes.json"), es_attr)

# ---------- carriers ----------
def carrier_attr(demand_def, price_import, carbon=0.0, shed=5000.0, avail_import=0.0):
    return {
        "carbon_intensity_carrier_import": scalar("", carbon, "kilotons/GWh"),
        "carbon_intensity_carrier_export": scalar("", carbon, "kilotons/GWh"),
        "demand": scalar("", demand_def, "GW"),
        "price_shed_demand": scalar("", shed, "Euro/MWh"),
        "availability_import": scalar("", avail_import, "GW"),
        "availability_export": scalar("", 0.0, "GW"),
        "availability_import_yearly": scalar("", "inf", "GWh"),
        "availability_export_yearly": scalar("", "inf", "GWh"),
        "price_export": scalar("", 0.0, "kiloEuro/GWh"),
        "price_import": scalar("", price_import, "kiloEuro/GWh"),
    }
def yearly_var():
    return pd.DataFrame({"year": YEARS, **{n: [1.0, 1.1, 1.21] for n in NODES}})

c = os.path.join(DST, "set_carriers", "electricity")
wjson(os.path.join(c, "attributes.json"), carrier_attr(50.0, 0.0))
wcsv(os.path.join(c, "demand.csv"), demand_scaled("electricity", ELEC_PEAK))
wcsv(os.path.join(c, "demand_yearly_variation.csv"), yearly_var())
c = os.path.join(DST, "set_carriers", "heat")
wjson(os.path.join(c, "attributes.json"), carrier_attr(0.0, 0.0))
wcsv(os.path.join(c, "demand.csv"), demand_scaled("heat", HEAT_PEAK))
wcsv(os.path.join(c, "demand_yearly_variation.csv"), yearly_var())
c = os.path.join(DST, "set_carriers", "natural_gas")
wjson(os.path.join(c, "attributes.json"), carrier_attr(0.0, 32.0, carbon=0.202, shed="inf", avail_import="inf"))
wcsv(os.path.join(c, "price_import.csv"),
     pd.DataFrame([{"node": n, "price_import": GAS_PRICE[n]} for n in NODES]))
c = os.path.join(DST, "set_carriers", "uranium")
wjson(os.path.join(c, "attributes.json"), carrier_attr(0.0, 1.7, carbon=0.0, shed="inf", avail_import="inf"))

# ---------- conversion technologies ----------
def conv_factor(inp, val):
    return {inp[0]: {"default_value": val, "unit": "GWh/GWh"}} if inp else \
           {"": {"default_value": 1.0, "unit": "GWh/GWh"}}

# Cost magnitudes rounded from the Crystal_Ball dataset (toy -> rounding is fine).
TECHS = {
 "nuclear": dict(ref="electricity", inp=["uranium"], cf=2.95, capex=6300, ofix=125, ovar=5.5,
   maxload=0.92, life=55, decline=0.0, profile=None,
   limit={"AT": 0, "CH": 4, "DE": 10, "FR": 70, "IT": 0},
   prebuilt={"AT": 0, "CH": 2, "DE": 4, "FR": 45, "IT": 0}),
 "natural_gas_turbine": dict(ref="electricity", inp=["natural_gas"], cf=1.88, capex=780, ofix=22, ovar=2.9,
   maxload=0.93, life=30, decline=0.0, profile=None,                       # firm/dispatchable peaker
   limit={n: "inf" for n in NODES},
   prebuilt={"AT": 2, "CH": 1, "DE": 12, "FR": 6, "IT": 10}),
 "photovoltaics": dict(ref="electricity", inp=[], cf=1.0, capex=490, ofix=12, ovar=0.0,
   maxload=None, life=30, decline=0.01, profile="pv",
   limit={"AT": 60, "CH": 40, "DE": 250, "FR": 300, "IT": 250},
   prebuilt={"AT": 3, "CH": 4, "DE": 30, "FR": 15, "IT": 25}),
 # Three PV clones, each differing from PV in EXACTLY ONE factor (capex / opex_fix / CF),
 # all capped at 1 GW/country -> their RC isolates that single factor's effect.
 "photovoltaics_capex": dict(ref="electricity", inp=[], cf=1.0, capex=500, ofix=12, ovar=0.0,   # +10 EUR capex
   maxload=None, life=30, decline=0.01, profile="pv",
   limit={n: 1 for n in NODES}, prebuilt={n: 0 for n in NODES}),
 "photovoltaics_opex": dict(ref="electricity", inp=[], cf=1.0, capex=490, ofix=24, ovar=0.0,     # 2x opex_fix
   maxload=None, life=30, decline=0.01, profile="pv",
   limit={n: 1 for n in NODES}, prebuilt={n: 0 for n in NODES}),
 "photovoltaics_lowcf": dict(ref="electricity", inp=[], cf=1.0, capex=490, ofix=12, ovar=0.0,   # half max_load
   maxload=None, life=30, decline=0.01, profile="pv_half",
   limit={n: 1 for n in NODES}, prebuilt={n: 0 for n in NODES}),
 "wind_onshore": dict(ref="electricity", inp=[], cf=1.0, capex=1100, ofix=20, ovar=0.7,
   maxload=None, life=25, decline=0.01, profile="wind",
   limit={"AT": 15, "CH": 45, "DE": 120, "FR": 90, "IT": 70},
   prebuilt={"AT": 1, "CH": 2, "DE": 25, "FR": 12, "IT": 6}),
 "run-of-river_hydro": dict(ref="electricity", inp=[], cf=1.0, capex=2900, ofix=37, ovar=2.0,
   maxload=None, life=50, decline=0.0, profile="hydro",
   limit={"AT": 6, "CH": 5, "DE": 3, "FR": 6, "IT": 6},
   prebuilt={"AT": 5, "CH": 4, "DE": 2, "FR": 5, "IT": 5}),
 "natural_gas_boiler": dict(ref="heat", inp=["natural_gas"], cf=1.1, capex=490, ofix=17, ovar=0.0,
   maxload=1.0, life=21, decline=0.0, profile=None,
   limit={n: "inf" for n in NODES},
   prebuilt={"AT": 10, "CH": 8, "DE": 45, "FR": 30, "IT": 32}),
 "heat_pump": dict(ref="heat", inp=["electricity"], cf=0.33, capex=900, ofix=20, ovar=0.0,
   maxload=1.0, life=19, decline=0.0, profile=None,                  # limit >= peak heat demand (incl. growth)
   limit={"AT": 20, "CH": 16, "DE": 80, "FR": 60, "IT": 55}, prebuilt={n: 0 for n in NODES}),
}

for t, g in TECHS.items():
    d = os.path.join(DST, "set_technologies", "set_conversion_technologies", t)
    ml = g["maxload"] if g["maxload"] is not None else 1.0
    a = {
        "capacity_addition_min": scalar("", 0.0, "GW"),
        "capacity_addition_max": scalar("", "inf", "GW"),
        "capacity_addition_unbounded": scalar("", 0.0, "GW"),
        "capacity_existing": scalar("", 0.0, "GW"),
        "capacity_limit": scalar("", "inf", "GW"),
        "min_load": scalar("", 0.0, "1"),
        "max_load": scalar("", ml, "1"),
        "lifetime": scalar("", g["life"], "1"),
        "opex_specific_variable": scalar("", g["ovar"], "Euro/MWh"),
        "opex_specific_fixed": scalar("", g["ofix"], "Euro/kW"),
        "reference_carrier": {"default_value": [g["ref"]]},
        "input_carrier": {"default_value": g["inp"]},
        "output_carrier": {"default_value": [g["ref"]]},
        "conversion_factor": conv_factor(g["inp"], g["cf"]),
        "carbon_intensity_technology": scalar("", 0.0, "kilotons/GWh"),
        "construction_time": scalar("", 0.0, "1"),
        "capacity_investment_existing": scalar("", 0.0, "GW"),
        "max_diffusion_rate": scalar("", "inf", "1"),
        "capex_specific_conversion": scalar("", g["capex"], "Euro/kW"),
    }
    wjson(os.path.join(d, "attributes.json"), a)
    if not all(v == "inf" for v in g["limit"].values()):
        wcsv(os.path.join(d, "capacity_limit.csv"),
             pd.DataFrame([{"node": n, "capacity_limit": g["limit"][n]} for n in NODES]))
    if any(v > 0 for v in g["prebuilt"].values()):
        wcsv(os.path.join(d, "capacity_existing.csv"),
             pd.DataFrame([{"node": n, "year_construction": 2020, "capacity_existing": g["prebuilt"][n]}
                           for n in NODES if g["prebuilt"][n] > 0]))
    if g["profile"] is not None:
        wcsv(os.path.join(d, "max_load.csv"), PROF[g["profile"]])
    if g["decline"] > 0:
        rows = [{"node": n, "year": y,
                 "capex_specific_conversion": round(g["capex"] * (1 - g["decline"]) ** i, 4)}
                for n in NODES for i, y in enumerate(YEARS)]
        wcsv(os.path.join(d, "capex_specific_conversion.csv"), pd.DataFrame(rows))

# ---------- storage: battery (power + energy separate) ----------
d = os.path.join(DST, "set_technologies", "set_storage_technologies", "battery")
bat = {
    "capacity_addition_min": scalar("", 0.0, "GW"), "capacity_addition_max": scalar("", "inf", "GW"),
    "capacity_addition_unbounded": scalar("", 0.0, "GW"), "capacity_existing": scalar("", 0.0, "GW"),
    "capacity_limit": scalar("", "inf", "GW"), "min_load": scalar("", 0.0, "1"),
    "max_load": scalar("", 1.0, "1"), "lifetime": scalar("", 13.0, "1"),
    "opex_specific_variable": scalar("", 0.0, "Euro/MWh"),
    "carbon_intensity_technology": scalar("", 0.0, "kilotons/GWh"),
    "construction_time": scalar("", 0.0, "1"), "capacity_investment_existing": scalar("", 0.0, "GW"),
    "opex_specific_fixed": scalar("", 2.5, "Euro/kW"), "max_diffusion_rate": scalar("", "inf", "1"),
    "efficiency_charge": scalar("", 0.93, "1"), "efficiency_discharge": scalar("", 0.93, "1"),
    "self_discharge": scalar("", 1e-3, "1"),
    "capex_specific_storage": scalar("", 280.0, "Euro/kW"),
    "capex_specific_storage_energy": scalar("", 290.0, "Euro/kWh"),
    "capacity_addition_min_energy": scalar("", 0.0, "GWh"), "capacity_addition_max_energy": scalar("", "inf", "GWh"),
    "capacity_existing_energy": scalar("", 0.0, "GWh"), "capacity_limit_energy": scalar("", "inf", "GWh"),
    "min_load_energy": scalar("", 0.0, "1"), "max_load_energy": scalar("", 1.0, "1"),
    "capacity_investment_existing_energy": scalar("", 0.0, "GWh"),
    "opex_specific_fixed_energy": scalar("", 0.0, "Euro/MWh"),
    "energy_to_power_ratio_min": scalar("", 1.0, "h"), "energy_to_power_ratio_max": scalar("", 12.0, "h"),
    "flow_storage_inflow": scalar("", 0.0, "GW"), "initial_storage_level": scalar("", "inf", "1"),
    "reference_carrier": {"default_value": ["electricity"]},
}
wjson(os.path.join(d, "attributes.json"), bat)

# ---------- transport: power_line + natural_gas_pipeline ----------
DIST = {("AT", "CH"): 680, ("AT", "DE"): 525, ("AT", "IT"): 765, ("CH", "DE"): 750,
        ("CH", "FR"): 435, ("CH", "IT"): 690, ("DE", "FR"): 875, ("FR", "IT"): 1100}
def dkey(a, b):
    return DIST[(a, b)] if (a, b) in DIST else DIST[(b, a)]
def transport(name, ref, capex_per_km, loss, life, allowed, prebuilt):
    d = os.path.join(DST, "set_technologies", "set_transport_technologies", name)
    a = {
        "capacity_addition_min": scalar("", 0.0, "GW"), "capacity_addition_max": scalar("", "inf", "GW"),
        "capacity_addition_unbounded": scalar("", 0.0, "GW"), "capacity_existing": scalar("", 0.0, "GW"),
        "capacity_limit": scalar("", 0.0, "GW"), "min_load": scalar("", 0.0, "1"),
        "max_load": scalar("", 1.0, "1"), "lifetime": scalar("", life, "1"),
        "opex_specific_variable": scalar("", 0.0, "kiloEuro/GWh"),
        "reference_carrier": {"default_value": [ref]},
        "carbon_intensity_technology": scalar("", 0.0, "kilotons/GWh/km"),
        "construction_time": scalar("", 0.0, "1"), "capacity_investment_existing": scalar("", 0.0, "GW"),
        "opex_specific_fixed": scalar("", 4000.0, "Euro/MW"), "max_diffusion_rate": scalar("", "inf", "1"),
        "transport_loss_factor_linear": scalar("", loss, "1/km"),
        "capex_per_distance_transport": scalar("", capex_per_km, "Euro/km/MW"),
        "distance": scalar("", "inf", "km"),
    }
    wjson(os.path.join(d, "attributes.json"), a)
    drows, lrows, erows = [], [], []
    for a2, b2 in allowed:
        for x, y in [(a2, b2), (b2, a2)]:
            e = f"{x}-{y}"
            drows.append({"edge": e, "distance": dkey(a2, b2)})
            lrows.append({"edge": e, "capacity_limit": "inf"})
            erows.append({"edge": e, "year_construction": 2020, "capacity_existing": prebuilt[(a2, b2)]})
    wcsv(os.path.join(d, "distance.csv"), pd.DataFrame(drows))
    wcsv(os.path.join(d, "capacity_limit.csv"), pd.DataFrame(lrows))
    wcsv(os.path.join(d, "capacity_existing.csv"), pd.DataFrame(erows))

transport("power_line", "electricity", 546.0, 5e-5, 60,
          allowed=[("DE", "FR"), ("AT", "DE"), ("AT", "CH"), ("CH", "IT"), ("FR", "IT")],
          prebuilt={("DE", "FR"): 4, ("AT", "DE"): 3, ("AT", "CH"): 2, ("CH", "IT"): 2, ("FR", "IT"): 3})
transport("natural_gas_pipeline", "natural_gas", 265.0, 5e-5, 60,
          allowed=[("AT", "DE"), ("CH", "DE"), ("AT", "IT"), ("FR", "IT")],
          prebuilt={("AT", "DE"): 8, ("CH", "DE"): 5, ("AT", "IT"): 6, ("FR", "IT"): 5})

print("Dataset written to", DST)
for nm, p in PROF.items():
    print(f"  {nm:5s} real CF (8760 mean): " + ", ".join(f"{n}={p[n].mean():.3f}" for n in NODES))
