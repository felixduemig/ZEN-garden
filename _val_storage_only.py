"""+-1% build/nobuild validation of the STORAGE-ONLY run (operational RC, new gate).

Reads RC from outputs_showcase_storage_only and validates against the OPERATIONAL
reconstruction (ratio_reduction_operational) — the value the heatmaps now use. For
each conversion case: capex*(1 -+ (1+-MARGIN)*ratio_op) -> build must / nobuild must not.
Includes the newly rescued photovoltaics_capex twins (AT/FR/IT, op-RC=10 EUR/kW, lifetime=0).
Storage validated e2p-consistent (rc_tight_e2p={battery:4}); gas_boiler free -> must not build.
"""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
SRC = os.path.join(BASE, "outputs_showcase_storage_only", DATA)
MARGIN = 0.01; REFY = 2025; VTOL = 1e-4
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_storage_only")
os.makedirs(ROOT, exist_ok=True)

conv = pd.read_csv(SRC + "/capacity_addition_analysis_conversion.csv")
stor = pd.read_csv(SRC + "/capacity_addition_analysis_storage.csv")

def rc_of(tech, node, y):  # OPERATIONAL rc + ratio
    r = conv[(conv.set_technologies == tech) & (conv.set_location == node)
             & (conv.set_time_steps_yearly == y)]
    return (float(r.rc_capex_equivalent_operational_input_units.iloc[0]),
            float(r.ratio_reduction_operational.iloc[0]))

def f_of(node, y):  # storage bundle (proportional)
    r = stor[(stor.set_technologies == "battery") & (stor.set_location == node)
             & (stor.set_time_steps_yearly == y)]
    return float(r.rc_mathematical.iloc[0]), float(r.ratio_reduction_proportional.iloc[0])

# 8 standard cases + the 3 newly rescued twins (op-RC=10, lifetime=0)
CONV_CASES = [("photovoltaics_capex", "AT", 0), ("photovoltaics_capex", "FR", 0),
              ("photovoltaics_capex", "IT", 0),            # <- twins (NEW)
              ("photovoltaics_capex", "CH", 0), ("photovoltaics_capex", "DE", 0),
              ("photovoltaics_opex", "IT", 0), ("photovoltaics_opex", "DE", 0),
              ("photovoltaics_lowcf", "IT", 0), ("photovoltaics_lowcf", "DE", 0),
              ("natural_gas_turbine", "FR", 0), ("natural_gas_turbine", "IT", 0)]
BATT_NODES = ["IT", "FR", "CH", "AT", "DE"]

def cfg(tight_e2p=False):
    so = {"Method": 2, "Crossover": 1, "Presolve": 0}
    if tight_e2p:
        so["rc_tight_e2p"] = {"battery": 4}
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": so}}

def run_model(name, tight_e2p=False):
    out = os.path.join(ROOT, name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(tight_e2p), open(tmp, "w"), indent=2)
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    return os.path.join(out, DATA)

def valc(sc, tech, node, y, ct="power"):
    d = pd.read_csv(os.path.join(sc, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == tech) & (d.set_capacity_types == ct)
          & (d.set_location == node) & (d.set_time_steps_yearly == y)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET); res = []

# --- conversion +-1% on the OPERATIONAL ratio ---
for tech, node, y in CONV_CASES:
    rc, ratio = rc_of(tech, node, y); year = REFY + y
    capex = read_capex(DATASET, tech, node, year)
    cb = capex * (1 - (1 + MARGIN) * ratio); cn = capex * (1 - (1 - MARGIN) * ratio)
    with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year, "value": cb}]):
        vb = valc(run_model(f"{tech}_{node}_b"), tech, node, y)
    with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year, "value": cn}]):
        vn = valc(run_model(f"{tech}_{node}_n"), tech, node, y)
    ok = (vb > VTOL) and not (vn > VTOL)
    res.append(dict(tech=tech, node=node, y=y, rc_op=round(rc, 1), ratio_op=round(ratio, 4),
                    vbuild=round(vb, 4), vnobuild=round(vn, 4),
                    result="PASS" if ok else "FAIL")); print(res[-1], flush=True)

# --- battery bundle, e2p-fixed at 4 (rc_tight_e2p) for all nodes ---
for node in BATT_NODES:
    rcb, f = f_of(node, 0); year = REFY
    cp = read_capex(DATASET, "battery", node, year, "power")
    ce = read_capex(DATASET, "battery", node, year, "energy")
    def ov(s, nd=node, yr=year, p=cp, e=ce):
        return [{"tech": "battery", "node": nd, "year": yr, "capacity_type": "power", "value": p * s},
                {"tech": "battery", "node": nd, "year": yr, "capacity_type": "energy", "value": e * s}]
    with capex_file_override(DATASET, ov(1 - (1 + MARGIN) * f)):
        vb = valc(run_model(f"battery_{node}_b", tight_e2p=True), "battery", node, 0, "power")
    with capex_file_override(DATASET, ov(1 - (1 - MARGIN) * f)):
        vn = valc(run_model(f"battery_{node}_n", tight_e2p=True), "battery", node, 0, "power")
    ok = (vb > VTOL) and not (vn > VTOL)
    res.append(dict(tech="battery", node=node, y=0, rc_op=round(rcb, 1), ratio_op=round(f, 4),
                    vbuild=round(vb, 4), vnobuild=round(vn, 4),
                    result="PASS" if ok else "FAIL")); print(res[-1], flush=True)

# --- gas_boiler capex~0 (ratio>1 -> must NOT build) ---
with capex_file_override(DATASET, [{"tech": "natural_gas_boiler", "node": "AT", "year": REFY, "value": 1.0}]):
    vfree = valc(run_model("gas_boiler_AT_free"), "natural_gas_boiler", "AT", 0)
res.append(dict(tech="natural_gas_boiler", node="AT", y=0, rc_op="ratio>1", ratio_op=">1",
                vbuild=round(vfree, 4), vnobuild="-",
                result="PASS (no build @ capex~0)" if vfree <= VTOL else "FAIL (builds!)"))
print(res[-1], flush=True)

pd.DataFrame(res).to_csv(os.path.join(ROOT, "val_storage_only_summary.csv"), index=False)
print("\n" + pd.DataFrame(res).to_string(index=False)); print("DONE", ROOT)
