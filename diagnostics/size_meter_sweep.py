"""FULL-SURFACE size-meter sweep: of ALL ~4000 Kimera signals, does ANY grade by
the SIZE of an order-dependent risk difference (max drawdown)? Uses the complete
field surface we just mapped. Same real return multiset, min-DD vs max-DD order
(opposite risk, identical trades), across windows of varying ΔDD; per signal,
Spearman(ΔDD across windows, that signal's min-vs-max divergence). A size-meter
is a signal whose divergence rises with the size of the risk gap."""
import sys, csv, math, random
sys.path.insert(0, "src")
import numpy as np
from scipy.stats import spearmanr
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
FRED = "data/raw/financial/fred/SP500.csv"
N, K, SEARCH = 7, 8, 300

def load_returns():
    px=[]
    for r in csv.reader(open(FRED)):
        if len(r)<2 or r[0]=="observation_date": continue
        try: px.append(float(r[1]))
        except: pass
    return [px[i]/px[i-1]-1 for i in range(1,len(px)) if px[i-1]]

def mdd(r):
    p=np.cumprod(1+np.asarray(r,float)); pk=np.maximum.accumulate(p)
    return float(abs((p/pk-1).min()))

def min_max_dd(ms):
    cands={tuple(sorted(ms,reverse=True)):0, tuple(sorted(ms)):0}
    for s in range(SEARCH):
        a=list(ms); random.Random(s).shuffle(a); cands[tuple(a)]=0
    scored={k:mdd(k) for k in cands}
    lo=min(scored,key=scored.get); hi=max(scored,key=scored.get)
    return lo, scored[lo], hi, scored[hi]

def render(i,r): return f"market day {i+1}: return {r:+.4f}"

def flatten(raw, prefix="", depth=0, out=None):
    if out is None: out={}
    if depth>6 or not isinstance(raw,dict): return out
    for k,v in raw.items():
        key=f"{prefix}.{k}" if prefix else k
        if isinstance(v,bool): continue
        if isinstance(v,(int,float)) and math.isfinite(float(v)): out[key]=float(v)
        elif isinstance(v,dict): flatten(v,key,depth+1,out)
    return out

ret=load_returns()
wins=[tuple(ret[i:i+N]) for i in range(0,len(ret)-N,N)]
wins=[w for w in wins if any(x>0 for x in w) and any(x<0 for x in w)]
vols=[np.std(w) for w in wins]; order=sorted(range(len(wins)),key=lambda k:vols[k])
windows=[wins[order[round(k*(len(order)-1)/(K-1))]] for k in range(K)]

ad=KimeraAdapter(REPO,target="entity",mode="batch",batch_timeout=10800.0)
print(f"size-meter sweep @ {ad.git_commit()[:12]}  K={K} windows, full field surface")
wdata=[]
for wi,ms in enumerate(windows):
    lo,lo_dd,hi,hi_dd=min_max_dd(ms)
    flo=flatten((ad.run_batch([render(i,r) for i,r in enumerate(lo)])[-1].raw))
    fhi=flatten((ad.run_batch([render(i,r) for i,r in enumerate(hi)])[-1].raw))
    wdata.append((abs(hi_dd-lo_dd), flo, fhi))
    print(f"  window {wi}: ΔDD={abs(hi_dd-lo_dd):.4f}  fields={len(flo)}")

common=set(wdata[0][1])&set(wdata[0][2])
for _,flo,fhi in wdata[1:]: common &= (set(flo)&set(fhi))
ddd=[wd[0] for wd in wdata]
results=[]
for f in common:
    divs=[]
    for _,flo,fhi in wdata:
        a,b=flo[f],fhi[f]; den=abs(a)+abs(b); divs.append(abs(a-b)/den if den else 0.0)
    if len(set(divs))>1:
        rho,p=spearmanr(ddd,divs,alternative="greater")
        if rho==rho: results.append((f,float(rho),float(p),float(np.mean(divs))))
results.sort(key=lambda x:(-x[1],x[2]))
print(f"\nfields present in all {K} windows: {len(common)}  | testable (varying): {len(results)}")
print(f"\n=== TOP candidate size-meters (signal divergence rises with ΔDD) ===")
print(f"{'rho':>6} {'p':>8} {'meandiv':>8}  field")
for f,rho,p,md in results[:25]:
    print(f"{rho:>6.3f} {p:>8.4f} {md:>8.4f}  {f}")
sig=[r for r in results if r[2]<0.05 and r[1]>0]
print(f"\nfields with rho>0 & p<0.05: {len(sig)} of {len(results)} tested "
      f"(expected ~{int(0.05*len(results))} by chance — multiple comparisons; candidates only)")
