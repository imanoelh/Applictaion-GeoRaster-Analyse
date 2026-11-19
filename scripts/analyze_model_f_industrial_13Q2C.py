from __future__ import annotations
import json
from pathlib import Path
import numpy as np, rasterio
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test'
ARCH=ROOT/'backend/data/models/building/experimental/benchmark_13Q1_FINAL'
OUT=ROOT/'backend/data/models/building/experimental/benchmark_13Q2C'; OUT.mkdir(parents=True,exist_ok=True)
PIDS=['GT_2024_difficult_02','GT_2024_industrial_02','GT_2024_residential_02','GT_2025_difficult_02','GT_2025_industrial_02','GT_2025_residential_02']; THS=[.35,.40,.45,.50,.55,.60]
def load(p):
    with rasterio.open(p) as s:return s.read(1),s.transform,s.crs
def dil(m):
    o=m.copy()
    for dr in(-1,0,1):
        for dc in(-1,0,1):o|=np.roll(np.roll(m,dr,0),dc,1)
    o[[0,-1],:]=False;o[:,[0,-1]]=False;return o
def edge(m):
    e=m.copy()
    for dr in(-1,0,1):
        for dc in(-1,0,1):
            if dr==dc==0:continue
            q=np.zeros_like(m);r0=max(0,dr);r1=m.shape[0]+min(0,dr);c0=max(0,dc);c1=m.shape[1]+min(0,dc);q[r0:r1,c0:c1]=m[r0-dr:r1-dr,c0-dc:c1-dc];e&=q
    return m^e
def score(p,g):
    p=p.astype(bool);g=g.astype(bool);tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());i=tp/(tp+fp+fn) if tp+fp+fn else 1.;d=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.;pr=tp/(tp+fp) if tp+fp else 0.;rc=tp/(tp+fn) if tp+fn else 0.;pb,gb=edge(p),edge(g);a=int((pb&dil(gb)).sum());b=int((gb&dil(pb)).sum());bf=2*a/(pb.sum()+gb.sum()) if pb.sum()+gb.sum() else 1.;return dict(iou=i,dice=d,precision=pr,recall=rc,f1=d,boundary_f1=bf,tp=tp,fp=fp,fn=fn)
def main():
    probs={};refs={}
    for pid in PIDS: probs[pid],_,_=load(ARCH/'model_f/probability'/(pid+'.tif')); refs[pid],_,_=load(BASE/'qa_13M1A/masks'/(pid+'_ground_truth_mask.tif'))
    sweep=[]
    for group,ids in [('industrial',[p for p in PIDS if 'industrial' in p]),('residential_difficult',[p for p in PIDS if 'industrial' not in p]),('all',PIDS)]:
        for th in THS:
            ss=[score(probs[p]>=th,refs[p]) for p in ids]; sweep.append({'group':group,'threshold':th,**{k:float(np.mean([x[k] for x in ss])) for k in ('iou','dice','precision','recall','f1','boundary_f1')}})
    baseline=[]
    for model,folder in [('MODEL_C','model_c'),('MODEL_F','model_f')]:
        for group,ids in [('industrial',[p for p in PIDS if 'industrial' in p]),('residential_difficult',[p for p in PIDS if 'industrial' not in p]),('all',PIDS)]:
            ss=[]
            for p in ids:
                a=probs[p] if model=='MODEL_F' else load(ARCH/folder/'probability'/(p+'.tif'))[0];ss.append(score(a>=.5,refs[p]))
            baseline.append({'model':model,'group':group,**{k:float(np.mean([x[k] for x in ss])) for k in ('iou','dice','precision','recall','f1','boundary_f1')}})
    stats=[]
    for p in PIDS:
        g=refs[p].astype(bool);q=probs[p];band=dil(g)&~g;inside=q[g];outside=q[band];stats.append({'patch_id':p,'context':'industrial' if 'industrial' in p else 'residential_difficult','gt_pixels':int(g.sum()),'inside':{k:float(np.percentile(inside,v)) for k,v in [('mean',50),('p10',10),('p25',25),('p50',50),('p75',75),('p90',90),('max',100)]},'boundary_band_mean':float(outside.mean()) if outside.size else None})
    (OUT/'threshold_sweep.json').write_text(json.dumps(sweep,indent=2),encoding='utf-8');(OUT/'baseline_context_metrics.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8');(OUT/'probability_stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8');print(json.dumps({'sweep':sweep,'baseline':baseline,'probability_stats':stats},indent=2))
if __name__=='__main__':main()
