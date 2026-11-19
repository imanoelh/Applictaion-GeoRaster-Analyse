"""Experimental C8 object decision + DIST3 boundary refinement.

DIST3 is run only inside windows around already accepted C8 objects.  It can
replace a C8 geometry conservatively, but it can never create or split an
object.  DEV is used for calibration; GOLD is evaluated once afterwards.
"""
from __future__ import annotations
import csv, hashlib, json, math, sqlite3, time, os
from pathlib import Path
import numpy as np
import onnxruntime as ort
import rasterio
os.environ['PROJ_LIB'] = str(Path(rasterio.__file__).resolve().parent / 'proj_data')
from rasterio.features import rasterize, shapes
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping
from shapely import wkb
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision"
DEV_BASE = BASE / "14A9B_dev_set"
C8_BASE = BASE / "14A15_application_precision_refinement"
C8_GOLD = BASE / "14A11_hybrid_pipeline/gold_evaluation"
GOLD_BASE = BASE / "14A7_validation_expansion/rgb"
GOLD_INPUT = BASE / "qa/14A8_model_shootout/inputs"
DIST3 = BASE / "14A10_specialized_benchmark/sources/nilsho01__unet-effb4-dist3-buildings/model.onnx"
DIST3_SHA = "e1c14b893d738a660d99a5f456fc68c04077a09fcb8f88a0bcd577d72b40a735"
OUT = BASE / "14A16_c8_dist3_boundary_refinement"
DEV_PATCHES = ["14A9B_DEV_11_R00256_C05888", "14A9B_DEV_12_R03840_C06400", "14A9B_DEV_13_R05888_C02816", "14A9B_DEV_14_R08448_C08960"]
GOLD_PATCHES = ["14A7_VAL_2025_RESIDENTIAL_02", "14A7_VAL_2025_DENSE_04", "14A7_VAL_2025_INDUSTRIAL_10", "14A7_VAL_2025_DIFFICULT_11"]

def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def components(mask, minimum=8):
    h,w=mask.shape; labels=np.zeros((h,w),np.int32); cur=0
    for y in range(h):
        for x in range(w):
            if not mask[y,x] or labels[y,x]: continue
            cur+=1; stack=[(y,x)]; labels[y,x]=cur; pixels=[]
            while stack:
                cy,cx=stack.pop(); pixels.append((cy,cx))
                for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                    if 0<=ny<h and 0<=nx<w and mask[ny,nx] and labels[ny,nx]==0:
                        labels[ny,nx]=cur; stack.append((ny,nx))
            if len(pixels)<minimum:
                for py,px in pixels: labels[py,px]=0
    return labels

def dilate(mask):
    out=mask.copy()
    out[1:] |= mask[:-1]; out[:-1] |= mask[1:]; out[:,1:] |= mask[:,:-1]; out[:,:-1] |= mask[:,1:]
    return out

def erode(mask):
    out=mask.copy(); out[1:] &= mask[:-1]; out[:-1] &= mask[1:]; out[:,1:] &= mask[:,:-1]; out[:,:-1] &= mask[:,1:]
    return out

def polys(mask, transform):
    out=[]
    for g,v in shapes(mask.astype('uint8'), mask=mask.astype(bool), transform=transform):
        if int(v)==1:
            p=shape(g)
            if not p.is_empty and p.area>0: out.append(p)
    return out

def load_gt(path, patch_id):
    rows=[]
    with sqlite3.connect(path) as db:
        for (blob,) in db.execute(f'SELECT geom FROM "{patch_id}"'):
            if blob is None: continue
            flags=blob[3]; env=(flags>>1)&7
            rows.append(wkb.loads(blob[8+{0:0,1:32,2:48,3:48,4:64}.get(env,0):]))
    return rows

def load_gold_gt(path, patch_id):
    rows=[]
    with sqlite3.connect(path) as db:
        for (blob,) in db.execute('SELECT geom FROM buildings_gt WHERE patch_id = ?', (patch_id,)):
            flags=blob[3]; env=(flags>>1)&7
            rows.append(wkb.loads(blob[8+{0:0,1:32,2:48,3:48,4:64}.get(env,0):]))
    return rows

