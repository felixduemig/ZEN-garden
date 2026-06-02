import sys
sys.path.insert(0, '.')
from zen_garden.postprocess.results import Results
import pandas as pd

r = Results('outputs_20260528-175237/rc_analysis/6_cb_rc_model')
sc = next(iter(r.solution_loader.scenarios.values()))
n_ts = sc.system.unaggregated_time_steps_per_year  # 96

fi = r.get_df('flow_conversion_input')
fo = r.get_df('flow_conversion_output')

hp_elec = fi.xs('heat_pump',     level='technology').xs('electricity', level='carrier').xs('CH', level='node')
hp_heat = fo.xs('heat_pump',     level='technology').xs('heat',        level='carrier').xs('CH', level='node')
fw      = fo.xs('wind_onshore',  level='technology').xs('electricity', level='carrier').xs('CH', level='node')
pv      = fo.xs('photovoltaics', level='technology').xs('electricity', level='carrier').xs('CH', level='node')
bl      = fo.xs('generic_baseload', level='technology').xs('electricity', level='carrier').xs('CH', level='node')

cap  = r.get_df('capacity')
ml   = r.get_df('max_load')
# Check cap index names
wind_cap_yr0 = float(cap.xs('wind_onshore', level='technology').xs('power', level='capacity_type').xs('CH', level='location').iloc[0])
wind_ml      = ml.xs('wind_onshore', level='technology').xs('CH', level='location')

elec_demand = r.get_df('demand').xs('electricity', level='carrier').xs('CH', level='node')

df = pd.DataFrame({
    'hp_elec_GW':        hp_elec.iloc[:n_ts].values,
    'hp_heat_GW':        hp_heat.iloc[:n_ts].values,
    'wind_prod_GW':      fw.iloc[:n_ts].values,
    'wind_cf':           wind_ml.iloc[:n_ts].values,
    'pv_GW':             pv.iloc[:n_ts].values,
    'baseload_GW':       bl.iloc[:n_ts].values,
    'elec_demand_GW':    elec_demand.iloc[:n_ts].values,
})
df['wind_potential_GW'] = df['wind_cf'] * wind_cap_yr0
df['curtailment_GW']    = df['wind_potential_GW'] - df['wind_prod_GW']
df['curtailment_pct']   = df['curtailment_GW'] / df['wind_potential_GW'].clip(lower=1e-9) * 100
df['balance']           = df['baseload_GW'] + df['wind_prod_GW'] + df['pv_GW'] - df['elec_demand_GW'] - df['hp_elec_GW']

print("Wind capacity CH year 0: %.3f GW" % wind_cap_yr0)
print("HP capacity CH:          3.706 GW heat = 1.225 GW electricity")
print()
print("Wind curtailment summary:")
print("  Avg potential: %.3f GW" % df['wind_potential_GW'].mean())
print("  Avg actual:    %.3f GW" % df['wind_prod_GW'].mean())
print("  Curtailed:     %.1f%%" % df['curtailment_pct'].mean())
print()
print("HP operation:")
print("  Max elec:  %.4f GW" % df['hp_elec_GW'].max())
print("  Avg elec:  %.4f GW" % df['hp_elec_GW'].mean())
print("  t > 0:     %d / %d timesteps" % ((df['hp_elec_GW'] > 0.001).sum(), n_ts))
print("  t at max:  %d timesteps (>1.20 GW)" % (df['hp_elec_GW'] > 1.20).sum())
print()
print("Electricity balance max imbalance: %.8f GW" % df['balance'].abs().max())
print()

print("All 96 timesteps (year 0):")
print("%-4s  %-8s  %-8s  %-10s  %-8s  %-8s  %-10s  %-8s" % (
    "t", "demand", "baseld", "wind_prod", "wind_cf", "pv", "hp_elec", "curtail%"))
for i, row in df.iterrows():
    print("%-4d  %-8.3f  %-8.3f  %-10.3f  %-8.4f  %-8.3f  %-10.3f  %-8.1f" % (
        i, row['elec_demand_GW'], row['baseload_GW'], row['wind_prod_GW'],
        row['wind_cf'], row['pv_GW'], row['hp_elec_GW'], row['curtailment_pct']))
