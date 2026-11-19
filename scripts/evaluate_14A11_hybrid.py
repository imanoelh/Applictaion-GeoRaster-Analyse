"""DEV-only frozen selection and one final C8 GOLD scoring; no model changes."""
from pathlib import Path
import sys,json,time
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,OUT,sha,dump,csvwrite
from evaluate_14A9_auto import score,filtered
from evaluate_14A8_shootout import objects,matrices,matching,boundaries,pixel,draw_geom,save_tif
from osgeo import gdal
from shapely import wkb
from shapely.geometry import mapping,shape
from pyproj import Transformer
from PIL import Image,ImageDraw,ImageFont
import numpy as np
P=json.loads((OUT/'protocol.json').read_text())
assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text()

def calibrate():
 assert json.loads((OUT/'qa/PSEUDO_TECHNICAL_QA.json').read_text())['all_checks_pass']
 assert not (OUT/'calibration/FROZEN_CANDIDATE.json').exists()
 records=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];targets={};baseprobs={};teacher_objects={}
 for r in records:
  pid=r['patch_id']
  with np.load(OUT/'dev'/(pid+'.npz')) as f:targets[pid]=f['mask'].astype(bool)
  with np.load(OUT/'teacher_predictions'/(pid+'.npz')) as f:baseprobs[pid]=f['c6']
  teacher_objects[pid]=[dict(geometry=shape(f['geometry'])) for f in json.loads((OUT/'hybrid_teacher'/(pid+'_PSEUDO_OBJECTS.geojson')).read_text())['features']]
 assert sum(map(len,teacher_objects.values()))==149
 base,_=score(records,baseprobs,dict(threshold=.3,min_component=479,morphology='NONE'),targets,teacher_objects)
 dump(OUT/'calibration/C6_DEV_PSEUDO_BASELINE.json',base);rows=[];history=json.loads((OUT/'models/training_history.json').read_text())
 for ck in history:
  probs={}
  for r in records:
   with np.load(OUT/'dev'/(f"epoch{ck['epoch']}__"+r['patch_id']+'.npz')) as f:probs[r['patch_id']]=f['probability']
  for threshold in P['calibration']['thresholds']:
   for minimum in P['calibration']['min_components']:
    for morph in P['calibration']['morphology']:
     config=dict(threshold=threshold,min_component=minimum,morphology=morph);metric,_=score(records,probs,config,targets,teacher_objects)
     passed=metric['SMALL_TP']>=base['SMALL_TP']+1 and metric['FP']<=max(base['FP']*1.5,base['FP']+5) and metric['final_boundary_f1']>=.95*base['final_boundary_f1']
     rows.append(dict(epoch=ck['epoch'],**config,**metric,constraints_pass=passed));print('C8_DEV',ck['epoch'],threshold,minimum,morph,round(metric['object_f1'],4),passed,flush=True)
 csvwrite(OUT/'calibration/DEV_GRID.csv',rows);feasible=[r for r in rows if r['constraints_pass']];best=max(feasible or rows,key=lambda r:(r['object_f1'],r['small_recall'],-r['FP'],r['final_boundary_f1'],-r['epoch']));ck=next(c for c in history if c['epoch']==best['epoch'])
 freeze=dict(model='MODEL_C8_HYBRID',checkpoint=ck['checkpoint'],checkpoint_sha256=ck['sha256'],epoch=best['epoch'],threshold=best['threshold'],min_component=best['min_component'],morphology=best['morphology'],connectivity=4,preprocessing='RGB_GLOBAL_PATCH_MINMAX_NATIVE512',object_iou=.3,dev_metric=best,dev_constraints_satisfied=bool(feasible),dev_labels='HYBRID_PSEUDO_NOT_HUMAN',protocol_sha256=sha(OUT/'protocol.json'))
 dump(OUT/'calibration/FROZEN_CANDIDATE.json',freeze);(OUT/'calibration/FROZEN_CANDIDATE.sha256').write_text(sha(OUT/'calibration/FROZEN_CANDIDATE.json'));print('C8_FROZEN',json.dumps(freeze),flush=True)

