"""Check-up: validate the RC values from run 164755 (heat_pump) via +-1% build/nobuild.
For each tested RC: reduce capex by (1+1%)*rc -> MUST build; by (1-1%)*rc -> MUST NOT build.
PASS = build builds AND nobuild does not. Runs are UN-perturbed (true build decision).
Also tests the diverging 164925 lifetime values (CH/DE y1) as a contrast (expected FAIL).
"""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"5_multiple_time_steps_per_year"); DATA=os.path.basename(DATASET)
MARGIN=0.01; REF_YEAR=2023; VALUE_TOL=1e-4
ROOT=os.path.join(BASE,f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_checkup_164755"); os.makedirs(ROOT,exist_ok=True)

# (node, yidx, rc_input_units, label)  -- 164755 = life==operativ; 164925_life = abweichend
CASES=[
 ("CH",0, 283.837214,"164755"), ("CH",1,2089.189146,"164755"), ("CH",2,2089.189146,"164755"),
 ("DE",0, 107.023966,"164755"), ("DE",1,2023.373464,"164755"), ("DE",2,2023.373464,"164755"),
 ("CH",1,1650.536644,"164925_life"), ("DE",1,1746.977113,"164925_life"),
]

def cfg():
    c=json.load(open("./config.json")); c.pop("plugins",None)
    c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
    c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
    so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
    return c  # NO perturbation -> echte Bauentscheidung

def run_model(name):
    out=os.path.join(ROOT,name); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"),indent=2)
    run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
    return os.path.join(out,DATA)

def val(sc,node,yidx):
    d=pd.read_csv(os.path.join(sc,"capacity_addition_analysis.csv"))
    r=d[(d.set_technologies=="heat_pump")&(d.set_capacity_types=="power")&(d.set_location==node)&(d.set_time_steps_yearly==yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET)
res=[]
for node,yidx,rc,lab in CASES:
    year=REF_YEAR+yidx; capex=read_capex(DATASET,"heat_pump",node,year); ratio=rc/capex
    cb=capex*(1-(1+MARGIN)*ratio); cn=capex*(1-(1-MARGIN)*ratio)
    tag=f"{lab}_{node}_y{yidx}"
    with capex_file_override(DATASET,[{"tech":"heat_pump","node":node,"year":year,"value":cb}]):
        vb=val(run_model(tag+"_build"),node,yidx)
    with capex_file_override(DATASET,[{"tech":"heat_pump","node":node,"year":year,"value":cn}]):
        vn=val(run_model(tag+"_nobuild"),node,yidx)
    ok=(np.isfinite(vb) and vb>VALUE_TOL) and not (np.isfinite(vn) and vn>VALUE_TOL)
    row=dict(source=lab,node=node,y=yidx,rc=round(rc,1),capex_build=round(cb,1),capex_nobuild=round(cn,1),
             value_build=round(vb,4),value_nobuild=round(vn,4),result="PASS" if ok else "FAIL")
    res.append(row); print("  ",row,flush=True)
df=pd.DataFrame(res); df.to_csv(os.path.join(ROOT,"checkup_164755_summary.csv"),index=False)
print("\n"+df.to_string(index=False)); print("\nSummary:",os.path.join(ROOT,"checkup_164755_summary.csv"))
