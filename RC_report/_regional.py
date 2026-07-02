import numpy as np, pandas as pd
F="outputs_CB_overnight/runC/Crystal_Ball/"
def s(f,k):
    d=pd.read_hdf(F+f,k); return d if isinstance(d,pd.Series) else d.iloc[:,0]
conv=pd.read_csv(F+"capacity_addition_analysis_conversion.csv")
# A) capacity census: built where, total GW
print("="*70,"\nA) BUILD-OUT CENSUS (all conversion techs, by built node-count)")
g=conv.groupby("set_technologies")
rows=[]
for t,sub in g:
    built=sub[sub["case"]=="built"]; nb=len(built); gw=built["value"].sum()
    rows.append((t,nb,round(gw,1)))
df=pd.DataFrame(rows,columns=["tech","n_built","tot_GW"]).sort_values("n_built",ascending=False)
print("Ubiquitous (built >=24/28 nodes):"); print(df[df.n_built>=24].to_string(index=False))
print("\nNever built (0 nodes), top by relevance:")
print(df[df.n_built==0].head(12)["tech"].tolist())
print("\nTop built capacity (GW):"); print(df.sort_values("tot_GW",ascending=False).head(12).to_string(index=False))

# B) electricity generation mix (weighted by typical-hour duration if available)
print("\n"+"="*70,"\nB) ELECTRICITY GENERATION MIX")
out=s("var_dict.h5","flow_conversion_output"); out=out[out.index.get_level_values("carrier")=="electricity"]
# try durations
dur=None
for key in ["time_steps_operation_duration","time_step_duration"]:
    try: dur=s("param_dict.h5",key); break
    except Exception: pass
od=out.reset_index()
tcol=[c for c in od.columns if "time" in c.lower()][0]; vcol=od.columns[-1]
if dur is not None:
    dd=dur.reset_index(); dtc=[c for c in dd.columns if "time" in c.lower()][0]
    wmap=dict(zip(dd[dtc].astype(int),dd[dd.columns[-1]]))
    od["w"]=od[tcol].astype(int).map(wmap).fillna(1.0); note="(duration-weighted)"
else:
    od["w"]=1.0; note="(unweighted across 10 typical hours)"
od["gen"]=od[vcol]*od["w"]
mix=od.groupby("technology")["gen"].sum().sort_values(ascending=False)
tot=mix.sum()
print("duration source:",note)
for t,v in mix.head(10).items(): print(f"  {t:24} {100*v/tot:5.1f}%")

# C) fleet diversity per node vs connectivity
print("\n"+"="*70,"\nC) FLEET DIVERSITY vs CONNECTIVITY")
ft=s("var_dict.h5","flow_transport")
deg={}
for e in ft.index.get_level_values("edge").unique():
    a,b=e.split("-"); 
    # count only power_line presence
for e in ft.index.get_level_values("edge").unique():
    if ("power_line",e,0) in ft.index:
        a,b=e.split("-"); deg[a]=deg.get(a,0)+0.5; deg[b]=deg.get(b,0)+0.5
built=conv[conv["case"]=="built"]
divn=built.groupby("set_location")["set_technologies"].nunique()
cc=pd.DataFrame({"fleet":divn}).reset_index().rename(columns={"set_location":"node"})
cc["plines"]=cc["node"].map(lambda n:int(deg.get(n,0)))
cc=cc.sort_values("plines",ascending=False)
print("most connected:"); print(cc.head(6).to_string(index=False))
print("least connected:"); print(cc.tail(6).to_string(index=False))
print(f"corr(fleet, plines) = {cc['fleet'].corr(cc['plines']):.2f}")

# D) PV closeness vs capacity factor (irradiation proxy)
print("\n"+"="*70,"\nD) PV: closeness (ratio) vs capacity factor")
ml=s("param_dict.h5","max_load")
pvcf=ml[ml.index.get_level_values("technology")=="photovoltaics"].groupby(ml[ml.index.get_level_values("technology")=="photovoltaics"].index.get_level_values("location")).mean()
pv=conv[(conv["set_technologies"]=="photovoltaics")]
pvb=pv[pv["case"]=="buildable_rc"][["set_location","ratio_reduction_operational"]].copy()
pvb["cf"]=pvb["set_location"].map(pvcf); pvb["ratio%"]=100*pvb["ratio_reduction_operational"]
pvb=pvb.sort_values("ratio%")
print("PV closest to build (unbuilt nodes), with PV capacity factor:")
print(pvb[["set_location","ratio%","cf"]].head(8).to_string(index=False))
print(f"PV built at {len(pv[pv.case=='built'])} nodes; corr(ratio, cf) among buildable = {pvb['ratio_reduction_operational'].corr(pvb['cf']):.2f}")

# E) electrolysis closeness vs cheap power
print("\n"+"="*70,"\nE) ELECTROLYSIS closeness vs mean electricity price")
lam=s("dual_dict.h5","constraint_nodal_energy_balance"); lam=lam[lam.index.get_level_values("carrier")=="electricity"]
mp=lam.groupby(lam.index.get_level_values("node")).mean()
el=conv[(conv["set_technologies"]=="electrolysis")&(conv["case"]=="buildable_rc")][["set_location","ratio_reduction_operational"]].copy()
el["meanprice"]=el["set_location"].map(mp); el["ratio%"]=100*el["ratio_reduction_operational"]
print(el.sort_values("ratio%").head(6).to_string(index=False))
