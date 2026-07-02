import pandas as pd, numpy as np
RUN='outputs_CB_overnight/runC/Crystal_Ball'
nu = pd.read_hdf(f'{RUN}/dual_dict.h5','constraint_capacity_factor_conversion').reset_index()
nu.columns=['t','tech','node','nu']
lam= pd.read_hdf(f'{RUN}/dual_dict.h5','constraint_nodal_energy_balance')  # (carrier,node,t)
dur= pd.read_hdf(f'{RUN}/param_dict.h5','time_steps_operation_duration').to_dict()
ov = pd.read_hdf(f'{RUN}/param_dict.h5','opex_specific_variable')  # (tech,loc,t)

def lget(carrier,node,t):
    try: return float(lam.loc[(carrier,node,t)])
    except Exception: return 0.0
def ovget(tech,node,t):
    try: return float(ov.loc[(tech,node,t)])
    except Exception: return 0.0

# tech: (ref_carrier, [(in_carrier, alpha)])
specs={'nuclear':('electricity',[('uranium',2.94694)]),
       'electrolysis':('hydrogen',[('electricity',1.90114)]),
       'photovoltaics':('electricity',[]),
       'wind_offshore':('electricity',[])}
nodes={'nuclear':'ES','electrolysis':'FI','photovoltaics':'CZ','wind_offshore':'FR'}
for tech,(refc,ins) in specs.items():
    n=nodes[tech]
    print(f'=== {tech} @ {n} (ref={refc}) ===')
    sub=nu[(nu.tech==tech)&(nu.node==n)].sort_values('t')
    rows=[]
    for _,row in sub.iterrows():
        t=int(row['t']); nuv=float(row['nu'])
        d=dur[t]
        cand = lget(refc,n,t) - sum(a*lget(c,n,t) for c,a in ins) - d*ovget(tech,n,t)
        cand_pos=max(0.0,cand)
        rows.append((t,d,round(lget(refc,n,t),3),round(nuv,4),round(cand_pos,4),round(nuv-cand_pos,5)))
    print('   t  dur   lam_ref     nu     nu_from_lam   diff')
    for r_ in rows: print('  ',r_)
    err=max(abs(a[3]-a[4]) for a in rows)
    print('   max|nu - nu_from_lambda| =', round(err,5))
