"""Minimal LP reproducing the saturated-island dual degeneracy (nuclear@ES essence).
ONE node, demand D. Supply:
  g1 = local renewables : cost 5,  cap 6   (maps to ES wind/PV/hydro at cap)
  g2 = import via line  : cost 8,  cap 4   (maps to FR/PT import at line cap; cost = landed neighbour price)
  shed = lost load      : cost 100 (= VOLL, upper bound on price)
Candidate to "build": nuclear, run-cost c_nuc=3, capex-per-hour k=6.
At D=10 the two supply sources EXACTLY meet demand -> both at cap -> nothing marginal
-> the balance dual lambda (the electricity price) is NON-UNIQUE.
"""
import numpy as np
from scipy.optimize import linprog

C_NUC, K = 3.0, 6.0
def solve(D):
    c   = [5., 8., 100.]                      # g1, g2, shed
    Aeq = [[1., 1., 1.]]; beq = [D]           # balance: g1+g2+shed = D
    Aub = [[1.,0.,0.],[0.,1.,0.]]; bub=[6.,4.]# caps g1<=6, g2<=4
    r = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq,
                bounds=[(0,None)]*3, method="highs")
    lam = r.eqlin.marginals[0]            # price (economic convention)
    mu  = -r.ineqlin.marginals                # cap rents
    return r, lam, mu

print(f"{'D':>7} {'g1':>6} {'g2':>6} {'shed':>6} | {'lambda':>8} {'mu1':>7} {'mu2':>7} | "
      f"{'nuc value=lam-3':>15} {'RC=k-value':>11} {'build?':>7}")
for D in [9.999, 10.000, 10.001]:
    r, lam, mu = solve(D)
    g1,g2,shed = r.x
    val = lam - C_NUC
    rc  = K - val
    print(f"{D:7.3f} {g1:6.3f} {g2:6.3f} {shed:6.3f} | {lam:8.3f} {mu[0]:7.3f} {mu[1]:7.3f} | "
          f"{val:15.3f} {rc:11.3f} {('YES' if rc<0 else 'no'):>7}")

print("\n--- dual feasible OPTIMAL set at D=10 (analytic) ---")
print("KKT: lambda = 5+mu1 = 8+mu2, mu1,mu2>=0, shed=0 -> lambda<=100")
print("=> lambda in [8, 100], mu1=lambda-5, mu2=lambda-8  (a whole INTERVAL)")
for lam in [8., 50., 100.]:
    mu1, mu2 = lam-5, lam-8
    dual_obj = 10*lam - 6*mu1 - 4*mu2
    val = lam - C_NUC; rc = K - val
    print(f"  lambda={lam:6.1f} -> mu1={mu1:5.1f} mu2={mu2:5.1f} | dual_obj={dual_obj:6.2f} "
          f"(primal cost=62) | nuc value={val:6.2f}  RC={rc:7.2f}")
print("\nprimal cost check: 5*6 + 8*4 = 62")
