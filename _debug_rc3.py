"""Warum baut IT y1 heat_pump trotz 267 EUR/kW nicht?
Check: natural_gas_boiler output, electricity prices, and what gets built instead."""
import os, sys, json
import pandas as pd

sys.path.insert(0, 'c:/Users/felix/Documents/GitHub/ZEN-garden')
os.chdir('c:/Users/felix/Documents/GitHub/ZEN-garden')

base = 'outputs_20260620-010246_rc_validate_dataset'

def load_h5(run_name, key):
    import h5py, numpy as np
    path = f'{base}/{run_name}/5_multiple_extended_countries/{key}.h5'
    result = {}
    with h5py.File(path, 'r') as f:
        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                result[name] = obj[()]
        f.visititems(visitor)
    return result

# --- Solver status ---
for run in ['conv_heat_pump_IT_y1_build', 'conv_heat_pump_ES_y0_build']:
    sol = json.load(open(f'{base}/{run}/5_multiple_extended_countries/solver.json'))
    print(f"{run}: solver_status={sol.get('status','?')}, termination={sol.get('termination_condition','?')}")
print()

# --- What IS being built in the IT y1 build run? ---
print("=== IT y1 build: ALL capacities added ===")
cap = pd.read_csv(f'{base}/conv_heat_pump_IT_y1_build/5_multiple_extended_countries/capacity_addition_analysis.csv')
built = cap[cap['value'] > 1e-6]
if built.empty:
    print("  NOTHING is built!")
else:
    print(built[['set_technologies','set_location','set_time_steps_yearly','set_capacity_types','value']].to_string())
print()

print("=== ES y0 build: ALL capacities added ===")
cap2 = pd.read_csv(f'{base}/conv_heat_pump_ES_y0_build/5_multiple_extended_countries/capacity_addition_analysis.csv')
built2 = cap2[cap2['value'] > 1e-6]
if built2.empty:
    print("  NOTHING is built!")
else:
    print(built2[['set_technologies','set_location','set_time_steps_yearly','set_capacity_types','value']].to_string())
print()

# --- Natural gas boiler data ---
ngb_path = '5_multiple_extended_countries/set_technologies/set_conversion_technologies/natural_gas_boiler/attributes.json'
ngb = json.load(open(ngb_path))
print("=== natural_gas_boiler attributes ===")
for k, v in ngb.items():
    print(f"  {k}: {v}")
print()

# --- Check capacity_addition_analysis for conversion (all techs) in IT y1 build run ===
conv_run = pd.read_csv(f'{base}/conv_heat_pump_IT_y1_build/5_multiple_extended_countries/capacity_addition_analysis_conversion.csv')
it_conv = conv_run[conv_run.set_location == 'IT']
print("=== IT y1 build: conversion capacity_addition_analysis (IT node) ===")
print(it_conv[['set_technologies','set_location','set_time_steps_yearly','capacity','value','case']].to_string())
