"""Phase 2: heat pump @ DE with bad COP=1.25 -> derive the COP it needs to build
(from the operational RC) and validate via +-1% (override the conversion factor) + a COP sweep.
COP lever:  1/COP1 = 1/COP0 - scaling*RC/W,  W = sum_{nu_t>0} m_t * lambda_elec_t  (m_t=1)."""
import os, json, shutil
import numpy as np, pandas as pd
from zen_garden import run

BASE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
SRC=os.path.join(BASE,"6_showcase_countries"); WD=os.path.join(BASE,"6_showcase_hpcop")
B=os.path.join(BASE,"outputs_hpcop_p1","cf0.8","6_showcase_hpcop")   # base bad-COP solve
NODE="DE"; CF0=0.8; COP0=1/CF0; r=0.06

# --- read base RC + duals ---
conv=pd.read_csv(os.path.join(B,"capacity_addition_analysis_conversion.csv"))
row=conv[(conv.set_technologies=="heat_pump")&(conv.set_location==NODE)&(conv.set_time_steps_yearly==0)].iloc[0]
RC=float(row["rc_capex_equivalent_operational_input_units"]); capex=float(row["capex_specific_input_units"])
dep=float(pd.read_hdf(os.path.join(B,"param_dict.h5"),"depreciation_time").loc["heat_pump"])
af=((1+r)**dep*r)/((1+r)**dep-1)
Sdelta=sum((1/(1+r))**y for y in range(3))     # 3 pay years
scaling=af*Sdelta
nu=pd.read_hdf(os.path.join(B,"dual_dict.h5"),"constraint_capacity_factor_conversion")
lam=pd.read_hdf(os.path.join(B,"dual_dict.h5"),"constraint_nodal_energy_balance")
hp=nu[(nu.index.get_level_values("technology")=="heat_pump")&(nu.index.get_level_values("node")==NODE)].reset_index()
hp.columns=["t","tech","node","nu"]
def lel(t):
    try: return float(lam.loc[("electricity",NODE,t)])
    except Exception: return 0.0
run_t=hp[hp.nu.abs()>1e-9]   # hours the HP would run (nu>0)
W=float(sum(lel(int(t)) for t in run_t.t))           # m_t = 1 (max_load), lambda_elec duration-weighted
print(f"RC={RC:.3f} capex={capex} dep={dep} af={af:.4f} Sdelta={Sdelta:.4f} scaling={scaling:.4f}")
print(f"run hours (nu>0)={len(run_t)}  W=sum m*lambda_elec={W:.3f}")

def cop_for(rc_frac):
    inv=1/COP0 - rc_frac*scaling*RC/W
    return 1/inv if inv>0 else float("inf")
COP_pred=cop_for(1.0); COP_build=cop_for(1.01); COP_nobuild=cop_for(0.99)
print(f"\nCOP0={COP0:.3f} -> COP needed (pred)={COP_pred:.4f}  build(+1%)={COP_build:.4f} nobuild(-1%)={COP_nobuild:.4f}",flush=True)

# --- validate: set HP cf=1/COP, re-solve, read DE build ---
def cfg(): return {"solver":{"name":"gurobi","save_duals":False,"save_reduced_costs":False,"use_scaling":0,
                   "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
def built_at(cop,tag):
    if os.path.exists(WD): shutil.rmtree(WD)
    shutil.copytree(SRC,WD)
    ap=os.path.join(WD,"set_technologies","set_conversion_technologies","heat_pump","attributes.json")
    a=json.load(open(ap)); a["conversion_factor"]["electricity"]["default_value"]=1/cop; json.dump(a,open(ap,"w"),indent=2)
    out=os.path.join(BASE,"outputs_hpcop_p2",tag);
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out)
    tmp=os.path.join(out,"_c.json"); json.dump(cfg(),open(tmp,"w")); run(config=tmp,dataset=WD,folder_output=out)
    d=pd.read_csv(os.path.join(out,"6_showcase_hpcop","capacity_addition_analysis.csv"))
    rr=d[(d.set_technologies=="heat_pump")&(d.set_capacity_types=="power")&(d.set_location==NODE)&(d.set_time_steps_yearly==0)]
    return float(rr["value"].iloc[0]) if len(rr) else np.nan

print("\n=== +-1% validation ===",flush=True)
bb=built_at(COP_build,"build"); bn=built_at(COP_nobuild,"nobuild")
print(f"  COP_build={COP_build:.4f}->built={bb:.4g} | COP_nobuild={COP_nobuild:.4f}->built={bn:.4g} -> {'PASS' if bb>1e-3 and not bn>1e-3 else 'FAIL'}",flush=True)

print("\n=== COP sweep (find true break-even) ===",flush=True)
for cop in [1.25, COP_pred, COP_pred*1.02, COP_pred*1.05, COP_pred*1.1, COP_pred*1.2]:
    b=built_at(cop,f"sweep_{cop:.3f}")
    print(f"  COP={cop:.4f} -> built={b:.4g}",flush=True)
print("DONE")
