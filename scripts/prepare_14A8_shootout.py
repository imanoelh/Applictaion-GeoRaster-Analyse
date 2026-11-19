"""Freeze GOLD inputs and historical benchmark settings before any gold inference."""
from pathlib import Path
import csv,json,hashlib,sys,os
import numpy as np
from osgeo import gdal,ogr
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';GOLD=BASE/'14A7_gold_set';OUT=BASE/'qa/14A8_model_shootout'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def csvwrite(p,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    for d in ('inputs','inference','models','overlays','diagnostics','logs'): (OUT/d).mkdir(parents=True,exist_ok=True)
    plan=OUT/'14A8_frozen_protocol.json'
    if plan.exists():raise RuntimeError('Protocol already frozen. Never silently change parameters after seeing GOLD outputs')
    manifest=list(csv.DictReader((GOLD/'manifest/14A7_GOLD_SET_manifest.csv').open(encoding='utf-8-sig')))
    assert len(manifest)==4 and sum(int(p['gt_buildings']) for p in manifest)==165
    hashes=[]
    def record(path,kind,pid=''):
        hashes.append(dict(PATCH=pid,KIND=kind,PATH=str(path.relative_to(ROOT)).replace('\\','/'),SIZE=path.stat().st_size,SHA256=sha(path)))
    for file in ['manifest/14A7_GOLD_SET_manifest.csv','manifest/GOLD_SET_LOCK.json','manifest/GOLD_VALIDATED_ANNOTATION_LOCK.json','manifest/14A8_SHOOTOUT_PROTOCOL.json']:
        record(GOLD/file,'GOLD_METADATA')
    fixed=ROOT/manifest[0]['gt_path'];assert sha(fixed)==manifest[0]['gt_sha256'];record(fixed,'HUMAN_GT_VECTOR')
    ds=gdal.OpenEx(str(fixed),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES']);l=ds.GetLayerByName('buildings_gt');counts={}
    for f in l:
        assert f['source']=='MANUAL';g=f.GetGeometryRef();assert g is not None and g.IsValid();counts[f['patch_id']]=counts.get(f['patch_id'],0)+1
    ds=None
    for p in manifest:
        pid=p['patch_id'];assert p['GOLD_SET_LOCKED']=='YES' and p['FORBIDDEN_FOR_TRAINING']=='YES';assert counts[pid]==int(p['gt_buildings'])
        rgb=ROOT/p['rgb_path'];mask=ROOT/p['mask_path'];assert sha(rgb)==p['rgb_sha256'] and sha(mask)==p['mask_sha256'];r=gdal.Open(str(rgb));m=gdal.Open(str(mask))
        assert (r.RasterXSize,r.RasterYSize)==(512,512) and r.GetGeoTransform()==m.GetGeoTransform() and r.GetProjection()==m.GetProjection()
        image=r.ReadAsArray();gt=m.ReadAsArray();assert image.shape==(3,512,512) and set(np.unique(gt))=={0,1}
        np.savez_compressed(OUT/'inputs'/(pid+'.npz'),rgb=image,gt=gt)
        record(rgb,'RGB',pid);record(mask,'HUMAN_GT_MASK',pid);r=None;m=None
    csvwrite(OUT/'14A8_gold_input_hashes.csv',hashes)
    old=list(csv.DictReader((GOLD/'manifest/14A8_model_candidates.csv').open(encoding='utf-8-sig')))
    lookup={p['model_id']:p for p in old};specs=[]
    for mid in ['MODEL_C','MODEL_C3','MODEL_C6','MODEL_D','MODEL_C2','MODEL_C4','MODEL_C5']:
        p=lookup[mid];torch_model=mid in ('MODEL_C6','MODEL_C5');path=p['weights_path'] if torch_model else p['onnx_path']
        threshold=.30 if mid in ('MODEL_C3','MODEL_C6','MODEL_C4') else .50
        minimum=479 if mid in ('MODEL_C3','MODEL_C6') else 4 if mid in ('MODEL_C','MODEL_D') else 1
        connectivity=8 if mid in ('MODEL_C','MODEL_D') else 4
        evidence={'MODEL_C':'backend/app/ai/config/building_model_catalog.py; postprocessing_service.py standard min4/connectivity8; 14A1E threshold0.5',
                  'MODEL_C3':'scripts/benchmark_14A6B_c3_vs_c6.py (14A6C restored version); model_c3.onnx identity from14A6C',
                  'MODEL_C6':'scripts/benchmark_14A6B_c3_vs_c6.py (14A6C restored version)',
                  'MODEL_D':'backend/app/ai/models/whu_onnx_building_adapter.py; standard PostProcessingConfig threshold0.5/min4/connectivity8 (not gold-calibrated)',
                  'MODEL_C2':'scripts/run_14A3_model_c2_finetuning.py; export_validate_model_c2_onnx.py; threshold0.5/4-connectivity/unfiltered',
                  'MODEL_C4':'scripts/benchmark_model_c4.py; threshold0.3/4-connectivity/unfiltered',
                  'MODEL_C5':'scripts/train_model_c5_balanced.py; threshold0.5/4-connectivity/unfiltered'}[mid]
        specs.append(dict(model=mid,architecture=p['architecture'],path=path,sha256=sha(ROOT/path),engine='PYTORCH_CPU' if torch_model else 'ONNX_RUNTIME_CPU',
             preprocessing='rgb_div255' if mid=='MODEL_D' else 'rgb_global_patch_minmax',input_size=512,tiling='ONE_NATIVE_512_TILE',overlap=0,TTA=False,resize='NONE',padding='NONE',
             output_activation='softmax_channel1' if mid=='MODEL_D' else 'sigmoid_out',threshold=threshold,min_component_pixels=minimum,connectivity=connectivity,morphology='NONE',evidence=evidence))
    # Historical E is exactly max(C,D), i.e. binary OR at common threshold0.5.
    c=next(p for p in specs if p['model']=='MODEL_C');d=next(p for p in specs if p['model']=='MODEL_D')
    specs.append(dict(model='MODEL_E',architecture='Historical C+D binary union',path=c['path']+';'+d['path'],sha256=c['sha256']+';'+d['sha256'],engine='ONNX_RUNTIME_CPU_COMPOSITE',
      preprocessing='C_global_minmax;D_rgb_div255',input_size=512,tiling='ONE_NATIVE_512_TILE',overlap=0,TTA=False,resize='NONE',padding='NONE',output_activation='max(sigmoidC,softmaxD_channel1)',threshold=.5,min_component_pixels=4,connectivity=8,morphology='NONE',evidence='backend/app/ai/models/hybrid_building_adapter.py; building_model_catalog.py benchmark-only union'))
    audit=[]
    for p in old:
        selected=next((s for s in specs if s['model']==p['model_id']),None)
        available=[x for x in (p['weights_path'],p['onnx_path']) if x and (ROOT/x).is_file()]
        reason='WORKER_LOAD_PENDING' if selected else 'MISSING_SMP' if p['model_id'] in ('MODEL_A','MODEL_H') else 'SEGFORMER_ENV_MISSING_OR_BROKEN' if p['model_id'] in ('MODEL_F','MODEL_F2') else 'UNRESOLVED_BUILDING_OUTPUT_CHANNEL'
        audit.append(dict(MODEL=p['model_id'],ARCHITECTURE=p['architecture'],WEIGHTS_PATH=';'.join(available),WEIGHTS_REAL='YES' if available else 'NO',LOADABLE='PENDING' if selected else 'NOT_REPRODUCIBLE',RUNTIME_AVAILABLE='YES' if selected else 'NO_OR_UNRESOLVED',INPUT_SIZE=p['input_resolution'],CPU_COMPATIBLE='YES',ONNX_AVAILABLE=p['onnx_available'],HISTORICAL_STATUS=p['status'],BENCHMARK_STATUS='PENDING' if selected else 'NOT_REPRODUCIBLE',REASON=reason))
    audit.append(dict(MODEL='MODEL_E',ARCHITECTURE=specs[-1]['architecture'],WEIGHTS_PATH=specs[-1]['path'],WEIGHTS_REAL='YES',LOADABLE='PENDING',RUNTIME_AVAILABLE='YES',INPUT_SIZE='512',CPU_COMPATIBLE='YES',ONNX_AVAILABLE='True',HISTORICAL_STATUS='BENCHMARK_ONLY',BENCHMARK_STATUS='PENDING',REASON='HISTORICAL_BINARY_UNION'))
    csvwrite(OUT/'14A8_model_availability.csv',audit)
    artifacts=[]
    for p in old:
        for path in (p['weights_path'],p['onnx_path']):
            if path and (ROOT/path).is_file():artifacts.append(dict(model=p['model_id'],path=path,sha256=sha(ROOT/path)))
    (OUT/'14A8_model_weight_hashes.json').write_text(json.dumps(artifacts,indent=2),encoding='utf-8')
    protocol=dict(models=specs,primary_object_iou=.30,secondary_object_ious=[.50,.70],matching='Hungarian gated max-cardinality then max IoU; one-to-one; annotated polygon IDs retained',
      gt_objects=165,patches=manifest,cpu_threads=4,inter_op_threads=1,warmup='one zero512 tile, excluded from timing; no gold tuning',
      pixel_metrics='Primary historical raw threshold masks as14A6C; FINAL filtered masks additionally reported; same GT masks for all',
      boundary='Historical14A1E clipped 8-neighbour erosion + 8-neighbour1px dilation, harmonic precision/recall; same as frozen14A7 protocol; old erroneous14A6C formula not reused',
      mean_boundary_distance='Historical14A1E symmetric chamfer8 (diag sqrt2), mean over all contour pixels in both directions, pixels',
      small_building_cutoff_m2=50,small_cutoff_source='Frozen14A7_SHOOTOUT_PROTOCOL before GOLD annotation; no medium/large cutoff invented',
      merges='Pred overlaps >=2 GT, intersection/GTarea>=0.30; fragments GT overlaps >=2 preds, intersection/predarea>=0.30. Supplemental, not TP credit.',
      ranking=['OBJECT_F1','OBJECT_RECALL','MISSED_ASC','FP_ASC','BOUNDARY_F1','PIXEL_IOU','CPU_TIME_MEAN_ASC'],
      gold_unchanged=True,no_training=True,no_threshold_sweep=True,no_promotion=True)
    plan.write_text(json.dumps(protocol,indent=2),encoding='utf-8');(OUT/'14A8_frozen_protocol.sha256').write_text(sha(plan),encoding='ascii')
    print('FROZEN',len(specs),'model engines; 4 GOLD patches/165 IDs; inputs hashed',flush=True)
if __name__=='__main__':main()
