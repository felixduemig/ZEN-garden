"""PV capex sweep at CZ (RC ratio 4.75%) -- show build STARTS at the RC and then ramps
incrementally (RC marks the start, not the amount). Mirrors _es_sweep.py."""
import json, os, sys
import pandas as pd, numpy as np
BASE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,BASE); os.chdir(BASE)
try:
    import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000000|0x00000001|0x00000040)
except Exception: pass
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
DATASET=os.path.join(BASE,"ZEN-models","data","Crystal_Ball"); DATA="Crystal_Ball"
ROOT=os.path.join(BASE,"outputs_CB_overnight","pv_sweep"); os.makedirs(ROOT,exist_ok=True)
TECH,NODE="photovoltaics","CZ"
CUTS=[0.03,0.06,0.12,0.25,0.50]   # RC ratio is 4.75% -> below builds 0, above ramps
def cfg():
    with open("./config.json") as f: c=json.load(f)
    c.pop("plugins",None); c.setdefault("solver",{}); c["solver"].setdefault("solver_options",{})
    c["solver"]["name"]="gurobi"; c["solver"]["save_duals"]=False; c["solver"]["save_reduced_costs"]=False
    c["solver"]["use_scaling"]=0; so=c["solver"]["solver_options"]
    so["Method"]=2; so["Crossover"]=1; so["Presolve"]=0; so["OutputFlag"]=0
    return c
def main():
    restore_leftover_swaps(DATASET)
    orig=read_capex(DATASET,TECH,NODE,2050)
    print(f"{TECH}@{NODE} orig capex={orig:.1f}; RC ratio ~4.75%",flush=True)
    rows=[]
    for cut in CUTS:
        new=orig*(1-cut)
        with capex_file_override(DATASET,[{"tech":TECH,"node":NODE,"year":2050,"value":new}]):
            out=os.path.join(ROOT,f"cut{int(cut*100)}"); os.makedirs(out,exist_ok=True)
            tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w"))
            run(config=tmp,dataset=DATASET,folder_output=out); os.remove(tmp)
        cap=pd.read_csv(os.path.join(out,DATA,"capacity_addition_analysis.csv"))
        b=cap[(cap.set_technologies==TECH)&(cap.set_location==NODE)&(cap.set_capacity_types=="power")&(cap.set_time_steps_yearly==0)]
        built=float(b["value"].iloc[0]) if len(b) else np.nan
        rows.append((cut,new,built))
        print(f"  cut {cut*100:>4.1f}%  capex {new:>6.0f} -> built {built:>8.3f} GW",flush=True)
        pd.DataFrame(rows,columns=["cut","capex","built_GW"]).to_csv(os.path.join(ROOT,"sweep.csv"),index=False)
    print("DONE",flush=True)
if __name__=="__main__": main()