def goldscore():
 freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());assert sha(OUT/'calibration/FROZEN_CANDIDATE.json')==(OUT/'calibration/FROZEN_CANDIDATE.sha256').read_text();assert sha(ROOT/freeze['checkpoint'])==freeze['checkpoint_sha256'];assert not (OUT/'gold_evaluation/FINAL_RESULT.json').exists()
 old=BASE/'qa/14A8_model_shootout';records=json.loads((old/'14A8_frozen_protocol.json').read_text())['patches'];gt={r['patch_id']:[] for r in records};targets={};probs={}
 ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):gt[f['patch_id']].append(dict(geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb())),fid=f.GetFID()))
 ds=None
 for r in records:
  pid=r['patch_id']
  with np.load(OUT/'gold_evaluation'/(pid+'.npz')) as f:probs[pid]=f['probability']
  with np.load(old/'inputs'/(pid+'.npz')) as f:targets[pid]=f['gt'].astype(bool)
 metric,per=score(records,probs,freeze,targets,gt);assert metric['GT']==165 and metric['SMALL_GT']==38;runtime=json.loads((OUT/'gold_evaluation/runtime.json').read_text());metric['cpu_mean_seconds']=float(np.mean([r['seconds'] for r in runtime]));bc=Counter();pc=Counter();rows=[];post=[]
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13);sheet=Image.new('RGB',(4*512,4*542),'white')
 for ri,r in enumerate(records):
  pid=r['patch_id'];prob=probs[pid];target=targets[pid];b=boundaries(prob>=freeze['threshold'],target)[0];bc.update({k:b[k] for k in ['BOUNDARY_PRED_PIXELS','BOUNDARY_GT_PIXELS','BOUNDARY_PRED_WITHIN1','BOUNDARY_GT_WITHIN1']});pix=pixel(prob>=freeze['threshold'],target);pc.update({k:pix[k] for k in ['PIXEL_TP','PIXEL_FP','PIXEL_FN']})
  t=time.perf_counter();final,pred,_=objects(filtered(prob,freeze),ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=freeze['min_component']));post.append(time.perf_counter()-t);mat,_=matrices(gt[pid],pred);pairs=matching(mat,.3);assert len({i for i,j,v in pairs})==len(pairs)==len({j for i,j,v in pairs});pd={i:(j,v) for i,j,v in pairs}
  for i,g in enumerate(gt[pid]):
   j,v=pd.get(i,(None,None));rows.append(dict(patch_id=pid,gt_id=g['fid'],area_m2=g['geometry'].area,matched=j is not None,prediction_id=pred[j]['label'] if j is not None else '',iou=v if v is not None else 0,best_iou=float(mat[i].max()) if len(pred) else 0))
  dump(OUT/'gold_evaluation'/(pid+'_C8_predictions.geojson'),dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32637'}},features=[dict(type='Feature',properties=dict(prediction_id=q['label']),geometry=mapping(q['geometry'])) for q in pred]));save_tif(OUT/'gold_evaluation'/(pid+'_C8_mask.tif'),final.astype('uint8'),ROOT/r['rgb_path'])
  rgbds=gdal.Open(str(ROOT/r['rgb_path']));rgb=np.moveaxis(rgbds.ReadAsArray()[:3],0,-1);tx=Transformer.from_crs('EPSG:32637',rgbds.GetProjection(),always_xy=True);inv=gdal.InvGeoTransform(rgbds.GetGeoTransform());im=Image.fromarray(rgb);dr=ImageDraw.Draw(im)
  for g in gt[pid]:draw_geom(dr,g['geometry'],tx,inv,'lime',1)
  for q in pred:draw_geom(dr,q['geometry'],tx,inv,'magenta',1)
  im.save(OUT/'gold_evaluation'/(pid+'_C8_overlay.png'))
  panels=[('RGB / '+pid,Image.fromarray(rgb)),('C6 / GT green',Image.open(old/'overlays'/('MODEL_C6__'+pid+'.png'))),('DIST3 / GT green',Image.open(BASE/'14A10_specialized_benchmark/overlays'/('UNET_DIST3__'+pid+'.png'))),('C8 frozen / GT green',im)]
  for col,(title,panel) in enumerate(panels):sheet.paste(panel,(col*512,ri*542+30));ImageDraw.Draw(sheet).text((col*512+3,ri*542+3),title,fill='black',font=font)
 assert len(rows)==165 and len({(r['patch_id'],r['gt_id']) for r in rows})==165 and sum(r['matched'] for r in rows)==metric['TP']
 bp=bc['BOUNDARY_PRED_WITHIN1']/max(1,bc['BOUNDARY_PRED_PIXELS']);br=bc['BOUNDARY_GT_WITHIN1']/max(1,bc['BOUNDARY_GT_PIXELS']);metric['raw_boundary_f1']=2*bp*br/(bp+br) if bp+br else 0;metric['raw_boundary_counts']=dict(bc);pt=pc['PIXEL_TP'];pf=pc['PIXEL_FP'];pn=pc['PIXEL_FN'];metric['raw_pixel_iou']=pt/(pt+pf+pn);metric['raw_dice']=2*pt/(2*pt+pf+pn);metric['cpu_postprocessing_mean_seconds']=float(np.mean(post));g=P['gates']
 gates=dict(object_f1=metric['object_f1']>g['f1_gt'],object_recall=metric['object_recall']>g['recall_gt'],small=metric['SMALL_TP']>=g['small_tp_ge'],missed=metric['FN']<g['missed_lt'],false_positives=metric['FP']<=g['fp_le'],boundary=metric['raw_boundary_f1']>=g['boundary_f1_ge'],cpu=metric['cpu_mean_seconds']<=g['cpu_mean_le'],dev_constraints=freeze['dev_constraints_satisfied'])
 csvwrite(OUT/'gold_evaluation/C8_GT_MATCHING.csv',rows);sheet.save(OUT/'gold_evaluation/14A11_C6_DIST3_C8_CONTACT.png');dump(OUT/'gold_evaluation/FINAL_RESULT.json',dict(model='MODEL_C8_HYBRID',metrics=metric,patches=per,gates=gates,candidate_ready_for_staging=all(gates.values()),gold_attempts=1,production_modified=False));print('C8_RESULT',json.dumps(metric),json.dumps(gates),flush=True)
if __name__=='__main__':{'calibrate':calibrate,'goldscore':goldscore}[sys.argv[1]]()
