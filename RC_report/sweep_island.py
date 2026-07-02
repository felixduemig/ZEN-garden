"""Sweep ISL scarce-hour demand; report ISL price, peaker output, baseload RC."""
import os, json, importlib, sys
from datetime import datetime
import pandas as pd, numpy as np
BASE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(BASE); os.chdir(ROOT)
sys.path.insert(0, BASE)
from zen_garden import run

def solve(scarce, capex=3000.0, tag=""):
    os.environ["ISL_SCARCE_DEMAND"]=str(scarce); os.environ["ISL_BASELOAD_CAPEX"]=str(capex)
    import build_island; importlib.reload(build_island); DS=build_island.build()
    out=os.path.join(ROOT,"outputs_island",f"d{scarce}_{tag}_{datetime.now():%H%M%S}"); os.makedirs(out,exist_ok=True)
    cfg={"solver":{"name":"gurobi","save_duals":True,"save_reduced_costs":True,"use_scaling":0,
         "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
    tmp=os.path.join(out,"_c.json"); json.dump(cfg,open(tmp,"w"))
    run(config=tmp,dataset=DS,folder_output=out)
    R=os.path.join(out,"rc_scarcity_demo")
    conv=pd.read_csv(os.path.join(R,"capacity_addition_analysis_conversion.csv"))
    b=conv[(conv.set_technologies=="baseload")&(conv.set_location=="ISL")].iloc[0]
    lam=pd.read_hdf(os.path.join(R,"dual_dict.h5"),"constraint_nodal_energy_balance")
    dur=pd.read_hdf(os.path.join(R,"param_dict.h5"),"time_steps_operation_duration").to_dict()
    p_isl=float(lam.loc[("electricity","ISL",0)])/dur[0]
    out_=pd.read_hdf(os.path.join(R,"var_dict.h5"),"flow_conversion_output")
    pk=out_[(out_.index.get_level_values("technology")=="peaker")&(out_.index.get_level_values("node")=="ISL")&(out_.index.get_level_values("time_operation")==0)]
    pk=float(pk.iloc[0]) if len(pk) else 0.0
    return dict(scarce=scarce, capex=capex, isl_price_h0=round(p_isl,4), peaker_h0=round(pk,4),
                case=b["case"], rc_op=round(float(b["rc_capex_equivalent_operational_input_units"]),2),
                ratio_op=round(float(b["ratio_reduction_operational"]),4))

rows=[]
for d in [30.0, 30.01, 30.5, 33.0, 40.0]:
    rows.append(solve(d)); print(rows[-1], flush=True)
print("\n=== SWEEP SUMMARY ===")
print(pd.DataFrame(rows).to_string(index=False))
