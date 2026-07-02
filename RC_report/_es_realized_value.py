"""READ-ONLY (no solve). Resolve the nuclear@ES contradiction by decomposing the
operational value per typical hour, clean(no-build) vs at-the-7.163GW-build.

opval = sum_t max_load_t * nu_t      (nu = dual of constraint_capacity_factor_conversion)
RC_op = capex - (opval - fix_opex*discount_sum) / scaling

clean nu  : runC/dual_dict.h5            (nuclear@ES NOT built)
build nu  : es_finite_proof/dual_dict.h5 (nuclear@ES built 7.163 GW at 0.5x capex)
The 0.5x build == the break-even build (step to the same 7.163 ceiling), so the
finite_proof equilibrium IS the break-even equilibrium -> its opval gives the TRUE
realizable value -> the implied break-even capex/cut."""
import os, sys
import numpy as np, pandas as pd
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNC = os.path.join(BASE, "outputs_CB_overnight", "runC", "Crystal_Ball")
BUILD = os.path.join(BASE, "outputs_CB_overnight", "es_finite_proof", "Crystal_Ball")

CAPEX_FULL = 5578.7
SCALING = 0.053667
FIX_OPEX = 98.881409
DISCOUNT_SUM = 1.0          # single-year snapshot, df0 = 1.0
KEY = "constraint_capacity_factor_conversion"


def load_nu(folder):
    d = pd.read_hdf(os.path.join(folder, "dual_dict.h5"), KEY)
    s = d if isinstance(d, pd.Series) else d.iloc[:, 0]
    df = s.rename("nu").reset_index()
    names = [c for c in df.columns if c != "nu"]
    # identify tech / node / time columns
    def pick(kind):
        for n in names:
            low = str(n).lower()
            if kind == "tech" and "techno" in low: return n
            if kind == "node" and ("node" in low or "location" in low): return n
            if kind == "time" and "time" in low: return n
        return None
    tc, nc, timec = pick("tech"), pick("node"), pick("time")
    sub = df[(df[tc] == "nuclear") & (df[nc] == "ES")].copy()
    sub = sub[[timec, "nu"]].rename(columns={timec: "t"})
    sub["t"] = sub["t"].astype(int)
    return sub.set_index("t")["nu"].sort_index()


def load_maxload(folder):
    p = pd.read_hdf(os.path.join(folder, "param_dict.h5"), "max_load")
    s = p if isinstance(p, pd.Series) else p.iloc[:, 0]
    df = s.rename("m").reset_index()
    names = [c for c in df.columns if c != "m"]
    def pick(kind):
        for n in names:
            low = str(n).lower()
            if kind == "tech" and "techno" in low: return n
            if kind == "node" and ("node" in low or "location" in low): return n
            if kind == "time" and "time" in low: return n
        return None
    tc, nc, timec = pick("tech"), pick("node"), pick("time")
    sub = df[(df[tc] == "nuclear") & (df[nc] == "ES")].copy()
    sub = sub[[timec, "m"]].rename(columns={timec: "t"})
    sub["t"] = sub["t"].astype(int)
    return sub.set_index("t")["m"].sort_index()


def load_price(folder):
    d = pd.read_hdf(os.path.join(folder, "dual_dict.h5"), "constraint_nodal_energy_balance")
    s = d if isinstance(d, pd.Series) else d.iloc[:, 0]
    df = s.rename("lam").reset_index()
    car = [c for c in df.columns if "carrier" in str(c).lower()][0]
    nod = [c for c in df.columns if "node" in str(c).lower()][0]
    tim = [c for c in df.columns if "time" in str(c).lower()][0]
    sub = df[(df[car] == "electricity") & (df[nod] == "ES")].copy()
    sub = sub[[tim, "lam"]].rename(columns={tim: "t"})
    sub["t"] = sub["t"].astype(int)
    return sub.set_index("t")["lam"].sort_index()


nu_c = load_nu(RUNC)
nu_b = load_nu(BUILD)
ml_c = load_maxload(RUNC)
lam_c = load_price(RUNC)
lam_b = load_price(BUILD)

# nuclear is built in BUILD but NOT in runC -> the capacity_factor constraint may be
# absent/NaN at no-build. Report what we have.
print("max_load_t (nuclear ES):", dict(ml_c.round(3)))
print()
hdr = f"{'t':>2} {'lam_clean':>10} {'lam_build':>10} {'nu_clean':>10} {'nu_build':>10} {'m':>6}"
print(hdr); print("-"*len(hdr))
allt = sorted(set(nu_c.index) | set(nu_b.index) | set(lam_c.index) | set(lam_b.index))
for t in allt:
    print(f"{t:>2} {lam_c.get(t,np.nan):>10.3f} {lam_b.get(t,np.nan):>10.3f} "
          f"{nu_c.get(t,np.nan):>10.4f} {nu_b.get(t,np.nan):>10.4f} {ml_c.get(t,np.nan):>6.3f}")

def opval(nu, ml):
    common = nu.index.intersection(ml.index)
    return float((ml.loc[common] * nu.loc[common]).sum()), {int(t): float(ml.get(t,0)*nu.get(t,0)) for t in nu.index}

ov_c, contrib_c = opval(nu_c, ml_c)
ov_b, contrib_b = opval(nu_b, ml_c)
print()
print(f"opval_clean (no-build nu)  = {ov_c:10.3f}")
print(f"opval_build (7.163GW nu)   = {ov_b:10.3f}")
rc_c = CAPEX_FULL - (ov_c - FIX_OPEX*DISCOUNT_SUM)/SCALING
print(f"\nRC_op clean  = {rc_c:8.2f} EUR/kW  ({100*rc_c/CAPEX_FULL:5.2f}%)   [target 125.99 / 2.26% -> validates method]")
# break-even capex from the realized (build) value:
capex_star = (ov_b - FIX_OPEX*DISCOUNT_SUM)/SCALING
cut_star = 1 - capex_star/CAPEX_FULL
print(f"break-even capex* (from build opval) = {capex_star:8.1f} EUR/kW")
print(f"implied break-even CUT = {100*cut_star:5.1f}%   [sweep bracket: (11.7%, 15%]]")
print("\nper-hour contribution to opval (max_load*nu):")
print(f"{'t':>2} {'clean':>12} {'build':>12} {'drop':>12}")
for t in sorted(set(contrib_c)|set(contrib_b)):
    c, b = contrib_c.get(t,0), contrib_b.get(t,0)
    print(f"{t:>2} {c:>12.2f} {b:>12.2f} {c-b:>12.2f}")
