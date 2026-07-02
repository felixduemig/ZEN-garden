"""Before/after demonstration for the report: lower ONLY photovoltaics_opex DE (year
2025) to its build point and regenerate the heatmap, to show the RC prediction
materialising (everything-held-equal). Duals on, storage-only perturbation."""
import json, os
from zen_garden import run
from rc_capex_file_override import capex_file_override, restore_leftover_swaps
import rc_heatmaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries")
OUT = os.path.join(BASE, "outputs_showcase_after_opexDE"); os.makedirs(OUT, exist_ok=True)
# build point: capex * (1 - (1+1%) * ratio_op),  ratio_op(opex,DE)=0.5124, capex=490
CB = 490.0 * (1 - 1.01 * 0.5124)   # ~236.4
cfg = {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
            "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
       "solver": {"name": "gurobi", "save_duals": True, "save_reduced_costs": True,
                  "use_scaling": 0,
                  "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0,
                                     "rc_perturbation": 0,
                                     "rc_storage_power_perturbation": 1e-4,
                                     "rc_tight_e2p": {"battery": 4}}}}
tmp = os.path.join(OUT, "_c.json"); json.dump(cfg, open(tmp, "w"), indent=2)
restore_leftover_swaps(DATASET)
with capex_file_override(DATASET, [{"tech": "photovoltaics_opex", "node": "DE",
                                    "year": 2025, "value": CB}]):
    run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)
rc_heatmaps.run(OUT, 150.0, "proportional", True)
print("DONE", OUT, "CB=", round(CB, 1))
