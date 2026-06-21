import pandas as pd
import numpy as np

base = 'outputs_20260620-010246_rc_validate_dataset'

# ---- BASELINE: heat_pump ----
conv = pd.read_csv(f'{base}/baseline/5_multiple_extended_countries/capacity_addition_analysis_conversion.csv')
hp = conv[conv.set_technologies == 'heat_pump']
print('=== BASELINE heat_pump ===')
cols = ['set_technologies','set_location','set_time_steps_yearly','capacity','value','case','ratio_reduction','rc_capex_equivalent_input_units','rc_reliable']
print(hp[cols].to_string())
print()

# ---- BUILD runs for IT heat_pump: was anything built? ----
for yidx in [1, 2]:
    run_dir = f'{base}/conv_heat_pump_IT_y{yidx}_build/5_multiple_extended_countries'
    cap = pd.read_csv(f'{run_dir}/capacity_addition_analysis.csv')
    hp_run = cap[cap.set_technologies == 'heat_pump']
    print(f'=== BUILD IT y{yidx}: heat_pump capacities ===')
    print(hp_run[['set_technologies','set_location','set_time_steps_yearly','set_capacity_types','value']].to_string())
    print()

# ---- BUILD run for ES battery y1 ----
run_dir = f'{base}/stor_battery_ES_y1_build/5_multiple_extended_countries'
cap = pd.read_csv(f'{run_dir}/capacity_addition_analysis.csv')
bat = cap[cap.set_technologies == 'battery']
print('=== BUILD battery ES y1: battery capacities ===')
print(bat[['set_technologies','set_location','set_time_steps_yearly','set_capacity_types','value']].to_string())
print()

# ---- Baseline battery ----
stor = pd.read_csv(f'{base}/baseline/5_multiple_extended_countries/capacity_addition_analysis_storage.csv')
bat_base = stor[stor.set_technologies == 'battery']
print('=== BASELINE battery ===')
scols = ['set_technologies','set_location','set_time_steps_yearly','capacity','value','case','ratio_reduction_proportional','rc_mathematical','rc_reliable']
scols_exist = [c for c in scols if c in bat_base.columns]
print(bat_base[scols_exist].to_string())
