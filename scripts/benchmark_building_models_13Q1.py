"""Deep, read-only 13Q.1 benchmark for available finalists.
Only archived C/H probabilities and the repaired six-patch GT masks are read.
Outputs are confined to benchmark_13Q1; production is never imported or changed.
"""
from __future__ import annotations
import json, time
from pathlib import Path
import numpy as np, rasterio
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test'
ARCH=ROOT/'backend/data/models/building/experimental/benchmark_13L/outputs'
OUT=ROOT/'backend/data/models/building/experimental/benchmark_13Q1'
PIDS=['GT_2024_difficult_02','GT_2024_industrial_02','GT_2024_residential_02','GT_2025_difficult_02','GT_2025_industrial_02','GT_2025_residential_02']

def load(path):
    with rasterio.open(path) as s: return s.read(1), s.profile.copy()
def boundary(m):
    m=m.astype(bool); er=m.copy()
    for dr in (-1,0,1):
      for dc in (-1,0,1):
       if dr==dc==0: continue
       q=np.zeros_like(m); r0=max(0,dr); r1=m.shape[0]+min(0,dr); c0=max(0,dc); c1=m.shape[1]+min(0,dc)
       q[r0:r1,c0:c1]=m[r0-dr:r1-dr,c0-dc:c1-dc]; er &= q
    return m^er
def dilate(m):
    out=m.copy()
    for dr in (-1,0,1):
      for dc in (-1,0,1): out |= np.roll(np.roll(m,dr,0),dc,1)
    out[[0,-1],:]=False; out[:,[0,-1]]=False; return out
def labels(m):
    m=m.astype(bool); lab=np.zeros(m.shape,np.int32); n=0
    for r,c in zip(*np.where(m & (lab==0))):
      n+=1; lab[r,c]=n; st=[(int(r),int(c))]
      while st:
       rr,cc=st.pop()
       for dr in (-1,0,1):
        for dc in (-1,0,1):
         if not(dr or dc): continue
         nr,nc=rr+dr,cc+dc
         if 0<=nr<m.shape[0] and 0<=nc<m.shape[1] and m[nr,nc] and lab[nr,nc]==0:
          lab[nr,nc]=n; st.append((nr,nc))
    return lab,n
def scores(p,g):
    p=p.astype(bool); g=g.astype(bool); tp=int((p&g).sum()); fp=int((p&~g).sum()); fn=int((~p&g).sum())
    i=tp/(tp+fp+fn) if tp+fp+fn else 1.; d=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.; pr=tp/(tp+fp) if tp+fp else 0.; rc=tp/(tp+fn) if tp+fn else 0.
    pb,gb=boundary(p),boundary(g); pd,gd=dilate(pb),dilate(gb); a=int((pb&gd).sum()); b=int((gb&pd).sum()); bf=2*a/(pb.sum()+gb.sum()) if pb.sum()+gb.sum() else 1.
    return {'iou':i,'dice':d,'precision':pr,'recall':rc,'f1':d,'boundary_f1_1px':bf,'tp':tp,'fp':fp,'fn':fn}
def overlay(rgb,mask):
    im=Image.fromarray(rgb.astype('uint8'),'RGB').convert('RGBA'); c=np.zeros((*mask.shape,4),np.uint8); c[mask.astype(bool)]=(255,40,20,100); return Image.alpha_composite(im,Image.fromarray(c,'RGBA')).convert('RGB')
def main():
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'overlays').mkdir(exist_ok=True); (OUT/'masks').mkdir(exist_ok=True)
    probs={m:{} for m in ('MODEL_C','MODEL_H')}; refs={}; rgbs={}; rows=[]
    for pid in PIDS:
      refs[pid],_=load(BASE/'qa_13M1A/masks'/(pid+'_ground_truth_mask.tif'))
      with rasterio.open(BASE/'images'/(pid+'.tif')) as s: rgbs[pid]=np.moveaxis(s.read((1,2,3)),0,-1)
      for model,folder in [('MODEL_C','model_c'),('MODEL_H','hotosm_unet_resnet34')]: probs[model][pid],prof=load(ARCH/folder/'probability'/(pid+'.tif'))
    threshold_rows=[]
    for model in probs:
      for th in (0.30,0.40,0.4371,0.50,0.60,0.70):
       ss=[scores(probs[model][p]>=th,refs[p]) for p in PIDS]; threshold_rows.append({'model':model,'threshold':th,**{k:float(np.mean([x[k] for x in ss])) for k in ('iou','dice','precision','recall','f1','boundary_f1_1px')}})
      ss=[scores(probs[model][p]>=.5,refs[p]) for p in PIDS]
      for pid,s in zip(PIDS,ss):
       pred=probs[model][pid]>=.5; lab,n=labels(pred); _,gn=labels(refs[pid]); r=dict(patch_id=pid,model=model,**s,predicted_components=n,reference_components=gn); rows.append(r)
       with rasterio.open(BASE/'images'/(pid+'.tif')) as src: profile=src.profile.copy()
       profile.update(driver='GTiff',count=1,dtype='uint8',compress='deflate',nodata=None)
       with rasterio.open(OUT/'masks'/(model+'_'+pid+'.tif'),'w',**profile) as dst: dst.write(pred.astype('uint8'),1)
       overlay(rgbs[pid],pred).save(OUT/'overlays'/(model+'_'+pid+'.png'))
    summary={}
    for model in probs:
      r=[x for x in rows if x['model']==model]; summary[model]={k:float(np.mean([x[k] for x in r])) for k in ('iou','dice','precision','recall','f1','boundary_f1_1px','predicted_components','reference_components')}
    (OUT/'threshold_sweep.json').write_text(json.dumps(threshold_rows,indent=2),encoding='utf-8'); (OUT/'patch_metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8'); (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    # Compact visual sheet: RGB, C and H per patch.
    cell=170; sheet=Image.new('RGB',(cell*3,cell*len(PIDS)),'white'); d=ImageDraw.Draw(sheet)
    for i,pid in enumerate(PIDS):
      for j,(label,im) in enumerate([('RGB',rgbs[pid]),('C',probs['MODEL_C'][pid]>=.5),('H',probs['MODEL_H'][pid]>=.5)]):
       x=j*cell; y=i*cell; d.text((x+2,y+2),pid+' '+label,fill='black'); z=Image.fromarray(im.astype('uint8')*255 if im.dtype==bool else im.astype('uint8'),'L').convert('RGB') if label!='RGB' else Image.fromarray(im.astype('uint8'),'RGB'); sheet.paste(z.resize((cell,cell)),(x,y+18))
    sheet.save(OUT/'contact_sheet_C_H.png'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
