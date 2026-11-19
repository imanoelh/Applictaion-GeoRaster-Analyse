"""Prepare RGB-only annotation candidates. No ML imports, labels or inference."""
from __future__ import annotations
import csv, hashlib, importlib.util, json, os, shutil
from pathlib import Path
from collections import Counter

_proj=Path(importlib.util.find_spec('rasterio').origin).parent/'proj_data'
os.environ['PROJ_DATA']=str(_proj);os.environ['PROJ_LIB']=str(_proj)
import numpy as np
import rasterio
from rasterio.windows import Window, bounds as window_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping
from shapely.ops import unary_union
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
AUDIT=BASE/'qa/14A7_extended_validation'
OUT=BASE/'14A7_validation_expansion'
SOURCE=ROOT/'backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif'

def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save_json(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def save_csv(p,rows,fields=None):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def protections():
    inv=json.loads((AUDIT/'14A7_source_inventory.json').read_text())
    spatial={r['path']:r for r in json.loads((AUDIT/'14A7_spatial_sources.json').read_text())}
    blocks=[]
    for r in inv['rasters']:
        path=r['path'].lower()
        if r.get('bands',0)<3 or max(r.get('width',999999),r.get('height',999999))>1024:continue
        if any(s in path for s in ('/images/','/rgb/','/patches/','source_rgb.tif','/raster_cache/')):
            s=spatial.get(r['path'])
            if s and not s.get('error'):blocks.append(dict(source=r['path'],reason='EXISTING_CROP_OR_BENCHMARK_RGB',bounds_32637=s['bounds_32637']))
    # Also protect declared historical catalog extents where its TIFF metadata disagree.
    catalog=json.loads((ROOT/'test-data/building-ground-truth/patch_catalog.json').read_text())
    for year in catalog['dates'].values():
        for r in year['patches']:
            b=r['bounds'];blocks.append(dict(source=r['patch_id'],reason='DECLARED_HISTORICAL_CROP_BOUNDS',bounds_32637=[b['left'],b['bottom'],b['right'],b['top']]))
    union=unary_union([box(*b['bounds_32637']) for b in blocks])
    save_json(OUT/'qa/14A7A_protected_footprints.json',dict(buffer_m=20,footprints=blocks,policy='Exclude every existing small RGB crop, including other-model TRAIN and historical benchmark ROIs; shared full orthophoto parent is recorded, not treated as a disjoint acquisition.'))
    return union,blocks

def screen():
    for d in ('rgb','gt_vector','gt_masks','qa','manifests','qgis'):(OUT/d).mkdir(parents=True,exist_ok=True)
    protected,blocks=protections();safe=protected.buffer(20)
    accepted=[];rejected=[]
    with rasterio.open(SOURCE) as ds:
        for row in range(0,ds.height-511,1024):
            for col in range(0,ds.width-511,1024):
                win=Window(col,row,512,512);b=list(window_bounds(win,ds.transform));utm=list(transform_bounds(ds.crs,'EPSG:32637',*b,densify_pts=21));geom=box(*utm)
                rec=dict(key=f'R{row:05d}_C{col:05d}',row=row,col=col,source=rel(SOURCE),bounds_native=b,bounds_32637=utm,
                         same_full_scene_parent_as_13R=True,used_existing_crop_parent=False)
                if geom.intersects(safe):
                    rejected.append(dict(**rec,reason='SPATIAL_OVERLAP_OR_WITHIN_20M_OF_EXISTING_CROP'));continue
                a=ds.read((1,2,3),window=win)
                if a.shape!=(3,512,512) or np.mean(np.any(a!=0,axis=0))<.98:
                    rejected.append(dict(**rec,reason='NODATA_OR_INCOMPLETE_RGB'));continue
                rec.update(index=len(accepted)+1,mean=float(a.mean()),std=float(a.std()),pixel_sha256=hashlib.sha256(a.tobytes()).hexdigest(),native_crs=ds.crs.to_wkt())
                accepted.append(rec)
        tiles=Image.new('RGB',(7*175,((len(accepted)+6)//7)*198),'white');draw=ImageDraw.Draw(tiles)
        for i,r in enumerate(accepted):
            a=ds.read((1,2,3),window=Window(r['col'],r['row'],512,512));im=Image.fromarray(a.transpose(1,2,0)).resize((175,175))
            x=(i%7)*175;y=(i//7)*198;tiles.paste(im,(x,y));draw.text((x+3,y+177),f"{r['index']:02d} {r['key']}",fill='black')
        tiles.save(OUT/'qa/14A7A_RGB_scene_screening.png')
    save_json(OUT/'qa/14A7A_screening_candidates.json',dict(source=rel(SOURCE),selection_basis='RGB visual inspection only; no model outputs',accepted=accepted,rejected=rejected))
    print(json.dumps(dict(accepted=len(accepted),rejected=len(rejected),protected_footprints=len(blocks),contact_sheet=rel(OUT/'qa/14A7A_RGB_scene_screening.png')),indent=2))

def materialize():
    selected=json.loads((OUT/'manifests/14A7A_visual_selection.json').read_text())
    pool=json.loads((OUT/'qa/14A7A_screening_candidates.json').read_text())['accepted']
    protected,blocks=protections();records=[];polys=[]
    with rasterio.open(SOURCE) as ds:
        for n,s in enumerate(selected,1):
            r=next(r for r in pool if r['index']==s['index']);win=Window(r['col'],r['row'],512,512);g=box(*r['bounds_32637'])
            if g.intersects(protected.buffer(20)):raise RuntimeError('Spatial audit failed')
            if any(g.intersection(p).area>.01 for p in polys):raise RuntimeError('Selected candidates overlap')
            polys.append(g)
            pid=f"14A7_VAL_2025_{s['scene_type']}_{n:02d}";target=OUT/'rgb'/f'{pid}.tif'
            a=ds.read((1,2,3),window=win);profile=ds.profile.copy();profile.update(driver='GTiff',height=512,width=512,count=3,transform=ds.window_transform(win),compress='deflate')
            if target.exists():
                with rasterio.open(target) as old:
                    if not np.array_equal(old.read((1,2,3)),a):raise RuntimeError('Existing RGB differs; do not overwrite')
            else:
                with rasterio.open(target,'w',**profile) as dst:dst.write(a)
            with rasterio.open(target) as checked:
                if checked.transform!=ds.window_transform(win) or checked.crs!=ds.crs or not np.array_equal(checked.read((1,2,3)),a):raise RuntimeError('Copy QA failed')
            rec=dict(patch_id=pid,rgb_path=rel(target),scene_type=s['scene_type'],year=2025,origin=rel(SOURCE),source_window=dict(row=r['row'],col=r['col'],height=512,width=512),
                     used_c3_train='NO',used_c4_train='NO',used_c5_train='NO',used_c6_train='NO',used_calibration='NO',used_benchmark='NO',manual_gt='NOT_ANNOTATED',qa_status='RGB_SPATIAL_QA_PASS',eligible='YES',
                     bounds_native=r['bounds_native'],bounds_32637=r['bounds_32637'],native_crs=ds.crs.to_wkt(),sha256=sha(target),pixel_sha256=r['pixel_sha256'],
                     rgb_matches_parent_window=True,min_distance_existing_crops_m=g.distance(protected),scene_observation=s['observation'],difficulty_tags=s.get('tags',[]),
                     same_parent_orthophoto_as_historical_data=True,split='VALIDATION_LOCKED_FOR_C3_C6',width=512,height=512,bands=3)
            records.append(rec)
    base=list(csv.DictReader((AUDIT/'14A7_additional_gt_required.csv').open(encoding='utf-8-sig')))
    base_records=[]
    r13_split=json.loads((ROOT/'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R/balanced_split_13R1B_manifest.json').read_text())
    f2train={r['patch_id'] for r in r13_split['train']}
    for r in base:
        p=ROOT/r['rgb']
        with rasterio.open(p) as ds:
            a=ds.read((1,2,3));crs=ds.crs.to_wkt();tr=list(ds.transform);shape=list(a.shape)
        f2=r['patch_id'] in f2train
        reason='OTHER_MODEL_F2_TRAIN_IN_13R1B_CORRECTED_MANIFEST' if f2 else 'SPATIAL_REUSE_OF_13L3_BENCHMARK_ROI'
        base_records.append(dict(patch_id=r['patch_id'],rgb_path=r['rgb'],scene_type='INDUSTRIAL',year=2025 if f2 else int(r['patch_id'].split('_')[1]),origin=r['rgb'],
             used_c3_train='NO',used_c4_train='NO',used_c5_train='NO',used_c6_train='NO',used_calibration='NO',used_benchmark='YES' if not f2 else 'NO',
             manual_gt='NOT_ANNOTATED',qa_status='EXCLUDED_'+reason,eligible='NO',other_model_f2_train=f2,source_split=r['existing_split'],
             bounds_32637=json.loads(r['bounds_32637']),native_crs=crs,transform=tr,shape=shape,sha256=sha(p),pixel_sha256=hashlib.sha256(a.tobytes()).hexdigest(),reason=reason))
    allrows=base_records+records
    required=['patch_id','rgb_path','scene_type','year','origin','used_c3_train','used_c4_train','used_c5_train','used_c6_train','used_calibration','used_benchmark','manual_gt','qa_status','eligible']
    save_csv(OUT/'manifests/14A7_validation_candidates.csv',[{k:r[k] for k in required} for r in allrows],required)
    save_json(OUT/'manifests/14A7_validation_manifest.json',dict(base_val_found=8,base_val_eligible=0,candidates=allrows,
         eligible_count=len(records),scene_counts=dict(Counter(r['scene_type'] for r in records)),train_leakage=0,gt_features=0,
         policy='New windows never overlap known existing crop footprints (20m minimum margin). Same acquisition/large RGB parent remains shared; this is spatial internal validation, not acquisition-independent external generalization.',
         source_sha256=sha(SOURCE),no_inference=True,no_training=True,no_gt_masks=True,originals_modified=False))
    # Input/reference coverage; do not infer TRAIN from a mere textual occurrence of a patch id.
    evidence=[]
    for root in [ROOT/'backend/data/fine_tuning/buildings',ROOT/'backend/data/models',ROOT/'test-data']:
        for p in root.rglob('*.json'):
            if OUT in p.parents or any(s in p.parts for s in ('site-packages','geoai_package','hf_home','orthogonalization_env')):continue
            if any(s in p.name.lower() for s in ('manifest','training_config','final_config','split','reference')):
                evidence.append(dict(path=rel(p),sha256=sha(p),bytes=p.stat().st_size))
    save_json(OUT/'qa/14A7A_historical_manifest_coverage.json',dict(manifests=evidence,training_code=['scripts/run_14A3_model_c2_finetuning.py','scripts/run_14A3B_model_c3_highres_revision.py','scripts/train_model_c4_experimental.py','scripts/train_model_c5_balanced.py','scripts/train_model_c6_14A6.py'],
        calibration_code='scripts/run_14A3C_model_c3_calibration.py',base_evidence=['test-data/diagnostics/13L3/*/source_rgb.tif','backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R/balanced_split_13R1B_manifest.json'],
        note='Footprints use actual georeferenced image sources, not inconsistent repeated bounds strings in old 13R manifests. All existing small RGB crops excluded from new selection.'))
    # Copy-free context/patch footprints, never building annotations.
    save_json(OUT/'qa/14A7A_patch_footprints.geojson',dict(type='FeatureCollection',name='validation_patch_bounds_NOT_buildings',crs={'type':'name','properties':{'name':'EPSG:32637'}},
         features=[dict(type='Feature',geometry=mapping(box(*r['bounds_32637'])),properties=dict(patch_id=r['patch_id'],scene_type=r['scene_type'])) for r in records]))
    print(json.dumps(dict(eligible=len(records),base_found=8,base_rejected=8,scene_counts=dict(Counter(r['scene_type'] for r in records))),indent=2))

if __name__=='__main__':
    import sys
    materialize() if '--materialize' in sys.argv else screen()
