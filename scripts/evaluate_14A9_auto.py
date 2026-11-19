"""Consensus, DEV-only selection, one final GOLD scoring. No production imports."""
from pathlib import Path
import sys,json,math
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9_auto import ROOT,BASE,AL,DEV,GOLD,OUT,sha,dump,csvwrite
from evaluate_14A8_shootout import objects,matrices,matching,boundaries,pixel,draw_geom,save_tif
from osgeo import gdal
from scipy import ndimage
import numpy as np
from PIL import Image,ImageDraw
from pyproj import Transformer
from shapely.geometry import mapping
P=json.loads((OUT/'protocol.json').read_text());assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text()
def loadprob(mid,pid):
 with np.load(OUT/'teacher_predictions'/(mid+'__'+pid+'.npz')) as f:return f['probability']
def consensus():
 rows=[];negative=[];mining=[];counts=Counter()
 for r in P['records']:
  pid=r['patch_id'];ps=np.stack([loadprob(m,pid) for m in ['MODEL_C','MODEL_C3','MODEL_C6','MODEL_D']]);votes=(ps>=np.array([.5,.3,.3,.5])[:,None,None]).sum(axis=0)
  with np.load(OUT/'teacher_predictions'/('MODEL_D__'+pid+'.npz')) as f:flip=f['hflip_probability']
  stable=np.abs(ps[3]-flip)<=.15;A=(votes>=3)&(ps[3]>=.5)&(ps.mean(axis=0)>=.6)&stable;B=(~A)&(ps[3]>=.95)&(flip>=.90);D=(ps.max(axis=0)<=.05)&(flip<=.05);mask=A|B
  weight=np.where(A,1.,np.where(B,.35,np.where(D,.5,0.))).astype('float32')
  kind='auto_train' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'auto_dev';np.savez_compressed(OUT/kind/(pid+'.npz'),mask=mask.astype('uint8'),weight=weight)
  bd=np.stack([ndimage.binary_dilation(boundaries_bool(p>=t),np.ones((3,3))) for p,t in zip(ps,[.5,.3,.3,.5])]).mean(axis=0)
  np.savez_compressed(OUT/'consensus'/(pid+'.npz'),votes=votes.astype('uint8'),confidence=ps.mean(axis=0),agreement=np.maximum(votes,4-votes)/4.,boundary_agreement=bd,tier=np.where(A,1,np.where(B,2,np.where(D,4,3))).astype('uint8'))
  _,pred,_=objects(mask,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1));labels,n=ndimage.label(mask,ndimage.generate_binary_structure(2,1))
  gdal_ds=gdal.Open(str(ROOT/r['rgb_path']));inv=gdal.InvGeoTransform(gdal_ds.GetGeoTransform());tx=Transformer.from_crs('EPSG:32637',gdal_ds.GetProjection(),always_xy=True)
  with np.load(OUT/'candidate_pool'/(pid+'.npz')) as f:rgb=np.moveaxis(f['rgb'],0,-1)
  overlay=Image.fromarray(rgb);dr=ImageDraw.Draw(overlay)
  vector_features=[]
  for q in pred:
   pixels=labels==q['label'];tier='TIER_A_HIGH_CONFIDENCE' if A[pixels].mean()>=.5 else 'TIER_B_MEDIUM_CONFIDENCE';area=q['geometry'].area;small=area<=50
   rows.append(dict(patch_id=pid,object_id=int(q['label']),source_image=r['rgb_path'],teacher_models='C;C3;C6;D;D_HFLIP',confidence=float(ps[:,pixels].mean()),agreement_score=float((votes[pixels]/4).mean()),model_votes_mean=float(votes[pixels].mean()),boundary_agreement=float(bd[pixels].mean()),area_m2=area,area_px=int(pixels.sum()),tier=tier,creation_method='FIXED_MULTI_TEACHER_CONSENSUS_NOT_HUMAN_GT',used_train=r['split']=='ACTIVE_LEARNING_TRAIN',split=r['split'],small=small,c6_mean=float(ps[2][pixels].mean()),tta_d_mean_absolute_delta=float(np.abs(ps[3]-flip)[pixels].mean())))
   vector_features.append(dict(type='Feature',geometry=mapping(q['geometry']),properties=rows[-1]))
   counts[kind+'_objects']+=1;counts['small']+=int(small);counts[tier]+=1;draw_geom(dr,q['geometry'],tx,inv,'lime' if tier.startswith('TIER_A') else 'orange',1)
   if small:mining.append(dict(patch_id=pid,object_id=int(q['label']),area_m2=area,c6_mean=float(ps[2][pixels].mean()),specialist_d_mean=float(ps[3][pixels].mean()),accepted_tier=tier,used_train=r['split']=='ACTIVE_LEARNING_TRAIN'))
  dump(OUT/'pseudo_labels'/(pid+'_PSEUDO_OBJECTS.geojson'),dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32637'}},features=vector_features))
  # Additional low C6 signal is an uncertain mining map, never direct positive GT.
  smallraw,nraw=ndimage.label(ps[2]>=.3,ndimage.generate_binary_structure(2,1));sizes=np.bincount(smallraw.ravel());sm=(sizes[smallraw]<479)&(smallraw>0)
  save_tif(OUT/'consensus'/(pid+'_SMALL_MINING.tif'),((ps[2]>=.1)&(ps[2]<.3)|sm).astype('uint8'),ROOT/r['rgb_path'])
  overlay.save(OUT/'qa'/(pid+'_consensus_overlay.png'));save_tif(OUT/'pseudo_labels'/(pid+'_PSEUDO_MASK.tif'),mask.astype('uint8'),ROOT/r['rgb_path']);save_tif(OUT/'hard_negatives'/(pid+'_CONSENSUS_BACKGROUND.tif'),D.astype('uint8'),ROOT/r['rgb_path'])
  negative.append(dict(patch_id=pid,split=r['split'],background_pixels=int(D.sum()),context=r['primary_group'],hard_context=r['primary_group']=='FP_CONTEXT',label='CONSENSUS_BACKGROUND_NOT_SEMANTIC_GROUND_TRUTH',used_train=r['split']=='ACTIVE_LEARNING_TRAIN',unconfirmed_disagreement_excluded=True))
  assert mask.any() or D.any();assert np.isfinite(weight).all()
 if not rows:raise RuntimeError('No usable pseudo-positive objects; stop without training')
 csvwrite(OUT/'pseudo_labels/object_manifest.csv',rows)
 if mining:csvwrite(OUT/'candidate_pool/SMALL_BUILDING_CANDIDATES.csv',mining)
 csvwrite(OUT/'hard_negatives/HARD_NEGATIVES.csv',negative)
 dump(OUT/'qa/CONSENSUS_SUMMARY.json',dict(counts=dict(counts),hard_negative_patches=sum(r['hard_context'] and r['used_train'] for r in negative),human_gt=False,uncertain_pixels_excluded=True,teachers_correlated=True))
 print('CONSENSUS',dict(counts),flush=True)
def boundaries_bool(a):return a & ~ndimage.binary_erosion(a,structure=np.ones((3,3),bool),border_value=0)
def filtered(prob,config):
 raw=prob>=config['threshold']
 if config['morphology']=='OPEN3':raw=ndimage.binary_opening(raw,structure=np.ones((3,3),bool))
 return raw
def score(records,probs,config,target_masks=None,gold_gt=None):
 total=Counter();per=[];bf=[];rawbf=[]
 for r in records:
  pid=r['patch_id'];prob=probs[pid];raw=filtered(prob,config);final,pred,_=objects(raw,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=config['min_component']))
  if gold_gt is None:
   target=target_masks[pid];_,gs,_=objects(target,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1))
  else:gs=gold_gt[pid];target=target_masks[pid]
  mat,inter=matrices(gs,pred);pairs=matching(mat,.3);matched={i for i,_,_ in pairs};tp=len(pairs);fp=len(pred)-tp;fn=len(gs)-tp
  small={i for i,g in enumerate(gs) if g['geometry'].area<=50};medium={i for i,g in enumerate(gs) if 50<g['geometry'].area<=200};large=set(range(len(gs)))-small-medium
  a=np.array([g['geometry'].area for g in gs]);pa=np.array([p['geometry'].area for p in pred]);merges=int(((inter/a[:,None]>=.3).sum(axis=0)>=2).sum()) if len(gs) and pred else 0;frag=int(((inter/pa[None,:]>=.3).sum(axis=1)>=2).sum()) if len(gs) and pred else 0
  pm=pixel(final,target);fb=boundaries(final,target)[0]['BOUNDARY_F1'];rb=boundaries(prob>=config['threshold'],target)[0]['BOUNDARY_F1'];bf.append(fb);rawbf.append(rb)
  vals=dict(TP=tp,FP=fp,FN=fn,GT=len(gs),PRED=len(pred),SMALL_GT=len(small),SMALL_TP=len(small&matched),MEDIUM_GT=len(medium),MEDIUM_TP=len(medium&matched),LARGE_GT=len(large),LARGE_TP=len(large&matched),MERGED=merges,FRAGMENTED=frag,PIXEL_TP=pm['PIXEL_TP'],PIXEL_FP=pm['PIXEL_FP'],PIXEL_FN=pm['PIXEL_FN']);total.update(vals);per.append(dict(patch_id=pid,**vals,boundary_f1=fb,raw_boundary_f1=rb))
 t=total;tp=t['TP'];fp=t['FP'];fn=t['FN'];pt=t['PIXEL_TP'];pf=t['PIXEL_FP'];pn=t['PIXEL_FN']
 result=dict(**dict(t),object_precision=tp/(tp+fp) if tp+fp else 0,object_recall=tp/(tp+fn) if tp+fn else 0,object_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,small_recall=t['SMALL_TP']/t['SMALL_GT'] if t['SMALL_GT'] else 0,medium_recall=t['MEDIUM_TP']/t['MEDIUM_GT'] if t['MEDIUM_GT'] else 0,large_recall=t['LARGE_TP']/t['LARGE_GT'] if t['LARGE_GT'] else 0,pixel_iou=pt/(pt+pf+pn) if pt+pf+pn else 1,dice=2*pt/(2*pt+pf+pn) if 2*pt+pf+pn else 1,final_boundary_f1=float(np.mean(bf)),raw_boundary_f1=float(np.mean(rawbf)))
 return result,per
