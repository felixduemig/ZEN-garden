import json, os
from zen_garden import run
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"5_multiple_time_steps_per_year"); DATA=os.path.basename(DATASET)
OUT=os.path.join(BASE,"outputs_test_opcol"); os.makedirs(OUT,exist_ok=True)
c=json.load(open("./config.json")); c.pop("plugins",None)
c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=True
c["solver"]["save_reduced_costs"]=True; c["solver"]["use_scaling"]=0
so=c["solver"]["solver_options"]; so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0
so["rc_perturbation"]=0; so["rc_lifetime_rhs_perturbation"]=1e-3; so["rc_storage_power_perturbation"]=1e-4
tmp=os.path.join(OUT,"_c.json"); json.dump(c,open(tmp,"w"),indent=2)
run(config=tmp, dataset=DATASET, folder_output=OUT); os.remove(tmp)
print("OUT:", os.path.join(OUT,DATA,"capacity_addition_analysis.csv"))
