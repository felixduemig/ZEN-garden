"""Debug + retry: PV CF sweep (diagnose the FAIL), GT fixed-opex (clean),
GT var-opex with the correct time x node opex_specific_variable format."""
import os, json, shutil
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
DS   = os.path.join(BASE, "6_showcase_countries")
CONV = os.path.join(DS, "set_technologies", "set_conversion_technologies")
BOUT = os.path.join(BASE, "outputs_showcase_storage_only", "6_showcase_countries")
ROOT = os.path.join(BASE, "outputs_showcase_levers2", datetime.now().strftime("%H%M%S")); os.makedirs(ROOT, exist_ok=True)
NODES = ["AT","CH","DE","FR","IT"]; YEARS = [2025,2026,2027]
r, lt = 0.06, 30; af = ((1+r)**lt*r)/((1+r)**lt-1)

conv = pd.read_csv(os.path.join(BOUT, "capacity_addition_analysis_conversion.csv"))
def rc(t,n):
    row=conv[(conv.set_technologies==t)&(conv.set_location==n)&(conv.set_time_steps_yearly==0)].iloc[0]
    return float(row["rc_capex_equivalent_operational_input_units"]), float(row["capex_specific_input_units"])
RC_pv,capex_pv=rc("photovoltaics","DE"); opexf_pv=12.0
RC_gt,capex_gt=rc("natural_gas_turbine","FR"); opexf_gt,opexv_gt=22.0,2.9
nu=pd.read_hdf(os.path.join(BOUT,"dual_dict.h5"),"constraint_capacity_factor_conversion")
dur=pd.read_hdf(os.path.join(BOUT,"param_dict.h5"),"time_steps_operation_duration")
gt=nu[(nu.index.get_level_values("technology")=="natural_gas_turbine")&(nu.index.get_level_values("node")=="FR")].reset_index()
gt.columns=["t","tech","node","nu"]; y0=gt[(gt.t<24)&(gt.nu.abs()>1e-9)]
E=float((0.93*dur.loc[y0.t.values].values).sum())
eps_pv=RC_pv/(capex_pv-RC_pv+opexf_pv/af); dfo_gt=af*RC_gt; dvo_gt=af*RC_gt/E
eps_pv_noopex=RC_pv/(capex_pv-RC_pv)
print(f"af={af:.5f} E={E:.1f} | eps_pv(with opex)={eps_pv*100:.2f}% eps_pv(no opex)={eps_pv_noopex*100:.2f}% | dvo_gt={dvo_gt:.4f} dfo_gt={dfo_gt:.3f}",flush=True)

def cfg():
    return {"solver":{"name":"gurobi","save_duals":False,"save_reduced_costs":False,"use_scaling":0,
            "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
def run_built(t,n,tag):
    out=os.path.join(ROOT,tag); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w")); run(config=tmp,dataset=DS,folder_output=out)
    d=pd.read_csv(os.path.join(out,"6_showcase_countries","capacity_addition_analysis.csv"))
    row=d[(d.set_technologies==t)&(d.set_capacity_types=="power")&(d.set_location==n)&(d.set_time_steps_yearly==0)]
    return float(row["value"].iloc[0]) if len(row) else np.nan

class ov:
    def __init__(s,path,df): s.path,s.df=path,df
    def __enter__(s):
        s.bak=s.path+".bak"; s.existed=os.path.isfile(s.path)
        if s.existed: shutil.copy2(s.path,s.bak)
        s.df.to_csv(s.path,index=False)
    def __exit__(s,*a):
        if s.existed: shutil.move(s.bak,s.path)
        elif os.path.isfile(s.path): os.remove(s.path)

def grid(col,default,node,value):
    return pd.DataFrame([[n,y,(value if n==node else default)] for n in NODES for y in YEARS],columns=["node","year",col])
def maxload_scaled(node,factor):
    p=os.path.join(CONV,"photovoltaics","max_load.csv"); m=pd.read_csv(p); m[node]=m[node]*factor; return ov(p,m)
def opexvar_timegrid(node,value):  # time x node, like max_load
    p=os.path.join(CONV,"photovoltaics","max_load.csv"); t=pd.read_csv(p)["time"]
    df=pd.DataFrame({"time":t});
    for n in NODES: df[n]=(value if n==node else opexv_gt)
    return ov(os.path.join(CONV,"natural_gas_turbine","opex_specific_variable.csv"),df)

# --- 1) PV CF sweep: when does PV@DE actually build? ---
print("\n=== PV@DE CF sweep ===",flush=True)
for fac in [1.15, 1.18, 1.21, 1.25, 1.30, 1.45]:
    with maxload_scaled("DE",fac):
        b=run_built("photovoltaics","DE",f"sweep_cf_{int(fac*100)}")
    print(f"  CF x{fac:.2f} (+{(fac-1)*100:.0f}%) -> built={b:.4g}",flush=True)

# --- 2) GT fixed-opex (node,year grid; should PASS) ---
print("\n=== GT fixed-opex ===",flush=True)
res={}
for lab,k in [("build",1.01),("nobuild",0.99)]:
    with ov(os.path.join(CONV,"natural_gas_turbine","opex_specific_fixed.csv"),grid("opex_specific_fixed",opexf_gt,"FR",opexf_gt-k*dfo_gt)):
        res[lab]=run_built("natural_gas_turbine","FR",f"gtfix_{lab}")
print(f"  build={res['build']:.4g} nobuild={res['nobuild']:.4g} -> {'PASS' if res['build']>1e-3 and not res['nobuild']>1e-3 else 'FAIL'}",flush=True)

# --- 3) GT var-opex (time x node format) ---
print("\n=== GT var-opex ===",flush=True)
res2={}
for lab,k in [("build",1.01),("nobuild",0.99)]:
    with opexvar_timegrid("FR",opexv_gt-k*dvo_gt):
        res2[lab]=run_built("natural_gas_turbine","FR",f"gtvar_{lab}")
print(f"  build={res2['build']:.4g} nobuild={res2['nobuild']:.4g} -> {'PASS' if res2['build']>1e-3 and not res2['nobuild']>1e-3 else 'FAIL'}",flush=True)
print("\nDONE",ROOT)
