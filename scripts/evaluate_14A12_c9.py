"""DEV calibration and one-to-one GOLD scoring for C9."""
from pathlib import Path
import sys,json,csv
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,sha
from evaluate_14A8_shootout import objects,matrices,matching,boundaries,pixel,save_tif
from osgeo import gdal
from shapely import wkb
from shapely.geometry import shape,mapping
import numpy as np
NEW=BASE/'14A12_refinement_pipeline';OLD=BASE/'14A11_hybrid_pipeline';P=json.loads((NEW/'protocol.json').read_text())
def csvwrite(p,rows):
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def evalset(records,probs,targets,config,gt=None):
 total=Counter();per=[];bfs=[]
 for r in records:
  pid=r['patch_id'];raw=probs[pid]>=config['threshold']
  if config['morphology']=='OPEN3':
   from scipy import ndimage;raw=ndimage.binary_opening(raw,np.ones((3,3),bool))
  final,pred,_=objects(raw,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=config['min_component']))
  if gt is None:
   _,gs,_=objects(targets[pid],ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1))
  else:gs=gt[pid]
  mat,_=matrices(gs,pred);pairs=matching(mat,.3);tp=len(pairs);fp=len(pred)-tp;fn=len(gs)-tp;match={i for i,j,v in pairs};small={i for i,g in enumerate(gs) if g['geometry'].area<=50};medium={i for i,g in enumerate(gs) if 50<g['geometry'].area<=200};large=set(range(len(gs)))-small-medium;pm=pixel(final,targets[pid]);bf=boundaries(final,targets[pid])[0]['BOUNDARY_F1'];bfs.append(bf)
  total.update(dict(TP=tp,FP=fp,FN=fn,GT=len(gs),PRED=len(pred),SMALL_GT=len(small),SMALL_TP=len(small&match),MEDIUM_GT=len(medium),MEDIUM_TP=len(medium&match),LARGE_GT=len(large),LARGE_TP=len(large&match),PIXEL_TP=pm['PIXEL_TP'],PIXEL_FP=pm['PIXEL_FP'],PIXEL_FN=pm['PIXEL_FN']))
  per.append(dict(patch_id=pid,TP=tp,FP=fp,FN=fn,GT=len(gs),PRED=len(pred),SMALL_TP=len(small&match),SMALL_GT=len(small),boundary_f1=bf))
 t=total;tp=t['TP'];fp=t['FP'];fn=t['FN'];f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.;small=t['SMALL_TP']/t['SMALL_GT'] if t['SMALL_GT'] else 0.;pt=t['PIXEL_TP'];pf=t['PIXEL_FP'];pn=t['PIXEL_FN'];result=dict(t,object_precision=tp/(tp+fp) if tp+fp else 0,object_recall=tp/(tp+fn) if tp+fn else 0,object_f1=f1,small_recall=small,final_boundary_f1=float(np.mean(bfs)),pixel_iou=pt/(pt+pf+pn),dice=2*pt/(2*pt+pf+pn))
 result['composite_objective']=f1+.5*small-.015*fp+.25*result['final_boundary_f1'];return result,per
def load_gt(records):
 out={r['patch_id']:[] for r in records};ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):out[f['patch_id']].append(dict(fid=f.GetFID(),geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
 return out
def calibrate():
 records=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];targets={};
 for r in records:
  with np.load(OLD/'dev'/(r['patch_id']+'.npz')) as z:targets[r['patch_id']]=z['mask'].astype(bool)
 rows=[]
 for ep in range(1,4):
  probs={r['patch_id']:np.load(NEW/'dev'/f'epoch{ep}__{r["patch_id"]}.npz')['probability'] for r in records}
  for th in P['calibration']['thresholds']:
   for mn in P['calibration']['min_components']:
    for mo in P['calibration']['morphology']:
     met,_=evalset(records,probs,targets,dict(threshold=th,min_component=mn,morphology=mo));rows.append(dict(epoch=ep,threshold=th,min_component=mn,morphology=mo,fragment_merge_threshold=.60,**met))
 csvwrite(NEW/'calibration/DEV_GRID.csv',rows);best=max(rows,key=lambda x:(x['composite_objective'],x['object_f1'],x['small_recall'],-x['FP'],-x['epoch']));ck=next(x for x in json.loads((NEW/'models/training_history.json').read_text()) if x['epoch']==best['epoch']);freeze=dict(model='MODEL_C9_HYBRID_REFINED',checkpoint=ck['checkpoint'],checkpoint_sha256=ck['sha256'],epoch=best['epoch'],threshold=best['threshold'],min_component=best['min_component'],morphology=best['morphology'],fragment_merge_threshold=.60,preprocessing='RGB_GLOBAL_PATCH_MINMAX_NATIVE512',dev_metric=best,dev_objective='F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1',gold_calibration=False,protocol_sha256=sha(NEW/'protocol.json'));(NEW/'calibration/FROZEN_CANDIDATE.json').write_text(json.dumps(freeze,indent=2));(NEW/'calibration/FROZEN_CANDIDATE.sha256').write_text(sha(NEW/'calibration/FROZEN_CANDIDATE.json'));print('C9_FREEZE',json.dumps(freeze),flush=True)
def goldscore():
 freeze=json.loads((NEW/'calibration/FROZEN_CANDIDATE.json').read_text());assert sha(ROOT/freeze['checkpoint'])==freeze['checkpoint_sha256'];records=json.loads((BASE/'qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text())['patches'];probs={};targets={}
 for r in records:
  with np.load(NEW/'gold_evaluation'/(r['patch_id']+'.npz')) as z:probs[r['patch_id']]=z['probability']
  with np.load(BASE/'qa/14A8_model_shootout/inputs'/(r['patch_id']+'.npz')) as z:targets[r['patch_id']]=z['gt'].astype(bool)
 gt=load_gt(records);met,per=evalset(records,probs,targets,freeze,gt);runtime=json.loads((NEW/'gold_evaluation/runtime.json').read_text());met['cpu_mean_seconds']=float(np.mean([x['seconds'] for x in runtime]));met['raw_boundary_f1']=met['final_boundary_f1'];met['raw_pixel_iou']=met['pixel_iou'];result=dict(model='MODEL_C9_HYBRID_REFINED',metrics=met,patches=per,production_modified=False,gold_attempts=1);(NEW/'gold_evaluation/FINAL_RESULT.json').write_text(json.dumps(result,indent=2));print('C9_GOLD',json.dumps(met),flush=True)
if __name__=='__main__':{'calibrate':calibrate,'goldscore':goldscore}[sys.argv[1]]()
