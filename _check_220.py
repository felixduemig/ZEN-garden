"""Re-run the 220 GW case (PV DE 2025 capex=5) and inspect DE: electricity generation
mix, demand coverage, cross-border export."""
import json, os, shutil
import pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, restore_leftover_swaps
from zen_garden.postprocess.results.results import Results

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
OUT = os.path.join(BASE, "outputs_tmp_220"); os.makedirs(OUT, exist_ok=True)
cfg = {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
            "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
       "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                  "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
tmp = os.path.join(OUT, "_c.json"); json.dump(cfg, open(tmp, "w"), indent=2)
restore_leftover_swaps(DATASET)
with capex_file_override(DATASET, [{"tech": "photovoltaics", "node": "DE", "year": 2025, "value": 5.0}]):
    run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)

r = Results(os.path.join(OUT, DATA))
Y = "2025"
gen = r.get_total("flow_conversion_output")
ele = gen.xs("electricity", level="carrier").xs("DE", level="node")[Y].sort_values(ascending=False)
print("\n=== DE electricity GENERATION by tech, 2025 [GWh] ===")
print(ele.round(0).to_string()); print("total gen:", round(ele.sum(), 0))
dem = r.get_total("demand").xs("electricity", level="carrier")["DE"] if "DE" in \
      r.get_total("demand").xs("electricity", level="carrier").columns else None
demDE = r.get_total("demand").loc[("electricity", "DE"), Y]
print("\nDE electricity demand 2025 [GWh]:", round(demDE, 0))
try:
    inp = r.get_total("flow_conversion_input")
    hp = inp.xs("electricity", level="carrier").xs("DE", level="node")[Y]
    print("DE electricity CONSUMED by conversion (e.g. heat_pump) 2025 [GWh]:")
    print(hp[hp > 1].round(0).to_string())
except Exception as e:
    print("flow_conversion_input n/a:", repr(e)[:80])
# transport: DE power_line edges
tr = r.get_total("flow_transport").xs("power_line", level="technology")[Y]
exp = tr.get("DE-FR", 0) + tr.get("DE-AT", 0)
imp = tr.get("FR-DE", 0) + tr.get("AT-DE", 0)
print("\n=== DE power_line flows 2025 [GWh] ===")
for e in ["DE-FR", "FR-DE", "DE-AT", "AT-DE"]:
    print(f"  {e}: {tr.get(e, 0):.0f}")
print(f"net export DE = {exp - imp:.0f}  (export {exp:.0f} - import {imp:.0f})")
# DE conversion capacities built
cap = pd.read_csv(os.path.join(OUT, DATA, "capacity_addition_analysis_conversion.csv"))
cap = cap[(cap.set_location == "DE") & (cap.set_time_steps_yearly == 0) & (cap.capacity > 1e-3)]
print("\n=== DE installed conversion capacity 2025 [GW] (capacity>0) ===")
print(cap[["set_technologies", "capacity", "case"]].round(2).to_string(index=False))
shutil.rmtree(OUT, ignore_errors=True)
print("\nDONE (tmp folder removed)")
