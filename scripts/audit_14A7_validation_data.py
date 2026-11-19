"""Read-only provenance and spatial leakage audit; never loads a model for inference."""
from __future__ import annotations
import csv
import hashlib
import json
import re
import sqlite3
import struct
import sys
import os
import importlib.util
from collections import Counter
from pathlib import Path

# Use Rasterio's matching PROJ database for this process only (system PostGIS differs).
_proj = Path(importlib.util.find_spec('rasterio').origin).parent / 'proj_data'
if (_proj/'proj.db').exists():
    os.environ['PROJ_DATA'] = str(_proj)
    os.environ['PROJ_LIB'] = str(_proj)
import rasterio
from rasterio.warp import transform_bounds
from shapely import wkb
from shapely.geometry import shape
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
EXP = BASE / '14A2_expansion'
OUT = BASE / 'qa/14A7_extended_validation'
ROOTS = [ROOT/'backend/data/fine_tuning/buildings', ROOT/'test-data', ROOT/'backend/data/ground_truth']
SEED = ['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']
C6_TRAIN = ['14A2_2024_06','14A2_2024_10','14A2_2025_02','14A2_2025_06']
HIST = ['14A_001_residential','14A_003_dense_urban']
TARGET = ['14A2_2024_11','14A2_2025_12','14A2_2024_14','14A2_2025_15']

def rel(p):
    return str(p.relative_to(ROOT)).replace('\\','/')

def write_csv(name, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def bbox_overlap(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))

def patch_id(name):
    patterns = [r'14A2_20\d{2}_\d{2}', r'14A_\d{3}_[a-z_]+', r'GT_20\d{2}_[a-z]+_\d{2}', r'13R_(?:industrial|residential|urban)_\d+_\d+_\d+']
    for pattern in patterns:
        m = re.search(pattern, name)
        if m:
            return re.sub(r'(_ground_truth|_v2)$', '', m.group())
    return name

def raster_record(p):
    with rasterio.open(p) as d:
        return dict(path=rel(p), patch_id=patch_id(p.stem), bands=d.count, width=d.width, height=d.height,
                    crs=d.crs.to_wkt() if d.crs else None, epsg=d.crs.to_epsg() if d.crs else None,
                    bounds=list(d.bounds), transform=list(d.transform), dtype=list(d.dtypes), status='READABLE')

def gpkg_geom(blob):
    if blob is None: return None
    if blob[:2] != b'GP': raise ValueError('Missing GeoPackage magic')
    flags = blob[3]
    env_bytes = {0:0,1:32,2:48,3:48,4:64}.get((flags >> 1) & 7)
    if env_bytes is None: raise ValueError('Invalid GeoPackage envelope code')
    return wkb.loads(blob[8+env_bytes:])

def quote(s): return '"' + s.replace('"','""') + '"'

def read_only_database(p):
    wal=Path(str(p)+'-wal')
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError('Active/nonempty SQLite WAL: persisted source must be stabilized before immutable audit')
    return sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)

