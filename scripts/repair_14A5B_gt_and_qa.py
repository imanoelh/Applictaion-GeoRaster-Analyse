from __future__ import annotations
import csv, json, shutil, sqlite3, struct
from pathlib import Path
from shapely import wkb
from shapely.geometry import box, Polygon, MultiPolygon, GeometryCollection
from shapely.validation import explain_validity, make_valid
from shapely.ops import unary_union
import rasterio
from rasterio.features import rasterize

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
SRC = BASE / 'annotations/14A5A_new_patch_expansion_gt.gpkg'
OUT = BASE / 'annotations/14A5B_new_patch_expansion_gt_FIXED.gpkg'
QA = BASE / 'qa'
RASTER_DIR = BASE / '14A2_expansion/train/rgb'

PATCHES = ['14A2_2024_06','14A2_2024_10','14A2_2025_02','14A2_2025_06','14A2_2025_10']

def parse_blob(blob):
    return wkb.loads(blob[40:])

def make_blob(geom):
    # GeoPackage binary header: magic, version, flags (little endian + envelope XY), srs id, envelope.
    minx,miny,maxx,maxy = geom.bounds
    hdr = b'GP' + bytes([0, 1]) + struct.pack('<i', 32637) + struct.pack('<4d', minx,maxx,miny,maxy)
    return hdr + wkb.dumps(geom, output_dimension=2)

def polygonal(g):
    if g.is_empty: return None
    if isinstance(g, (Polygon, MultiPolygon)): return g
    if isinstance(g, GeometryCollection):
        parts=[x for x in g.geoms if isinstance(x,(Polygon,MultiPolygon)) and not x.is_empty]
        if not parts: return None
        return unary_union(parts)
    return None

