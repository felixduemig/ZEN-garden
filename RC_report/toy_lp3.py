"""RIGOROUS minimal counterexample: at a degenerate no-build vertex the dispatch price
is non-unique on an interval [p_lo, p_hi]; the operational RC reads p_hi (the
*demand-relief* / scarcity value) while a finite build of a new SUPPLY tech realizes
only p_lo (the *supply-displacement* value).  => RC over-states the build value, and the
gap is exactly the width of the degenerate price interval = the self-cannibalization the
first finite build triggers.  Mirrors CB nuclear@ES (price robustly pinned at p_hi).

1 node, 2 identical hours (weight 1). Demand D=100 each hour.
  Incumbent BASE G1 : cap 100, cost 10   (cheap, at cap at the no-build optimum)
  Incumbent PEAK G2 : cap 100, cost 50   (idle at the no-build optimum)
  Candidate BASE  C : cost 5, available both hours, invest cost I per unit firm cap.
"""
import numpy as np
from scipy.optimize import linprog
H=2; D=100.0; c1,c2,cC=10.0,50.0,5.0

def dispatch(Ccap=0.0, dp=0.0):
    # vars g1_t,g2_t,c_t
    cost=np.array([c1,c1,c2,c2,cC,cC])
    A_eq=np.array([[1,0,1,0,1,0],[0,1,0,1,0,1]],float); b_eq=np.array([D+dp,D+dp])
    bnds=[(0,100)]*2+[(0,100)]*2+[(0,Ccap)]*2
    r=linprog(cost,A_eq=A_eq,b_eq=b_eq,bounds=bnds,method='highs')
    return r, np.abs(r.eqlin.marginals)

r0,lam=dispatch(0.0)
print('NO-BUILD: g1=%.0f,%.0f  g2=%.0f,%.0f  (G1 at cap, G2 idle => DEGENERATE vertex)'%tuple(r0.x[:4]))
print('HiGHS reports price lambda =',np.round(lam,2))
# reveal the degenerate price INTERVAL by one-sided RHS perturbation
_,lam_up =dispatch(0.0,dp=+1e-4)   # +demand: marginal unit is G2  -> p_hi
_,lam_dn =dispatch(0.0,dp=-1e-4)   # -demand: marginal unit is G1  -> p_lo
p_hi,p_lo=lam_up[0],lam_dn[0]
print('right-derivative price p_hi (demand+) = %.1f   (= G2 cost, the DEMAND-RELIEF value)'%p_hi)
print('left -derivative price p_lo (demand-) = %.1f   (= G1 cost, the SUPPLY-DISPLACE value)'%p_lo)
print('=> optimal dispatch price is NON-UNIQUE on [%.0f, %.0f] (dual degeneracy)\n'%(p_lo,p_hi))

for tag,p in [('reads p_hi (scarcity/Gurobi-CB)',p_hi),('reads p_lo (right derivative)',p_lo)]:
    V=2*max(0.0,p-cC)
    print('  operational RC %s: lambda=%.0f -> reconstructed break-even I* = %.0f'%(tag,p,V))

def build_x(I):
    cost=np.array([c1,c1,c2,c2,cC,cC,I])
    A_eq=np.array([[1,0,1,0,1,0,0],[0,1,0,1,0,1,0]],float); b_eq=np.array([D,D])
    A_ub=np.array([[0,0,0,0,1,0,-1],[0,0,0,0,0,1,-1]],float); b_ub=[0,0]
    bnds=[(0,100)]*2+[(0,100)]*2+[(0,None)]*2+[(0,None)]
    return linprog(cost,A_ub=A_ub,b_ub=b_ub,A_eq=A_eq,b_eq=b_eq,bounds=bnds,method='highs').x[-1]
lo,hi=0.0,200.0
for _ in range(50):
    m=(lo+hi)/2
    if build_x(m)>1e-6: lo=m
    else: hi=m
true_be=(lo+hi)/2
print('\\nTRUE break-even invest cost (finite re-solve / bisection) = %.1f'%true_be)
print('  (= 2*(G1cost-Ccost)=2*(10-5)=10 ; new base displaces the CHEAP running G1, not idle G2)')
print('RECONSTRUCTED break-even if RC reads p_hi=%.0f : %.0f  => OVER-STATEMENT %.1fx'%(p_hi,2*(p_hi-cC),(2*(p_hi-cC))/true_be))
print('At I=%.0f (just below the p_hi reconstruction): built capacity = %.4f  => NO BUILD'%(2*(p_hi-cC)-1, build_x(2*(p_hi-cC)-1)))
print('\\nVERDICT: RC is correct iff the solver reports the LOW end p_lo (the right-derivative).')
print('At a scarcity vertex CB-Gurobi robustly reports p_hi -> intrinsic over-statement;')
print('the missing info (how far price falls on a finite build) is NOT in any single-solve dual.')
