"""CONFIRMATORY validation of the size-meter candidate, pre-registered, on
INDEPENDENT data (NASDAQ — the candidate came from SP500). Tests ONLY the 3
pre-specified live/global thermodynamic signals. A real size-meter replicates
across markets; an SP500 fluke won't."""
import sys, csv, math, random
sys.path.insert(0, "src")
import numpy as np
from scipy.stats import spearmanr
from ophamin.seeing.substrate import KimeraAdapter

REPO="/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
FRED="data/raw/financial/fred/NASDAQCOM.csv"   # INDEPENDENT series
N,K,SEARCH=7,8,300
PREREGISTERED=[                                  # fixed BEFORE the run
  "thermo_bridge_state.ness.rolling_mean_sigma",     # primary (sweep rho=0.976)
  "thermo_bridge_state.ness.sigma_total",
  "thermo_bridge_state.layer2.entanglement_entropy",
]
def load():
    px=[]
    for r in csv.reader(open(FRED)):
        if len(r)<2 or r[0]=="observation_date": continue
        try: px.append(float(r[1]))
        except: pass
    return [px[i]/px[i-1]-1 for i in range(1,len(px)) if px[i-1]]
def mdd(r):
    p=np.cumprod(1+np.asarray(r,float)); pk=np.maximum.accumulate(p); return float(abs((p/pk-1).min()))
def min_max_dd(ms):
    c={tuple(sorted(ms,reverse=True)):0,tuple(sorted(ms)):0}
    for s in range(SEARCH):
        a=list(ms); random.Random(s).shuffle(a); c[tuple(a)]=0
    sc={k:mdd(k) for k in c}; lo=min(sc,key=sc.get); hi=max(sc,key=sc.get); return lo,sc[lo],hi,sc[hi]
def render(i,r): return f"market day {i+1}: return {r:+.4f}"
def flat(raw,pre="",dep=0,o=None):
    if o is None: o={}
    if dep>6 or not isinstance(raw,dict): return o
    for k,v in raw.items():
        key=f"{pre}.{k}" if pre else k
        if isinstance(v,bool): continue
        if isinstance(v,(int,float)) and math.isfinite(float(v)): o[key]=float(v)
        elif isinstance(v,dict): flat(v,key,dep+1,o)
    return o
ret=load()
wins=[tuple(ret[i:i+N]) for i in range(0,len(ret)-N,N)]
wins=[w for w in wins if any(x>0 for x in w) and any(x<0 for x in w)]
vols=[np.std(w) for w in wins]; order=sorted(range(len(wins)),key=lambda k:vols[k])
windows=[wins[order[round(k*(len(order)-1)/(K-1))]] for k in range(K)]
ad=KimeraAdapter(REPO,target="entity",mode="batch",batch_timeout=10800.0)
print(f"CONFIRMATORY @ {ad.git_commit()[:12]} | series=NASDAQ (independent) | K={K}")
print("pre-registered:", PREREGISTERED)
ddd=[]; divs={f:[] for f in PREREGISTERED}
for wi,ms in enumerate(windows):
    lo,lo_dd,hi,hi_dd=min_max_dd(ms)
    flo=flat(ad.run_batch([render(i,r) for i,r in enumerate(lo)])[-1].raw)
    fhi=flat(ad.run_batch([render(i,r) for i,r in enumerate(hi)])[-1].raw)
    ddd.append(abs(hi_dd-lo_dd))
    for f in PREREGISTERED:
        if f in flo and f in fhi:
            a,b=flo[f],fhi[f]; den=abs(a)+abs(b); divs[f].append(abs(a-b)/den if den else 0.0)
        else: divs[f].append(None)
    print(f"  window {wi}: ΔDD={abs(hi_dd-lo_dd):.4f}")
print("\n=== CONFIRMATORY RESULT (independent NASDAQ data) ===")
for f in PREREGISTERED:
    y=divs[f]
    if any(v is None for v in y): print(f"  {f}: absent on some windows"); continue
    if len(set(y))<2: print(f"  {f}: no variance"); continue
    rho,p=spearmanr(ddd,y,alternative="greater")
    verdict="CONFIRMED" if (rho>0 and p<0.05) else "not confirmed"
    print(f"  {f}\n     rho={rho:.3f} p={p:.4f}  -> {verdict}")
