"""Is the storage discharge INTERIOR (0 < discharge < power_cap) or itself AT CAP?
Only an interior source pins the price. Check ES (FAIL) vs FR (PASS) per hour."""
import numpy as np, pandas as pd
F="outputs_CB_overnight/runC/Crystal_Ball/"
def s(f,k):
    d=pd.read_hdf(F+f,k); return d if isinstance(d,pd.Series) else d.iloc[:,0]
DIS=s("var_dict.h5","flow_storage_discharge")
CAP=s("var_dict.h5","capacity"); CAP=CAP[CAP.index.get_level_values("capacity_type")=="power"]
FT=s("var_dict.h5","flow_transport")
OUT=s("var_dict.h5","flow_conversion_output"); OUT=OUT[OUT.index.get_level_values("carrier")=="electricity"]
def capp(tech,loc):
    c=CAP[(CAP.index.get_level_values("technology")==tech)&(CAP.index.get_level_values("location")==loc)]
    return float(c.iloc[0]) if len(c) else np.nan

def verdict(node):
    print(f"\n===== {node} =====")
    for t in range(10):
        setters=[]
        # storage discharge interior?
        dd=DIS[(DIS.index.get_level_values("node")==node)&(DIS.index.get_level_values("time_operation")==t)]
        for idx,fl in dd.items():
            fl=float(fl)
            if fl<=1e-6: continue
            tech=idx[DIS.index.names.index("technology")]
            cp=capp(tech,node); util=100*fl/cp if cp==cp and cp>0 else np.nan
            if cp==cp and 0.01*cp<fl<0.99*cp:
                setters.append(f"{tech}({util:.0f}%)")
        # uncongested import?
        for ed in FT.index.get_level_values("edge").unique():
            if not ed.endswith(f"-{node}"): continue
            key=("power_line",ed,t)
            if key not in FT.index: continue
            fl=float(FT.loc[key]); cp=capp("power_line",ed)
            if fl>1e-6 and cp==cp and 0.01*cp<fl<0.99*cp:
                setters.append(f"imp:{ed}({100*fl/cp:.0f}%)")
        # detail of storage at-cap (for context)
        atcap=[]
        for idx,fl in dd.items():
            fl=float(fl)
            if fl<=1e-6: continue
            tech=idx[DIS.index.names.index("technology")]
            cp=capp(tech,node); 
            if cp==cp and fl>=0.99*cp: atcap.append(f"{tech}@cap")
        flag = "DEGENERATE" if not setters else "ok"
        print(f"  h{t}: interior setters = {setters if setters else 'NONE'}   "
              f"{'['+','.join(atcap)+']' if atcap else ''}   -> {flag}")
verdict("ES"); verdict("FR")
