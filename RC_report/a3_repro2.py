import pandas as pd, numpy as np, json
RUN='outputs_CB_overnight/runC/Crystal_Ball'
def rd(key): return pd.read_hdf(f'{RUN}/{key}')
nu  = pd.read_hdf(f'{RUN}/dual_dict.h5','constraint_capacity_factor_conversion').reset_index()
nu.columns=['time_operation','technology','node','dual']
dur = pd.read_hdf(f'{RUN}/param_dict.h5','time_steps_operation_duration').to_dict()
ml  = pd.read_hdf(f'{RUN}/param_dict.h5','max_load').reset_index()
ml.columns=['technology','location','time_operation','m']
dep = pd.read_hdf(f'{RUN}/param_dict.h5','depreciation_time')
capexp = pd.read_hdf(f'{RUN}/param_dict.h5','capex_specific_conversion')
ofixp  = pd.read_hdf(f'{RUN}/param_dict.h5','opex_specific_fixed')
r=0.05; dy=2
print('capex param idx', capexp.index.names)
print('ofix param idx', ofixp.index.names)

def capex_of(t,n):
    s=capexp.xs(t,level='technology')
    for lvl in ['location','node']:
        if lvl in s.index.names:
            s=s.xs(n,level=lvl); break
    return float(np.squeeze(s.values).ravel()[0])
def ofix_of(t,n):
    s=ofixp.xs(t,level='technology')
    s=s.xs(n,level='location')
    return float(np.squeeze(s.values).ravel()[0])

REP={('nuclear','ES'):0.022584,('electrolysis','FI'):0.097383,
     ('photovoltaics','CZ'):0.047513,('wind_offshore','FR'):0.11182}
for (t,n),rep in REP.items():
    lt=float(dep.loc[t]); af=((1+r)**lt*r)/((1+r)**lt-1)
    df0=1.0  # iv=1, single year y=0 -> (1/(1+r))^0 = 1
    scaling=af*df0
    cs=capex_of(t,n); ofx=ofix_of(t,n)
    sub=nu[(nu.technology==t)&(nu.node==n)].merge(
        ml[(ml.technology==t)&(ml.location==n)],on=['technology','time_operation'],how='left')
    sub['m']=sub['m'].fillna(1.0)
    V_noW=(sub['m']*sub['dual']).sum()
    V_W  =(sub['m']*sub['dual']*sub['time_operation'].map(dur)).sum()
    # operational value net of fixed opex (single pay-year y=0, delta=df0=1)
    for lab,V in [('noW',V_noW),('W',V_W)]:
        ev = V - ofx*df0
        ratio = 1 - ev/(scaling*cs)
        print(f'{t:13s}{n} [{lab}] V={V:12.3f} ofix={ofx:8.3f} af={af:.4f} scaling={scaling:.4f} cs={cs:9.2f} -> ratio={ratio:+.5f}  (reported {rep:.5f})  match={abs(ratio-rep)<1e-3}')
