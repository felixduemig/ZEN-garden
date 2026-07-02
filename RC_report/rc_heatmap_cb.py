"""CB RC heatmaps, ETH style, parametrised: excerpt (10 nodes) + full (appendix),
plain Stage-0 (markers only) vs reliability (swing hatch). 20 conversion techs."""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D
ETH_GREEN="#627313"; ETH_RED="#B7352D"; ETH_GREY="#6F6F6F"; ETH_DARK="#1A1A1A"
plt.rcParams.update({"font.family":"serif","font.serif":["CMU Serif","Times New Roman","DejaVu Serif"],
                     "text.color":ETH_DARK,"axes.edgecolor":ETH_GREY,"figure.facecolor":"white","savefig.facecolor":"white"})
CMAP=LinearSegmentedColormap.from_list("eth",[(0,ETH_GREEN),(0.5,"#EDE7D3"),(1,ETH_RED)]); CMAP.set_bad((0,0,0,0))
SWING_THR=1.0; VMAX=100.0
TECHS=["photovoltaics","wind_onshore","wind_offshore","run-of-river_hydro","reservoir_hydro","nuclear",
       "natural_gas_turbine","natural_gas_turbine_CCS","electrolysis","SMR","SMR_CCS","fuel_cell",
       "heat_pump","heat_pump_DH","electrode_boiler","natural_gas_boiler",
       "coal_to_cement_fuel","methanol_from_hydrogen","DAC","haber_bosch"]
EXC=["DE","FR","NO","SE","CH","CZ","SK","BG","ES","FI"]
LAB={
 # --- original 18 labels ---
 ("nuclear","ES"):"F",("electrolysis","FI"):"F",("coal_to_cement_fuel","SK"):"F",
 ("photovoltaics","CZ"):"P",("photovoltaics","NO"):"P",("photovoltaics","SE"):"P",("wind_onshore","NO"):"P",
 ("wind_onshore","CH"):"P",("wind_offshore","FR"):"P",("wind_offshore","SE"):"P",("run-of-river_hydro","SK"):"P",
 ("run-of-river_hydro","SE"):"P",("reservoir_hydro","CH"):"P",("reservoir_hydro","SE"):"P",("heat_pump_DH","SE"):"P",
 ("methanol_from_hydrogen","BG"):"P",("natural_gas_turbine_CCS","ES"):"P",("nuclear","FR"):"P",
 # --- overnight batch 2 PASS (21) ---
 ("photovoltaics","SK"):"P",("photovoltaics","FI"):"P",("electrolysis","CH"):"P",
 ("reservoir_hydro","NO"):"P",("reservoir_hydro","CZ"):"P",("reservoir_hydro","FR"):"P",
 ("run-of-river_hydro","BG"):"P",("run-of-river_hydro","CH"):"P",("run-of-river_hydro","CZ"):"P",
 ("heat_pump_DH","ES"):"P",("heat_pump_DH","FR"):"P",("heat_pump_DH","BG"):"P",("heat_pump_DH","DE"):"P",
 ("DAC","SE"):"P",("wind_onshore","BG"):"P",("methanol_from_hydrogen","DE"):"P",
 ("electrode_boiler","DE"):"P",("fuel_cell","ES"):"P",("SMR_CCS","DE"):"P",
 ("coal_to_cement_fuel","CZ"):"P",("natural_gas_boiler","DE"):"P",
 # --- overnight batch 2 FAIL (5): 3 high-swing (flag caught) + 2 low-swing peakers (false negatives) ---
 ("natural_gas_turbine_CCS","SK"):"F",("natural_gas_turbine_CCS","CZ"):"F",("SMR_CCS","ES"):"F",
 ("natural_gas_turbine","NO"):"F",("natural_gas_turbine_CCS","BG"):"F"}
def load(r): return pd.read_csv(f"outputs_CB_overnight/{r}/Crystal_Ball/capacity_addition_analysis_conversion.csv")
C=load("runC"); B=load("runB")
m=C.merge(B[["set_technologies","set_location","ratio_reduction_operational"]],on=["set_technologies","set_location"],suffixes=("","_B"))
m["swing"]=(m["ratio_reduction_operational_B"]-m["ratio_reduction_operational"]).abs()*100
m=m[m["set_technologies"].isin(TECHS)]

