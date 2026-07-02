"""Storage validation with e2p FIXED at 4 in the build/nobuild runs (matches the RC's assumption)."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"6_showcase_countries"); DATA=os.path.basename(DATASET)
ROOT=os.path.join(BASE,f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_battery2"); os.makedirs(ROOT,exist_ok=True)
MARGIN=0.01; REFY=2025; VTOL=1e-4; F=0.788   # perturbed bundle ratio (IT y0)
def cfg():  # build/nobuild WITH e2p fixed at 4 (no other perturbation)
    return {"analysis":{"time_series_aggregation":{"hoursPerPeriod":1,"clusterMethod":"hierarchical"}},
            "solver":{"name":"gurobi","save_duals":False,"save_reduced_costs":False,"use_scaling":0,
            "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"rc_tight_e2p":{"battery":4}}}}
def run_model(name):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA)
def valc(sc,ct="power"):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies=="battery")&(d.set_capacity_types==ct)&(d.set_location=="IT")&(d.set_time_steps_yearly==0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan
restore_leftover_swaps(DATASET)
cp=read_capex(DATASET,"battery","IT",REFY,"power"); ce=read_capex(DATASET,"battery","IT",REFY,"energy")
def ov(s): return [{"tech":"battery","node":"IT","year":REFY,"capacity_type":"power","value":cp*s},
                   {"tech":"battery","node":"IT","year":REFY,"capacity_type":"energy","value":ce*s}]
with capex_file_override(DATASET,ov(1-(1+MARGIN)*F)): vb=valc(run_model("b"))
with capex_file_override(DATASET,ov(1-(1-MARGIN)*F)): vn=valc(run_model("n"))
ok=(vb>VTOL) and not (vn>VTOL)
print(f"RESULT battery IT (e2p fixed 4): ratio={F} build={vb:.4f} nobuild={vn:.4f} -> {'PASS' if ok else 'FAIL'}",flush=True)
