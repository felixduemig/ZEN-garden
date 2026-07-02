"""Re-validate battery IT with the PERTURBED bundle RC (storage RC needs the perturbation)."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"6_showcase_countries"); DATA=os.path.basename(DATASET)
OUT=os.path.join(BASE,"outputs_showcase_pert"); os.makedirs(OUT,exist_ok=True)
ROOT=os.path.join(BASE,f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_battery"); os.makedirs(ROOT,exist_ok=True)
MARGIN=0.01; REFY=2025; VTOL=1e-4
def cfg(pert):
    c={"analysis":{"time_series_aggregation":{"hoursPerPeriod":1,"clusterMethod":"hierarchical"}},
       "solver":{"name":"gurobi","save_duals":pert,"save_reduced_costs":pert,"use_scaling":0,
       "solver_options":{"Method":2,"Crossover":1,"Presolve":0}}}
    if pert: c["solver"]["solver_options"].update({"rc_perturbation":0,"rc_lifetime_rhs_perturbation":1e-3,
        "rc_storage_power_perturbation":1e-4,"rc_tight_e2p":{"battery":4}})
    return c
def run_model(name,pert):
    out=os.path.join(ROOT if not pert else OUT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(pert),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA)
def valc(sc,ct="power"):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies=="battery")&(d.set_capacity_types==ct)&(d.set_location=="IT")&(d.set_time_steps_yearly==0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan
restore_leftover_swaps(DATASET)
# 1) pert run to get the correct bundle RC
sc=run_model("pert_base",True)
st=pd.read_csv(sc+"/capacity_addition_analysis_storage.csv")
r=st[(st.set_technologies=="battery")&(st.set_location=="IT")&(st.set_time_steps_yearly==0)]
rc=float(r.rc_mathematical.iloc[0]); f=float(r.ratio_reduction_proportional.iloc[0])
print(f"PERT battery IT bundle RC={rc:.1f} ratio={f:.3f}",flush=True)
# 2) +-1% build/nobuild (un-perturbed true build decision)
cp=read_capex(DATASET,"battery","IT",REFY,"power"); ce=read_capex(DATASET,"battery","IT",REFY,"energy")
def ov(s): return [{"tech":"battery","node":"IT","year":REFY,"capacity_type":"power","value":cp*s},
                   {"tech":"battery","node":"IT","year":REFY,"capacity_type":"energy","value":ce*s}]
with capex_file_override(DATASET,ov(1-(1+MARGIN)*f)): vb=valc(run_model("b",False))
with capex_file_override(DATASET,ov(1-(1-MARGIN)*f)): vn=valc(run_model("n",False))
ok=(vb>VTOL) and not (vn>VTOL)
print(f"RESULT battery IT: rc={rc:.1f} ratio={f:.3f} build={vb:.4f} nobuild={vn:.4f} -> {'PASS' if ok else 'FAIL'}",flush=True)