def render(nodes, markers, hatch, fname, annot):
    nt,nn=len(TECHS),len(nodes)
    val=np.full((nt,nn),np.nan); cat=np.empty((nt,nn),object); sw=np.zeros((nt,nn)); bld=np.full((nt,nn),np.nan); ab=np.full((nt,nn),np.nan)
    sub=m[m["set_location"].isin(nodes)]
    for _,r in sub.iterrows():
        i=TECHS.index(r["set_technologies"]); j=nodes.index(r["set_location"]); case=r["case"]
        if case=="built": cat[i,j]="built"; bld[i,j]=r["value"] if r["value"]>1e-6 else r.get("capacity",np.nan)
        elif case in("at_limit","not_buildable"): cat[i,j]="blocked"
        elif case=="buildable_rc":
            cat[i,j]="rc"; val[i,j]=r["ratio_reduction_operational"]*100; sw[i,j]=r["swing"]; ab[i,j]=r["rc_capex_equivalent_operational_input_units"]
        else: cat[i,j]="other"
    big=nn>12; fs=11 if big else 8; mk=26 if big else 80
    fig,ax=plt.subplots(figsize=(0.62*nn+3.4,0.46*nt+1.7)); ax.set_facecolor("white")
    norm=Normalize(0,VMAX); ax.imshow(np.ma.masked_invalid(val),cmap=CMAP,norm=norm,aspect="auto",zorder=2)
    for i in range(nt):
        for j in range(nn):
            if not np.isfinite(val[i,j]):
                c={"built":"white","blocked":"black","other":"#D9D9D9"}.get(cat[i,j],"#D9D9D9")
                ax.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor=c,edgecolor="none",zorder=1.5))
                if cat[i,j]=="built" and np.isfinite(bld[i,j]) and bld[i,j]>0.05:
                    ax.text(j,i,f"{bld[i,j]:.0f}",ha="center",va="center",fontsize=fs-1,color=ETH_DARK,zorder=4)
            else:
                if hatch and sw[i,j]>=SWING_THR:
                    ax.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor="none",edgecolor=ETH_DARK,hatch="////",lw=0,zorder=3.2,alpha=0.5))
                if annot:
                    ax.text(j,i-0.16,f"{val[i,j]:.0f}%",ha="center",va="center",fontsize=fs,fontweight="bold",color=ETH_DARK,zorder=4)
                    if np.isfinite(ab[i,j]): ax.text(j,i+0.24,f"({ab[i,j]:,.0f})".replace(",", " "),ha="center",va="center",fontsize=fs-2.5,color=ETH_DARK,zorder=4)
                else:
                    ax.text(j,i,f"{val[i,j]:.0f}",ha="center",va="center",fontsize=fs,color=ETH_DARK,zorder=4)
            if markers:
                lab=LAB.get((TECHS[i],nodes[j]))
                if lab:
                    mx,my=j+0.30,i-0.30   # top-right corner, clear of the centred numbers
                    if lab=="P":          # black ring (PASS), white halo for any fill
                        ax.scatter(mx,my,s=mk*0.66,marker="o",facecolors="none",edgecolors="white",linewidths=2.8,zorder=5.9)
                        ax.scatter(mx,my,s=mk*0.66,marker="o",facecolors="none",edgecolors="black",linewidths=1.2,zorder=6)
                    else:                 # black cross (FAIL), white halo
                        ax.scatter(mx,my,s=mk*0.8,marker="x",c="white",linewidths=3.0,zorder=5.9)
                        ax.scatter(mx,my,s=mk*0.8,marker="x",c="black",linewidths=1.5,zorder=6)
    ax.set_xticks(range(nn)); ax.set_xticklabels(nodes,fontsize=8 if big else 9,rotation=90 if big else 0)
    ax.set_yticks(range(nt)); ax.set_yticklabels(TECHS,fontsize=8)
    ax.set_xticks(np.arange(-.5,nn,1),minor=True); ax.set_yticks(np.arange(-.5,nt,1),minor=True)
    ax.grid(which="minor",color="#BFBFBF",lw=0.6,zorder=3.5); ax.tick_params(which="minor",length=0); ax.tick_params(length=0)
    ax.set_xlim(-.5,nn-.5); ax.set_ylim(nt-.5,-.5); ax.set_xlabel("Node (hub → island)",fontsize=9)
    cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=CMAP),ax=ax,fraction=0.02,pad=0.01,extend="max")
    cb.set_label("rel. CAPEX reduction to build [%]  (green=close, red=far)\n"
                 "bracket: absolute reduced cost [EUR/kW]",fontsize=8); cb.ax.tick_params(labelsize=7)
    leg=[Patch(facecolor="white",edgecolor=ETH_GREY,label="built (# = GW)"),
         Patch(facecolor="black",label="at-limit / not buildable"),
         Patch(facecolor="#D9D9D9",edgecolor=ETH_GREY,label="unreliable / n.a.")]
    if hatch: leg.append(Patch(facecolor="#EDE7D3",edgecolor=ETH_DARK,hatch="////",label=f"swing≥{SWING_THR:.0f}pp (lower bound)"))
    if markers: leg+=[Line2D([0],[0],marker="o",color="none",markerfacecolor="none",markeredgecolor="black",markeredgewidth=1.4,markersize=8,label="tested PASS"),
                      Line2D([0],[0],marker="x",color="black",linestyle="none",markeredgewidth=1.8,markersize=8,label="tested FAIL")]
    fig.legend(handles=leg,loc="lower center",bbox_to_anchor=(0.5,-0.05),ncol=3,fontsize=8,frameon=False)
    fig.tight_layout(); fig.savefig("RC_report/"+fname,dpi=200,bbox_inches="tight"); plt.close(fig); print("saved",fname)

allnodes=sorted(m["set_location"].unique())
render(EXC, True, False, "cb_rc_excerpt_stage0.png", True)        # 5.2.2 plain + tested markers
render(EXC, True, True,  "cb_rc_excerpt_reliability.png", True)   # 5.2.3 with swing hatch
render(allnodes, False, False, "cb_rc_full_normal.png", False)    # appendix full normal
render(allnodes, True, True,  "cb_rc_full_reliability.png", False)# appendix full reliability
