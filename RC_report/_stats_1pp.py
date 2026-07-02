"""Confirm 1pp confusion (tested set) + recompute excerpt stable fraction at 1pp."""
import pandas as pd

C = pd.read_csv("outputs_CB_overnight/runC/Crystal_Ball/capacity_addition_analysis_conversion.csv")
B = pd.read_csv("outputs_CB_overnight/runB/Crystal_Ball/capacity_addition_analysis_conversion.csv")
m = C.merge(B[["set_technologies", "set_location", "ratio_reduction_operational"]],
            on=["set_technologies", "set_location"], suffixes=("", "_B"))
m["swing"] = (m["ratio_reduction_operational_B"] - m["ratio_reduction_operational"]).abs() * 100
sw = {(r.set_technologies, r.set_location): r.swing for _, r in m.iterrows()}

# tested set (from _viz_swing.py)
P = [("photovoltaics","CZ"),("photovoltaics","NO"),("photovoltaics","SE"),("wind_onshore","NO"),("wind_onshore","CH"),("wind_offshore","FR"),("wind_offshore","SE"),("run-of-river_hydro","SK"),("run-of-river_hydro","SE"),("reservoir_hydro","CH"),("reservoir_hydro","SE"),("heat_pump_DH","SE"),("methanol_from_hydrogen","BG"),("natural_gas_turbine_CCS","ES"),("nuclear","FR"),("photovoltaics","SK"),("photovoltaics","FI"),("electrolysis","CH"),("reservoir_hydro","NO"),("reservoir_hydro","CZ"),("reservoir_hydro","FR"),("run-of-river_hydro","BG"),("run-of-river_hydro","CH"),("run-of-river_hydro","CZ"),("heat_pump_DH","ES"),("heat_pump_DH","FR"),("heat_pump_DH","BG"),("heat_pump_DH","DE"),("DAC","SE"),("wind_onshore","BG"),("methanol_from_hydrogen","DE"),("electrode_boiler","DE"),("fuel_cell","ES"),("SMR_CCS","DE"),("coal_to_cement_fuel","CZ"),("natural_gas_boiler","DE"),("methanol_from_hydrogen","SK"),("DAC","NO"),("run-of-river_hydro","FR"),("methanol_from_hydrogen","CH"),("heat_pump_DH","FI"),("electrode_boiler","SK")]
F = [("nuclear","ES"),("electrolysis","FI"),("coal_to_cement_fuel","SK"),("natural_gas_turbine","NO"),("natural_gas_turbine_CCS","BG"),("natural_gas_turbine_CCS","SK"),("natural_gas_turbine_CCS","CZ"),("SMR_CCS","ES"),("coal_to_cement_fuel","CH"),("SMR_CCS","CH"),("SMR","SK"),("haber_bosch","SE"),("natural_gas_turbine_CCS","FR"),("nuclear","FI"),("SMR_CCS","SK"),("SMR_CCS","SE"),("methanol_from_hydrogen","CZ"),("natural_gas_turbine","BG"),("natural_gas_turbine_CCS","FI"),("SMR_CCS","FI"),("DAC","FR")]
THR = 1.0
swP = [sw.get(c, 0) for c in P]; swF = [sw.get(c, 0) for c in F]
TP = sum(s >= THR for s in swF); FN = sum(s < THR for s in swF)
FP = sum(s >= THR for s in swP); TN = sum(s < THR for s in swP)
print(f"TESTED (n={len(P)+len(F)}): TP={TP} FP={FP} FN={FN} TN={TN}  prec={TP/(TP+FP):.2f} rec={TP/(TP+FN):.2f}")
print("  FN (missed):", [c for c in F if sw.get(c,0) < THR])
print("  FP (over-warned):", [c for c in P if sw.get(c,0) >= THR])

# excerpt stable fraction at 1pp (20 techs x 10 nodes, buildable_rc only)
TECHS = ["photovoltaics","wind_onshore","wind_offshore","run-of-river_hydro","reservoir_hydro","nuclear","natural_gas_turbine","natural_gas_turbine_CCS","electrolysis","SMR","SMR_CCS","fuel_cell","heat_pump","heat_pump_DH","electrode_boiler","natural_gas_boiler","coal_to_cement_fuel","methanol_from_hydrogen","DAC","haber_bosch"]
EXC = ["DE","FR","NO","SE","CH","CZ","SK","BG","ES","FI"]
e = m[(m.set_technologies.isin(TECHS)) & (m.set_location.isin(EXC)) & (m.case == "buildable_rc")]
n = len(e); stable = int((e["swing"] < THR).sum()); flagged = n - stable
print(f"EXCERPT buildable_rc cells: n={n}  stable(<1pp)={stable} ({stable/n:.0%})  flagged(>=1pp)={flagged} ({flagged/n:.0%})")
