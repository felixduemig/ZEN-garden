import pandas as pd, numpy as np
RUN='outputs_CB_overnight/runC/Crystal_Ball'
def P(k,f='var_dict'): return pd.read_hdf(f'{RUN}/{f}.h5',k)
nu = P('constraint_capacity_factor_conversion','dual_dict').reset_index(); nu.columns=['t','tech','node','nu']
ml = P('max_load','param_dict').reset_index(); ml.columns=['tech','loc','t','m']
dur= P('time_steps_operation_duration','param_dict').to_dict()
lam= P('constraint_nodal_energy_balance','dual_dict')

# per-step contribution m_t * nu_t for nuclear ES
t='nuclear'; n='ES'
sub=nu[(nu.tech==t)&(nu.node==n)].merge(ml[(ml.tech==t)&(ml.loc==n)],left_on=['tech','t'],right_on=['tech','t'],how='left')
sub['m']=sub['m'].fillna(1.0); sub['contrib']=sub['m']*sub['nu']
sub['lam_ph']=sub['t'].map(lambda tt: float(lam.loc[('electricity','ES',tt)])/dur[tt])
print('=== nuclear ES per-step:  m*nu contribution and per-hour elec price')
print(sub[['t','m','nu','contrib','lam_ph']].round(4).to_string(index=False))
print('TOTAL m*nu =', round(sub['contrib'].sum(),3))

# NGT marginal cost: natural_gas price (lambda) * conversion + varopex
ngt_conv = P('conversion_factor','param_dict')
g=ngt_conv[ngt_conv.index.get_level_values('technology')=='natural_gas_turbine']
print('\\nNGT conversion carriers:', g.index.get_level_values('carrier').unique().tolist())
for c in g.index.get_level_values('carrier').unique():
    print('  alpha', c, round(float(g[g.index.get_level_values('carrier')==c].iloc[0]),4))
ov=P('opex_specific_variable','param_dict')
print('NGT varopex', float(ov[ov.index.get_level_values('technology')=='natural_gas_turbine'].iloc[0]))

# per-hour price of electricity and natural_gas at ES across steps
print('\\n=== ES per-hour prices (lambda/dur):')
for c in ['electricity','natural_gas']:
    vals=[round(float(lam.loc[(c,'ES',tt)])/dur[tt],4) if (c,'ES',tt) in lam.index else None for tt in range(10)]
    print(f'  {c:14s}', vals)

# electricity per-hour price across ALL nodes at step 0 (detect congestion/islanding)
print('\\n=== electricity per-hour price across nodes, step 0:')
nodes=sorted(set(lam.index.get_level_values('node')))
ph={nd: round(float(lam.loc[('electricity',nd,0)])/dur[0],4) for nd in nodes if ('electricity',nd,0) in lam.index}
print(' ', ph)