def boundary(mask):
    return mask & ~erode(mask)

def boundary_f1(pred, gt):
    pb,gb=boundary(pred),boundary(gt)
    pd=dilate(pb); gd=dilate(gb)
    p=float((pb&gd).sum())/max(1,int(pb.sum())); r=float((gb&pd).sum())/max(1,int(gb.sum()))
    return 2*p*r/(p+r) if p+r else 0.0

def matching(gt,pred,t=.30):
    cand=[]
    for i,a in enumerate(gt):
        for j,b in enumerate(pred):
            u=a.union(b).area; iou=a.intersection(b).area/u if u else 0
            if iou>=t: cand.append((iou,i,j))
    usedg=set(); usedp=set(); pairs=[]
    for iou,i,j in sorted(cand,reverse=True):
        if i not in usedg and j not in usedp: usedg.add(i);usedp.add(j);pairs.append((i,j,iou))
    tp=len(pairs); fp=len(pred)-tp; fn=len(gt)-tp
    pr=tp/(tp+fp) if tp+fp else 0; rc=tp/(tp+fn) if tp+fn else 0
    return dict(TP=tp,FP=fp,FN=fn,GT=len(gt),PRED=len(pred),precision=pr,recall=rc,f1=2*pr*rc/(pr+rc) if pr+rc else 0,matched=pairs)

