"""Final reliability flag = perturbation swing classifier, applied to ALL conversion
buildable_rc cases (runB perturbed vs runC clean operational RC). Overlay the 18
validated +-1% labels -> threshold + precision/recall + population split. CSV only."""
import numpy as np, pandas as pd
def load(run):
    df=pd.read_csv(f"outputs_CB_overnight/{run}/Crystal_Ball/capacity_addition_analysis_conversion.csv")
    return df.set_index(["set_technologies","set_location"])
B,C=load("runB"),load("runC")
col="ratio_reduction_operational"
j=C[[col,"value","capacity_ceiling","rc_reliable"]].join(
    B[[col]],lsuffix="_C",rsuffix="_B",how="inner")
# buildable_rc universe: unbuilt (value~0), finite operational ratio in (0,1]
j=j[(j["value"].abs()<1e-6)]
j=j[(j[col+"_C"]>1e-9)&(j[col+"_C"]<=1.0)&(j[col+"_B"]>1e-9)&(j[col+"_B"]<=1.0)]
j["swing_pp"]=(j[col+"_B"]-j[col+"_C"]).abs()*100
print(f"buildable_rc conversion cases with both runs: {len(j)}")

labels={  # +-1% ground truth
 ("nuclear","ES"):"FAIL",("electrolysis","FI"):"FAIL",("coal_to_cement_fuel","SK"):"FAIL",
 ("photovoltaics","CZ"):"PASS",("photovoltaics","NO"):"PASS",("photovoltaics","SE"):"PASS",
 ("wind_onshore","NO"):"PASS",("wind_onshore","CH"):"PASS",("wind_offshore","FR"):"PASS",
 ("wind_offshore","SE"):"PASS",("run-of-river_hydro","SK"):"PASS",("run-of-river_hydro","SE"):"PASS",
 ("reservoir_hydro","CH"):"PASS",("reservoir_hydro","SE"):"PASS",("heat_pump_DH","SE"):"PASS",
 ("methanol_from_hydrogen","BG"):"PASS",("natural_gas_turbine_CCS","ES"):"PASS",("nuclear","FR"):"PASS"}

print("\n=== swing at the 18 validated labels ===")
print(f"{'tech':24} {'node':4} {'label':5} {'op_C%':>7} {'op_B%':>7} {'swing_pp':>9}")
rows=[]
for (t,n),lab in labels.items():
    if (t,n) in j.index:
        r=j.loc[(t,n)]
        sw=float(r["swing_pp"]); rc=float(r[col+"_C"])*100; rb=float(r[col+"_B"])*100
        rows.append((t,n,lab,sw)); 
        print(f"{t:24} {n:4} {lab:5} {rc:7.2f} {rb:7.2f} {sw:9.2f}")
    else:
        print(f"{t:24} {n:4} {lab:5}   (not in buildable set / built)")

print("\n=== threshold scan (swing classifier) ===")
lab_df=pd.DataFrame(rows,columns=["t","n","lab","sw"])
for thr in [0.5,1.0,2.0,3.0]:
    pred_fail=lab_df["sw"]>=thr
    is_fail=lab_df["lab"]=="FAIL"
    TP=int((pred_fail&is_fail).sum()); FP=int((pred_fail&~is_fail).sum())
    FN=int((~pred_fail&is_fail).sum()); TN=int((~pred_fail&~is_fail).sum())
    prec=TP/(TP+FP) if TP+FP else float('nan'); rec=TP/(TP+FN) if TP+FN else float('nan')
    print(f"  thr={thr:4.1f}pp -> flagged_FAIL: TP={TP} FP={FP} FN={FN} TN={TN}  "
          f"precision={prec:.2f} recall={rec:.2f}")

print("\n=== population split at thr=1.0pp (all buildable_rc conversion) ===")
thr=1.0
n_rel=int((j["swing_pp"]<thr).sum()); n_flag=int((j["swing_pp"]>=thr).sum())
print(f"  reliable (swing<{thr}pp): {n_rel} ({100*n_rel/len(j):.1f}%)")
print(f"  flagged  (swing>={thr}pp): {n_flag} ({100*n_flag/len(j):.1f}%)")
