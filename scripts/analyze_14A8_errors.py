"""Document inspected error thumbnails and fixed-filter effects; never tune GOLD."""
from pathlib import Path
import csv,json
import numpy as np
from scipy import ndimage
from osgeo import ogr,gdal,osr
from shapely import wkb
from shapely.ops import transform as geom_transform
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def csvread(path):return list(csv.DictReader(path.open(encoding='utf-8-sig')))
def csvwrite(path,rows):
 with path.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 protocol=json.loads((OUT/'14A8_frozen_protocol.json').read_text());models=json.loads((OUT/'14A8_summary.json').read_text())['models_benchmarked'];specs={s['model']:s for s in protocol['models']}
 fp=csvread(OUT/'14A8_false_positive_analysis.csv');fn=csvread(OUT/'14A8_missed_buildings_analysis.csv')
 # Human/model-assistant visual inspection of the generated diagnostic sheets.
 reviewed_fp=[2,5,13,14,16,33,34,37,47,58,48,65,59,85,67,96,91,101,102,103,106,119,131,144,146,184,175,196,200,229,241,252,253,254,255,256,259,257,261,273,276,275,279,281,288,289,297,309]
 reviewed_ids={'FP'+str(i) for i in reviewed_fp}
 for r in fp:
  if r['REVIEW_ID'] in reviewed_ids:
   number=int(r['REVIEW_ID'][2:]);r['VISUAL_REVIEW']='YES';r['BASIS']='INSPECTED_RGB_AND_GREEN_GT_MAGENTA_PREDICTION_DIAGNOSTIC_SHEET'
   r['CATEGORY']='ROAD' if number==259 else 'BARE_SOIL' if number in (33,85) else 'OTHER' if number==34 else 'ROOF_LIKE_OBJECT'
   r['NOTE']='Roof/roof-edge overlap, undersegmentation or merged footprints can fail one-to-one IoU; FP is relative to locked GT, not proof of non-building.'
   if number==259:r['NOTE']='C6 prediction covers road/crosswalk surface in difficult patch; visible semantic road false positive.'
   if number in (33,85):r['NOTE']='Large prediction on brown bare-soil plot beside road; non-roof context visible.'
   if number==34:r['NOTE']='Ambiguous grey object/ground context; no material class forced from RGB.'
 reviewed_fn=[7,5,39,37,67,65,91,89,119,117,149,147,175,173,203,201,305,273,386,354,461,434,543,515,625,593,704,673,785,753,863,836,869,883,892,906,915,929,938,951,960,974,983,997,1006,1020,1029,1042,1048,1049,1055,1056,1062,1063,1067,1068,1074,1075,1081,1082,1088,1089,1094,1095]
 for r in fn:
  if r['REVIEW_ID'] in {'FN'+str(i) for i in reviewed_fn}:
   r['VISUAL_REVIEW']='YES';r['NOTE']='Inspected RGB: small annotated structure not sufficiently covered/matched; neighbouring shadow and adjacent roofs in dense scenes are context hypotheses, not proven causal mechanisms.'
   if 'DENSE_CLUSTER' in r['CATEGORIES'] and 'SHADOW' not in r['CATEGORIES']:r['CATEGORIES']+=';SHADOW'
 csvwrite(OUT/'14A8_false_positive_analysis.csv',fp)
 # Quantify loss caused by the already frozen minimum component filter, not a new parameter choice.
 ds=gdal.OpenEx(str(ROOT/protocol['patches'][0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES']);small={}
 for f in ds.GetLayerByName('buildings_gt'):
  g=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))
  if g.area<=50:small[f.GetFID()]=dict(patch=f['patch_id'],geometry=g,area=g.area)
 ds=None;rows=[]
 for p in protocol['patches']:
  pid=p['patch_id'];r=gdal.Open(str(ROOT/p['rgb_path']));tr=r.GetGeoTransform();proj=r.GetProjection();r=None;tx=Transformer.from_crs('EPSG:32637',proj,always_xy=True);individual={}
  for fid,g in small.items():
   if g['patch']!=pid:continue
   vector=ogr.GetDriverByName('Memory').CreateDataSource('');srs=osr.SpatialReference();srs.ImportFromWkt(proj);layer=vector.CreateLayer('gt',srs,ogr.wkbUnknown);feature=ogr.Feature(layer.GetLayerDefn());feature.SetGeometry(ogr.CreateGeometryFromWkb(geom_transform(tx.transform,g['geometry']).wkb));layer.CreateFeature(feature)
   mem=gdal.GetDriverByName('MEM').Create('',512,512,1,gdal.GDT_Byte);mem.SetGeoTransform(tr);mem.SetProjection(proj);mem.GetRasterBand(1).Fill(0);gdal.RasterizeLayer(mem,[1],layer,burn_values=[1]);individual[fid]=mem.ReadAsArray().astype(bool);mem=None;vector=None
  for mid in models:
   raw=gdal.Open(str(OUT/'models'/mid/(pid+'_raw_threshold.tif'))).ReadAsArray().astype(bool);final=gdal.Open(str(OUT/'models'/mid/(pid+'_final_mask.tif'))).ReadAsArray().astype(bool);spec=specs[mid]
   labels,_=ndimage.label(raw,structure=ndimage.generate_binary_structure(2,1 if spec['connectivity']==4 else 2));sizes=np.bincount(labels.ravel())
   for fid,mask in individual.items():
    n=int(mask.sum());raw_hit=int((raw&mask).sum());final_hit=int((final&mask).sum());overlap_labels=np.unique(labels[mask&raw]);removed=(raw_hit>0 and final_hit==0)
    rows.append(dict(MODEL=mid,PATCH=pid,GT_ID=fid,AREA_M2=small[fid]['area'],GT_PIXELS=n,RAW_THRESHOLD_BUILDING_PIXELS=raw_hit,FINAL_BUILDING_PIXELS=final_hit,RAW_COVERAGE=raw_hit/n if n else None,FINAL_COVERAGE=final_hit/n if n else None,
      FROZEN_MIN_COMPONENT=spec['min_component_pixels'],MAX_OVERLAPPING_RAW_COMPONENT_PIXELS=int(sizes[overlap_labels].max()) if len(overlap_labels) else 0,ALL_RAW_COVERAGE_REMOVED_BY_FROZEN_FILTER=removed))
    if removed:
     for e in fn:
      if e['MODEL']==mid and e['PATCH']==pid and int(e['GT_ID'])==fid:e['NOTE']+=' All positive raw-threshold pixels covering this GT were removed by the frozen min-component filter; no threshold/min-area sweep performed.'
 csvwrite(OUT/'14A8_missed_buildings_analysis.csv',fn);csvwrite(OUT/'14A8_small_building_analysis.csv',rows)
 summary=dict(fp_total=len(fp),fp_visually_reviewed=sum(r['VISUAL_REVIEW']=='YES' for r in fp),fn_total=len(fn),fn_visually_reviewed=sum(r['VISUAL_REVIEW']=='YES' for r in fn),
  reviewed_fp_categories={k:sum(r['VISUAL_REVIEW']=='YES' and r['CATEGORY']==k for r in fp) for k in ['ROAD','BARE_SOIL','SHADOW','VEGETATION','INDUSTRIAL_SURFACE','ROOF_LIKE_OBJECT','OTHER']},
  small_gt=len(small),filter_effects={mid:dict(small_with_raw_positive_pixels=sum(r['MODEL']==mid and r['RAW_THRESHOLD_BUILDING_PIXELS']>0 for r in rows),small_with_all_raw_coverage_removed=sum(r['MODEL']==mid and r['ALL_RAW_COVERAGE_REMOVED_BY_FROZEN_FILTER'] for r in rows)) for mid in models},
  limits='Review covers principal FP (two largest per model/scene) and small FN examples. Unreviewed events remain explicit. Visual tags are observations/hypotheses, not new semantic ground truth. No GOLD data change or calibration.')
 (OUT/'14A8_error_analysis_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