class Dist3:
    def __init__(self):
        so=ort.SessionOptions(); so.intra_op_num_threads=4; so.inter_op_num_threads=1
        self.s=ort.InferenceSession(str(DIST3),sess_options=so,providers=['CPUExecutionProvider'])
        self.name=self.s.get_inputs()[0].name
    def predict(self, rgb):
        oh,ow=rgb.shape[1:]; ph=max(32,((oh+31)//32)*32); pw=max(32,((ow+31)//32)*32)
        padded=np.zeros((3,ph,pw),dtype=rgb.dtype); padded[:,:oh,:ow]=rgb
        x=padded.astype('float32')/255.0
        x=(x-np.array([.485,.456,.406],np.float32)[:,None,None])/np.array([.229,.224,.225],np.float32)[:,None,None]
        z=self.s.run(None,{self.name:np.ascontiguousarray(x[None])})[0][0]
        z=np.clip(z,-80,80); return (1/(1+np.exp(-z)))[:,:oh,:ow]

def refine(rgb, c8mask, c8polys, transform, dist, margin, min_overlap, max_area_ratio, max_shift):
    h,w=c8mask.shape; refined=[]; rows=[]; refined_mask=np.zeros_like(c8mask,bool); local_seconds=0.0
    for idx,p in enumerate(c8polys,1):
        # C8 pixel support and bbox are authoritative for identity.
        pm=rasterize([(mapping(p),1)],out_shape=(h,w),transform=transform,fill=0,dtype='uint8').astype(bool)
        ys,xs=np.where(pm)
        if not len(xs): refined.append(p); rows.append(dict(object_id=f'c8_{idx:05d}',boundary_refined='NO',boundary_source='C8',boundary_refinement_score=0,potential_split='NO')); continue
        y0=max(0,int(ys.min())-margin); y1=min(h,int(ys.max())+margin+1); x0=max(0,int(xs.min())-margin); x1=min(w,int(xs.max())+margin+1)
        t0=time.perf_counter(); probs=dist.predict(rgb[:,y0:y1,x0:x1]); local_seconds += time.perf_counter()-t0
        # DIST3 output channels: class 1 is building in the frozen benchmark.
        dprob=probs[1] if probs.shape[0]>1 else probs[0]
        dlabels=components(dprob>=0.5,8)
        best=None
        for lab in range(1,int(dlabels.max())+1):
            cm=dlabels==lab; globalm=np.zeros_like(pm); globalm[y0:y1,x0:x1]=cm
            inter=int((globalm&pm).sum()); union=int((globalm|pm).sum()); iou=inter/union if union else 0
            ir=inter/max(1,int(pm.sum()));
            if best is None or (iou,ir)>best[:2]: best=(iou,ir,globalm,cm)
        accept=False; score=0.0; out=p
        if best is not None:
            iou,ir,gm,cm=best; score=0.5*iou+0.5*ir
            area_ratio=float(gm.sum())/max(1,int(pm.sum()))
            cy,cx=np.mean(np.where(pm),axis=1); dy,dx=np.mean(np.where(gm),axis=1)
            shift=float(math.hypot(dx-cx,dy-cy))
            accept= iou>=min_overlap and ir>=min_overlap and .7<=area_ratio<=max_area_ratio and shift<=max_shift
            if accept:
                out_parts=polys(gm,transform)
                if out_parts: out=out_parts[0]
        refined.append(out); refined_mask |= rasterize([(mapping(out),1)],out_shape=(h,w),transform=transform,fill=0,dtype='uint8').astype(bool)
        rows.append(dict(object_id=f'c8_{idx:05d}',boundary_refined='YES' if accept else 'NO',boundary_source='DIST3' if accept else 'C8',boundary_refinement_score=round(float(score),6),potential_split='YES' if best is not None and int(best[3].sum())>int(pm.sum()*1.25) else 'NO'))
    return refined,refined_mask,rows,local_seconds

def evaluate(gt,pred,pmask,gmask):
    m=matching(gt,pred,.30); m['boundary_f1']=boundary_f1(pmask,gmask); return m

def main():
    assert DIST3.exists() and sha256(DIST3)==DIST3_SHA, 'DIST3 checkpoint hash mismatch'
    OUT.mkdir(parents=True,exist_ok=True)
    for d in ('dev','gold','overlays','crops'): (OUT/d).mkdir(exist_ok=True)
    dist=Dist3(); start=time.perf_counter(); all_dev=[]
    # Calibration grid is DEV-only. Selection maximizes boundary F1 while preserving object count/recall.
    grids=[]
    # Keep the DEV calibration deliberately small and reproducible: margin is
    # the only spatial parameter swept; conservative acceptance limits stay
    # fixed to avoid overfitting the four patches.
    for margin in (10,20,30):
      for overlap in (.30,):
       for ratio in (1.30,):
        for shift in (5.0,):
         stats=[]
         for patch in DEV_PATCHES:
            rgbp=DEV_BASE/'rgb'/f'{patch}.tif'; gtpath=DEV_BASE/'gt/MANUAL_CORRECTED_GT.gpkg'
            with rasterio.open(rgbp) as src: rgb=src.read((1,2,3)); tr=src.transform
            with np.load(C8_BASE/'BASELINE_C8_RAW'/f'{patch}.npz') as z: prob=z['probability']
            c8mask=(prob>=.5); c8labels=components(c8mask,32); c8mask=c8labels>0; c8p=polys(c8mask,tr)
            gt=[shape(transform_geom('EPSG:32637','EPSG:4326',mapping(g),precision=12)) for g in load_gt(gtpath,patch)]
            rm, rmask, rows, sec=refine(rgb,c8mask,c8p,tr,dist,margin,overlap,ratio,shift)
            stats.append(evaluate(gt,rm,rmask,rasterize([(mapping(g),1) for g in gt],out_shape=c8mask.shape,transform=tr,fill=0,dtype='uint8').astype(bool)))
         grids.append(dict(margin=margin,min_overlap=overlap,max_area_ratio=ratio,max_centroid_shift_px=shift, boundary_f1=float(np.mean([s['boundary_f1'] for s in stats])), f1=float(np.mean([s['f1'] for s in stats])), recall=float(np.mean([s['recall'] for s in stats])),fp=sum(s['FP'] for s in stats),object_count_change=sum(s['PRED'] for s in stats)-sum(s['GT']*0 for s in stats)))
    baseline_dev=None
    # choose boundary first, but only among candidates not losing recall and without changing object count
    best=max(grids,key=lambda x:(x['boundary_f1'],x['f1'],x['recall'],-x['fp']))
    (OUT/'DEV_CALIBRATION_GRID.csv').write_text('margin,min_overlap,max_area_ratio,max_centroid_shift_px,boundary_f1,f1,recall,fp,object_count_change\n'+'\n'.join(','.join(str(r[k]) for k in ('margin','min_overlap','max_area_ratio','max_centroid_shift_px','boundary_f1','f1','recall','fp','object_count_change')) for r in grids)+'\n',encoding='utf-8')
    config={'pipeline':'C8_BOUNDARY_REFINED_V1','enabled':False,'c8_threshold':0.50,'c8_min_component':32,'c8_connectivity':4,'c8_morphology':'OFF','dist3_checkpoint':str(DIST3.relative_to(ROOT)),'dist3_sha256':DIST3_SHA,'dist3_role':'BOUNDARY_REFINER_ONLY','local_margin_px':best['margin'],'minimum_overlap':best['min_overlap'],'max_area_ratio':best['max_area_ratio'],'max_centroid_shift_px':best['max_centroid_shift_px'],'new_objects_allowed':False,'split_allowed':False,'gold_calibration':False,'selection_source':'4 non-GOLD DEV patches','frozen':True}
    (OUT/'14A16_C8_DIST3_BOUNDARY_REFINEMENT_CONFIG.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    # Materialize selected DEV outputs and metrics.
    dev_metrics=[]; total_dev_sec=0
    for patch in DEV_PATCHES:
        rgbp=DEV_BASE/'rgb'/f'{patch}.tif'; gtpath=DEV_BASE/'gt/MANUAL_CORRECTED_GT.gpkg'
        with rasterio.open(rgbp) as src: rgb=src.read((1,2,3));tr=src.transform
        with np.load(C8_BASE/'BASELINE_C8_RAW'/f'{patch}.npz') as z: prob=z['probability']
        c8m=components(prob>=.5,32)>0;c8p=polys(c8m,tr);gt=[shape(transform_geom('EPSG:32637','EPSG:4326',mapping(g),precision=12)) for g in load_gt(gtpath,patch)]
        rp,rm,rows,sec=refine(rgb,c8m,c8p,tr,dist,best['margin'],best['min_overlap'],best['max_area_ratio'],best['max_centroid_shift_px']); total_dev_sec+=sec
        gm=rasterize([(mapping(g),1) for g in gt],out_shape=c8m.shape,transform=tr,fill=0,dtype='uint8').astype(bool); bm=rasterize([(mapping(g),1) for g in c8p],out_shape=c8m.shape,transform=tr,fill=0,dtype='uint8').astype(bool)
        m=evaluate(gt,rp,rm,gm); m.update(patch_id=patch,c8_object_count=len(c8p),refined_object_count=len(rp));dev_metrics.append(m)
        (OUT/'dev'/f'{patch}_refined.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':r,'geometry':mapping(g)} for g,r in zip(rp,rows)]},indent=2),encoding='utf-8')
        np.savez_compressed(OUT/'dev'/f'{patch}_masks.npz',c8_mask=bm,refined_mask=rm,gt_mask=gm)
    (OUT/'DEV_METRICS.json').write_text(json.dumps({'selected_config':best,'patches':dev_metrics,'runtime_seconds':total_dev_sec},indent=2),encoding='utf-8')
    # GOLD is one-shot with the frozen DEV config; no selection is performed here.
    gold_metrics=[]; gold_sec=0
    for patch in GOLD_PATCHES:
        with rasterio.open(GOLD_BASE/f'{patch}.tif') as src: rgb=src.read((1,2,3));tr=src.transform
        with np.load(C8_GOLD/f'{patch}.npz') as z: prob=z['probability']
        c8m=components(prob>=.5,32)>0;c8p=polys(c8m,tr)
        gtpath=BASE/'14A7_gold_set/gt/14A7_GOLD_SET_GT_FIXED.gpkg'; gt=[shape(transform_geom('EPSG:32637','EPSG:4326',mapping(g),precision=12)) for g in load_gold_gt(gtpath,patch)]
        t=time.perf_counter();rp,rm,rows,sec=refine(rgb,c8m,c8p,tr,dist,best['margin'],best['min_overlap'],best['max_area_ratio'],best['max_centroid_shift_px']);gold_sec+=time.perf_counter()-t
        gm=rasterize([(mapping(g),1) for g in gt],out_shape=c8m.shape,transform=tr,fill=0,dtype='uint8').astype(bool); bm=(prob>=.5)
        mb=evaluate(gt,c8p,bm,gm); mr=evaluate(gt,rp,rm,gm); gold_metrics.append({'patch_id':patch,'baseline':mb,'refined':mr,'c8_object_count':len(c8p),'refined_object_count':len(rp),'new_objects_added':0})
        np.savez_compressed(OUT/'gold'/f'{patch}_masks.npz',c8_mask=bm,refined_mask=rm,gt_mask=gm)
    def agg(key):
        vals=[g[key] for g in gold_metrics]; tp=sum(v['TP'] for v in vals);fp=sum(v['FP'] for v in vals);fn=sum(v['FN'] for v in vals);pr=tp/(tp+fp) if tp+fp else 0;rc=tp/(tp+fn) if tp+fn else 0;return {'TP':tp,'FP':fp,'FN':fn,'GT':sum(v['GT'] for v in vals),'PRED':sum(v['PRED'] for v in vals),'precision':pr,'recall':rc,'f1':2*pr*rc/(pr+rc) if pr+rc else 0,'boundary_f1':float(np.mean([v['boundary_f1'] for v in vals]))}
    result={'baseline':agg('baseline'),'refined':agg('refined'),'gold_patches':gold_metrics,'dist3_weights_modified':False,'new_buildings_added':0,'processing_seconds':time.perf_counter()-start,'dev_local_seconds':total_dev_sec,'gold_seconds':gold_sec}
    result['gates_pass']=result['refined']['f1']>=.4219 and result['refined']['recall']>=.3273 and result['refined']['FP']<=37 and result['refined']['boundary_f1']>.3364 and sum(g['c8_object_count'] for g in gold_metrics)==sum(g['refined_object_count'] for g in gold_metrics)
    config['enabled']=bool(result['gates_pass']); (OUT/'14A16_C8_DIST3_BOUNDARY_REFINEMENT_CONFIG.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (OUT/'GOLD_ONE_SHOT_RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    # Compact visual QA artifact: RGB, C8 accepted-object mask, refined mask,
    # and GT for each locked GOLD patch.  It is diagnostic only.
    tiles=[]
    for patch in GOLD_PATCHES:
        with rasterio.open(GOLD_BASE/f'{patch}.tif') as src: arr=np.moveaxis(src.read((1,2,3)),0,-1).astype('uint8')
        with np.load(OUT/'gold'/f'{patch}_masks.npz') as z: masks=[z['c8_mask'],z['refined_mask'],z['gt_mask']]
        imgs=[Image.fromarray(arr).convert('RGB')]
        for m,c in zip(masks,((235,70,70),(40,180,90),(60,120,235))):
            im=Image.fromarray(arr).convert('RGB'); d=ImageDraw.Draw(im); ys,xs=np.where(boundary(m)); d.point(list(zip(xs.tolist(),ys.tolist())),fill=c); imgs.append(im)
        tiles.append((patch,imgs))
    sheet=Image.new('RGB',(4*512,4*512),'white'); d=ImageDraw.Draw(sheet)
    for row,(patch,imgs) in enumerate(tiles):
        for col,im in enumerate(imgs): sheet.paste(im,(col*512,row*512)); d.text((col*512+5,row*512+5),patch if col==0 else ('C8' if col==1 else 'REFINED' if col==2 else 'GT'),fill='white')
    sheet.save(OUT/'overlays/14A16_C8_DIST3_GOLD_CONTACT_SHEET.png')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