def calibrate():
 records=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];targets={}
 for r in records:
  with np.load(OUT/'auto_dev'/(r['patch_id']+'.npz')) as f:targets[r['patch_id']]=f['mask'].astype(bool)
 base,_=score(records,{r['patch_id']:loadprob('MODEL_C6',r['patch_id']) for r in records},dict(threshold=.3,min_component=479,morphology='NONE'),targets)
 dump(OUT/'calibration/BASELINE_C6_DEV_PSEUDO.json',base);rows=[];hist=json.loads((OUT/'models/training_history.json').read_text())
 for ck in hist:
  probs={}
  for r in records:
   with np.load(OUT/'auto_dev'/(f"epoch{ck['epoch']}__"+r['patch_id']+'.npz')) as f:probs[r['patch_id']]=f['probability']
  for threshold in P['calibration']['thresholds']:
   for minimum in P['calibration']['min_components']:
    for morph in P['calibration']['morphology']:
     config=dict(threshold=threshold,min_component=minimum,morphology=morph);metric,_=score(records,probs,config,targets)
     passed=(metric['SMALL_TP']>=base['SMALL_TP']+1 and metric['FP']<=max(base['FP']*1.5,base['FP']+3) and metric['final_boundary_f1']>=.95*base['final_boundary_f1'])
     rows.append(dict(epoch=ck['epoch'],**config,**metric,constraints_pass=passed));print('DEV_CALIBRATE',ck['epoch'],threshold,minimum,morph,round(metric['object_f1'],4),flush=True)
 csvwrite(OUT/'calibration/DEV_GRID.csv',rows);feasible=[r for r in rows if r['constraints_pass']];best=max(feasible or rows,key=lambda r:(r['object_f1'],r['small_recall'],-r['FP'],r['final_boundary_f1'],-r['epoch']))
 ck=next(c for c in hist if c['epoch']==best['epoch']);freeze=dict(model='MODEL_C7_AUTO',checkpoint=ck['checkpoint'],checkpoint_sha256=ck['sha256'],epoch=best['epoch'],threshold=best['threshold'],min_component=best['min_component'],morphology=best['morphology'],connectivity=4,preprocessing='RGB_GLOBAL_PATCH_MINMAX',dev_metric=best,dev_constraints_satisfied=bool(feasible),dev_labels='PSEUDO_NOT_HUMAN',protocol_sha256=sha(OUT/'protocol.json'))
 dump(OUT/'calibration/FROZEN_CANDIDATE.json',freeze);(OUT/'calibration/FROZEN_CANDIDATE.sha256').write_text(sha(OUT/'calibration/FROZEN_CANDIDATE.json'));print('FROZEN',best,flush=True)
