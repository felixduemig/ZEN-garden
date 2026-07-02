import json, os, sys
from zen_garden import run
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET=os.path.join(BASE,"6_showcase_countries")
# mode: base (no perturbation) | pert (RHS + storage) | spert (storage only)
mode = sys.argv[1] if len(sys.argv)>1 else "base"
OUTNAME={"base":"outputs_showcase_test","pert":"outputs_showcase_basecase_perturbed",
         "spert":"outputs_showcase_storage_only"}.get(mode,"outputs_showcase_test")
OUT=os.path.join(BASE,OUTNAME); os.makedirs(OUT,exist_ok=True)
c={"analysis":{"time_series_aggregation":{"hoursPerPeriod":1,"clusterMethod":"hierarchical",
       "extremePeriodMethod":"None"}},
   "solver":{"name":"gurobi","save_duals":True,"save_reduced_costs":True,"use_scaling":0,
   "solver_options":{"Method":2,"Crossover":1,"Presolve":0}}}
if mode=="pert":
    c["solver"]["solver_options"].update({"rc_perturbation":0,"rc_lifetime_rhs_perturbation":1e-3,
        "rc_storage_power_perturbation":1e-4,"rc_tight_e2p":{"battery":4}})
elif mode=="spert":   # storage perturbation only, NO RHS perturbation
    c["solver"]["solver_options"].update({"rc_perturbation":0,
        "rc_storage_power_perturbation":1e-4,"rc_tight_e2p":{"battery":4}})
tmp=os.path.join(OUT,"_c.json"); json.dump(c,open(tmp,"w"),indent=2)
run(config=tmp,dataset=DATASET,folder_output=OUT); os.remove(tmp)
print("DONE", mode, OUT)
