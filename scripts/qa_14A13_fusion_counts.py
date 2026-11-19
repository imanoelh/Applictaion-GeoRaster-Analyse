"""Derive merge/fragment counts from already saved one-shot fusion masks."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE
from evaluate_14A8_shootout import objects,matrices,matching
from osgeo import gdal
from shapely import wkb
import numpy as np
OUT=BASE/'14A13_fusion_v2';B8=BASE/'qa/14A8_model_shootout';records=json.loads((B8/'14A8_frozen_protocol.json').read_text())['patches']
gt={r['patch_id']:[] for r in records};ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
for f in ds.GetLayerByName('buildings_gt'):gt[f['patch_id']].append(dict(geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
merged=fragmented=0
for r in records:
 pid=r['patch_id'];mask=gdal.Open(str(OUT/'predictions'/(pid+'_fusion_mask.tif'))).ReadAsArray().astype(bool);_,pred,_=objects(mask,ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=1));mat,inter=matrices(gt[pid],pred);pairs=matching(mat,.3);ga=np.array([g['geometry'].area for g in gt[pid]]);pa=np.array([p['geometry'].area for p in pred]);merged+=int(((inter/ga[:,None]>=.3).sum(axis=0)>=2).sum()) if len(pred) else 0;fragmented+=int(((inter/pa[None,:]>=.3).sum(axis=1)>=2).sum()) if len(pred) else 0
res=json.loads((OUT/'gold_evaluation/FINAL_RESULT.json').read_text());res['metrics']['MERGED']=merged;res['metrics']['FRAGMENTED']=fragmented;(OUT/'gold_evaluation/FINAL_RESULT.json').write_text(json.dumps(res,indent=2));print('FUSION_COUNTS',merged,fragmented)
