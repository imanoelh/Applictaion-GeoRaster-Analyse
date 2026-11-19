"""Read-only source GT QA. Masks/final annotation lock only after all checks pass."""
from pathlib import Path
import csv,json,hashlib,sqlite3,zipfile,sys,xml.etree.ElementTree as ET
from collections import Counter
import numpy as np
from PIL import Image,ImageDraw
from osgeo import ogr,gdal,osr
from shapely import wkb
from shapely.geometry import Polygon
from shapely.validation import explain_validity
from shapely.ops import transform as geom_transform
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set'
QA=OUT/'qa/14A7B_gold';QA.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def csvwrite(p,rows,fields):
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    manifest=list(csv.DictReader((OUT/'manifest/14A7_GOLD_SET_manifest.csv').open(encoding='utf-8-sig')))
    lock=json.loads((OUT/'manifest/GOLD_SET_LOCK.json').read_text(encoding='utf-8'));patches=lock['patches'];ids={p['patch_id'] for p in patches}
    assert len(manifest)==4 and {p['patch_id'] for p in manifest}==ids and lock['GOLD_SET_LOCKED']
    assert all(p['GOLD_SET_LOCKED']=='YES' for p in manifest)
    with zipfile.ZipFile(OUT/'qgis/14A7_GOLD_SET_MANUAL_4.qgz') as z:
        xml=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
    sources={l.findtext('datasource').split('|')[0] for l in xml.findall('./projectlayers/maplayer') if l.findtext('provider')=='ogr'}
    assert len(sources)==1;snapshot=Path(sys.argv[sys.argv.index('--gt')+1]) if '--gt' in sys.argv else Path(next(iter(sources)));before=sha(snapshot)
    conn=sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro',uri=True);integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
    meta=conn.execute('SELECT table_name,last_change,srs_id FROM gpkg_contents').fetchall();sqlcount=conn.execute('SELECT COUNT(*) FROM buildings_gt').fetchone()[0];conn.close()
    ds=ogr.Open(str(snapshot),0);layer=ds.GetLayerByName('buildings_gt');assert layer is not None
    crs=layer.GetSpatialRef();assert crs.GetAuthorityCode(None)=='32637'
    rows=[];errors=[];geoms={p:[] for p in ids};seen_ids={};seen_geoms={};counts=Counter({k:0 for k in ('features','null','empty','invalid','self_intersection','zero_area','multipart','oob','cross_patch','wrong_patch','duplicates','attribute_errors')});footprints={};rasters={};to_native={}
    protected=json.loads((OUT.parent/'14A7_validation_expansion/qa/14A7A_protected_footprints.json').read_text())['footprints']
    for p in patches:
        pid=p['patch_id'];path=ROOT/p['rgb_path'];assert sha(path)==p['sha256'];r=gdal.Open(str(path));assert (r.RasterXSize,r.RasterYSize,r.RasterCount)==(512,512,3)
        gt=r.GetGeoTransform();proj=r.GetProjection();tx=Transformer.from_crs(proj,'EPSG:32637',always_xy=True);to_native[pid]=Transformer.from_crs('EPSG:32637',proj,always_xy=True)
        # Densify the native raster edges before UTM transformation; not merely an axis-aligned UTM box.
        border=[]
        for a,b in [((0,0),(512,0)),((512,0),(512,512)),((512,512),(0,512)),((0,512),(0,0))]:
            for t in np.linspace(0,1,65)[:-1]:
                x=a[0]+t*(b[0]-a[0]);y=a[1]+t*(b[1]-a[1]);border.append(tx.transform(gt[0]+x*gt[1]+y*gt[2],gt[3]+x*gt[4]+y*gt[5]))
        footprints[pid]=Polygon(border);rasters[pid]=dict(path=path,transform=gt,projection=proj,rgb=np.moveaxis(r.ReadAsArray(),0,-1));r=None
        a=p['bounds_32637']
        for f in protected:
            b=f['bounds_32637'];assert not(a[0]<b[2]+20 and a[2]>b[0]-20 and a[1]<b[3]+20 and a[3]>b[1]-20),'Historical spatial leakage'
    for f in layer:
        attrs=f.items();fid=f.GetFID();pid=attrs.get('patch_id');bid=attrs.get('building_id');gref=f.GetGeometryRef();g=wkb.loads(bytes(gref.ExportToWkb())) if gref else None
        issue=[];counts['features']+=1
        if g is None:issue.append('NULL_GEOMETRY');counts['null']+=1
        elif g.is_empty:issue.append('EMPTY_GEOMETRY');counts['empty']+=1
        else:
            if not g.is_valid:
                reason=explain_validity(g);issue.append('INVALID:'+reason);counts['invalid']+=1
                if 'self-intersection' in reason.lower():counts['self_intersection']+=1
            if g.area<=0:issue.append('ZERO_AREA');counts['zero_area']+=1
            if g.geom_type not in ('Polygon','MultiPolygon'):issue.append('INCOHERENT_MULTIPART_OR_TYPE:'+g.geom_type);counts['multipart']+=1
            if pid in footprints:
                if not footprints[pid].buffer(1e-6).covers(g):issue.append('OUT_OF_BOUNDS');counts['oob']+=1
                others=[k for k,fp in footprints.items() if k!=pid and fp.intersection(g).area>1e-8]
                if others:issue.append('CROSS_PATCH:'+','.join(others));counts['cross_patch']+=1
                if any(footprints[k].buffer(1e-6).covers(g) for k in others):counts['wrong_patch']+=1;issue.append('WRONG_PATCH_ASSIGNMENT')
                geoms[pid].append((fid,g))
            normalized=g.normalize().wkb
            if normalized in seen_geoms:issue.append('DUPLICATE_GEOMETRY_OF_FID:'+str(seen_geoms[normalized]));counts['duplicates']+=1
            else:seen_geoms[normalized]=fid
        ae=[]
        if pid not in ids:ae.append('UNKNOWN_PATCH_ID')
        if not isinstance(bid,str) or not bid.strip():ae.append('MISSING_BUILDING_ID')
        elif bid in seen_ids:ae.append('DUPLICATE_BUILDING_ID')
        else:seen_ids[bid]=fid
        expected=next((p['scene_type'] for p in patches if p['patch_id']==pid),None)
        if attrs.get('scene_type')!=expected:ae.append('SCENE_TYPE_MISMATCH')
        if attrs.get('source')!='MANUAL':ae.append('SOURCE_NOT_MANUAL')
        if attrs.get('review_status') not in ('UNREVIEWED','REVIEWED','VALIDATED'):ae.append('INVALID_REVIEW_STATUS')
        counts['attribute_errors']+=len(ae);issue+=ae
        row=dict(fid=fid,patch_id=pid,building_id=bid,area_m2=g.area if g is not None else None,issues=';'.join(issue));rows.append(row)
        if issue:errors.append(row)
    ds=None;assert sqlcount==counts['features'];assert sha(snapshot)==before
    per_patch=[dict(patch_id=p['patch_id'],buildings=len(geoms[p['patch_id']]),qa='PENDING_ANNOTATIONS_NOT_PERSISTED' if not geoms[p['patch_id']] else 'FAIL' if any(r['patch_id']==p['patch_id'] for r in errors) else 'PASS') for p in patches]
    passed=not errors and all(p['buildings']>0 for p in per_patch) and integrity=='ok';alignment=[];masks={}
    if passed:
        maskdir=OUT/'gt_masks';maskdir.mkdir(exist_ok=True)
        for p in patches:
            pid=p['patch_id'];r=rasters[pid];srs=osr.SpatialReference();srs.ImportFromWkt(r['projection']);srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            v=ogr.GetDriverByName('Memory').CreateDataSource('');l=v.CreateLayer('gt',srs,ogr.wkbUnknown)
            for fid,g in geoms[pid]:
                native=geom_transform(to_native[pid].transform,g);feat=ogr.Feature(l.GetLayerDefn());feat.SetGeometry(ogr.CreateGeometryFromWkb(native.wkb));l.CreateFeature(feat)
            path=maskdir/(pid+'.tif');d=gdal.GetDriverByName('GTiff').Create(str(path),512,512,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE']);d.SetProjection(r['projection']);d.SetGeoTransform(r['transform']);d.GetRasterBand(1).Fill(0)
            assert gdal.RasterizeLayer(d,[1],l,burn_values=[1],options=['ALL_TOUCHED=FALSE'])==0;d=None;v=None;d=gdal.Open(str(path));a=d.ReadAsArray()
            ok=d.GetGeoTransform()==r['transform'] and d.GetProjection()==r['projection'] and a.shape==(512,512) and set(np.unique(a)).issubset({0,1});assert ok
            masks[pid]=a;alignment.append(dict(patch_id=pid,crs_match=True,transform_match=True,width=512,height=512,pixel_alignment='PASS',mask_sha256=sha(path)));d=None
    sheet=Image.new('RGB',(768,4*292),'white');draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(patches):
        pid=p['patch_id'];r=rasters[pid];im=Image.fromarray(r['rgb'].astype('uint8'));overlay=im.copy();od=ImageDraw.Draw(overlay);inv=gdal.InvGeoTransform(r['transform'])
        for fid,g in geoms[pid]:
            parts=[g] if g.geom_type=='Polygon' else list(g.geoms) if g.geom_type=='MultiPolygon' else []
            for part in parts:
                for ring in [part.exterior]+list(part.interiors):
                    native=geom_transform(to_native[pid].transform,ring);pts=[tuple(gdal.ApplyGeoTransform(inv,x,y)) for x,y in native.coords];od.line(pts,fill='yellow',width=3)
        y=i*292;draw.text((4,y+2),pid+(' | HUMAN GT' if passed else ' | QA PENDING / NOT VALIDATED'),fill='black')
        sheet.paste(im.resize((256,256)),(0,y+30));sheet.paste(overlay.resize((256,256)),(256,y+30))
        if pid in masks:sheet.paste(Image.fromarray(masks[pid]*255).convert('RGB').resize((256,256),Image.Resampling.NEAREST),(512,y+30))
        else:draw.text((520,y+130),'MASK NOT GENERATED',fill='red')
    sheet.save(QA/'14A7B_HUMAN_GT_CONTACT_SHEET.png')
    csvwrite(QA/'features_qa.csv',rows,['fid','patch_id','building_id','area_m2','issues'])
    csvwrite(QA/'patches_qa.csv',per_patch,['patch_id','buildings','qa'])
    csvwrite(QA/'alignment_qa.csv',alignment,['patch_id','crs_match','transform_match','width','height','pixel_alignment','mask_sha256'])
    result=dict(source=str(snapshot),source_sha256=before,original_unchanged=sha(snapshot)==before,sqlite_integrity=integrity,gpkg_metadata=meta,counts=dict(counts),per_patch=per_patch,
                errors=errors,masks_generated=len(masks),alignment='PASS' if passed and len(masks)==4 else 'NOT_RUN',gold_ready=passed,
                selection_lock=True,annotation_validation_lock=passed,train_leakage=0,no_automatic_ai_injection_performed=True,no_model_inference=True,
                annotation_origin_evidence='Source attributes and stored features only; manual authoring cannot be proved by an attribute alone',
                blocker=None if passed else 'ANNOTATIONS_NOT_PERSISTED' if counts['features']==0 else 'GEOMETRY_ATTRIBUTE_OR_COVERAGE_QA_FAILED')
    dump(QA/'gold_gt_qa.json',result)
    if passed:
        final=dict(GOLD_SET_LOCKED='YES',FORBIDDEN_FOR_TRAINING='YES',FORBIDDEN_FOR_FINE_TUNING='YES',FORBIDDEN_FOR_THRESHOLD_CALIBRATION='YES',FORBIDDEN_FOR_PSEUDO_LABEL_TRAINING='YES',FORBIDDEN_FOR_HYPERPARAMETER_TUNING='YES',allowed_uses=['BENCHMARK','VALIDATION','MODEL_COMPARISON'],source_gt_sha256=before,masks=alignment,patch_ids=sorted(ids),buildings=counts['features'])
        dump(OUT/'manifest/GOLD_VALIDATED_ANNOTATION_LOCK.json',final)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
