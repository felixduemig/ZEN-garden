"""Minimal toy LP proving WHY the operational RC over-states the build value at a
degenerate (scarcity) no-build vertex.  scipy.optimize.linprog, sub-second.

Setup (1 node, 2 identical hours, weight 1 each):
  demand d = 100 each hour.
  Incumbent base generator G1: cap 100, marginal cost 10.
  Incumbent peak generator  G2: cap 100, marginal cost 50.
  Candidate BASELOAD tech C: marginal cost 5, available both hours,
     specific investment cost I (per unit firm capacity, both hours).

No-build optimum: G1=100 (at cap), G2=0.  Demand met exactly, no shed.
=> G1 at its UPPER bound, G2 at its LOWER bound (0): a DEGENERATE vertex.
The energy-balance price lambda is NOT unique: lambda in [10, 50].
   - reduced cost of G2 (at 0): 50 - lambda >= 0  ->  lambda <= 50
   - cap-dual of G1 (at cap):   lambda = 10 + mu1, mu1>=0 -> lambda >= 10
The cap-factor / operational RC reads ONE lambda (whatever the solver reports)
and values C at (lambda - 5) per hour.  But a finite build of C displaces G1
(cost 10), NOT G2 (cost 50, which is idle).  So:
   reconstructed value/unit  = 2*(lambda - 5)         (lambda up to 50 -> up to 90)
   TRUE marginal value/unit  = 2*(10 - 5) = 10        (G1 displaced)
"""
import numpy as np
from scipy.optimize import linprog

def solve_dispatch(C_cap, lam_report='high', eps=0.0):
    # variables: g1_1,g1_2,g2_1,g2_2,c_1,c_2  (>=0)
    # cost
    c = np.array([10,10, 50,50, 5,5], float)
    # equality: g1_t+g2_t+c_t = d_t
    d = 100.0
    A_eq = np.array([[1,0, 1,0, 1,0],
                     [0,1, 0,1, 0,1]], float)
    b_eq = np.array([d+eps, d+eps])
    # bounds: g1<=100, g2<=100, c<=C_cap
    bnds = [(0,100)]*2 + [(0,100)]*2 + [(0,C_cap)]*2
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bnds, method='highs')
    return res

# ---- 1. no-build solve, extract reported price -----------------------------
res0 = solve_dispatch(C_cap=0.0)
g = res0.x
lam = -res0.eqlin.marginals   # shadow price of demand balance (per hour)
print('NO-BUILD dispatch  g1=%.1f,%.1f  g2=%.1f,%.1f' % (g[0],g[1],g[2],g[3]))
print('reported energy price lambda per hour =', np.round(lam,4))
print('  (theory: lambda non-unique in [10,50]; HiGHS reports one vertex)')

# reconstructed operational value of 1 unit of C  (cap-factor dual ~ lambda - cost_C)
nu = np.maximum(0.0, lam - 5.0)         # per-hour cap-factor dual for C
V_recon = nu.sum()                      # value per unit capacity (2 hrs, weight 1)
print('reconstructed value of 1 unit C  = sum_t max(0,lambda-5) =', round(V_recon,4))
print('=> reconstructed break-even invest cost I* =', round(V_recon,4))

# ---- 2. TRUE build value: re-solve at a grid of I, find threshold ----------
def builds(I, C_cap=200.0):
    # full investment LP: minimize dispatch + I*C_cap_used
    # var: g1_1,g1_2,g2_1,g2_2,c_1,c_2, x(capacity)
    c = np.array([10,10,50,50,5,5, I], float)
    A_eq = np.array([[1,0,1,0,1,0,0],
                     [0,1,0,1,0,1,0]], float)
    b_eq = np.array([100.0,100.0])
    # c_t <= x  ->  c_t - x <= 0
    A_ub = np.array([[0,0,0,0,1,0,-1],
                     [0,0,0,0,0,1,-1]], float)
    b_ub = np.array([0.0,0.0])
    bnds = [(0,100)]*2+[(0,100)]*2+[(0,None)]*2+[(0,None)]
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bnds, method='highs')
    return r.x[-1]   # built capacity x

grid = [5,9,9.9,10,10.1,20,45,50,70,89,90,91]
print('\\n  I (invest)   built capacity x')
for I in grid:
    print('   %6.1f        %.4f' % (I, builds(I)))
true_be = 10.0
print('\\nTRUE break-even invest cost (C displaces G1@10, value=2*(10-5)) =', true_be)
print('RECONSTRUCTED break-even =', round(V_recon,4),
      ' -> OVER-STATEMENT factor =', round(V_recon/true_be,2),'x')
print('At I just below reconstructed break-even (e.g. I=89<%.0f): build = %.4f  => NO BUILD (validation FAIL)'%(V_recon, builds(89)))
