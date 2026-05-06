import pandas as pd
import numpy as np

out = 'outputs_20260506-122956/rc_analysis/5_multiple_time_steps_per_year'

# Duals
df_dual = pd.read_hdf(f'{out}/dual_dict.h5', key='constraint_technology_lifetime')
print("=== Duals: constraint_technology_lifetime ===")
print(df_dual.to_string())

# Capex
df_capex = pd.read_hdf(f'{out}/param_dict.h5', key='capex_specific_conversion')
print("\n=== capex_specific_conversion (internal) ===")
print(df_capex.to_string())

# fraction_year
import json
with open('outputs_20260506-122956/rc_analysis/5_multiple_time_steps_per_year/system.json') as f:
    sys = json.load(f)
fraction_year = sys['unaggregated_time_steps_per_year'] / sys['total_hours_per_year']
print(f"\nfraction_year = {fraction_year:.6f}")
print(f"capex NGB in Euro/kW = {df_capex.loc[('natural_gas_boiler','CH',0)] / fraction_year:.1f}")
