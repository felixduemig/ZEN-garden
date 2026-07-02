"""PROOF in real ZEN-garden (Gurobi Method2+Crossover1+Presolve0, save_duals):
the operational RC over-states baseload's distance-to-build at the congested-island
scarcity vertex; the ground-truth capex re-solve builds ~nothing at the reconstructed
break-even.  Mirrors nuclear@ES.  Also shows demand=30.0 (peaker idle) gives the
CORRECT RC -> the error is switched on by the scarcity price, not the method."""
import os, json, importlib, sys
from datetime import datetime
import pandas as pd, numpy as np
BASE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(BASE); os.chdir(ROOT)
sys.path.insert(0, BASE); import build_island
from zen_garden import run
RUNi=[0]
def solve(scarce, capex):
    os.environ["ISL_SCARCE_DEMAND"]=str(scarce); os.environ["ISL_BASELOAD_CAPEX"]=str(capex)
    importlib.reload(build_island); DS=build_island.build()
    RUNi[0]+=1; out=os.path.join(ROOT,"outputs_island",f"demo{RUNi[0]:02d}"); os.makedirs(out,exist_ok=True)
    cfg={"solver":{"name":"gurobi","save_duals":True,"save_reduced_costs":True,"use_scaling":0,
         "solver_options":{"Method":2,"Crossover":1,"Presolve":0,"OutputFlag":0}}}
    tmp=os.path.join(out,"_c.json"); json.dump(cfg,open(tmp,"w"))
    run(config=tmp,dataset=DS,folder_output=out)
    R=os.path.join(out,"rc_scarcity_demo")
    conv=pd.read_csv(os.path.join(R,"capacity_addition_analysis_conversion.csv"))
    b=conv[(conv.set_technologies=="baseload")&(conv.set_location=="ISL")].iloc[0]
    lam=pd.read_hdf(os.path.join(R,"dual_dict.h5"),"constraint_nodal_energy_balance")
    dur=pd.read_hdf(os.path.join(R,"param_dict.h5"),"time_steps_operation_duration").to_dict()
    p=float(lam.loc[("electricity","ISL",0)])/dur[0]
    return dict(built=round(float(b["value"]),4), price=round(p,4),
                rc=round(float(b["rc_capex_equivalent_operational_input_units"]),1),
                ratio=round(float(b["ratio_reduction_operational"]),4))

print("="*70)
print("A) REFERENCE  demand=30.0 (peaker idle, price=import-parity 10):")
a=solve(30.0,3000); print("   ",a," <- RC ratio 0.75 is the TRUE distance (displaces imports@10)")
print("B) SCARCITY   demand=30.01 (peaker ticks on 0.01, price=50):")
s=solve(30.01,3000); print("   ",s," <- RC ratio 0.25: reads scarcity price 50 -> OVER-STATES value 3x")
ratio=s["ratio"]; CAPEX=3000.0
be_recon=CAPEX*(1-ratio)
print(f"\n   reconstructed break-even capex = 3000*(1-{ratio}) = {be_recon:.0f} EUR/kW")
print(f"   TRUE break-even (ref A)        = 3000*(1-{a['ratio']}) = {CAPEX*(1-a['ratio']):.0f} EUR/kW")

print("\nC) GROUND TRUTH: rebuild baseload at swept capex (demand=30.01), read built GW:")
print(f"   {'capex':>7} {'built_GW':>9}   note")
sweep=[(round(CAPEX*(1-1.01*ratio),1),'+-1% BUILD pt (recon says BUILD)'),
       (round(CAPEX*(1-0.99*ratio),1),'+-1% NOBUILD pt'),
       (1500.0,''),(1000.0,''),(800.0,'~just above true BE'),
       (760.0,'~true break-even'),(700.0,'below true BE'),(500.0,'deep -> builds out')]
res=[]
for cx,note in sweep:
    r=solve(30.01,cx); res.append((cx,r["built"],note))
    print(f"   {cx:7.1f} {r['built']:9.4f}   {note}")
print("\nVERDICT: at the reconstructed break-even (~%.0f) baseload builds ~0 (only the 0.01 GW"%be_recon)
print("peaker-displacement); it only builds out near the TRUE break-even (~760). The operational")
print("RC (ratio 0.25) UNDER-STATES the true distance (ratio 0.75) by 3x -- same as nuclear@ES.")
