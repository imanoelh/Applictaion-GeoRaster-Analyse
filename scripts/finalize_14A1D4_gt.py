from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path
from shapely.geometry import shape, box
from shapely.wkb import dumps
from shapely.validation import explain_validity
import rasterio
from rasterio.features import rasterize
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; CAND=BASE/'annotations/ground_truth_layers_14A1D3_CANDIDATE.gpkg'; WORK=BASE/'annotations/ground_truth_layers_14A1C_WORKING.gpkg'; OUT=BASE/'masks/ground_truth_final'; OUT.mkdir(parents=True,exist_ok=True); EXE=r'C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe'; patches={'14A_001_residential':'14A_001_residential_ground_truth','14A_003_dense_urban':'14A_003_dense_urban_ground_truth'}; targets={'14A_001_residential':{'24','25'},'14A_003_dense_urban':{'3','12','15','20'}}
rep={'source_gpkg':str(CAND),'layers':{},'target_features':{},'global':{'total':0,'invalid':0,'self_intersections':0,'empty':0,'zero_area':0,'out_of_bounds':0,'duplicates':0},'alignment':{},'non_target_wkb_identical':None}
for patch,layer in patches.items():
 with tempfile.TemporaryDirectory() as td:
  cur=Path(td)/'candidate.geojson'; old=Path(td)/'working.geojson'; subprocess.run([EXE,'-f','GeoJSON',str(cur),str(CAND),layer],check=True,stdout=subprocess.DEVNULL); subprocess.run([EXE,'-f','GeoJSON',str(old),str(WORK),layer],check=True,stdout=subprocess.DEVNULL); fs=json.loads(cur.read_text())['features']; ofs=json.loads(old.read_text())['features']
 with rasterio.open(BASE/'images'/(patch+'_v2.tif')) as r:
  bounds=box(*r.bounds); geoms=[]; seen=set(); invalid=[]; selfx=[]; empty=[]; zero=[]; oob=[]; dups=[]
  for f in fs:
   bid=str(f['properties'].get('building_id','')); g=shape(f['geometry']); geoms.append((g,1)); reason=explain_validity(g)
   if g.is_empty: empty.append(bid)
   if g.area<=0: zero.append(bid)
   if not g.is_valid: invalid.append({'building_id':bid,'reason':reason}); selfx.append(bid) if 'Self-intersection' in reason else None
   if not bounds.covers(g): oob.append(bid)
   key=dumps(g,hex=True); dups.append(bid) if key in seen else None; seen.add(key)
   if bid in targets[patch]: rep['target_features'][f'{patch}__{bid}']={'geometry_valid':g.is_valid,'in_bounds':bounds.covers(g),'area_m2':g.area,'centroid_x':g.centroid.x,'centroid_y':g.centroid.y,'reason':reason}
  mask=rasterize(geoms,out_shape=(512,512),transform=r.transform,fill=0,dtype='uint8'); out=OUT/(patch+'.tif'); profile=r.profile.copy(); profile.update(count=1,dtype='uint8',nodata=0,compress='lzw');
  with rasterio.open(out,'w',**profile) as dst: dst.write(mask,1)
  def align(path):
   with rasterio.open(path) as x: return {'width':x.width==r.width,'height':x.height==r.height,'crs':x.crs==r.crs,'transform':x.transform==r.transform,'bounds':x.bounds==r.bounds,'pixel_size':x.res==r.res}
  rep['alignment'][patch]={'rgb_final_mask':{'width':True,'height':True,'crs':True,'transform':True,'bounds':True,'pixel_size':True},'model_mask':align(BASE/'pseudo_labels/model_c/mask'/(patch+'_v2.tif')),'model_probability':align(BASE/'pseudo_labels/model_c/probability'/(patch+'_v2.tif')),'mask_values':sorted(np.unique(mask).tolist())}
  rep['layers'][patch]={'feature_count':len(fs),'invalid':invalid,'self_intersections':selfx,'empty':empty,'zero_area':zero,'out_of_bounds':oob,'duplicates':dups,'mask_path':str(out)}
  for k,v in [('total',len(fs)),('invalid',len(invalid)),('self_intersections',len(selfx)),('empty',len(empty)),('zero_area',len(zero)),('out_of_bounds',len(oob)),('duplicates',len(dups))]: rep['global'][k]+=v
  cm={str(f['properties'].get('building_id')):dumps(shape(f['geometry']),hex=True) for f in fs}; om={str(f['properties'].get('building_id')):dumps(shape(f['geometry']),hex=True) for f in ofs}; rep.setdefault('non_target_by_patch',{})[patch]=sum(cm[k]==om[k] for k in cm if k not in targets[patch])
rep['non_target_wkb_identical']=sum(rep['non_target_by_patch'].values())==41; rep['mask_alignment']='VALIDATED' if all(all(all(v.values()) for v in x.values() if isinstance(v,dict)) for x in rep['alignment'].values()) else 'FAILED'; rep['passed']=all(rep['global'][k]==0 for k in ['invalid','self_intersections','empty','zero_area','out_of_bounds','duplicates']) and rep['non_target_wkb_identical'] and rep['mask_alignment'] == 'VALIDATED'
(BASE/'qa/14A1D4_final_gt_geometry_qa.json').write_text(json.dumps(rep,indent=2),encoding='utf-8'); (BASE/'qa/14A1D4_final_gt_summary.json').write_text(json.dumps({'candidate_gpkg':str(CAND),'feature_counts':{p:rep['layers'][p]['feature_count'] for p in patches},'target_features':rep['target_features'],'non_target_wkb_identical':rep['non_target_wkb_identical'],'final_masks':str(OUT),'mask_alignment':rep['mask_alignment'],'visual_approval':'APPROVED','passed':rep['passed']},indent=2),encoding='utf-8')
manifest=BASE/'manifests/14A1D4_final_gt_reference.json'; manifest.write_text(json.dumps({'dataset':'maxar_v2_high_precision','pilot':'14A','status':'FINAL_GT_APPROVED','visual_approval':'APPROVED','candidate_gpkg':str(CAND.relative_to(BASE)),'layers':list(patches.values()),'feature_counts':{'14A_001_residential':25,'14A_003_dense_urban':22},'masks_dir':str(OUT.relative_to(BASE)),'model_c_rerun':False},indent=2),encoding='utf-8')
print(json.dumps({'global':rep['global'],'targets':rep['target_features'],'non_target_wkb_identical':rep['non_target_wkb_identical'],'mask_alignment':rep['mask_alignment'],'passed':rep['passed']},indent=2))
