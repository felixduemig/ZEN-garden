"""Phase 1: sweep the heat-pump COP to find where it stops being built (becomes
buildable_rc), so we can derive the COP needed. Reports heat_pump case/value per cf."""
import os, json, shutil
import pandas as pd
from zen_garden import run
BASE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
SRC=os.path.join(BASE,"6_showcase_countries"); WD=os.path.join(BASE,"6_showcase_hpcop")

def solve(cf):
    if os.path.exists(WD): shutil.rmtree(WD)
    shutil.copytree(SRC,WD)
    ap=os.path.join(WD,"set_technologies","set_conversion_technologies","heat_pump","attributes.json")
    a=json.load(open(ap)); a["conversion_factor"]["electricity"]["default_value"]=cf; json.dump(a,open(ap,"w"),indent=2)
    out=os.path.join(BASE,"outputs_hpcop_p1",f"cf{cf}");
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out)
    cfg={"solver":{"name":"gurobi","save_duals":True,"save_reduced_costs":True,"use_scaling":0,
         "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
    tmp=os.path.join(out,"_c.json"); json.dump(cfg,open(tmp,"w")); run(config=tmp,dataset=WD,folder_output=out)
    d=pd.read_csv(os.path.join(out,"6_showcase_hpcop","capacity_addition_analysis_conversion.csv"))
    d=d[d.set_time_steps_yearly==0]
    hp=d[d.set_technologies=="heat_pump"]
    return hp[["set_location","value","case","rc_capex_equivalent_operational_input_units","ratio_reduction_operational"]]

for cf in [0.8, 1.0, 1.3, 1.7]:
    hp=solve(cf)
    print(f"\n##### COP = 1/{cf} = {1/cf:.2f} (cf={cf}) #####",flush=True)
    print(hp.to_string(index=False),flush=True)
