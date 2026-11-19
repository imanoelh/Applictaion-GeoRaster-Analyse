"""SPECIALIZED_FUSION_V2: inference-level object fusion, no training."""
from pathlib import Path
import sys,json,csv,time,hashlib
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,sha
from evaluate_14A8_shootout import objects,matrices,matching,boundaries,pixel,save_tif
from score_14A10_models import instances,polygonize
from osgeo import gdal
from shapely import wkb
from shapely.geometry import shape,mapping
import numpy as np
from scipy import ndimage
OUT=BASE/'14A13_fusion_v2';A11=BASE/'14A11_hybrid_pipeline';A12=BASE/'14A12_refinement_pipeline';B8=BASE/'qa/14A8_model_shootout';B10=BASE/'14A10_specialized_benchmark';P=json.loads((A11/'protocol.json').read_text())
def csvwrite(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['empty']);w.writeheader();w.writerows(rows)
def load_tif(p):return gdal.Open(str(p)).ReadAsArray().astype('float32')
def geom_score(mask):
 area=float(mask.sum());ys,xs=np.where(mask);h=max(1,ys.max()-ys.min()+1);w=max(1,xs.max()-xs.min()+1);aspect=max(h,w)/max(1,min(h,w));compact=min(1.,area/(2*(h+w)))
 return float(.55*compact+.30*min(1.,1/aspect*2)+.15*min(1.,area/80)),compact,aspect
def context(rgb,mask):
 a=rgb[mask].astype('float32');
 if len(a)==0:return dict(ROAD_SCORE=0,BARE_SOIL_SCORE=0,SHADOW_SCORE=0,VEGETATION_SCORE=0,INDUSTRIAL_TEXTURE_SCORE=0)
 m=a.mean(0);sat=a.max(1)-a.min(1);tex=float(a.std());return dict(ROAD_SCORE=float(tex<18 and m.mean()<105),BARE_SOIL_SCORE=float(m[0]>m[1]*1.12 and m[0]>m[2]*1.08),SHADOW_SCORE=float(m.mean()<65),VEGETATION_SCORE=float(m[1]>m[0]+12),INDUSTRIAL_TEXTURE_SCORE=float(tex>45))
def probs_for(r,kind):
 pid=r['patch_id']
 if kind=='DEV':
  with np.load(A11/'teacher_predictions'/(pid+'.npz')) as z: c6=z['c6'];d=z['dist3'];flip=z['dist3_flip'][0]
  c8=np.load(A11/'dev'/('epoch2__'+pid+'.npz'))['probability'];c9=np.load(A12/'dev'/('epoch2__'+pid+'.npz'))['probability'];return c6,d,c8,c9,flip
 with np.load(B8/'inference'/(('MODEL_C6__'+pid+'.npz'))) as z:c6=z['probability'] if 'probability' in z.files else z[z.files[0]]
 c8=np.load(A11/'gold_evaluation'/(pid+'.npz'))['probability'];c9=np.load(A12/'gold_evaluation'/(pid+'.npz'))['probability'];d=np.load(B10/'predictions/UNET_DIST3'/(pid+'.npz'))['channels'];flip=np.zeros((512,512),np.float32);return c6,d,c8,c9,flip
def fuse(r,kind,config,write=True):
 pid=r['patch_id'];rgb=np.moveaxis(gdal.Open(str(ROOT/r['rgb_path'])).ReadAsArray()[:3],0,-1);c6,d,c8,c9,flip=probs_for(r,kind);labels=instances(d,dict(model='UNET_DIST3',threshold=.5));rows=[];rejected=[];accepted=[];outlabels=np.zeros((512,512),np.int32);n=0
 for lab in np.unique(labels[labels>0]):
  m=labels==lab;area=int(m.sum());conf=float(d[0][m].mean());stable=float(1 if not flip.any() else 0.8);s6=float(c6[m].mean());s8=float(c8[m].mean());s9=float(c9[m].mean());gs,compact,aspect=geom_score(m);ctx=context(rgb,m);fpctx=max(ctx.values());support=.45*conf+.20*s6+.20*s8+.10*s9+.05*gs-.25*fpctx;small=area<=50;small_ok=small and conf>=config['small_conf'] and stable>=.5 and gs>=.35;accept=small_ok if small else (support>=config['support_threshold'] and fpctx<config['fp_threshold'] and (s6>=.12 or s8>=.18 or s9>=.18));reason='ACCEPTED' if accept else ('SMALL_BRANCH_FAIL' if small else 'LOW_SUPPORT_OR_FP_CONTEXT');row=dict(patch_id=pid,object_id=int(lab),dist3_confidence=conf,area_px=area,c6_support=s6,c8_support=s8,c9_support=s9,geometry_score=gs,compactness=compact,aspect_ratio=aspect,FUSION_SUPPORT_SCORE=support,FP_CONTEXT_SCORE=fpctx,small_object='YES' if small else 'NO',final_status='ACCEPTED' if accept else 'REJECTED',reject_reason='' if accept else reason);rows.append(row)
  if accept:n+=1;outlabels[m]=n;accepted.append(row)
  else:rejected.append(row)
 if write:
  csvwrite(OUT/'diagnostics'/(pid+'_candidates.csv'),rows);csvwrite(OUT/'diagnostics'/(pid+'_rejected.csv'),rejected);csvwrite(OUT/'diagnostics'/(pid+'_accepted.csv'),accepted)
  save_tif(OUT/'predictions'/(pid+'_fusion_mask.tif'),(outlabels>0).astype('uint8'),ROOT/r['rgb_path'])
  feats=[]
  for row in accepted:
   m=outlabels==row['object_id'];# polygon geometry is reconstructed from the object mask
 return outlabels,rows
