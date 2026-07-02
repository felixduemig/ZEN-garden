import pandas as pd, numpy as np
RUN='outputs_CB_overnight/runC/Crystal_Ball'
def P(k,f='var_dict'): return pd.read_hdf(f'{RUN}/{f}.h5',k)
out=P('flow_conversion_output'); cap=P('capacity'); ml=P('max_load','param_dict')
lam=P('constraint_nodal_energy_balance','dual_dict'); dur=P('time_steps_operation_duration','param_dict').to_dict()
ov=P('opex_specific_variable','param_dict'); cf=P('conversion_factor','param_dict')
imp=P('flow_import'); shed=P('shed_demand')

def price(c,n,t):
    try: return float(lam.loc[(c,n,t)])/dur[t]
    except Exception: return None
def capv(tech,loc):
    v=cap[(cap.index.get_level_values('technology')==tech)&(cap.index.get_level_values('location')==loc)]
    return float(v.iloc[0]) if len(v) else 0.0
def mlv(tech,loc,t):
    v=ml[(ml.index.get_level_values('technology')==tech)&(ml.index.get_level_values('location')==loc)&(ml.index.get_level_values('time_operation')==t)]
    return float(v.iloc[0]) if len(v) else 1.0
def mc(tech,loc,t):
    g=cf[cf.index.get_level_values('technology')==tech]; c=0.0
    for carr in g.index.get_level_values('carrier').unique():
        a=float(g[g.index.get_level_values('carrier')==carr].iloc[0]); c+=a*(price(carr,loc,t) or 0.0)
    o=ov[(ov.index.get_level_values('technology')==tech)&(ov.index.get_level_values('location')==loc)]
    return c+(float(o.iloc[0]) if len(o) else 0.0)

def fingerprint(carrier, node, t):
    g=out[(out.index.get_level_values('carrier')==carrier)&(out.index.get_level_values('node')==node)&(out.index.get_level_values('time_operation')==t)]
    g=g[g.values>1e-6]
    rows=[]; n_atcap=0
    for tech in g.index.get_level_values('technology'):
        o=float(g[g.index.get_level_values('technology')==tech].iloc[0])
        avail=capv(tech,node)*mlv(tech,node,t); atcap=abs(o-avail)<1e-3*max(1,avail)
        n_atcap+=atcap; rows.append((tech,round(o,2),round(mc(tech,node,t),4),atcap))
    sh=shed[(shed.index.get_level_values('carrier')==carrier)&(shed.index.get_level_values('node')==node)&(shed.index.get_level_values('time_operation')==t)]
    shv=float(sh.iloc[0]) if len(sh) else 0.0
    return rows,n_atcap,len(rows),shv

cases=[('nuclear','electricity','ES',0,'FAIL'),
       ('photovoltaics','electricity','CZ',5,'PASS'),  # PV top step
       ('wind_offshore','electricity','FR',0,'PASS')]
for tech,carr,node,t,res in cases:
    rows,nat,ntot,shv=fingerprint(carr,node,t)
    pr=price(carr,node,t); mcs=[r[2] for r in rows] or [0]
    print('='*78)
    print(f'{tech} ({res}): {carr}@{node} step{t}  price={pr:.4f}  shed={shv:.3g}  suppliers_at_cap={nat}/{ntot}')
    print('   running-supplier mc: min=%.4f max=%.4f  scarcity(all_at_cap)=%s'%(min(mcs),max(mcs), nat==ntot and ntot>0))
    for r_ in sorted(rows,key=lambda z:-z[2]): print('     %-22s out=%8.2f mc=%8.4f at_cap=%s'%r_)

# ---- electrolysis: flexible LOAD on cheap FI electricity (input-side degeneracy) ----
print('='*78); print('electrolysis (FAIL): INPUT = electricity @ FI  (margin = lam_H2 - 1.901*lam_elec)')
for t in range(10):
    pe=price('electricity','FI',t); ph=price('hydrogen','FI',t)
    margin=(ph or 0)-1.90114*(pe or 0)
    # FI electricity supply at cap?
    rows,nat,ntot,shv=fingerprint('electricity','FI',t)
    print(f'  step{t}: lam_elec={pe:.4f} lam_H2={ph:.4f}  margin={margin:+.4f}  elec_suppliers_at_cap={nat}/{ntot} shed={shv:.2g}')
# FI electricity curtailment check: total avail renewable vs used
print('  -> low lam_elec at FI = cheap-electricity-surplus regime (renewables near floor).')
print('     Building electrolysis raises FI elec demand -> raises lam_elec -> margin shrinks (self-cannibalization on the INPUT).')
