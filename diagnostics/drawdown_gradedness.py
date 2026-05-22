"""DIAGNOSTIC (Tier-1 tooling): does Kimera's representation GRADE by max-drawdown,
or only DETECT order (saturated)? Same real return multiset, arrangements spanning
the FULL drawdown range (perfect set control). Resolves MEM4's open question."""
import sys, csv, random
sys.path.insert(0, "src")
import numpy as np
from scipy.stats import spearmanr
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
FRED = "data/raw/financial/fred/SP500.csv"
N, K, M = 7, 4, 5   # window len, #multisets, #arrangements spanning DD

def load_returns():
    px=[]
    for row in csv.reader(open(FRED)):
        if len(row)<2 or row[0]=="observation_date": continue
        try: px.append(float(row[1]))
        except ValueError: continue
    return [px[i]/px[i-1]-1 for i in range(1,len(px)) if px[i-1]]

def mdd(r):
    p=np.cumprod(1+np.asarray(r,float)); pk=np.maximum.accumulate(p)
    return float(abs((p/pk-1).min()))

def dd_spanning_arrangements(multiset, m):
    """m arrangements of the SAME multiset at evenly-spaced drawdown quantiles."""
    seen={}
    for s in range(400):
        a=list(multiset); random.Random(s).shuffle(a); a=tuple(a)
        seen[a]=mdd(a)
    # add sorted extremes (min/max DD candidates)
    seen[tuple(sorted(multiset,reverse=True))]=mdd(sorted(multiset,reverse=True))  # gains first ~ low DD
    seen[tuple(sorted(multiset))]=mdd(sorted(multiset))                            # losses first ~ high DD
    uniq=sorted(seen.items(), key=lambda kv: kv[1])
    idx=[round(k*(len(uniq)-1)/(m-1)) for k in range(m)]
    return [uniq[i] for i in idx]   # list of (arrangement, dd)

def render(i,r): return f"market day {i+1}: return {r:+.4f}"
def cstate(res):
    raw=res.raw or {}
    return {k:float(raw[v]) for k,v in [("c","arachne_web_coupling_frobenius"),("o","arachne_web_order_parameter"),("m","knowledge_mass")] if isinstance(raw.get(v),(int,float))}
def primes(res):
    ch=(res.raw or {}).get("prime_chain")
    return frozenset(str(p) for p in ch) if isinstance(ch,list) and ch else None
def jac(a,b): u=a|b; return len(a&b)/len(u) if u else 1.0
def sdist(a,b):
    ds=[abs(a[k]-b[k])/(abs(a[k])+abs(b[k])) if (abs(a[k])+abs(b[k])) else 0 for k in a if k in b]
    return float(np.mean(ds)) if ds else None

ret=load_returns()
wins=[tuple(ret[i:i+N]) for i in range(0,len(ret)-N,N)]
vols=[np.std(w) for w in wins]
order=sorted(range(len(wins)),key=lambda k:vols[k])
picks=[order[round(k*(len(order)-1)/(K-1))] for k in range(K)]
multisets=[wins[i] for i in picks]

ad=KimeraAdapter(REPO,target="entity",mode="batch",batch_timeout=10800.0)
print(f"diagnostic @ {ad.git_commit()[:12]}  K={K} multisets x M={M} DD-spanning arrangements")
all_ddd, all_pd, all_sd = [],[],[]
for wi,ms in enumerate(multisets):
    arrs=dd_spanning_arrangements(ms,M)
    ref_arr,ref_dd=arrs[0]
    res_ref=ad.run_batch([render(i,r) for i,r in enumerate(ref_arr)])[-1]
    pr_ref,st_ref=primes(res_ref),cstate(res_ref)
    print(f"\nwindow {wi} (vol={np.std(ms):.4f}) DD range {arrs[0][1]:.4f}..{arrs[-1][1]:.4f}")
    for arr,dd in arrs[1:]:
        res=ad.run_batch([render(i,r) for i,r in enumerate(arr)])[-1]
        ddd=dd-ref_dd
        pd=1-jac(pr_ref,primes(res)) if (pr_ref and primes(res)) else None
        sd=sdist(st_ref,cstate(res))
        all_ddd.append(ddd); all_pd.append(pd); all_sd.append(sd)
        print(f"   ΔDD={ddd:.4f}  prime_dist={pd}  state_dist={sd}")
print("\n=== POOLED (does representation grade by drawdown?) ===")
print("Spearman ΔDD vs prime_dist:", [round(x,4) for x in spearmanr(all_ddd,all_pd)])
print("Spearman ΔDD vs state_dist:", [round(x,4) for x in spearmanr(all_ddd,all_sd)])
