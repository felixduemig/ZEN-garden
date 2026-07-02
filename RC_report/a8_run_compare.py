import pandas as pd, numpy as np
def load(run):
    R=f'outputs_CB_overnight/{run}/Crystal_Ball'
    nu=pd.read_hdf(f'{R}/dual_dict.h5','constraint_capacity_factor_conversion').reset_index(); nu.columns=['t','tech','node','nu']
    mu=pd.read_hdf(f'{R}/dual_dict.h5','constraint_technology_lifetime')
    ml=pd.read_hdf(f'{R}/param_dict.h5','max_load').reset_index(); ml.columns=['tech','loc','t','m']
    return nu,mu,ml
for t,n in [('nuclear','ES'),('electrolysis','FI')]:
    print('='*70); print(f'{t} @ {n}')
    for run in ['runA','runB','runC']:
        nu,mu,ml=load(run)
        s=nu[(nu.tech==t)&(nu.node==n)].merge(ml[(ml.tech==t)&(ml.loc==n)],on=['tech','t'],how='left')
        s['m']=s['m'].fillna(1.0)
        V=(s['m']*s['nu']).sum()
        nuvals=s.sort_values('t')['nu'].round(2).tolist()
        # lifetime dual
        try:
            md=mu[(mu.index.get_level_values('technology')==t)&(mu.index.get_level_values('location')==n)]
            muv=float(md.iloc[0])
        except Exception: muv=None
        print(f'  {run}: Sum_m*nu={V:9.3f}  mu_life={muv}  nu_per_step={nuvals}')
