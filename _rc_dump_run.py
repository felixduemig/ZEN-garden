"""Exact per-constraint reduced-cost decomposition of capacity_addition for the
FAIL cases + PASS contrasts, using the perturbed baseline config."""
import json, os
from zen_garden import run
from rc_capex_file_override import restore_leftover_swaps

BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"5_multiple_extended_countries"); DATA_NAME=os.path.basename(DATASET)
ROOT=os.path.join(BASE,"outputs_rc_dump"); os.makedirs(ROOT,exist_ok=True)

TARGETS=[
  {"tech":"heat_pump","node":"IT","capacity_type":"power"},       # FAIL y1,y2
  {"tech":"heat_pump","node":"ES","capacity_type":"power"},       # PASS y0
  {"tech":"photovoltaics","node":"DE","capacity_type":"power"},   # PASS carry-over
  {"tech":"battery","node":"ES","capacity_type":"power"},         # FAIL y1
  {"tech":"battery","node":"ES","capacity_type":"energy"},
  {"tech":"battery","node":"CH","capacity_type":"power"},         # PASS
  {"tech":"battery","node":"CH","capacity_type":"energy"},
]

def cfg():
    c=json.load(open("./config.json")); c.pop("plugins",None)
    c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
    c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
    so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
    so["rc_tight_e2p"]={"battery":16,"pumped_hydro":22}
    so["rc_perturbation"]=0; so["rc_lifetime_rhs_perturbation"]=1e-3; so["rc_storage_power_perturbation"]=1e-4
    c.setdefault("analysis",{})
    c["analysis"]["rc_dual_dump"]=True
    c["analysis"]["rc_dual_dump_targets"]=TARGETS
    return c

restore_leftover_swaps(DATASET)
out=os.path.join(ROOT,"dump"); os.makedirs(out,exist_ok=True)
tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"),indent=2)
run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
print("DONE ->", os.path.join(out,DATA_NAME,"rc_dual_decomposition.csv"))
