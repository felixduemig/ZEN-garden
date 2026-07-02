"""Diagnostic: per hour, list ALL electricity sources at a node (conversion producers,
storage discharge, imports) with utilisation, and whether ANY runs strictly interior.
Tests whether nuclear@FR (PASS) really has no interior price-setter (global effect)
or my flag had a capacity-lookup bug."""
import numpy as np, pandas as pd
F="outputs_CB_overnight/runC/Crystal_Ball/"
def s(f,k):
    d=pd.read_hdf(F+f,k); return d if isinstance(d,pd.Series) else d.iloc[:,0]
OUT=s("var_dict.h5","flow_conversion_output"); OUT=OUT[OUT.index.get_level_values("carrier")=="electricity"]
CAP=s("var_dict.h5","capacity")
print("capacity index names:", list(CAP.index.names))
print("capacity_type values:", list(pd.unique(CAP.index.get_level_values(CAP.index.names[1]))[:6]))
DIS=s("var_dict.h5","flow_storage_discharge")
ML=s("param_dict.h5","max_load")
FT=s("var_dict.h5","flow_transport")
def cap_of(tech,loc):
    c=CAP[(CAP.index.get_level_values("technology")==tech)&(CAP.index.get_level_values("location")==loc)]
    # take power capacity if capacity_type present
    if "capacity_type" in CAP.index.names:
        c=c[c.index.get_level_values("capacity_type")=="power"]
    return float(c.iloc[0]) if len(c) else np.nan
def maxload(tech,loc,t):
    m=ML[(ML.index.get_level_values("technology")==tech)&(ML.index.get_level_values("location")==loc)&(ML.index.get_level_values("time_operation")==t)]
    return float(m.iloc[0]) if len(m) else 1.0

def dump(node, hours):
    for t in hours:
        prod=OUT[(OUT.index.get_level_values("node")==node)&(OUT.index.get_level_values("time_operation")==t)]
        print(f"\n--- {node} h{t} ---")
        any_int=False
        for idx,fl in prod.items():
            tech=idx[OUT.index.names.index("technology")]; fl=float(fl)
            if fl<1e-6: continue
            cp=cap_of(tech,node); av=maxload(tech,node,t)*cp if cp==cp else np.nan
            util=100*fl/av if av==av and av>0 else np.nan
            interior = (av==av and av>1e-9 and 0.01*av<fl<0.99*av)
            any_int = any_int or interior
            print(f"   gen {tech:24} out {fl:8.3f}  maxL*cap {av if av==av else float('nan'):8.3f}  util {util:6.1f}%  {'INTERIOR' if interior else ''}")
        # storage discharge into electricity
        if DIS is not None:
            dd=DIS[(DIS.index.get_level_values("node")==node)&(DIS.index.get_level_values("time_operation")==t)]
            for idx,fl in dd.items():
                fl=float(fl)
                if fl>1e-6:
                    tech=idx[DIS.index.names.index("technology")]
                    print(f"   STO {tech:24} discharge {fl:8.3f}  (storage = interior price-setter)")
                    any_int=True
        # imports
        for ed in FT.index.get_level_values("edge").unique():
            if not ed.endswith(f"-{node}"): continue
            key=("power_line",ed,t)
            if key not in FT.index: continue
            fl=float(FT.loc[key]); cp=cap_of("power_line",ed)
            if fl>1e-6:
                util=100*fl/cp if cp==cp and cp>0 else np.nan
                unc = cp==cp and 0.01*cp<fl<0.99*cp
                print(f"   imp {ed:24} flow {fl:8.3f}  cap {cp:8.3f}  util {util:6.1f}%  {'UNCONGESTED->pins' if unc else 'at cap'}")
                if unc: any_int=True
        print(f"   => interior price-setter present: {any_int}")

print("="*60,"\nES (FAIL) value hour h0 + a couple others")
dump("ES",[0,2,3])
print("\n"+"="*60,"\nFR (PASS) — its value hours")
dump("FR",[0,1,2])
