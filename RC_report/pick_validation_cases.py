"""Pick 5 ROBUST buildable_rc conversion cases for the +-1% CB validation:
low perturbation swing (clean vs pert), price-taker techs, mid-range ratio, headroom."""
import pandas as pd, numpy as np
def load(run):
    d=pd.read_csv(f'outputs_CB_overnight/{run}/Crystal_Ball/capacity_addition_analysis_conversion.csv')
    return d
C=load('runC'); B=load('runB')
key=['set_technologies','set_location']
m=C.merge(B[key+['ratio_reduction_operational']],on=key,suffixes=('_C','_B'))
m['swing']=(m['ratio_reduction_operational_C']-m['ratio_reduction_operational_B']).abs()
# filters: buildable_rc + reliable + unbuilt + finite headroom + sensible ratio
f=m[(m.case=='buildable_rc')&(m.rc_reliable==True)&(m.value==0)
    &(m.ratio_reduction_operational_C.between(0.03,0.45))
    &(m.swing<0.01)]
# prefer robust price-taker techs (variable renewables, well-behaved)
prefer={'photovoltaics','wind_onshore','wind_offshore','run-of-river_hydro','reservoir_hydro','biomass_plant'}
f=f.copy(); f['is_pref']=f.set_technologies.isin(prefer)
# headroom: capacity_ceiling finite&>0 (not inf, not at limit) OR inf is fine too
f['ceil_ok']=(f.capacity_ceiling>0)
f=f[f.ceil_ok]
f=f.sort_values(['is_pref','swing'],ascending=[False,True])
cols=['set_technologies','set_location','capex_specific_input_units','ratio_reduction_operational_C',
      'ratio_reduction_operational_B','swing','capacity_ceiling','rc_capex_equivalent_operational_input_units']
pd.set_option('display.width',220)
print('Top robust candidates (low swing, price-taker, mid ratio):')
print(f[cols].head(25).to_string(index=False))
# pick a diverse 5: distinct techs, distinct nodes where possible
picked=[]; seen_tn=set(); seen_node=set()
for _,r in f.iterrows():
    t,n=r.set_technologies,r.set_location
    if (t,n) in seen_tn: continue
    # prefer diversity of tech then node
    if t in [p[0] for p in picked] and len(picked)>=2: continue
    picked.append((t,n,2050,0,round(float(r.ratio_reduction_operational_C),6),
                   round(float(r.capacity_ceiling),3)))
    seen_tn.add((t,n))
    if len(picked)==5: break
print('\nPICKED 5:')
for p in picked: print('  ',p)
