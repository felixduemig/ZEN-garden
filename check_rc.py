import pandas as pd
import h5py
import numpy as np

out = 'outputs_20260506-110322/standard/5_multiple_time_steps_per_year'

# 1) List all param keys
with h5py.File(f'{out}/param_dict.h5', 'r') as f:
    all_keys = list(f.keys())
    capex_keys = [k for k in all_keys if 'capex' in k.lower()]
    print("All capex param keys:", capex_keys)

# 2) Read capex_specific_conversion
try:
    df_capex = pd.read_hdf(f'{out}/param_dict.h5', key='capex_specific_conversion')
    print("\ncapex_specific_conversion (internal model values):")
    print(df_capex)
except Exception as e:
    print("capex read error:", e)

# 3) Read dual of constraint_technology_lifetime
with h5py.File(f'{out}/dual_dict.h5', 'r') as f:
    all_dual_keys = list(f.keys())
    lifetime_keys = [k for k in all_dual_keys if 'lifetime' in k.lower()]
    print("\nDual keys (lifetime):", lifetime_keys)

if lifetime_keys:
    try:
        df_dual = pd.read_hdf(f'{out}/dual_dict.h5', key=lifetime_keys[0])
        print("\ndual_constraint_technology_lifetime:")
        print(df_dual)
    except Exception as e:
        print("dual read error:", e)

# 4) System info
try:
    df_sys = pd.read_hdf(f'{out}/param_dict.h5', key='system')
    print("\nSystem params:", df_sys)
except Exception as e:
    print("system read error:", e)
