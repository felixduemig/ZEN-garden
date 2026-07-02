import pandas as pd, numpy as np
RUN='outputs_CB_overnight/runC/Crystal_Ball'
def P(k,f='var_dict'): return pd.read_hdf(f'{RUN}/{f}.h5',k)
NODE='ES'; T=0
out=P('flow_conversion_output'); cap=P('capacity'); ml=P('max_load','param_dict')
lam=P('constraint_nodal_energy_balance','dual_dict'); dur=P('time_steps_operation_duration','param_dict').to_dict()
ov=P('opex_specific_variable','param_dict'); cf=P('conversion_factor','param_dict')

def capv(tech,loc):
    v=cap[(cap.index.get_level_values('technology')==tech)&(cap.index.get_level_values('location')==loc)]
    return float(v.iloc[0]) if len(v) else np.nan
def mlv(tech,loc,t):
    v=ml[(ml.index.get_level_values('technology')==tech)&(ml.index.get_level_values('location')==loc)&(ml.index.get_level_values('time_operation')==t)]
    return float(v.iloc[0]) if len(v) else np.nan
def mc(tech,loc,t):  # per-hour marginal cost = sum_in alpha*price_in + varopex
    g=cf[cf.index.get_level_values('technology')==tech]
    c=0.0
    for carr in g.index.get_level_values('carrier').unique():
        a=float(g[g.index.get_level_values('carrier')==carr].iloc[0])
        try: p=float(lam.loc[(carr,loc,t)])/dur[t]
        except Exception: p=0.0
        c+=a*p
    o=ov[(ov.index.get_level_values('technology')==tech)&(ov.index.get_level_values('location')==loc)]
    return c+(float(o.iloc[0]) if len(o) else 0.0)

elec=out[(out.index.get_level_values('carrier')=='electricity')&(out.index.get_level_values('node')==NODE)&(out.index.get_level_values('time_operation')==T)]
elec=elec[elec.values>1e-6]
price=float(lam.loc[('electricity',NODE,T)])/dur[T]
print(f'ES electricity per-hour price step0 = {price:.4f}')
print(f'{"tech":22s} {"output":>9s} {"avail_max":>10s} {"at_max?":>8s} {"marg_cost":>10s}')
for tech in elec.index.get_level_values('technology'):
    o=float(elec[elec.index.get_level_values('technology')==tech].iloc[0])
    avail=capv(tech,NODE)*mlv(tech,NODE,T)
    print(f'{tech:22s} {o:9.4f} {avail:10.4f} {str(abs(o-avail)<1e-3):>8s} {mc(tech,NODE,T):10.4f}')
print(f'\\n=> max generator marginal cost among running units, vs price {price:.4f}')
print('   ALL running units at availability max => SCARCITY vertex; price = scarcity rent > every marginal cost')
