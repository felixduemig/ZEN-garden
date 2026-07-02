import pandas as pd, numpy as np
r=0.05; dy=2
REP={ # run -> (tech,node)-> reported operational ratio
 'runA':{('nuclear','ES'):0.032001,('electrolysis','FI'):0.123564},
 'runB':{('nuclear','ES'):0.11697,('electrolysis','FI'):0.147697},
 'runC':{('nuclear','ES'):0.022584,('electrolysis','FI'):0.097383}}
dep={'nuclear':55.0,'electrolysis':27.0}
for run in ['runA','runB','runC']:
    R=f'outputs_CB_overnight/{run}/Crystal_Ball'
    nu=pd.read_hdf(f'{R}/dual_dict.h5','constraint_capacity_factor_conversion').reset_index(); nu.columns=['t','tech','node','nu']
    ml=pd.read_hdf(f'{R}/param_dict.h5','max_load').reset_index(); ml.columns=['tech','loc','t','m']
    capexp=pd.read_hdf(f'{R}/param_dict.h5','capex_specific_conversion')
    ofixp =pd.read_hdf(f'{R}/param_dict.h5','opex_specific_fixed')
    dur=pd.read_hdf(f'{R}/param_dict.h5','time_steps_operation_duration').to_dict()
    print('======',run)
    for (t,n),rep in REP[run].items():
        lt=dep[t]; af=((1+r)**lt*r)/((1+r)**lt-1); scaling=af*1.0
        cs=float(np.squeeze(capexp.xs(t,level='technology').xs(n,level='node').values).ravel()[0])
        ofx=float(np.squeeze(ofixp.xs(t,level='technology').xs(n,level='location').values).ravel()[0])
        s=nu[(nu.tech==t)&(nu.node==n)].merge(ml[(ml.tech==t)&(ml.loc==n)],on=['tech','t'],how='left')
        nmiss=s['m'].isna().sum(); s['m']=s['m'].fillna(1.0)
        V=(s['m']*s['nu']).sum()
        ratio=1-(V-ofx)/(scaling*cs)
        print(f'  {t:13s}{n}: V={V:9.3f} m_missing={nmiss} ofix={ofx:8.3f} cs={cs:9.2f} -> ratio={ratio:+.5f} (reported {rep:.5f}) match={abs(ratio-rep)<2e-3}')