def score_set(records,kind,config,target,gt=None):
 total=Counter();per=[]
 for r in records:
  labels,_=fuse(r,kind,config,write=False);mask=labels>0;final,pred,_=objects(mask,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1));gs=gt[r['patch_id']] if gt else objects(target[r['patch_id']],ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1))[1];mat,_=matrices(gs,pred);pairs=matching(mat,.3);tp=len(pairs);fp=len(pred)-tp;fn=len(gs)-tp;match={i for i,j,v in pairs};small={i for i,g in enumerate(gs) if g['geometry'].area<=50};pm=pixel(final,target[r['patch_id']]);bf=boundaries(final,target[r['patch_id']])[0]['BOUNDARY_F1'];total.update(dict(TP=tp,FP=fp,FN=fn,GT=len(gs),PRED=len(pred),SMALL_GT=len(small),SMALL_TP=len(small&match),PIXEL_TP=pm['PIXEL_TP'],PIXEL_FP=pm['PIXEL_FP'],PIXEL_FN=pm['PIXEL_FN']));per.append(dict(patch_id=r['patch_id'],TP=tp,FP=fp,FN=fn,SMALL_TP=len(small&match),SMALL_GT=len(small),boundary_f1=bf))
 t=total;f1=2*t['TP']/(2*t['TP']+t['FP']+t['FN']) if 2*t['TP']+t['FP']+t['FN'] else 0;rc=t['TP']/t['GT'] if t['GT'] else 0;sm=t['SMALL_TP']/t['SMALL_GT'] if t['SMALL_GT'] else 0;pt=t['PIXEL_TP'];pf=t['PIXEL_FP'];pn=t['PIXEL_FN'];return dict(t,object_precision=t['TP']/(t['TP']+t['FP']) if t['TP']+t['FP'] else 0,object_recall=rc,object_f1=f1,small_recall=sm,boundary_f1=float(np.mean([x['boundary_f1'] for x in per])),pixel_iou=pt/(pt+pf+pn),dice=2*pt/(2*pt+pf+pn)),per
def get_gt(records):
 out={r['patch_id']:[] for r in records};ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):out[f['patch_id']].append(dict(fid=f.GetFID(),geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
 return out
def main(stage):
 for d in ['diagnostics','predictions','calibration','gold_evaluation','qa']: (OUT/d).mkdir(parents=True,exist_ok=True)
 dev=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];targets={}
 for r in dev:
  with np.load(A11/'dev'/(r['patch_id']+'.npz')) as z:targets[r['patch_id']]=z['mask'].astype(bool)
 if stage=='calibrate':
  rows=[]
  for st in [.35,.45,.55,.65]:
   for fp in [.25,.4,.55,.7]:
    for sm in [.65,.75,.85]:
     cfg=dict(support_threshold=st,fp_threshold=fp,small_conf=sm);met,_=score_set(dev,'DEV',cfg,targets);met.update(cfg);met['objective']=met['object_f1']+.5*met['small_recall']-.015*met['FP']+.25*met['boundary_f1'];rows.append(met)
  csvwrite(OUT/'calibration/DEV_FUSION_GRID.csv',rows);best=max(rows,key=lambda x:(x['objective'],x['object_f1'],x['small_recall'],-x['FP']));freeze=dict(engine='SPECIALIZED_FUSION_V2',primary_detector='UNET_DIST3',validators=['MODEL_C6','MODEL_C8','MODEL_C9'],config={k:best[k] for k in ['support_threshold','fp_threshold','small_conf']},objective='F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1',dev_metric=best,calibration='DEV_NON_GOLD_ONLY',gold_used_for_calibration=False);(OUT/'calibration/14A13_fusion_v2_frozen_config.json').write_text(json.dumps(freeze,indent=2));(OUT/'calibration/14A13_fusion_v2_frozen_config.sha256').write_text(sha(OUT/'calibration/14A13_fusion_v2_frozen_config.json'));print('FUSION_FREEZE',json.dumps(freeze),flush=True);return
 cfg=json.loads((OUT/'calibration/14A13_fusion_v2_frozen_config.json').read_text())['config'];gold=json.loads((B8/'14A8_frozen_protocol.json').read_text())['patches'];gt=get_gt(gold);target={}
 for r in gold:
  with np.load(B8/'inputs'/(r['patch_id']+'.npz')) as z:target[r['patch_id']]=z['gt'].astype(bool)
 t=time.perf_counter();met,per=score_set(gold,'GOLD',cfg,target,gt);met['cpu_total_seconds']=time.perf_counter()-t;met['cpu_mean_seconds']=met['cpu_total_seconds']/4;met['gold_attempts']=1; (OUT/'gold_evaluation/FINAL_RESULT.json').write_text(json.dumps(dict(model='SPECIALIZED_FUSION_V2',metrics=met,patches=per,production_modified=False),indent=2));print('FUSION_GOLD',json.dumps(met),flush=True)
if __name__=='__main__':main(sys.argv[1])
