"""Lead 3 + Lead 1: reproduce the reported operational RC from saved native duals,
check time-step weighting, conversion-carrier handling, scaling. Run C (clean)."""
import pandas as pd, numpy as np, h5py, json
from zen_garden.postprocess.results.results import Results

RUN = 'outputs_CB_overnight/runC/Crystal_Ball'
r = Results(RUN)
params = r.solution_loader.scenarios['none'].optimization_setup.parameters if False else None

# ---- raw native duals & params via pandas read_hdf -------------------------
def rd(fn, key):
    return pd.read_hdf(f'{RUN}/{fn}.h5', key)

nu = rd('dual_dict','constraint_capacity_factor_conversion')          # (time_op,tech,node)
dur = rd('param_dict','time_steps_operation_duration')               # duration weights
ml  = rd('param_dict','max_load')
print('dur index names', dur.index.names, 'shape', dur.shape)
print(dur.head(12))
print('max_load index names', ml.index.names, 'shape', ml.shape)
print(ml.head())

# discount / system
with open(f'{RUN}/system.json') as f: system = json.load(f)
print('interval_between_years', system.get('interval_between_years'))
print('reference_year', system.get('reference_year'), 'optimized_years', system.get('optimized_years'))
