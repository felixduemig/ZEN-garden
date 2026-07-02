"""Overnight Crystal Ball RC run. Mode A = no rhs perturbation (storage perturbed + e2p
fixed); Mode B = rhs perturbation 1e-3 (+ storage perturbed + e2p fixed). Operational RC
(our new code) is the primary column. Heatmaps OFF (28 nodes x 68 techs is too much);
we only need the classified CSVs. Output: outputs_CB_overnight/run<MODE>/Crystal_Ball/."""
import json, os, sys
from zen_garden import run

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")   # ABSOLUTE (run() needs it)
MODE = sys.argv[1] if len(sys.argv) > 1 else "A"   # A=no rhs pert, B=rhs pert, C=fully clean
RHS = 1e-3 if MODE == "B" else 0
STORAGE_PERT = 0 if MODE == "C" else 1e-4          # C = NO perturbation at all
E2P = {} if MODE == "C" else {"battery": 16, "pumped_hydro": 22, "salt_cavern_storage": 145}
OUT = os.path.join(BASE, "outputs_CB_overnight", f"run{MODE}")
os.makedirs(OUT, exist_ok=True)

with open("./config.json") as f:
    config = json.load(f)
config.pop("plugins", None)
config.setdefault("analysis", {}); config["analysis"].pop("dataset", None)
config.setdefault("solver", {}); config["solver"].setdefault("solver_options", {})
config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
config["solver"]["use_scaling"] = 0
so = config["solver"]["solver_options"]
so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 0
so["rc_perturbation"] = 0
so["rc_lifetime_rhs_perturbation"] = RHS
so["rc_storage_power_perturbation"] = STORAGE_PERT
if E2P:
    so["rc_tight_e2p"] = E2P
so["LogFile"] = os.path.join(OUT, "solver.log")

tmp = os.path.join(OUT, "_c.json"); json.dump(config, open(tmp, "w"), indent=2)
print(f"=== CB run {MODE}: rhs_pert={RHS}, storage_pert=1e-4, e2p battery:4 -> {OUT} ===", flush=True)
run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)
print(f"=== DONE run {MODE} -> {os.path.join(OUT, 'Crystal_Ball', 'capacity_addition_analysis.csv')} ===", flush=True)
