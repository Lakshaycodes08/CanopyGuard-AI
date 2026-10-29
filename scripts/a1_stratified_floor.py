import sys, glob, os, re, json
import numpy as np, rasterio

D=sys.argv[1]; NF=sys.argv[2]
NMAD_SCALE=1.4826
STABLE_LIMIT=3.0; SCALE=10; MINVALID=0.5

def nmad(a):
    a=np.asarray(a,float); return float(NMAD_SCALE*np.median(np.abs(a-np.median(a))))

def agg(arr, k, minvalid):
    h,w=arr.shape; H,W=h//k, w//k
    a=arr[:H*k,:W*k].reshape(H,k,W,k)
    valid=np.isfinite(a)
    cnt=valid.sum(axis=(1,3))
    s=np.where(valid,a,0.0).sum(axis=(1,3))
    out=np.where(cnt>=minvalid*k*k, s/np.maximum(cnt,1), np.nan)
    return out

ids=sorted({re.search(r'_t(\d+)\.tif$',f).group(1) for f in glob.glob(os.path.join(D,'chm_2022_t*.tif'))})
nf=json.load(open(NF)); adm=sorted({int(e["tile"]) for e in nf["heights"]})
print(f"tiles in zip: {len(ids)}   admitted tiles in noise_floor.json: {len(adm)}")
print(f"zip ids match admitted set: {sorted(int(i) for i in ids)==adm}")

alld=[]; allh=[]
for t in ids:
    fa=os.path.join(D,f'chm_2022_t{t}.tif'); fb=os.path.join(D,f'chm_2023_t{t}.tif')
    if not os.path.exists(fb): continue
    with rasterio.open(fa) as s: a=s.read(1).astype(float); nd=s.nodata
    with rasterio.open(fb) as s: b=s.read(1).astype(float); nd2=s.nodata
    for arr,n in ((a,nd),(b,nd2)):
        if n is not None: arr[arr==n]=np.nan
    valid=np.isfinite(a)&np.isfinite(b)
    ch=np.where(valid,b-a,np.nan)
    stable=valid&(np.abs(np.nan_to_num(ch))<=STABLE_LIMIT)
    am=np.where(stable,a,np.nan); bm=np.where(stable,b,np.nan)
    A=agg(am,SCALE,MINVALID); B=agg(bm,SCALE,MINVALID)
    d=B-A
    m=np.isfinite(d)&np.isfinite(A)
    alld.append(d[m]); allh.append(A[m])

d=np.concatenate(alld); h=np.concatenate(allh)
print(f"\npooled 10 m stable cells: {d.size:,}")
print(f"PUBLISHED  : cells 25,569   sigma 0.120079   mean -0.07996   LoD95 0.235354")
print(f"RECOMPUTED : cells {d.size:,}   sigma {nmad(d):.6f}   mean {d.mean():+.5f}   LoD95 {1.96*nmad(d):.6f}")

print("\n=== sigma stratified by 2022 canopy height of the SAME cell ===")
bins=[(-99,1),(1,2),(2,5),(5,10),(10,20),(20,30),(30,99)]
print(f"{'height band (m)':>16} {'cells':>9} {'sigma':>9} {'LoD95':>9} {'mean':>9}  vs pooled")
pool=nmad(d)
for lo,hi in bins:
    m=(h>=lo)&(h<hi)
    if m.sum()<50: continue
    s=nmad(d[m])
    lbl=f"{max(lo,0):g}-{hi:g}" if hi<99 else f">{lo:g}"
    print(f"{lbl:>16} {m.sum():>9,} {s:>9.4f} {1.96*s:>9.4f} {d[m].mean():>+9.4f}  {s/pool:>5.2f}x")