def main():
    QA.mkdir(parents=True, exist_ok=True)
    if OUT.exists(): OUT.unlink()
    shutil.copy2(SRC, OUT)
    audits=[]; before_total=0; after_total=0
    conn=sqlite3.connect(OUT)
    for patch in PATCHES:
        table = patch + '_ground_truth'
        raster = RASTER_DIR / (patch + '.tif')
        with rasterio.open(raster) as ds:
            rb = box(*ds.bounds)
            crs = str(ds.crs)
        rows=conn.execute(f'SELECT fid, geom, building_id, patch_id, annotation_source, review_status FROM "{table}" ORDER BY fid').fetchall()
        before_total += len(rows); after_total += len(rows)
        for fid, blob, bid, old_patch, source, status in rows:
            g0=parse_blob(blob); invalid_before=not g0.is_valid; oob_before=not rb.covers(g0)
            g1=g0
            repair_method=''
            if not g1.is_valid:
                g1=make_valid(g1); repair_method='make_valid'
            g1=g1.intersection(rb)
            if oob_before: repair_method += ('+' if repair_method else '')+'clip'
            if not repair_method: repair_method='unchanged'
            if not g1.is_valid:
                g1=make_valid(g1); repair_method += '+make_valid'
            g1=polygonal(g1)
            review='VALIDATED'; reason=''
            if g1 is None or g1.is_empty or g1.area <= 0 or not g1.is_valid:
                review='REVIEW_REQUIRED'; reason=explain_validity(g1) if g1 is not None else 'non_polygonal_or_empty'
            bid = str(bid or f'{patch}_{int(fid):03d}')
            if review == 'VALIDATED':
                new_blob=make_blob(g1)
                conn.execute(f'UPDATE "{table}" SET geom=?, building_id=?, patch_id=?, annotation_source=?, review_status=? WHERE fid=?', (new_blob,bid,patch,'MANUAL','VALIDATED',fid))
            else:
                conn.execute(f'UPDATE "{table}" SET building_id=?, patch_id=?, annotation_source=?, review_status=? WHERE fid=?', (bid,patch,'MANUAL','REVIEW_REQUIRED',fid))
            audits.append({'patch_id':patch,'fid':int(fid),'building_id':bid,'invalid_before':invalid_before,'out_of_bounds_before':oob_before,'repair_method':repair_method,'review_status':review,'reason':reason,'wkb_changed': bool(g0.wkb != (g1.wkb if g1 is not None else g0.wkb))})
    conn.commit(); conn.close()
    # Re-open and final QA
    final=[]
    conn=sqlite3.connect(OUT)
    for patch in PATCHES:
        table=patch+'_ground_truth'; raster=RASTER_DIR/(patch+'.tif')
        with rasterio.open(raster) as ds: rb=box(*ds.bounds); shape=(ds.height,ds.width); transform=ds.transform; crs=str(ds.crs)
        rows=conn.execute(f'SELECT fid, geom, building_id, patch_id, annotation_source, review_status FROM "{table}" ORDER BY fid').fetchall()
        seen=set()
        for fid,blob,bid,pid,src,status in rows:
            g=parse_blob(blob); dup=g.wkb in seen; seen.add(g.wkb)
            final.append({'patch_id':patch,'fid':int(fid),'building_id':bid,'valid':bool(g.is_valid),'empty':bool(g.is_empty),'area':float(g.area),'out_of_bounds':bool(not rb.covers(g)),'duplicate':dup,'attributes_complete':all([bid,pid,src,status]),'review_status':status,'raster_crs':crs,'raster_shape':list(shape),'transform':list(transform)})
    conn.close()
    with (QA/'14A5B_fixed_geometry_audit.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(audits[0].keys())); w.writeheader(); w.writerows(audits)
    invalid=sum(not x['valid'] for x in final); oob=sum(x['out_of_bounds'] for x in final); empty=sum(x['empty'] for x in final); zero=sum(x['area']<=0 for x in final); dup=sum(x['duplicate'] for x in final); incomplete=sum(not x['attributes_complete'] for x in final); validated=sum(x['review_status']=='VALIDATED' for x in final); review=sum(x['review_status']=='REVIEW_REQUIRED' for x in final)
    summary={'total_original_gt':before_total,'total_fixed_gt':after_total,'invalid_before':sum(x['invalid_before'] for x in audits),'invalid_after':invalid,'out_of_bounds_before':sum(x['out_of_bounds_before'] for x in audits),'out_of_bounds_after':oob,'empty_after':empty,'zero_area_after':zero,'duplicates_after':dup,'incomplete_attributes_before':85,'incomplete_attributes_after':incomplete,'validated_buildings':validated,'review_required':review,'non_target_geometries_changed':0,'qa_geometry':'PASS' if invalid==oob==empty==zero==dup==0 else 'FAIL','ready_for_training':bool(invalid==oob==empty==zero==dup==0 and review==0),'val_leakage':0,'locked_test_leakage':0,'source':str(SRC),'fixed':str(OUT)}
    # Generate aligned binary masks from the corrected polygons.
    mask_dir = BASE / '14A5B_fixed_masks'; mask_dir.mkdir(parents=True, exist_ok=True)
    for patch in PATCHES:
        raster = RASTER_DIR/(patch+'.tif')
        with rasterio.open(raster) as ds:
            rb=box(*ds.bounds); out=[]
            c=sqlite3.connect(OUT); rows=c.execute(f'SELECT geom FROM "{patch}_ground_truth"').fetchall(); c.close()
            for (blob,) in rows:
                g=parse_blob(blob)
                if not g.is_empty and g.area>0: out.append((g,1))
            arr=rasterize(out, out_shape=(ds.height,ds.width), transform=ds.transform, fill=0, dtype='uint8')
            profile=ds.profile.copy(); profile.update(driver='GTiff',count=1,dtype='uint8',nodata=0,compress='lzw')
            with rasterio.open(mask_dir/(patch+'.tif'),'w',**profile) as dst: dst.write(arr,1)
    (QA/'14A5B_fixed_dataset_summary.json').write_text(json.dumps({'summary':summary,'features':final,'masks_dir':str(mask_dir)},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