def goldscore():
 from shapely import wkb
 freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());assert sha(OUT/'calibration/FROZEN_CANDIDATE.json')==(OUT/'calibration/FROZEN_CANDIDATE.sha256').read_text();old=BASE/'qa/14A8_model_shootout';records=json.loads((old/'14A8_frozen_protocol.json').read_text())['patches'];gt={r['patch_id']:[] for r in records};probs={};targets={}
 ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):gt[f['patch_id']].append(dict(geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb())),fid=f.GetFID()))
 ds=None
 for r in records:
  with np.load(OUT/'gold_evaluation'/(r['patch_id']+'.npz')) as f:probs[r['patch_id']]=f['probability']
  with np.load(old/'inputs'/(r['patch_id']+'.npz')) as f:targets[r['patch_id']]=f['gt'].astype(bool)
 metric,per=score(records,probs,freeze,targets,gt);timings=json.loads((OUT/'gold_evaluation/inference_times.json').read_text());metric['cpu_mean_seconds']=float(np.mean([r['seconds'] for r in timings]));g=P['gold_gates']
 # Historical 14A8 BoundaryF1 aggregates boundary precision/recall counts, not patch mean.
 totals=Counter();raw_pixels=Counter()
 for r in records:
  b=boundaries(probs[r['patch_id']]>=freeze['threshold'],targets[r['patch_id']])[0]
  totals.update({k:b[k] for k in ['BOUNDARY_PRED_PIXELS','BOUNDARY_GT_PIXELS','BOUNDARY_PRED_WITHIN1','BOUNDARY_GT_WITHIN1']})
  pix=pixel(probs[r['patch_id']]>=freeze['threshold'],targets[r['patch_id']]);raw_pixels.update({k:pix[k] for k in ['PIXEL_TP','PIXEL_FP','PIXEL_FN']})
 bp=totals['BOUNDARY_PRED_WITHIN1']/max(1,totals['BOUNDARY_PRED_PIXELS']);br=totals['BOUNDARY_GT_WITHIN1']/max(1,totals['BOUNDARY_GT_PIXELS']);metric['raw_boundary_f1']=2*bp*br/(bp+br) if bp+br else 0
 rt=raw_pixels['PIXEL_TP'];rf=raw_pixels['PIXEL_FP'];rn=raw_pixels['PIXEL_FN'];metric['raw_pixel_iou']=rt/(rt+rf+rn) if rt+rf+rn else 1;metric['raw_dice']=2*rt/(2*rt+rf+rn) if 2*rt+rf+rn else 1
 gates=dict(object_f1=metric['object_f1']>g['object_f1_gt'],object_recall=metric['object_recall']>g['recall_gt'],missed=metric['FN']<g['missed_lt'],small=metric['small_recall']>=g['small_recall_ge'],false_positives=metric['FP']<=g['fp_le'],boundary=metric['raw_boundary_f1']>=g['raw_boundary_f1_ge'],cpu=metric['cpu_mean_seconds']<=g['cpu_mean_seconds_le'],dev_constraints=freeze['dev_constraints_satisfied'])
 result=dict(metrics=metric,patches=per,gates=gates,decision='CANDIDATE_ACCEPTED_FOR_STAGING' if all(gates.values()) else 'CANDIDATE_REJECTED',production_modified=False,model='MODEL_C7_AUTO',gold_attempts=1)
 dump(OUT/'gold_evaluation/FINAL_RESULT.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':{'consensus':consensus,'calibrate':calibrate,'goldscore':goldscore}[sys.argv[1]]()
