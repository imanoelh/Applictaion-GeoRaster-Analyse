"""Freeze one C6+dist3 experimental learning cycle. Never changes prior data."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9B_datasets import ROOT,BASE,AL,DEV,GOLD,sha,dump,csvwrite
from gold_set_14A7_guard import assert_non_gold_development_records
from osgeo import gdal
from pyproj import Transformer
from shapely.geometry import box
import numpy as np
OUT=BASE/'14A11_hybrid_pipeline'
def main():
 if (OUT/'protocol.json').exists():raise RuntimeError('Existing cycle: refuse replacing protocol')
 for d in ['inputs','teacher_predictions','hybrid_teacher','small_candidates','hard_negatives','train','dev','models','calibration','qa','gold_evaluation','logs']:(OUT/d).mkdir(parents=True,exist_ok=True)
 gold={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};expected=json.loads((AL/'qa/GOLD_HASHES_AFTER.json').read_text());assert all(gold.get(p)==h for p,h in expected.items());dump(OUT/'qa/GOLD_BEFORE.json',gold)
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text())
 previous=json.loads((BASE/'14A2_expansion/manifests/dataset_manifest.json').read_text())['patches']
 for pid in ['14A2_2024_11','14A2_2025_11']:
  m=next(r for r in previous if r['patch_id']==pid);assert m['split']=='train';path=BASE/'14A2_expansion/train/rgb'/(pid+'.tif');d=gdal.Open(str(path));tr=d.GetGeoTransform();tx=Transformer.from_crs(d.GetProjection(),'EPSG:32637',always_xy=True);points=[tx.transform(*gdal.ApplyGeoTransform(tr,x,y)) for x,y in [(0,0),(512,0),(512,512),(0,512)]];b=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
  records.append(dict(patch_id=pid,rgb_path=str(path.relative_to(ROOT)),rgb_sha256=sha(path),split='ACTIVE_LEARNING_TRAIN',bounds_32637=b,scene_type=m['scene_type'],primary_group='INDUSTRIAL_HISTORICAL_TRAIN',historical_train_status='TRAIN_PREVIOUSLY_USED_RGB_ONLY_NO_OLD_LABELS'))
 assert_non_gold_development_records(records)
 train=[r for r in records if r['split']=='ACTIVE_LEARNING_TRAIN'];dev=[r for r in records if r['split']=='DEV_CALIBRATION'];assert len(train)==12 and len(dev)==4
 assert not any(box(*a['bounds_32637']).intersection(box(*b['bounds_32637'])).area>0 for a in train for b in dev)
 hashes=set()
 for r in records:
  d=gdal.Open(str(ROOT/r['rgb_path']));a=d.ReadAsArray()[:3];assert a.shape==(3,512,512);pixelhash=hashlib.sha256(a.tobytes()).hexdigest();assert pixelhash not in hashes;hashes.add(pixelhash);r['pixel_sha256']=pixelhash
  np.savez_compressed(OUT/'inputs'/(r['patch_id']+'.npz'),rgb=a)
 c6=ROOT/'backend/data/models/model_c6_experimental/best_model_c6.pth';dist3=BASE/'14A10_specialized_benchmark/sources/nilsho01__unet-effb4-dist3-buildings/model.onnx'
 assert sha(c6)=='7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84';assert sha(dist3)=='e1c14b893d738a660d99a5f456fc68c04077a09fcb8f88a0bcd577d72b40a735'
 protocol=dict(model='MODEL_C8_HYBRID',teacher='HYBRID_TEACHER_C6_DIST3',max_cycles=1,records=records,c6_path=str(c6.relative_to(ROOT)),c6_sha256=sha(c6),dist3_path=str(dist3.relative_to(ROOT)),dist3_sha256=sha(dist3),
  hybrid=dict(c6_threshold=.3,c6_min_component=479,dist3_threshold=.5,dist3_seed_threshold=.5,
   consensus='IoU>=0.30 OR intersection/DIST3area>=0.60 with C6 support; choose geometry by fixed boundary/compactness/confidence proxy, preserve DIST3 units when one C6 overlaps multiple units',
   dist3_only='area>=1m2, compactness>=0.08, aspect<=8; mean confidence>=0.80 and flip IoU>=0.50 OR mean>=0.95 and flip IoU>=0.35; rejection score<0.55',
   c6_only='mean C6>=0.85 AND mean DIST3>=0.05; do not discard merely for absent thresholded DIST3 object',
   conflicts='positive overlap without consensus -> UNCERTAIN; never hard-supervise',
   fragment_merge='shared4-neighbour contact>=2pixels, mean boundary<0.25, mean mask>0.80, orientation delta<=20deg (squares exempt), same overlapping C6 component, combined compactness>=0.6*minimum source compactness',
   split='DIST3 object intersecting >=2 C6 cores of >=20px; split only if internal boundary>=0.35 occupies>=1% object; watershed boundary elevation with C6 core seeds',
   negatives='both C6 and DIST3/flip<0.05; rejected objects are uncertain unless corroborated by this background evidence',
   fp_score='0.30*(1-confidence)+0.25*(1-flipIoU)+0.20*shape_penalty+0.15*C6_background_fraction+0.10*flat_texture + 0.15*road/bare-context proxy, capped1; semantic maps/road distances NOT_AVAILABLE',
   weights=dict(CONSENSUS=1.,DIST3_ONLY=.6,C6_ONLY=.75,BACKGROUND=.7,UNCERTAIN=0.),area_balance='clip(200/object_pixels,0.25,4); contact gaps background weight1'),
  training=dict(epochs=3,seed=1411,batch=1,native_size=512,lr_backbone=2e-5,lr_head=1e-4,weight_decay=1e-4,trainable='all backbone and main classifier; aux frozen; BN running stats frozen',loss='weighted BCE + weighted Dice; contact separation targets; clipping1',early_stopping_patience=2,selection='DEV pseudo-label weighted loss for early stop; object metrics for final checkpoint/config selection',augmentation='seeded flips, rotations90, brightness0.9-1.1',threads=4),
  calibration=dict(thresholds=[.2,.3,.5],min_components=[4,32,128,479],morphology=['NONE','OPEN3'],connectivity=4,object_iou=.3,constraints='Small TP>=baselineC6+1, FP<=max(1.5*baselineFP,baselineFP+5), final BoundaryF1>=95% baseline. If none feasible, freeze best F1 and fail DEV gate.',dev_labels='HYBRID_PSEUDO_NOT_HUMAN'),
  gates=dict(f1_gt=.3491,recall_gt=.22424242424242424,small_tp_ge=1,missed_lt=128,fp_le=64,boundary_f1_ge=.2829149533*.95,cpu_mean_le=12.1923543),ambitious=dict(f1_ge=.5,recall_ge=.5,small_recall_ge=.25,boundary_ge=.2829149533),
  gold_policy='One frozen candidate inference per GOLD patch, no retuning; cached baselines only; no teacher hybrid generation on GOLD',production='MODEL_C_UNCHANGED')
 dump(OUT/'protocol.json',protocol);(OUT/'protocol.sha256').write_text(sha(OUT/'protocol.json'));dump(OUT/'qa/SPLIT_QA.json',dict(train=12,dev=4,train_dev_overlap=0,gold_overlap=0,industrial_added_train_only=2,human_corrected_gt_used=False));print('FROZEN_C8',12,4)
if __name__=='__main__':main()
