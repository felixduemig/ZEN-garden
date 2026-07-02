"""Reproduce reported operational RC from saved native duals, two weightings."""
import pandas as pd, numpy as np, json

def rd(RUN, fn, key): return pd.read_hdf(f'{RUN}/{fn}.h5', key)

RUN='outputs_CB_overnight/runC/Crystal_Ball'
nu  = rd(RUN,'dual_dict','constraint_capacity_factor_conversion')   # (time_op,tech,node)
dur = rd(RUN,'param_dict','time_steps_operation_duration')          # (time_op)
ml  = rd(RUN,'param_dict','max_load')                               # (tech,loc,time_op)
dep = rd(RUN,'param_dict','depreciation_time')                      # (tech)
try:
    ofix = rd(RUN,'param_dict','opex_specific_fixed')
except Exception as e:
    ofix=None; print('no opex_specific_fixed', e)
with open(f'{RUN}/system.json') as f: system=json.load(f)

# discount rate
import h5py
with h5py.File(f'{RUN}/param_dict.h5','r') as f:
    dr = float(np.array(f['discount_rate']['table'])[0][-1]) if 'discount_rate' in f else None
print('discount_rate raw lookup:', dr)
# fallback: read attributes
r = dr if dr is not None else 0.06
dy = int(system['interval_between_years'])   # 2
# single optimized year -> years=[0]; last_year_entire_horizon: build from horizon
# For single-year run, scaling = af * discount_factors[0]; discount_factors[0] with iv:
years=[0]; first_year=0
# entire horizon last year:
n_entire = system.get('optimized_years',1)
# emulate energy_system discount factor: for the only year, y==last_entire? if reference covers dy yrs
last_year_entire = 0   # single year run; will test both iv=1 and iv=dy
ml = ml.reset_index()
ml.columns = list(ml.index.names)+['m'] if False else ['technology','location','time_operation','m']
nu = nu.reset_index(); nu.columns=['time_operation','technology','node','dual']
durd = dur.to_dict()

REPORTED = {('nuclear','ES'):125.990437, ('electrolysis','FI'):56.134354,
            ('photovoltaics','CZ'):15.060872, ('wind_offshore','FR'):213.708236*0+213.39408*0+215.39408}
# capex input units
capex = {('nuclear','ES'):5578.678491,('electrolysis','FI'):576.42823,
         ('photovoltaics','CZ'):316.985488,('wind_offshore','FR'):1926.256275}

def dep_of(t):
    return float(np.squeeze(dep.xs(t, level='technology').values)) if 'technology' in dep.index.names else float(dep.loc[t])

# fraction_year for input-units conversion: RC_input_units = RC_model / fraction_year
# We'll instead match model-units by also dividing reported by ... actually reported is input_units.
# Get fraction_year from results helper later; here compare RATIO instead (dimensionless), which
# is independent of fraction_year: ratio = RC_input/capex_input = RC_model/capex_model.
RATIO_REPORTED={('nuclear','ES'):0.022584,('electrolysis','FI'):0.097383,
                ('photovoltaics','CZ'):0.047513,('wind_offshore','FR'):0.11182}

for (t,n) in REPORTED:
    lt = dep_of(t)
    af = ((1.0+r)**lt * r)/((1.0+r)**lt-1.0)
    # pay_years: single year -> just [0]; n_periods = floor(lt/dy)>=1
    # discount_factors[0]: iv loop
    for iv_label, iv in [('iv=1',1),('iv=dy',dy)]:
        df0 = sum((1.0/(1.0+r))**(dy*0+i) for i in range(iv))
        scaling = af*df0
        sub_nu = nu[(nu.technology==t)&(nu.node==n)]
        sub_ml = ml[(ml.technology==t)&(ml.location==n)]
        mrg = sub_nu.merge(sub_ml,left_on=['technology','node','time_operation'],
                           right_on=['technology','location','time_operation'],how='left')
        mrg['m']=mrg['m'].fillna(1.0)
        # ofix
        ofx=0.0
        if ofix is not None:
            try:
                of_s=ofix
                idx_names=of_s.index.names
                # locate (t, n)
                sel=of_s
                ofx=float(np.squeeze(of_s.xs((t,n),level=[i for i,nm in enumerate(idx_names) if nm in('technology','location')]).values)) if False else 0.0
            except Exception:
                ofx=0.0
        V_noW = (mrg['m']*mrg['dual']).sum()
        V_W   = (mrg['m']*mrg['dual']*mrg['time_operation'].map(durd)).sum()
        cs=capex[(t,n)]
        # ratio = RC/capex = 1 - V/(scaling*capex)
        ratio_noW = 1 - V_noW/(scaling*cs)
        ratio_W   = 1 - V_W/(scaling*cs)
        if iv_label=='iv=1':
            print(f'{t:14s}{n}: lt={lt:.1f} af={af:.4f} df0={df0:.4f} scaling={scaling:.4f}')
        print(f'    [{iv_label}] V_noW={V_noW:11.3f} ratio_noW={ratio_noW:+.5f} | V_W={V_W:13.1f} ratio_W={ratio_W:+.4f} | reported_ratio={RATIO_REPORTED[(t,n)]:.5f}')
