"""e2p-consistent storage validation across multiple nodes (n>1).
1 perturbed base run -> read each node's bundle RC; then +-1% build/nobuild WITH e2p fixed at 4."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"6_showcase_countries"); DATA=os.path.basename(DATASET)
ROOT=os.path.join(BASE,f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_batt_multi"); os.makedirs(ROOT,exist_ok=True)
MARGIN=0.01; REFY=2025; VTOL=1e-4; NODES=["CH","FR","DE","AT"]   # IT already validated
def cfg(pert):
    c={"analysis":{"time_series_aggregation":{"hoursPerPeriod":1,"clusterMethod":"hierarchical"}},
       "solver":{"name":"gurobi","save_duals":pert,"save_reduced_costs":pert,"use_scaling":0,
       "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"rc_tight_e2p":{"battery":4}}}}
    if pert: c["solver"]["solver_options"].update({"rc_perturbation":0,"rc_lifetime_rhs_perturbation":1e-3,"rc_storage_power_perturbation":1e-4})
    return c
def run_model(name,pert):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(pert),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA)
def valp(sc,node):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies=="battery")&(d.set_capacity_types=="power")&(d.set_location==node)&(d.set_time_steps_yearly==0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan
restore_leftover_swaps(DATASET)
# perturbed base -> bundle RC per node
sc=run_model("pert_base",True)
st=pd.read_csv(sc+"/capacity_addition_analysis_storage.csv")
res=[]
for node in NODES:
    r=st[(st.set_technologies=="battery")&(st.set_location==node)&(st.set_time_steps_yearly==0)]
    rc=float(r.rc_mathematical.iloc[0]); f=float(r.ratio_reduction_proportional.iloc[0])
    cp=read_capex(DATASET,"battery",node,REFY,"power"); ce=read_capex(DATASET,"battery",node,REFY,"energy")
    def ov(s): return [{"tech":"battery","node":node,"year":REFY,"capacity_type":"power","value":cp*s},
                       {"tech":"battery","node":node,"year":REFY,"capacity_type":"energy","value":ce*s}]
    with capex_file_override(DATASET,ov(1-(1+MARGIN)*f)): vb=valp(run_model(f"{node}_b",False),node)
    with capex_file_override(DATASET,ov(1-(1-MARGIN)*f)): vn=valp(run_model(f"{node}_n",False),node)
    ok=(vb>VTOL) and not (vn>VTOL)
    res.append(dict(node=node,rc=round(rc,1),ratio=round(f,3),build=round(vb,3),nobuild=round(vn,3),result="PASS" if ok else "FAIL"))
    print(res[-1],flush=True)
pd.DataFrame(res).to_csv(os.path.join(ROOT,"val_batt_multi_summary.csv"),index=False)
print("\n"+pd.DataFrame(res).to_string(index=False)); print("DONE")
