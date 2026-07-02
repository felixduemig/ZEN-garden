"""READ-ONLY. Decompose what sets lambda_electricity@ES at the scarcity hour h0
(runC clean no-build solve). Shows: local producers (flow vs cap), import lines
(flow vs cap, congestion dual), and whether lambda_ES = lambda_neighbor + congestion.
Tests Felix's hypothesis: is the import-capacity dual MISSING from the price?"""
import os
import numpy as np, pandas as pd
F = "outputs_CB_overnight/runC/Crystal_Ball/"
DUAL, VAR, PARAM = F+"dual_dict.h5", F+"var_dict.h5", F+"param_dict.h5"
H = 0  # scarcity hour

def s(f, k):
    d = pd.read_hdf(f, k)
    return d if isinstance(d, pd.Series) else d.iloc[:, 0]

# 1) nodal electricity price lambda
lam = s(DUAL, "constraint_nodal_energy_balance")
lam = lam[lam.index.get_level_values("carrier") == "electricity"]
def lamnode(n, h=H):
    v = lam[(lam.index.get_level_values("node")==n) & (lam.index.get_level_values("time_operation")==h)]
    return float(v.iloc[0]) if len(v) else np.nan
print(f"=== electricity price lambda @ h{H} ===")
for n in ["ES","FR","PT"]:
    print(f"  lambda_{n} = {lamnode(n):8.3f}")
ess="ES"
print("  (ES all hours: " + ", ".join(f"{h}:{lamnode(ess,h):.1f}" for h in range(10)) + ")")

# 2) import lines touching ES
ft = s(VAR, "flow_transport")
cft = s(DUAL, "constraint_capacity_factor_transport")   # congestion dual
cap = s(VAR, "capacity")
edges = sorted({e for e in ft.index.get_level_values("edge").unique() if "ES" in e})
print(f"\n=== power_line edges touching ES @ h{H} (flow, capacity, util, congestion-dual) ===")
print(f"{'edge':8} {'tech':12} {'flow':>9} {'cap':>9} {'util%':>7} {'congDual':>10}")
for e in edges:
    for tech in ft.index.get_level_values("technology").unique():
        key = (tech, e, H)
        if key not in ft.index: continue
        fl = float(ft.loc[key])
        if abs(fl) < 1e-9 and tech!="power_line": continue
        # capacity of this transport tech on this edge (power capacity, year 0)
        ck = cap[(cap.index.get_level_values("technology")==tech) &
                 (cap.index.get_level_values("location")==e)]
        capv = float(ck.iloc[0]) if len(ck) else np.nan
        cd = cft[(cft.index.get_level_values("technology")==tech) &
                 (cft.index.get_level_values("edge")==e) &
                 (cft.index.get_level_values("time_operation")==H)]
        cdv = float(cd.iloc[0]) if len(cd) else np.nan
        util = 100*fl/capv if capv else np.nan
        if tech=="power_line" or abs(fl)>1e-9:
            print(f"{e:8} {tech:12} {fl:9.3f} {capv:9.3f} {util:7.1f} {cdv:10.3f}")

# 3) electricity producers at ES at h0: output vs capacity (at cap?) + capfactor dual
out = s(VAR, "flow_conversion_output")
out = out[(out.index.get_level_values("carrier")=="electricity") &
          (out.index.get_level_values("node")=="ES") &
          (out.index.get_level_values("time_operation")==H)]