def inspect_gpkg(p):
    results = []
    try:
        with read_only_database(p) as c:
            tables = c.execute('SELECT table_name,column_name,geometry_type_name,srs_id FROM gpkg_geometry_columns').fetchall()
            for table,col,typ,srs in tables:
                keys = [x[1] for x in c.execute('PRAGMA table_info('+quote(table)+')')]
                rows = c.execute('SELECT * FROM '+quote(table)).fetchall()
                errors = []; geoms = []; statuses = Counter(); sources = Counter(); duplicates=0; seen=set()
                for row in rows:
                    attrs=dict(zip(keys,row)); blob=attrs.get(col)
                    try:
                        g=gpkg_geom(blob)
                        if g is None or g.is_empty: errors.append({'id':attrs.get('building_id',attrs.get('fid')),'error':'EMPTY'})
                        elif not g.is_valid or g.area<=0 or g.geom_type not in ('Polygon','MultiPolygon'):
                            errors.append({'id':attrs.get('building_id',attrs.get('fid')),'error':explain_validity(g),'type':g.geom_type})
                        else: geoms.append(g)
                        if g is not None:
                            if g.wkb in seen: duplicates+=1
                            seen.add(g.wkb)
                    except Exception as e: errors.append({'id':attrs.get('fid'),'error':str(e)})
                    statuses[str((attrs.get('annotation_status'),attrs.get('review_status')))]+=1
                    sources[str(attrs.get('annotation_source',attrs.get('label_source')))]+=1
                results.append(dict(path=rel(p), layer=table, patch_id=patch_id(table), geometry_type=typ, srs_id=srs,
                                    feature_count=len(rows), valid_polygon_count=len(geoms), errors=errors, exact_duplicates=duplicates,
                                    statuses=dict(statuses), sources=dict(sources), bounds=[min(g.bounds[0] for g in geoms),min(g.bounds[1] for g in geoms),max(g.bounds[2] for g in geoms),max(g.bounds[3] for g in geoms)] if geoms else None))
    except Exception as e:
        results.append(dict(path=rel(p), layer=None, feature_count=None, error=str(e)))
    return results

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inventory=[]; rasters=[]; vectors=[]; json_vectors=[]
    reuse = '--reuse-inventory' in sys.argv
    if reuse:
        cached=json.loads((OUT/'14A7_source_inventory.json').read_text(encoding='utf-8'))
        rasters=cached['rasters']; vectors=cached['geopackage_layers']; json_vectors=cached['geojson_layers']
        inventory=list(csv.DictReader((OUT/'14A7_file_inventory.csv').open(encoding='utf-8-sig')))
    for root in ([] if reuse else ROOTS):
        for p in sorted(root.rglob('*')):
            if not p.is_file() or OUT in p.parents: continue
            if p.suffix.lower() not in ('.tif','.gpkg','.geojson','.json','.csv','.png','.jpg','.qgz','.qgs'): continue
            path=rel(p); lower=path.lower()
            role='metadata_or_report'
            if p.suffix.lower() in ('.qgz','.qgs'): role='qgis_project'
            elif p.suffix.lower()=='.gpkg': role='vector_container'
            elif 'pseudo' in lower or any(s in lower for s in ('/model_c/','/model_d/','/model_f/','whu_orthogonalized','/prediction')): role='prediction_or_pseudo_label'
            elif any(s in lower for s in ('/rgb/','/images/','/patches/')): role='rgb_or_source_image'
            elif 'mask' in lower: role='mask_requires_provenance'
            elif 'annotation' in lower: role='annotation_requires_provenance'
            elif 'manifest' in lower: role='manifest'
            inventory.append(dict(path=path,bytes=p.stat().st_size,extension=p.suffix.lower(),role=role))
            if p.suffix.lower()=='.tif':
                try:
                    r=raster_record(p);r['role']=role;rasters.append(r)
                except Exception as e:rasters.append(dict(path=path,status='FAILED',error=str(e)))
            elif p.suffix.lower()=='.gpkg': vectors.extend(inspect_gpkg(p))
            elif p.suffix.lower()=='.geojson':
                try:
                    data=json.loads(p.read_text(encoding='utf-8-sig'));fs=data.get('features',[])
                    json_vectors.append(dict(path=path,patch_id=patch_id(p.stem),feature_count=len(fs),role=role,
                        properties_sample=[f.get('properties') for f in fs[:2]]))
                except Exception as e:json_vectors.append(dict(path=path,error=str(e)))
    write_csv('14A7_file_inventory.csv',inventory)
    (OUT/'14A7_source_inventory.json').write_text(json.dumps(dict(rasters=rasters,geopackage_layers=vectors,geojson_layers=json_vectors),indent=2),encoding='utf-8')
    source={r['path']:r for r in rasters if r.get('status')=='READABLE'}
    analysis_crs=source[rel(EXP/'train/rgb'/f'{SEED[0]}.tif')]['crs']
    spatial=[]
    for r in source.values():
        original=list(r['bounds'])
        r['source_bounds']=original
        if r.get('crs'):
            r['bounds']=list(transform_bounds(r['crs'],analysis_crs,*original,densify_pts=21))
        else:
            r['spatial_error']='CRS_MISSING'
        spatial.append(dict(path=r['path'],source_crs=r.get('crs'),source_bounds=original,bounds_32637=r['bounds'],error=r.get('spatial_error')))
    (OUT/'14A7_spatial_sources.json').write_text(json.dumps(spatial,indent=2),encoding='utf-8')
    train_bounds={pid:source[rel(EXP/'train/rgb'/f'{pid}.tif')]['bounds'] for pid in SEED+C6_TRAIN}
    # Direct C6 updates plus inherited C3 training are both prohibited validation sources.
    protected={pid:source[rel(EXP/'train/rgb'/f'{pid}.tif')]['bounds'] for pid in sorted(set(SEED+C6_TRAIN+TARGET))}
    split=json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches']
    primary=[]
    for row in split:
        pid=row['patch_id']; p=EXP/row['split']/'rgb'/f'{pid}.tif'
        if rel(p) not in source: continue
        primary.append((pid,source[rel(p)],row['split'],row['scene_type']))
    legacy=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test'
    for p in sorted((legacy/'images').glob('*.tif')):
        primary.append((p.stem,source[rel(p)],'HISTORICAL_TEST_13M',p.stem.split('_')[2]))
    for p in sorted((BASE/'images').glob('*.tif')):
        if '_v2' not in p.stem:primary.append((p.stem,source[rel(p)],'HISTORICAL_14A' if p.stem in HIST else 'UNASSIGNED',p.stem))
    for p in sorted((ROOT/'test-data/building-ground-truth').glob('*/patches/*.tif')):
        if p.stem not in {x[0] for x in primary}:primary.append((p.stem,source[rel(p)],'HISTORICAL_CATALOG',p.stem.split('_')[2]))
    r13=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R'
    for rr in json.loads((r13/'training_ready_manifest.json').read_text()):
        matches=[r for r in rasters if r.get('patch_id')==rr['patch_id'] and r.get('bands',0)>=3]
        if matches:primary.append((rr['patch_id'],matches[0],rr['split'],rr['scene_type']))
    hist_bounds={pid:source[rel(BASE/'images'/f'{pid}.tif')]['bounds'] for pid in HIST}
    audit=[]
    for pid,r,split_name,scene in primary:
        overlaps={k:round(bbox_overlap(r['bounds'],b)/((r['bounds'][2]-r['bounds'][0])*(r['bounds'][3]-r['bounds'][1])),6) for k,b in protected.items() if bbox_overlap(r['bounds'],b)>0.01}
        v=[v for v in vectors if v.get('patch_id')==pid and v.get('feature_count')]
        rb=r['bounds']
        valid=[v for v in v if v.get('valid_polygon_count')==v['feature_count'] and not v.get('errors') and not v.get('exact_duplicates')
               and v.get('srs_id')==32637 and v.get('bounds') and all((v['bounds'][0]>=rb[0]-1e-7,v['bounds'][1]>=rb[1]-1e-7,v['bounds'][2]<=rb[2]+1e-7,v['bounds'][3]<=rb[3]+1e-7))]
        approved=[x for x in valid if (pid in SEED and '14A2B2_seed_ground_truth_FIXED_CANDIDATE' in x['path'])
                  or (pid in HIST and 'ground_truth_layers_14A1D3_CANDIDATE' in x['path'])
                  or (x.get('statuses') and all(('VALIDATED' in k and ('REVIEWED' in k or "None, 'VALIDATED'" in k)) for k in x['statuses']))]
        historical_overlaps={k:round(bbox_overlap(r['bounds'],b)/((rb[2]-rb[0])*(rb[3]-rb[1])),6) for k,b in hist_bounds.items() if bbox_overlap(r['bounds'],b)>0.01}
        used_c3=pid in SEED;used_c6=pid in C6_TRAIN;cal=pid in SEED;historic=pid in HIST
        reasons=[]
        if split_name.lower()=='train':reasons.append('ORIGINAL_TRAIN_SPLIT_NOT_VALIDATION')
        if used_c3:reasons.append('C3_TRAIN_AND_INHERITED_C6_TRAIN')
        if used_c6:reasons.append('C6_DIRECT_TRAIN')
        if cal:reasons.append('C3_CALIBRATION')
        if historic:reasons.append('14A6C_HISTORICAL_CONTROL_ONLY')
        elif historical_overlaps:reasons.append('SPATIAL_ALIAS_OF_14A6C_HISTORICAL_REGION')
        if overlaps and not (used_c3 or used_c6):reasons.append('SPATIAL_OVERLAP_WITH_TRAIN_OR_PREVIOUS_TARGETED_GT')
        if pid in TARGET:reasons.append('PREVIOUS_TARGETED_GT_NOT_NEW_INDEPENDENT_VALIDATION')
        if pid.startswith('13R_'):reasons.append('MODEL_C_PSEUDO_LABEL_NOT_HUMAN_GT')
        if not valid:reasons.append('NO_TECHNICALLY_VALID_VECTOR_GT')
        if not approved:reasons.append('NO_APPROVED_COMPLETE_MANUAL_GT')
        # Repaired 13M data are explicitly approximate, not newly approved high-precision GT.
        if any('evaluation_ground_truth' in v['path'] for v in valid):reasons.append('13M_APPROXIMATE_REPAIRED_GT_NOT_HIGH_PRECISION_APPROVAL')
        audit.append(dict(PATCH=pid,SPLIT=split_name,SCENE_TYPE=scene,USED_C3_TRAIN='YES' if used_c3 else 'NO',USED_C6_TRAIN='YES' if used_c6 else 'NO',
            INHERITED_C6_TRAIN='YES' if used_c3 else 'NO',USED_CALIBRATION='YES' if cal else 'NO',USED_14A6C='YES' if historic else 'NO',
            USED_C4_C5_OR_TARGETED='YES' if pid in SEED+TARGET else 'NO',VALID_GT='YES_APPROVED' if approved else ('TECHNICAL_ONLY' if valid else 'NO'),ELIGIBLE_14A7='NO' if reasons else 'YES',
            SPATIAL_OVERLAPS=json.dumps(overlaps),HISTORICAL_REGION_OVERLAPS=json.dumps(historical_overlaps),GT_LAYERS=json.dumps([{'path':x['path'],'layer':x['layer'],'count':x['feature_count'],'valid':x['valid_polygon_count']} for x in v]),
            RGB=r['path'],SOURCE_CRS=r.get('crs'),SOURCE_BOUNDS=json.dumps(r.get('source_bounds')),BOUNDS=json.dumps(r['bounds']),REASON=';'.join(reasons)))
    write_csv('14A7_data_leakage_audit.csv',audit)
    summary=dict(status='AUDIT_COMPLETED_NO_INFERENCE',files=len(inventory),raster_count=len(rasters),geopackage_layers=len(vectors),geojson_layers=len(json_vectors),
                 candidates=len(audit),eligible=sum(x['ELIGIBLE_14A7']=='YES' for x in audit),train_leakage_executed=0,checkpoints={})
    for name,p in [('MODEL_C3',ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx'),('MODEL_C6',ROOT/'backend/data/models/model_c6_experimental/best_model_c6.pth')]:
        summary['checkpoints'][name]=dict(path=rel(p),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    (OUT/'14A7_inventory_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print('Nonempty vector provenance is recorded in 14A7_data_leakage_audit.csv')

if __name__=='__main__':main()
