"""Decisive probe: does heat_pump IT y1 / battery ES y1 EVER build as capex -> ~0?
If not even at capex~0 -> operating-cost-dominated phantom (no finite capex triggers build).
"""
import json, os
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "5_multiple_extended_countries")
DATA_NAME = os.path.basename(DATASET)
ROOT = os.path.join(BASE, "outputs_probe_phantom")
os.makedirs(ROOT, exist_ok=True)
TIGHT_E2P = {"battery": 16, "pumped_hydro": 22}

def cfg():
    c = json.load(open("./config.json")); c.pop("plugins", None)
    c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
    c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
    so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
    so["rc_tight_e2p"]=dict(TIGHT_E2P)
    return c

def run_model(name):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(), open(tmp,"w"), indent=2)
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    return os.path.join(out, DATA_NAME)

def val(sc, tech, node, yidx, ctype="power"):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies==tech)&(d.set_capacity_types==ctype)&(d.set_location==node)&(d.set_time_steps_yearly==yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET)
print("=== PROBE: capex -> ~free ===", flush=True)

# heat_pump IT y1 (year 2024): set capex to 1 (essentially free)
c0 = read_capex(DATASET, "heat_pump", "IT", 2024)
print(f"heat_pump IT 2024 baseline capex = {c0}", flush=True)
with capex_file_override(DATASET, [{"tech":"heat_pump","node":"IT","year":2024,"value":1.0}]):
    sc = run_model("hp_IT_y1_free")
v = val(sc, "heat_pump", "IT", 1)
print(f">>> heat_pump IT y1 @ capex=1: build value = {v}", flush=True)

# battery ES y1: set both power+energy capex to 1
cp = read_capex(DATASET, "battery", "ES", 2024, "power")
ce = read_capex(DATASET, "battery", "ES", 2024, "energy")
print(f"battery ES 2024 baseline capex power={cp} energy={ce}", flush=True)
with capex_file_override(DATASET, [{"tech":"battery","node":"ES","year":2024,"capacity_type":"power","value":1.0},
                                   {"tech":"battery","node":"ES","year":2024,"capacity_type":"energy","value":1.0}]):
    sc = run_model("bat_ES_y1_free")
v = val(sc, "battery", "ES", 1, "power")
print(f">>> battery ES y1 @ capex=1: build value = {v}", flush=True)
