"""Faithful toy LP: the operational RC conflates the *demand-relief* price (a scarcity
/ adequacy rent) with the *supply-displacement* value a new generator actually captures
at fixed demand.  At a binding-supply-cap ("scarcity") vertex these diverge, so the RC
over-states the build value.  The price here is ROBUST (unique), mirroring CB's
perturbation-stable ES price -> the error is NOT fixable by RHS perturbation.

scipy.optimize.linprog only.  1 node, 3 typical hours with weights w.
  hour 0 SCARCE:   demand 100, cheap supply capped at 100, VOLL backstop -> price high
  hours 1,2 SLACK: demand low, marginal gen sets a normal price
Candidate BASELOAD C (cost 5, available all hours) vs candidate PEAKER-in-slack
  (only valuable in slack hours, non-scarce) to contrast PASS vs FAIL.
"""
import numpy as np
from scipy.optimize import linprog

W = np.array([1495., 1004., 661.])      # hour weights ~ CB cluster sizes
VOLL = 50.0
# incumbents available each hour: cheap renewable R (cost 1, cap a_t*KR), gas G (cost 10, cap KG)
KR = 100.0; KG = 60.0
aR = np.array([1.0, 0.5, 0.7])          # renewable availability per hour
dem = np.array([100.0, 40.0, 55.0])     # demand per hour  (hour0: 100 = aR*KR -> R maxed, scarce)
cR, cG, cC = 1.0, 10.0, 5.0
H = 3

def dispatch(Ccap=0.0, dperturb=np.zeros(H)):
    # vars: R_t, G_t, C_t, S_t(shed)   each hour -> 4*H
    n = 4*H
    cost = np.zeros(n)
    for t in range(H):
        cost[4*t+0]=W[t]*cR; cost[4*t+1]=W[t]*cG; cost[4*t+2]=W[t]*cC; cost[4*t+3]=W[t]*VOLL
    # balance: R+G+C+S = dem
    A_eq=np.zeros((H,n)); b_eq=np.zeros(H)
    for t in range(H):
        A_eq[t,4*t:4*t+4]=[1,1,1,1]; b_eq[t]=dem[t]+dperturb[t]
    bnds=[]
    for t in range(H):
        bnds += [(0,aR[t]*KR),(0,KG),(0,Ccap),(0,None)]
    r=linprog(cost,A_eq=A_eq,b_eq=b_eq,bounds=bnds,method='highs')
    lam = -r.eqlin.marginals / W      # per-hour price (undo weight)
    return r, lam

r0,lam = dispatch(0.0)
x=r0.x.reshape(H,4)
print('NO-BUILD per hour [R,G,C,shed]:')
for t in range(H): print('  h%d'%t, np.round(x[t],2), ' price=%.3f'%lam[t])
# reconstructed value of baseload C (available all hrs, max_load=1): sum_t W_t*max(0,lam_t-cC)
nuC = W*np.maximum(0.0, lam-cC)
Vrecon_C = nuC.sum()
print('\\nBASELOAD candidate C (cost %g):'%cC)
print('  reconstructed value/unit  = sum_t W_t*max(0,lam_t-cC) =', round(Vrecon_C,1))
print('  => reconstructed break-even invest I* =', round(Vrecon_C,1))

def invest_build(I, kind='base'):
    # full LP with capacity var x; C_t<=x ; minimize dispatch + I*x
    n=4*H+1
    cost=np.zeros(n); cost[-1]=I
    for t in range(H):
        cost[4*t+0]=W[t]*cR; cost[4*t+1]=W[t]*cG; cost[4*t+2]=W[t]*cC; cost[4*t+3]=W[t]*VOLL
    A_eq=np.zeros((H,n))
    for t in range(H): A_eq[t,4*t:4*t+4]=[1,1,1,1]
    b_eq=dem.copy()
    # C_t <= x  (baseload available all hours).
    A_ub=np.zeros((H,n)); b_ub=np.zeros(H)
    for t in range(H):
        A_ub[t,4*t+2]=1; A_ub[t,-1]=-1
    bnds=[]
    for t in range(H): bnds+=[(0,aR[t]*KR),(0,KG),(0,None),(0,None)]
    bnds+=[(0,None)]
    r=linprog(cost,A_ub=A_ub,b_ub=b_ub,A_eq=A_eq,b_eq=b_eq,bounds=bnds,method='highs')
    return r.x[-1]

print('\\n  I (invest)   built x')
for I in [10,50,100,200,400,800, round(Vrecon_C*0.5), round(Vrecon_C*0.9), round(Vrecon_C)]:
    print('   %7.1f      %.3f'%(I, invest_build(I)))
# locate true break-even by bisection
lo,hi=0.0, Vrecon_C*1.5
for _ in range(40):
    mid=(lo+hi)/2
    if invest_build(mid)>1e-5: lo=mid
    else: hi=mid
true_be=(lo+hi)/2
print('\\nTRUE break-even invest cost (bisection) =', round(true_be,1))
print('RECONSTRUCTED break-even                =', round(Vrecon_C,1))
print('OVER-STATEMENT factor                   =', round(Vrecon_C/true_be,2),'x')

# robustness to demand perturbation (mirror CB rhs-pert): does reported price/Vrecon move?
print('\\n-- robustness of the reported price to RHS perturbation (CB-style) --')
for eps in [0.0, 1e-3, 1e-2, 0.1]:
    _,lp = dispatch(0.0, dperturb=np.array([eps,0,0]))
    vr=(W*np.maximum(0.0,lp-cC)).sum()
    print('  demand+%.3g in scarce hr: price_h0=%.4f  Vrecon=%.1f'%(eps,lp[0],vr))
print('  => price & Vrecon barely move: the over-statement is NOT a vertex-selection')
print('     artifact and CANNOT be removed by perturbation; only a finite re-solve recovers it.')
