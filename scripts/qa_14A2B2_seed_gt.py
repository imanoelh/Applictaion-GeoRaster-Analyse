from pathlib import Path
import json
from qgis.core import QgsApplication,QgsVectorLayer
from shapely.geometry import shape
from shapely.validation import explain_validity
ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; APP=QgsApplication([],False); APP.initQgis(); ids=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']; result=[]
for pid in ids:
 lyr=QgsVectorLayer(f"{EXP/'annotations/14A2B_seed_ground_truth_WORKING.gpkg'}|layername={pid}_SEED_GROUND_TRUTH",pid,'ogr'); feats=list(lyr.getFeatures()); seen=set(); invalid=empty=zero=out=dup=0
 with __import__('rasterio').open(EXP/next(r['split'] for r in json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches'] if r['patch_id']==pid)/'rgb'/f'{pid}.tif') as src: bounds=src.bounds
 for f in feats:
  g=shape(__import__('json').loads(__import__('qgis').__doc__ or '{}')) if False else None
  wkb=bytes(f.geometry().asWkb()); key=wkb
  if key in seen: dup+=1
  seen.add(key); empty+=int(f.geometry().isEmpty()); zero+=int(f.geometry().area()<=0); invalid+=int(not f.geometry().isGeosValid()); b=f.geometry().boundingBox(); out+=int(b.xMinimum()<bounds.left or b.xMaximum()>bounds.right or b.yMinimum()<bounds.bottom or b.yMaximum()>bounds.top)
 result.append({'patch_id':pid,'feature_count':len(feats),'invalid':invalid,'empty':empty,'zero_area':zero,'out_of_bounds':out,'duplicates':dup,'annotation_sources':{str(v):sum(1 for f in feats if f['annotation_source']==v) for v in ('ASSISTED_C','ASSISTED_F','ASSISTED_C_AND_F','MANUAL')}})
(EXP/'qa/14A2B2_seed_gt_qa.json').write_text(json.dumps({'final_validation_run':False,'reason':'Seed GT layers are pending human annotation','patches':result},indent=2),encoding='utf-8'); print(json.dumps(result,indent=2)); APP.exitQgis()
