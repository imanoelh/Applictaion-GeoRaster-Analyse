"""14A.7-LITE isolated data preparation; never imports the production application."""
from pathlib import Path
import csv,hashlib,json,sys,time,importlib.util,os
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
SOURCE=BASE/'14A7_validation_expansion'
OUT=BASE/'14A7_gold_set'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def csvwrite(p,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def prepare():
    for d in ('manifest','qgis','gt','qa','ai_assisted/probability','ai_assisted/masks','ai_assisted/overlays'): (OUT/d).mkdir(parents=True,exist_ok=True)
    m=json.loads((SOURCE/'manifests/14A7_validation_manifest.json').read_text(encoding='utf-8'))
    pool=[p for p in m['candidates'] if p['eligible']=='YES'];assert len(pool)==14
    # Metadata-only selection: no prediction, metric, or gold label informs the choice.
    weights={'RESIDENTIAL':{'SMALL_BUILDINGS':4,'IRREGULAR_ROOFS':3,'ROAD':1},
             'DENSE':{'SMALL_BUILDINGS':3,'ADJACENT_ROOFS':2,'SHADOW':2},
             'INDUSTRIAL':{'COMPLEX_ROOFS':4,'VEHICLES_NOT_BUILDINGS':2,'BARE_SOIL':1,'SCENE_TYPE_PROVISIONAL':-2},
             'DIFFICULT':{'EDGE_BUILDINGS':3,'LOW_CONTRAST':2,'BARE_SOIL':2}}
    selected=[];ranking=[]
    for category,ww in weights.items():
        ranked=sorted([p for p in pool if p['scene_type']==category],key=lambda p:(-sum(ww.get(t,0) for t in p['difficulty_tags']),p['patch_id']))
        selected.append(ranked[0])
        ranking.extend(dict(patch_id=p['patch_id'],category=category,score=sum(ww.get(t,0) for t in p['difficulty_tags']),selected=p==ranked[0]) for p in ranked)
    ids={p['patch_id'] for p in selected};assert len(ids)==4
    lockpath=OUT/'manifest/GOLD_SET_LOCK.json'
    if lockpath.exists():
        old=json.loads(lockpath.read_text());assert set(old['patch_ids'])==ids,'Never silently change a locked gold set'
    # Check all protected TRAIN/calibration/benchmark footprints again, not just patch names.
    protected=json.loads((SOURCE/'qa/14A7A_protected_footprints.json').read_text())
    if isinstance(protected,dict):protected=protected.get('footprints',protected.get('protected',[]))
    rows=[]
    for p in selected:
        assert all(p[k]=='NO' for k in ('used_c3_train','used_c4_train','used_c5_train','used_c6_train','used_calibration','used_benchmark'))
        assert p['min_distance_existing_crops_m']>=20
        a=p['bounds_32637']
        for f in protected:
            b=f['bounds_32637']
            assert not(a[0]<b[2]+20 and a[2]>b[0]-20 and a[1]<b[3]+20 and a[3]>b[1]-20),'Protected geographic footprint overlap'
        assert sha(ROOT/p['rgb_path'])==p['sha256']
        rows.append(dict(patch_id=p['patch_id'],rgb_path=p['rgb_path'],scene_type=p['scene_type'],rgb_sha256=p['sha256'],
                         GOLD_SET_LOCKED='YES',role='FINAL_BENCHMARK_ONLY',training_allowed='NO',fine_tuning_allowed='NO',
                         pseudo_label_training_allowed='NO',threshold_calibration_allowed='NO',hyperparameter_tuning_allowed='NO',
                         manual_gt_status='PENDING',min_distance_historical_crops_m=p['min_distance_existing_crops_m']))
    csvwrite(OUT/'manifest/14A7_GOLD_SET_manifest.csv',rows)
    dump(lockpath,dict(GOLD_SET_LOCKED=True,patch_ids=[p['patch_id'] for p in selected],patches=selected,
         forbidden_uses=['training','fine_tuning','pseudo_label_training','threshold_calibration','hyperparameter_tuning'],
         source_manifest=str((SOURCE/'manifests/14A7_validation_manifest.json').relative_to(ROOT)),source_manifest_sha256=sha(SOURCE/'manifests/14A7_validation_manifest.json'),
         independence='SPATIALLY_DISJOINT_INTERNAL_SAME_ACQUISITION_NOT_EXTERNAL',
         enforcement='Manifest and offline pipeline guard; existing production/training code unchanged. All future consumers must apply the guard.'))
    others=[p for p in pool if p['patch_id'] not in ids]
    dump(OUT/'manifest/AI_ASSISTED_POOL.json',dict(role='AI_ASSISTED_CORRECTION_POOL_NOT_GROUND_TRUTH',model='MODEL_C6',patches=others,
         preannotation_is_gt=False,training_allowed_before_human_validation=False,no_full_manual_annotation_required=True))
    dump(OUT/'qa/selection_ranking.json',dict(weights=weights,tie_break='patch_id ascending',ranking=ranking,model_predictions_used=False,
         note='Scene classes are visual strata, not certified land use. Fixed selection before any gold annotation or model evaluation.'))
    # Local provenance audit only: a declaration in old documentation is not an independent licensing clearance.
    archive='backend/data/models/building/experimental/'
    models=[
      ('MODEL_A','U-Net / ResNet34','Kastela DOF5','building segmentation','640 / 256 effective (legacy config)','SOURCE_LICENSE_NOT_RECONFIRMED','backend/data/models/building/kastela-dof5/unet_best.pt','', 'torch;segmentation_models_pytorch','production_rgb_zscore_v1','LEGACY'),
      ('MODEL_C','DeepLabV3 / ResNet50','SpaceNet2','building segmentation','512','MIT source declaration',archive+'spacenet2-deeplab/best_deeplab.pth',archive+'spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx','onnxruntime','full-raster RGB minmax; sigmoid','PRODUCTION_UNCHANGED'),
      ('MODEL_C3','DeepLabV3 / ResNet50','MODEL_C + local seed manual GT','local building transfer learning','256 native training / 512 inference','INHERITS_C_SOURCE_TERMS_NOT_RECONFIRMED','backend/data/models/model_c3_experimental/best_model_c3_WEIGHTED_BCE_DICE.pth','backend/data/models/model_c3_experimental/model_c3.onnx','onnxruntime','per-RGB minmax; sigmoid','EXPERIMENTAL'),
      ('MODEL_C6','DeepLabV3 / ResNet50','MODEL_C3 + 4 local 14A5B patches','local building transfer learning','256 native training / 512 inference','INHERITS_C_SOURCE_TERMS_NOT_RECONFIRMED','backend/data/models/model_c6_experimental/best_model_c6.pth','','torch;torchvision','per-RGB minmax; sigmoid','EXPERIMENTAL_PREANNOTATION_ONLY'),
      ('MODEL_D','U-Net++ / EfficientNetB4','WHU Building','aerial building footprints','512','Apache-2.0 source declaration',archive+'whu_unetplusplus_effb4/model.pth',archive+'whu_unetplusplus_effb4/onnx/model.onnx','onnxruntime','RGB /255; 2-channel softmax building channel1','EXPERIMENTAL'),
      ('MODEL_F','SegFormer B0 / MiT-B0','SpaceNet2 Paris','satellite building footprints','512 input /128 logits upsampled','MIT source declaration',archive+'benchmark_13Q0B/model_f_segformer/best_segformer.pth','','torch;transformers','RGB /255; sigmoid; bilinear resize logits','EXPERIMENTAL_RUNTIME_TO_REVALIDATE'),
      ('MODEL_H','U-Net / ResNet34 3-channel instance head','HOTOSM VHR','building instance masks','512','AGPL-3.0 historical declaration; licensing review before integration',archive+'benchmark_13L/hotosm_unet_instance/unet_bldg_instance.pth','','torch;segmentation_models_pytorch','channel semantics and preprocessing must be rechecked against archived runner','EXPERIMENTAL_LICENSE_AND_RUNTIME_GATE'),
      ('MODEL_G','DINOv3-S/16 + UPerNet','HOTOSM VHR','building segmentation','256 input / stride192','LICENSE_NOT_RECONFIRMED', '',archive+'benchmark_13Q0B/model_g_dinov3s/model.onnx','onnxruntime','3 logits; building channel unresolved in historical reports','BLOCKED_OUTPUT_SEMANTICS'),
      ('MODEL_F2','SegFormer B0 / MiT-B0','MODEL_F + 13R1B pseudo-label transfer learning','industrial roofs','512','INHERITS_F_SOURCE_TERMS_NOT_RECONFIRMED',archive+'model_f2_industrial_finetuned/best_model_f2.pth','','torch;transformers','see 13R1B training runner; not interchangeable with MODEL_F','EXPERIMENTAL'),
    ]
    for v in (2,4,5):
        models.append((f'MODEL_C{v}','DeepLabV3 / ResNet50','C-family + local GT / balanced crops','local building transfer learning','256 train /512 inference','INHERITS_C_SOURCE_TERMS_NOT_RECONFIRMED',f'backend/data/models/model_c{v}_experimental/'+('best_model_c2.pth' if v==2 else f'final_model_c{v}.pth'),f'backend/data/models/model_c{v}_experimental/model_c{v}.onnx' if v!=5 else '', 'torch;torchvision','variant-specific config; no new run','HISTORICAL_EXPERIMENTAL'))
    audit=[]
    for mid,arch,data,special,size,lic,weight,onnx,deps,pre,status in models:
        artifacts=[dict(path=p,exists=(ROOT/p).is_file(),bytes=(ROOT/p).stat().st_size if (ROOT/p).is_file() else None,sha256=sha(ROOT/p) if (ROOT/p).is_file() else None) for p in (weight,onnx) if p]
        missing=[dep for dep in deps.split(';') if importlib.util.find_spec(dep) is None]
        audit.append(dict(model_id=mid,architecture=arch,training_dataset=data,building_specialization=special,input_resolution=size,cpu_compatibility='YES_ARCHITECTURALLY',
            license=lic,local_weights_available=bool(weight and (ROOT/weight).is_file()),weights_path=weight,onnx_available=bool(onnx and (ROOT/onnx).is_file()),onnx_path=onnx,
            expected_speed='NOT_MEASURED_IN_THIS_STEP; compare cold-load and seconds/512 tile in 14A8',preprocessing=pre,missing_runtime_modules=';'.join(missing),
            runtime_status='MISSING_MODULES' if missing else 'MODULES_FOUND_STRICT_LOAD_PENDING',status=status,artifacts=artifacts))
    dump(OUT/'qa/local_model_artifacts.json',dict(python=sys.executable,models=audit,no_model_execution_in_audit=True,license_source='Local adapters and historical reports only; UNKNOWN is not license approval'))
    csvwrite(OUT/'manifest/14A8_model_candidates.csv',[{k:v for k,v in a.items() if k!='artifacts'} for a in audit])
    print(json.dumps(dict(gold=[p['patch_id'] for p in selected],ai_pool=len(others),models_audited=len(audit)),indent=2))

def preannotate():
    import numpy as np,rasterio,torch
    from rasterio.features import shapes
    from PIL import Image
    import rasterio as rio
    os.environ['PROJ_DATA']=str(Path(rio.__file__).parent/'proj_data');os.environ['PROJ_LIB']=os.environ['PROJ_DATA']
    # The installed torchvision has its native operators. A temporary Library
    # registration here crashes during Python shutdown (14A.7B lifecycle audit).
    # Use the normal module-owned operator lifetime; no model math changes.
    from torchvision.models.segmentation import deeplabv3_resnet50
    from torchvision.models.segmentation.deeplabv3 import DeepLabHead
    pool=json.loads((OUT/'manifest/AI_ASSISTED_POOL.json').read_text())['patches']
    gold=json.loads((OUT/'manifest/GOLD_SET_LOCK.json').read_text())['patches']
    assert len(pool)==10 and not ({p['patch_id'] for p in pool}&{p['patch_id'] for p in gold})
    for p in pool:
        a=p['bounds_32637']
        for g in gold:
            b=g['bounds_32637'];assert not (a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]),'Gold spatial guard'
    ck=ROOT/'backend/data/models/model_c6_experimental/best_model_c6.pth';before=sha(ck)
    torch.set_num_threads(4);start=time.perf_counter()
    model=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);model.classifier=DeepLabHead(2048,1)
    model.load_state_dict(torch.load(ck,map_location='cpu',weights_only=True)['state_dict'],strict=True);model.eval();load=time.perf_counter()-start
    rows=[];features=[]
    for p in pool:
        pid=p['patch_id'];path=ROOT/p['rgb_path'];assert sha(path)==p['sha256']
        with rasterio.open(path) as ds:rgb=ds.read((1,2,3));profile=ds.profile.copy();transform=ds.transform
        x=rgb.astype('float32');lo,hi=float(x.min()),float(x.max());x=(x-lo)/max(1e-6,hi-lo)
        t=time.perf_counter()
        with torch.inference_mode():prob=torch.sigmoid(model(torch.from_numpy(x[None]))['out'][0,0]).numpy()
        elapsed=time.perf_counter()-t;binary=(prob>=.30).astype('uint8');filtered=np.zeros_like(binary)
        # Polygonize the exact native grid; area in pixel count, no smoothing or model tuning.
        count=0
        for geo,val in shapes(binary,mask=binary.astype(bool),transform=transform,connectivity=4):
            # Native raster cells have constant planar coordinate area; determinant converts polygon area to pixels.
            def ringarea(r):
                r=[(~transform)*(x,y) for x,y in r]
                return abs(sum(r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1] for i in range(len(r)-1)))/2
            area=ringarea(geo['coordinates'][0])-sum(ringarea(r) for r in geo['coordinates'][1:])
            if area<478.5:continue
            count+=1;features.append(dict(type='Feature',geometry=geo,properties=dict(patch_id=pid,proposal_id=f'{pid}_C6_{count:03d}',source='MODEL_C6_PREDICTION',review_status='UNREVIEWED',is_ground_truth=0)))
        from rasterio.features import rasterize
        geos=[(f['geometry'],1) for f in features if f['properties']['patch_id']==pid]
        if geos:filtered=rasterize(geos,out_shape=(512,512),transform=transform,dtype='uint8')
        for kind,arr,dtype in [('probability',prob,'float32'),('masks',filtered,'uint8')]:
            dst=OUT/'ai_assisted'/kind/(pid+'.tif');pr=profile.copy();pr.update(driver='GTiff',count=1,dtype=dtype,nodata=None,compress='deflate')
            with rasterio.open(dst,'w',**pr) as ds:ds.write(arr.astype(dtype),1)
        rgba=np.moveaxis(rgb,0,-1).astype('float32');rgba[filtered.astype(bool)]=.6*rgba[filtered.astype(bool)]+.4*np.array([180,0,255]);Image.fromarray(rgba.astype('uint8')).save(OUT/'ai_assisted/overlays'/(pid+'.png'))
        rows.append(dict(patch_id=pid,inference_seconds=elapsed,proposals=count,threshold=.30,minimum_component_pixels=479,rgb_sha256=p['sha256'],mask_sha256=sha(OUT/'ai_assisted/masks'/(pid+'.tif'))))
        print(pid,'proposals',count,'seconds',round(elapsed,2),flush=True)
    dump(OUT/'ai_assisted/AI_PREANNOTATION.geojson',dict(type='FeatureCollection',name='AI_PREANNOTATION_NOT_GROUND_TRUTH',crs={'type':'name','properties':{'name':'EPSG:4326'}},features=features))
    assert sha(ck)==before
    dump(OUT/'qa/C6_preannotation_execution.json',dict(checkpoint_sha256=before,checkpoint_unchanged=True,strict_load='PASS',engine='PYTORCH_CPU',threads=4,model_load_seconds=load,patches=rows,
        gold_inference_count=0,gt_features_written=0,training_started=False,normalization='per-patch RGB minmax as 14A6C',postprocessing='sigmoid >=0.30; 4-connected min479 pixels; no smoothing',
        caveat='479px filter can remove small buildings. Proposals are incomplete and require human deletion/edit/addition. Not GT, no quality metrics.'))

if __name__=='__main__':preannotate() if '--preannotate' in sys.argv else prepare()
