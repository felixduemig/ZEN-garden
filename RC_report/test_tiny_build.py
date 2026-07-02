"""Test the 'solver swallows tiny economic builds' hypothesis:
make the marginal block deliberately tiny (peaker excess 1e-3..1e-7) at a capex BELOW
the marginal break-even, so a tiny build IS economically optimal. Does Gurobi realize
it (build = excess) or round it to 0?"""
import os, json, importlib, sys
BASE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(BASE); os.chdir(ROOT)
sys.path.insert(0, BASE)
import pandas as pd, build_island
from zen_garden import run

def solve(scarce, capex, tag):
    os.environ["ISL_SCARCE_DEMAND"]=repr(scarce); os.environ["ISL_BASELOAD_CAPEX"]=str(capex)
    importlib.reload(build_island); DS=build_island.build()
    out=os.path.join(ROOT,"outputs_island",f"tiny_{tag}"); os.makedirs(out,exist_ok=True)
    cfg={"solver":{"name":"gurobi","save_duals":False,"save_reduced_costs":False,"use_scaling":0,
         "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
    tmp=os.path.join(out,"_c.json"); json.dump(cfg,open(tmp,"w"))
    run(config=tmp,dataset=DS,folder_output=out)
    R=os.path.join(out,"rc_scarcity_demo")
    conv=pd.read_csv(os.path.join(R,"capacity_addition_analysis.csv"))
    b=conv[(conv.set_technologies=="baseload")&(conv.set_location=="ISL")]["value"].sum()
    o=pd.read_hdf(os.path.join(R,"var_dict.h5"),"flow_conversion_output")
    pk=o[(o.index.get_level_values("technology")=="peaker")&(o.index.get_level_values("node")=="ISL")&(o.index.get_level_values("time_operation")==0)]
    pk=float(pk.iloc[0]) if len(pk) else 0.0
    return float(b), pk

res=[]
for excess in [1e-2, 1e-3, 1e-5, 1e-7]:
    b,pk=solve(30.0+excess, 2000.0, f"{excess:.0e}")
    res.append((excess,pk,b))
print("\nRESULTS (capex 2000 < marginal break-even 2255 -> a build of size 'excess' IS optimal):")
print(f"  {'peaker_excess':>14} {'peaker_out':>12} {'baseload_built':>15} {'realized?':>10}")
for excess,pk,b in res:
    print(f"  {excess:14.0e} {pk:12.3e} {b:15.3e} {str(b>1e-12):>10}")
