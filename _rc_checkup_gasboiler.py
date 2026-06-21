"""Gas boiler check-up (run 164755). y0 = built (rc=0). y1/y2 = carry-over with
ratio_reduction=2.255>1 -> break-even capex negative -> +-1% untestable. Instead set
capex ~0 (free) and check whether ANY additional gas boiler builds in that year.
If 0 even when free -> the rc=1975 is a carry-over phantom (not a real distance)."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"5_multiple_time_steps_per_year"); DATA=os.path.basename(DATASET)
REF_YEAR=2023
ROOT=os.path.join(BASE,f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_checkup_gasboiler"); os.makedirs(ROOT,exist_ok=True)
CASES=[("CH",1),("CH",2),("DE",1),("DE",2)]  # carry-over years

def cfg():
    c=json.load(open("./config.json")); c.pop("plugins",None)
    c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
    c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
    so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
    return c

def run_model(name):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA)

def val(sc,node,yidx):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies=="natural_gas_boiler")&(d.set_capacity_types=="power")&(d.set_location==node)&(d.set_time_steps_yearly==yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET)
res=[]
for node,yidx in CASES:
    year=REF_YEAR+yidx; capex=read_capex(DATASET,"natural_gas_boiler",node,year)
    with capex_file_override(DATASET,[{"tech":"natural_gas_boiler","node":node,"year":year,"value":1.0}]):
        v=val(run_model(f"gb_{node}_y{yidx}_free"),node,yidx)
    row=dict(node=node,y=yidx,capex_orig=round(capex,1),capex_test=1.0,rc_164755=1975.4,
             value_build_when_free=round(v,4),
             verdict="PHANTOM (baut nie, auch gratis nicht)" if (not np.isfinite(v) or v<=1e-4) else "BAUT (rc real!)")
    res.append(row); print("  ",row,flush=True)
df=pd.DataFrame(res); df.to_csv(os.path.join(ROOT,"checkup_gasboiler_summary.csv"),index=False)
print("\n"+df.to_string(index=False)); print("\nSummary:",os.path.join(ROOT,"checkup_gasboiler_summary.csv"))
