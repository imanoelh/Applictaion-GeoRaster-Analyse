"""Repair the authorized GOLD copy only; preserve source and every object ID."""
from pathlib import Path
import sqlite3,json,hashlib,csv,tempfile
import numpy as np
from osgeo import ogr,gdal
from shapely import wkb,make_valid
from shapely.geometry import Polygon,Point
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set'
SRC=OUT/'gt/14A7_GOLD_manual_gt.gpkg';DST=OUT/'gt/14A7_GOLD_SET_GT_FIXED.gpkg';QA=OUT/'qa/14A7B_gold'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(path):
    ds=ogr.Open(str(path),0);layer=ds.GetLayerByName('buildings_gt');rows={f.GetFID():dict(attrs=f.items(),wkb=bytes(f.GetGeometryRef().ExportToWkb())) for f in layer};ds=None;return rows
def digest(rows):return hashlib.sha256(json.dumps({str(fid):{'attrs':r['attrs'],'wkb':r['wkb'].hex()} for fid,r in sorted(rows.items())},sort_keys=True).encode()).hexdigest()
def main():
    if DST.exists():raise RuntimeError('Existing corrected GT must never be overwritten automatically')
    original=read(SRC);assert len(original)==165
    original_sha=sha(SRC);logical=digest(original);wal=Path(str(SRC)+'-wal');wal_sha=sha(wal) if wal.exists() else None
    patches=json.loads((OUT/'manifest/GOLD_SET_LOCK.json').read_text())['patches'];footprints={}
    for p in patches:
        d=gdal.Open(str(ROOT/p['rgb_path']));gt=d.GetGeoTransform();tx=Transformer.from_crs(d.GetProjection(),'EPSG:32637',always_xy=True);border=[]
        for a,b in [((0,0),(512,0)),((512,0),(512,512)),((512,512),(0,512)),((0,512),(0,0))]:
            for z in np.linspace(0,1,65)[:-1]:
                x=a[0]+z*(b[0]-a[0]);y=a[1]+z*(b[1]-a[1]);border.append(tx.transform(gt[0]+x*gt[1]+y*gt[2],gt[3]+x*gt[4]+y*gt[5]))
        footprints[p['patch_id']]=Polygon(border);d=None
    # SQLite backup includes committed WAL records; copying just the main file would lose the 165 features.
    with tempfile.TemporaryDirectory(prefix='14A7B_snapshot_') as td:
        snap=Path(td)/'snapshot.gpkg';a=sqlite3.connect(SRC.resolve().as_uri()+'?mode=ro',uri=True);b=sqlite3.connect(snap);a.backup(b);a.close();b.close()
        assert digest(read(snap))==logical
        ds=gdal.VectorTranslate(str(DST),str(snap),format='GPKG',geometryType='GEOMETRY');assert ds is not None;ds=None
    copied=read(DST);assert all(copied[f]['wkb']==r['wkb'] and copied[f]['attrs']==r['attrs'] for f,r in original.items())
    ds=ogr.Open(str(DST),1);layer=ds.GetLayerByName('buildings_gt');changes=[];targets=set()
    for fid,r in original.items():
        g=wkb.loads(r['wkb']);p=r['attrs']['patch_id'];fp=footprints[p];h=g;actions=[]
        if not h.is_valid:
            h=make_valid(h);assert h.geom_type in ('Polygon','MultiPolygon') and h.is_valid and not h.is_empty
            # Retain all polygon pieces under the original building identity, including tiny lobes.
            assert abs(h.area-g.area)/max(g.area,1e-20)<.005,'Ambiguous invalid geometry repair'
            actions.append('MAKE_VALID_ALL_POLYGON_PARTS_RETAINED')
        if not fp.buffer(1e-6).covers(h):
            assert h.geom_type=='Polygon'
            maximum=max(Point(x,y).distance(fp) for x,y in h.exterior.coords)
            clipped=h.intersection(fp);loss=(h.area-clipped.area)/h.area
            assert maximum<.5 and loss<.02 and clipped.geom_type=='Polygon' and not clipped.is_empty,'Clip exceeds minor border correction; stop for human review'
            h=clipped;actions.append('STRICT_CLIP_NATIVE_RASTER_FOOTPRINT')
        if actions:
            assert h.is_valid and fp.buffer(1e-6).covers(h) and h.area>0
            f=layer.GetFeature(fid);f.SetGeometry(ogr.CreateGeometryFromWkb(h.wkb));assert layer.SetFeature(f)==0;targets.add(fid)
            changes.append(dict(fid=fid,patch_id=p,building_id=r['attrs']['building_id'],actions=';'.join(actions),old_area_m2=g.area,new_area_m2=h.area,
                                before_wkb_sha256=hashlib.sha256(r['wkb']).hexdigest(),after_wkb_sha256=hashlib.sha256(h.wkb).hexdigest(),geometry_type=h.geom_type,
                                retained_part_areas_m2=[part.area for part in h.geoms] if h.geom_type=='MultiPolygon' else [h.area],before_wkb_hex=r['wkb'].hex(),after_wkb_hex=h.wkb.hex()))
    ds=None;fixed=read(DST);assert set(original)==set(fixed)
    untouched=[fid for fid in original if fid not in targets];assert len(untouched)==139
    assert all(fixed[f]['wkb']==original[f]['wkb'] for f in untouched)
    assert all(fixed[f]['attrs']==original[f]['attrs'] for f in original)
    assert digest(read(SRC))==logical and sha(SRC)==original_sha
    assert not wal.exists() or sha(wal)==wal_sha
    assert len(targets)==26
    evidence=dict(source=str(SRC),fixed_copy=str(DST),source_main_sha256=original_sha,source_wal_sha256=wal_sha,source_logical_features_sha256=logical,
                  original_unchanged=True,total_features=165,changed_features=26,unchanged_geometry_wkb=139,all_attributes_and_ids_unchanged=True,
                  clips=22,make_valid=4,added_features=0,deleted_features=0,duplicate_deletions=0,polygon_features=161,multipolygon_features=4,
                  snapshot_method='SQLite read-only backup including committed WAL; OGR schema GEOMETRY preserves polygon/multipolygon WKB',changes=changes)
    (QA/'controlled_copy_repairs.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    with (QA/'controlled_copy_repairs.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=[k for k in changes[0] if not k.endswith('_hex')];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in changes)
    print(json.dumps({k:v for k,v in evidence.items() if k!='changes'},indent=2))
if __name__=='__main__':main()
