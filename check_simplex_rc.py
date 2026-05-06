import pandas as pd
import h5py
import numpy as np

out = 'outputs_20260506-114446/simplex_rc_primal_simplex/5_multiple_time_steps_per_year'

# Capex
df_capex = pd.read_hdf(f'{out}/param_dict.h5', key='capex_specific_conversion')
print("capex_specific_conversion (internal):")
print(df_capex[df_capex.index.get_level_values(0).str.contains('photovoltaics')])

fraction_year = 96 / 8760
print(f"\nfraction_year = {fraction_year:.6f}")
print("\ncapex in input units (Euro/kW):")
pv_copy = df_capex[df_capex.index.get_level_values(0) == 'photovoltaics_copy']
print(pv_copy / fraction_year)

# Duals
df_dual = pd.read_hdf(f'{out}/dual_dict.h5', key='constraint_technology_lifetime')
print("\ndual_constraint_technology_lifetime (photovoltaics_copy):")
mask = df_dual.index.get_level_values(0) == 'photovoltaics_copy'
print(df_dual[mask])

# Manual formula trace for year 0
r = 0.06
lt = 24.0
af = (r * (1+r)**lt) / ((1+r)**lt - 1)
print(f"\nannuity_factor = {af:.6f}")

years = [0, 1, 2]
dy = 1
first_year = 0
discount_factors = {y: (1/(1+r))**(dy*(y-first_year)) for y in years}
print(f"discount_factors = {discount_factors}")

for y_inv in years:
    n_periods = int(np.floor(lt / dy))
    pay_years = [y for y in years if y_inv <= y <= y_inv + n_periods - 1]
    discount_sum = sum(discount_factors[y] for y in pay_years)
    scaling = af * discount_sum

    duals = df_dual[mask]
    elec_value = 0.0
    for y in pay_years:
        d = float(duals[
            (duals.index.get_level_values(1) == 'power') &
            (duals.index.get_level_values(2) == 'CH') &
            (duals.index.get_level_values(3) == y)
        ].iloc[0])
        elec_value += -d

    cs = float(pv_copy[pv_copy.index.get_level_values(2) == y_inv].iloc[0])
    rc = cs - elec_value / scaling
    rc_input = rc / fraction_year

    print(f"\ny_inv={y_inv}: pay_years={pay_years}, scaling={scaling:.4f}, "
          f"elec_value={elec_value:.4f}, cs={cs:.4f} -> rc={rc:.4f} -> {rc_input:.2f} Euro/kW")
