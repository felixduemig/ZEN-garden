"""SINGLE-SOLVE degeneracy flag prototype (read-only, runC).
For a candidate (tech,node): for each of its value hours, decide if the node has
NO interior price-setter (no local gen strictly interior, no uncongested active
import, no shedding) -> flagged hour. Report the VALUE-WEIGHTED flagged share
(Sum_flagged max_load*nu / Sum_all). High share => RC is a lower bound (degenerate).
Compare against known PASS/FAIL labels."""
import numpy as np, pandas as pd
F="outputs_CB_overnight/runC/Crystal_Ball/"
def s(f,k):
    d=pd.read_hdf(F+f,k); return d if isinstance(d,pd.Series) else d.iloc[:,0]
OUT=s("var_dict.h5","flow_conversion_output")
OUT=OUT[OUT.index.get_level_values("carrier")=="electricity"]
CAP=s("var_dict.h5","capacity"); CAP=CAP[CAP.index.get_level_values("capacity_type")=="power"]
ML =s("param_dict.h5","max_load")
FT =s("var_dict.h5","flow_transport")
CFT=s("dual_dict.h5","constraint_capacity_factor_transport")
NU =s("dual_dict.h5","constraint_capacity_factor_conversion")
try: SHED=s("var_dict.h5","shed_demand"); SHED=SHED[SHED.index.get_level_values("carrier")=="electricity"]
except Exception: SHED=None
HOURS=range(10); TOL=0.01

def cap_of(tech,loc):
    c=CAP[(CAP.index.get_level_values("technology")==tech)&(CAP.index.get_level_values("location")==loc)]
    return float(c.iloc[0]) if len(c) else np.nan
def maxload(tech,loc,t):
    m=ML[(ML.index.get_level_values("technology")==tech)&(ML.index.get_level_values("location")==loc)&(ML.index.get_level_values("time_operation")==t)]
    return float(m.iloc[0]) if len(m) else 1.0

def interior_setter(node,t):
    # 1) any local electricity producer strictly interior?
    prod=OUT[(OUT.index.get_level_values("node")==node)&(OUT.index.get_level_values("time_operation")==t)]
    for idx,fl in prod.items():
        tech=idx[OUT.index.names.index("technology")]; fl=float(fl)
        cp=cap_of(tech,node); av=maxload(tech,node,t)*cp if cp==cp else np.nan
        if av and av>1e-9 and TOL*av < fl < (1-TOL)*av:
            return True,f"gen {tech} interior {fl:.2f}/{av:.2f}"
    # 2) any import line uncongested & active (pins price to neighbour)?
    for ed in FT.index.get_level_values("edge").unique():
        if not ed.endswith(f"-{node}"): continue
        key=("power_line",ed,t)
        if key not in FT.index: continue
        fl=float(FT.loc[key]); cp=cap_of("power_line",ed)
        if cp==cp and cp>1e-9 and TOL*cp < fl < (1-TOL)*cp:
            return True,f"import {ed} uncongested {fl:.2f}/{cp:.2f}"
    # 3) shedding?
    if SHED is not None:
        sh=SHED[(SHED.index.get_level_values("node")==node)&(SHED.index.get_level_values("time_operation")==t)]
        if len(sh) and float(sh.iloc[0])>1e-6:
            return True,"shedding (lambda=VOLL)"
    return False,"NO interior setter -> price floats"

def flag_case(tech,node,label):
    vals={}; flagged={}
    for t in HOURS:
        nu=NU[(NU.index.get_level_values("technology")==tech)&(NU.index.get_level_values("node")==node)&(NU.index.get_level_values("time_operation")==t)]
        nuv=float(nu.iloc[0]) if len(nu) else 0.0
        v=maxload(tech,node,t)*max(nuv,0.0)
        vals[t]=v
        deg,_=interior_setter(node,t); flagged[t]=not deg
    tot=sum(vals.values()) or 1e-9
    share=sum(v for t,v in vals.items() if flagged[t])/tot
    topt=max(vals,key=vals.get)
    print(f"{tech:20} @ {node:3} [{label:4}] flagged_value_share = {100*share:5.1f}%   "
          f"(top value hour h{topt}={100*vals[topt]/tot:.0f}%, flagged={flagged[topt]})")
    return share

print("=== single-solve degeneracy flag vs known labels ===")
for tech,node,label in [("nuclear","ES","FAIL"),("electrolysis","FI","FAIL"),
                        ("nuclear","FR","PASS"),("photovoltaics","CZ","PASS"),
                        ("wind_offshore","FR","PASS"),("photovoltaics","NO","PASS")]:
    try: flag_case(tech,node,label)
    except Exception as e: print(f"{tech}@{node}: ERROR {e}")
