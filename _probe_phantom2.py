import json, os
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"5_multiple_extended_countries"); DATA_NAME=os.path.basename(DATASET)
ROOT=os.path.join(BASE,"outputs_probe_phantom"); os.makedirs(ROOT,exist_ok=True)
def cfg():
    c=json.load(open("./config.json")); c.pop("plugins",None)
    c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
    c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
    so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
    so["rc_tight_e2p"]={"battery":16,"pumped_hydro":22}
    return c
def run_model(name):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA_NAME)
def val(sc,tech,node,yidx,ctype="power"):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies==tech)&(d.set_capacity_types==ctype)&(d.set_location==node)&(d.set_time_steps_yearly==yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan
restore_leftover_swaps(DATASET)
# heat_pump IT y2 free
with capex_file_override(DATASET,[{"tech":"heat_pump","node":"IT","year":2025,"value":1.0}]):
    sc=run_model("hp_IT_y2_free")
print(f">>> heat_pump IT y2 @ capex=1: {val(sc,'heat_pump','IT',2)}",flush=True)
# heat_pump IT y1 exactly at reported-RC threshold capex=571 (=3600-3029)
for cx in (571.0, 150.0):
    with capex_file_override(DATASET,[{"tech":"heat_pump","node":"IT","year":2024,"value":cx}]):
        sc=run_model(f"hp_IT_y1_cx{int(cx)}")
    print(f">>> heat_pump IT y1 @ capex={cx}: {val(sc,'heat_pump','IT',1)}",flush=True)