ml = s(PARAM, "max_load")
ccf = s(DUAL, "constraint_capacity_factor_conversion")
print(f"\n=== ES electricity producers @ h{H} (output, max_load*cap, util, interior?) ===")
print(f"{'tech':22} {'output':>9} {'maxL*cap':>9} {'util%':>7} {'capfacDual':>11} {'interior':>9}")
rows=[]
for idx, fl in out.items():
    tech = idx[out.index.names.index("technology")]
    fl=float(fl)
    ck = cap[(cap.index.get_level_values("technology")==tech) &
             (cap.index.get_level_values("location")=="ES")]
    capv=float(ck.iloc[0]) if len(ck) else np.nan
    mlv = ml[(ml.index.get_level_values("technology")==tech) &
             (ml.index.get_level_values("location")=="ES") &
             (ml.index.get_level_values("time_operation")==H)]
    mlv=float(mlv.iloc[0]) if len(mlv) else 1.0
    avail=mlv*capv
    util=100*fl/avail if avail else np.nan
    nu=ccf[(ccf.index.get_level_values("technology")==tech) &
           (ccf.index.get_level_values("node")=="ES") &
           (ccf.index.get_level_values("time_operation")==H)]
    nuv=float(nu.iloc[0]) if len(nu) else np.nan
    interior = "YES" if (fl>1e-6 and util<99.0) else ("idle" if fl<=1e-6 else "AT-CAP")
    if fl>1e-9 or (capv and capv>1e-6):
        rows.append((tech,fl,avail,util,nuv,interior))
for tech,fl,avail,util,nuv,interior in sorted(rows,key=lambda r:-r[1]):
    print(f"{tech:22} {fl:9.3f} {avail:9.3f} {util:7.1f} {nuv:11.3f} {interior:>9}")

# 4) duality check: is lambda_ES = lambda_neighbor + congestion?
print(f"\n=== DUALITY CHECK @ h{H} ===")
lam_es=lamnode("ES")
for nb in ["FR","PT"]:
    e=f"{nb}-ES"; e2=f"ES-{nb}"
    for ed in (e,e2):
        cd = cft[(cft.index.get_level_values("technology")=="power_line") &
                 (cft.index.get_level_values("edge")==ed) &
                 (cft.index.get_level_values("time_operation")==H)]
        if len(cd):
            cdv=float(cd.iloc[0])
            print(f"  via {ed}: lambda_{nb}={lamnode(nb):.2f} + |congDual|={abs(cdv):.2f} "
                  f"= {lamnode(nb)+abs(cdv):.2f}   vs lambda_ES={lam_es:.2f}")

# 5) transport losses on the import lines + does the lossy duality relation close?
print(f"\n=== transport losses + lossy duality relation @ h{H} ===")
ftl = s(VAR, "flow_transport_loss")
def floss(edge):
    fk=("power_line",edge,H); lk=("power_line",edge,H)
    f=float(ft.loc[fk]) if fk in ft.index else np.nan
    l=float(ftl.loc[lk]) if lk in ftl.index else np.nan
    return f,l
for nb,edge in [("FR","FR-ES"),("PT","PT-ES")]:
    f,l=floss(edge)
    lossfrac=l/f if f else np.nan
    cd=cft[(cft.index.get_level_values("technology")=="power_line") &
           (cft.index.get_level_values("edge")==edge) &
           (cft.index.get_level_values("time_operation")==H)]
    cong=abs(float(cd.iloc[0])) if len(cd) else np.nan
    landed=(lamnode(nb)+cong)
    implied=landed/(1-lossfrac) if lossfrac==lossfrac else np.nan
    print(f"  {edge}: flow {f:.3f}, loss {l:.4f} ({100*lossfrac:.2f}%);  "
          f"(lambda_{nb}+cong)/(1-loss) = {implied:.2f}  vs lambda_ES={lamnode('ES'):.2f}")

# 6) any demand shedding at ES h0? (VOLL = upper bound of the price interval)
print(f"\n=== demand shedding @ ES h{H} ===")
try:
    shed=s(VAR,"shed_demand") if "/shed_demand" in pd.HDFStore(VAR,'r').keys() else None
except Exception:
    shed=None
with pd.HDFStore(VAR,'r') as st:
    shedkeys=[k for k in st.keys() if 'shed' in k.lower()]
print("  shed vars:", shedkeys)
for k in shedkeys:
    d=s(VAR,k)
    try:
        sub=d[(d.index.get_level_values("carrier")=="electricity") &
              (d.index.get_level_values("node")=="ES") &
              (d.index.get_level_values("time_operation")==H)]
        print(f"   {k} @ES,elec,h0 = {float(sub.iloc[0]) if len(sub) else 'n/a'}")
    except Exception as e:
        print(f"   {k}: {e}")
