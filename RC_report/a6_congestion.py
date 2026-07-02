import pandas as pd, numpy as np
RUN='outputs_CB_overnight/runC/Crystal_Ball'
def P(k,f='var_dict'): return pd.read_hdf(f'{RUN}/{f}.h5',k)

# NGT capacity at ES vs its output (is it at cap?)
cap=P('capacity')
print('cap idx',cap.index.names)
for tech in ['natural_gas_turbine','wind_onshore','reservoir_hydro','biomass_plant','nuclear']:
    try:
        v=cap[(cap.index.get_level_values('technology')==tech)&(cap.index.get_level_values('location')=='ES')]
        print(f'  cap {tech:20s} ES =', round(float(v.iloc[0]),4))
    except Exception as e: print(tech,'err',str(e)[:40])

out=P('flow_conversion_output')
print('\\nNGT ES output by step (vs cap):')
g=out[(out.index.get_level_values('technology')=='natural_gas_turbine')&(out.index.get_level_values('node')=='ES')&(out.index.get_level_values('carrier')=='electricity')]
print('  ', [round(float(g[g.index.get_level_values('time_operation')==t].iloc[0]),4) if len(g[g.index.get_level_values('time_operation')==t]) else 0 for t in range(10)])

# transport flow into ES at step 0
ft=P('flow_transport')
print('\\ntransport flow idx', ft.index.names)
# edges into/out of ES
edges=sorted(set(ft.index.get_level_values('edge')))
es_edges=[e for e in edges if 'ES' in e]
print('edges touching ES:', es_edges)
for e in es_edges:
    vals=[round(float(ft.loc[(e,t)]),4) if (e,t) in ft.index else None for t in range(10)]
    print(f'  flow {e}:', vals)

# transport capacity on those edges
print('\\ntransport capacities (edge):')
for e in es_edges:
    try:
        v=cap[(cap.index.get_level_values('location')==e)]
        if len(v): print(f'  cap {e} =', round(float(v.iloc[0]),4))
    except Exception: pass

# congestion dual: constraint_capacity_factor_transport for ES edges step0
nut=P('constraint_capacity_factor_transport','dual_dict')
print('\\ntransport cap-factor dual idx', nut.index.names)
for e in es_edges:
    try:
        sub=nut[nut.index.get_level_values('edge')==e] if 'edge' in nut.index.names else None
        if sub is not None and len(sub):
            print(f'  {e}: nonzero steps', [int(s) for s in sub[abs(sub.values)>1e-9].index.get_level_values('time_operation')][:10])
    except Exception as ex: print(e,'err',str(ex)[:40])
