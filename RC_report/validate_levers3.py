"""Diagnose the gas-turbine (variable-cost) levers via sweeps, at FR and IT.
Separates: knife-edge precision vs price-setter self-cannibalisation vs formula error.
For each lever, sweep the reduction and read built capacity; compare to the prediction."""
import os, json, shutil
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
DS   = os.path.join(BASE, "6_showcase_countries")
CONV = os.path.join(DS, "set_technologies", "set_conversion_technologies")
BOUT = os.path.join(BASE, "outputs_showcase_storage_only", "6_showcase_countries")
ROOT = os.path.join(BASE, "outputs_showcase_levers3", datetime.now().strftime("%H%M%S")); os.makedirs(ROOT, exist_ok=True)
NODES = ["AT","CH","DE","FR","IT"]; YEARS = [2025,2026,2027]
r, lt = 0.06, 30; af = ((1+r)**lt*r)/((1+r)**lt-1)
opexf_gt, opexv_gt = 22.0, 2.9

conv = pd.read_csv(os.path.join(BOUT, "capacity_addition_analysis_conversion.csv"))
def rcv(n):
    row = conv[(conv.set_technologies=="natural_gas_turbine")&(conv.set_location==n)&(conv.set_time_steps_yearly==0)].iloc[0]
    return float(row["rc_capex_equivalent_operational_input_units"])
nu  = pd.read_hdf(os.path.join(BOUT,"dual_dict.h5"),"constraint_capacity_factor_conversion")
dur = pd.read_hdf(os.path.join(BOUT,"param_dict.h5"),"time_steps_operation_duration")
def E_of(n):
    g = nu[(nu.index.get_level_values("technology")=="natural_gas_turbine")&(nu.index.get_level_values("node")==n)].reset_index()
    g.columns=["t","tech","node","nu"]; y0=g[(g.t<24)&(g.nu.abs()>1e-9)]
    return float((0.93*dur.loc[y0.t.values].values).sum())

def cfg():
    return {"solver":{"name":"gurobi","save_duals":False,"save_reduced_costs":False,"use_scaling":0,
            "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
def run_built(n,tag):
    out=os.path.join(ROOT,tag); os.makedirs(out,exist_ok=True)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w")); run(config=tmp,dataset=DS,folder_output=out)
    d=pd.read_csv(os.path.join(out,"6_showcase_countries","capacity_addition_analysis.csv"))
    row=d[(d.set_technologies=="natural_gas_turbine")&(d.set_capacity_types=="power")&(d.set_location==n)&(d.set_time_steps_yearly==0)]
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
def grid_fixed(node,value):
    return ov(os.path.join(CONV,"natural_gas_turbine","opex_specific_fixed.csv"),
              pd.DataFrame([[n,y,(value if n==node else opexf_gt)] for n in NODES for y in YEARS],columns=["node","year","opex_specific_fixed"]))
def grid_var(node,value):
    t=pd.read_csv(os.path.join(CONV,"photovoltaics","max_load.csv"))["time"]; df=pd.DataFrame({"time":t})
    for n in NODES: df[n]=(value if n==node else opexv_gt)
    return ov(os.path.join(CONV,"natural_gas_turbine","opex_specific_variable.csv"),df)

for NODE in ["FR", "IT"]:
    RC = rcv(NODE); E = E_of(NODE); dfp = af*RC; dvp = af*RC/E if E>0 else float("nan")
    print(f"\n##### GT@{NODE}: RC={RC:.2f}  E={E:.1f}  pred fixedopex -{dfp:.3f}  pred varopex -{dvp:.4f}", flush=True)
    print("  --- fixed-opex sweep (reduce opex_fixed by d) ---", flush=True)
    for d in [dfp*0.5, dfp, dfp*1.5, dfp*2, dfp*4]:
        with grid_fixed(NODE, opexf_gt - d): b = run_built(NODE, f"{NODE}_fix_{d:.2f}")
        print(f"    -{d:7.3f} EUR/kW/yr -> built={b:.4g}", flush=True)
    print("  --- var-opex sweep (reduce opex_var by d) ---", flush=True)
    for d in [dvp, dvp*5, dvp*20, dvp*100, dvp*300]:
        with grid_var(NODE, opexv_gt - d): b = run_built(NODE, f"{NODE}_var_{d:.3f}")
        print(f"    -{d:7.3f} EUR/MWh -> built={b:.4g}", flush=True)
print("\nDONE", ROOT)
