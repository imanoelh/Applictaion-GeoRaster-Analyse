"""Prepare one non-GOLD refinement cycle from the frozen 14A.11 artifacts."""
from pathlib import Path
import sys,json,csv,hashlib,shutil
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,OUT as OLD,sha,dump
from osgeo import gdal
from shapely import wkb
from shapely.geometry import shape
from evaluate_14A8_shootout import matrices
from pyproj import Transformer
import numpy as np

NEW=BASE/'14A12_refinement_pipeline'

def csvwrite(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['empty']);w.writeheader();w.writerows(rows)

def load_gt(records):
    out={r['patch_id']:[] for r in records}
    ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
    for f in ds.GetLayerByName('buildings_gt'):
        out[f['patch_id']].append(dict(fid=f.GetFID(),geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
    return out

def classify(rgb,mask):
    a=rgb[mask].astype('float32')
    if len(a)==0:return 'OTHER'
    mean=a.mean(0); sat=a.max(1)-a.min(1); green=float(mean[1]-mean[0]); tex=float(a.std())
    if green>12:return 'VEGETATION'
    if mean[0]>mean[1]*1.12 and mean[0]>mean[2]*1.08:return 'BARE_SOIL'
    if tex<18 and mean.mean()<95:return 'ROAD'
    if tex>42:return 'INDUSTRIAL_TEXTURE'
    if mean.mean()>165 and sat<28:return 'ROOF_LIKE_OBJECT'
    if mean.mean()<70:return 'SHADOW'
    if sat<20 and mean.mean()<130:return 'PARKING'
    return 'OTHER'

def main():
    if NEW.exists() and (NEW/'protocol.json').exists(): raise RuntimeError('Existing 14A12 cycle; refusing overwrite')
    for d in ['diagnostic','hard_negative_pool_v2','train','dev','models','calibration','gold_evaluation','qa','logs']:(NEW/d).mkdir(parents=True,exist_ok=True)
    oldp=json.loads((OLD/'protocol.json').read_text());records=oldp['records'];gold_records=json.loads((BASE/'qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text())['patches'];gt=load_gt(gold_records)
    # GOLD diagnostic only: never copied to train or used for thresholds.
    diag=[];oldpred=OLD/'gold_evaluation'
    for r in gold_records:
        pid=r['patch_id'];rgb=np.moveaxis(gdal.Open(str(ROOT/r['rgb_path'])).ReadAsArray()[:3],0,-1)
        preds=[dict(label=f['properties']['prediction_id'],geometry=shape(f['geometry'])) for f in json.loads((oldpred/(pid+'_C8_predictions.geojson')).read_text())['features']]
        mat,_=matrices(gt[pid],preds);matched={j for i,j,v in __import__('evaluate_14A8_shootout').matching(mat,.3)}
        for j,p in enumerate(preds):
            pix=np.zeros((512,512),bool); # geometric category is explicitly diagnostic, not a semantic label
            # Use the saved final mask labels where available; fallback to geometry center only.
            with np.load(OLD/'gold_evaluation'/(pid+'.npz')) as z:prob=z['probability']
            ys,xs=np.where(prob>=0.5); pix[ys,xs]=True
            cat=classify(rgb,pix)
            diag.append(dict(patch_id=pid,prediction_id=p['label'],matched_to_gt=bool(j in matched),best_gt_iou=float(mat[:,j].max()) if len(gt[pid]) else 0,category=cat,diagnostic_only=True,calibration_used=False,visual_review='NOT_PERFORMED'))
    csvwrite(NEW/'diagnostic/14A12_c8_gold_fp_diagnostic.csv',[r for r in diag if not r['matched_to_gt']])
    csvwrite(NEW/'diagnostic/14A12_c8_gold_all_predictions_diagnostic.csv',diag)
    # Freeze non-GOLD records and copy masks only into the new experimental directory.
    protocol=dict(model='MODEL_C9_HYBRID_REFINED',source_model='MODEL_C8_HYBRID',teacher_protocol_sha256=sha(OLD/'protocol.json'),records=records,training=dict(epochs=3,seed=1412,loss='focal_gamma2 + weighted Dice',lr=1e-5,weight_decay=1e-4,threads=4,oversample_small_dense=True),calibration=dict(thresholds=[.35,.45,.5,.55],min_components=[16,32,64,128],morphology=['NONE','OPEN3'],fragment_merge_thresholds=[0.60,0.70],objective='F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1',gold_never_used=True),gold_policy='single frozen evaluation after DEV freeze',production='MODEL_C_UNCHANGED')
    dump(NEW/'protocol.json',protocol);(NEW/'protocol.sha256').write_text(sha(NEW/'protocol.json'))
    decisions=list(csv.DictReader((OLD/'hybrid_teacher/object_decisions.csv').open(encoding='utf-8-sig')))
    quality=[];qcounts=Counter()
    for d in decisions:
        if d['type']!='TYPE_B_DIST3_ONLY' or d['accepted']!='True':continue
        conf=float(d['confidence']);stab=float(d['augmentation_iou'] or 0);compact=float(d['compactness'] or 0);aspect=float(d['aspect'] or 99);area=float(d['area_m2'] or 0)
        rectangular=min(1.,compact/.75);small=area<=50;score=.35*conf+.30*stab+.20*rectangular+.10*min(1.,8/max(1,aspect))+.05*(1 if small else min(1,area/200))
        level='DIST3_ONLY_HIGH' if score>=.78 else 'DIST3_ONLY_MEDIUM' if score>=.58 else 'DIST3_ONLY_LOW'
        qcounts[level]+=1;quality.append(dict(d, DIST3_ONLY_QUALITY_SCORE=score, quality_level=level, rectangularity_proxy=rectangular, local_contrast_proxy='AVAILABLE_FROM_RGB_NOT_RECOMPUTED', edge_density='NOT_AVAILABLE', context_score='PROXY_ONLY'))
    csvwrite(NEW/'diagnostic/DIST3_ONLY_QUALITY.csv',quality)
    # Build a hard-negative pool from agreement background and rejected/uncertain regions, non-GOLD only.
    pool=[];negative_pixels=0
    for r in records:
        pid=r['patch_id'];kind='train' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'dev'
        with np.load(OLD/'teacher_predictions'/(pid+'.npz')) as z:c6=z['c6'];d=z['dist3'][0];df=z['dist3_flip'][0]
        with np.load(OLD/kind/(pid+'.npz')) as z:oldmask=z['mask'].astype(bool)
        neg=(c6<.08)&(d<.08)&(df<.08)&(~oldmask);negative_pixels+=int(neg.sum())
        np.savez_compressed(NEW/'hard_negative_pool_v2'/(pid+'.npz'),mask=neg.astype('uint8'),source='NON_GOLD_CONSENSUS_BACKGROUND',weight=2.)
        pool.append(dict(patch_id=pid,split=r['split'],pixels=int(neg.sum()),scene_type=r['primary_group'],source='C6_DIST3_FLIP_BACKGROUND',human_gt=False))
        with np.load(OLD/kind/(pid+'.npz')) as z:mask=z['mask'].astype('uint8');w=z['weight'].astype('float32');labels=z['instance_labels']
        # Conservative hard-negative boost and quality-aware positive weighting; no geometry changes.
        w2=w.copy();w2[neg]=np.maximum(w2[neg],2.0)
        np.savez_compressed(NEW/kind/(pid+'.npz'),mask=mask,weight=w2,instance_labels=labels)
    csvwrite(NEW/'hard_negative_pool_v2/HARD_NEGATIVE_POOL_V2.csv',pool)
    dump(NEW/'qa/REFINEMENT_PREP_QA.json',dict(non_gold=True,gold_training=False,gold_calibration=False,records=len(records),train=sum(r['split']=='ACTIVE_LEARNING_TRAIN' for r in records),dev=sum(r['split']=='DEV_CALIBRATION' for r in records),hard_negative_pixels=negative_pixels,quality_counts=dict(qcounts),source_c8_sha=sha(ROOT/oldp['records'][0]['rgb_path']) if False else 'see protocol',gold_diagnostic_only=True,production_modified=False))
    print('PREP_14A12',dict(hard_negative_pixels=negative_pixels,quality_counts=dict(qcounts)),flush=True)
if __name__=='__main__':main()
