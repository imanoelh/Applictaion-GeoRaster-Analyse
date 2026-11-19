"""Recover only the GeoPackage binary header in a separate TRAIN archive copy."""
from pathlib import Path
import hashlib,json,sqlite3,struct
from collections import Counter
from shapely import wkb

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
SRC=BASE/'annotations/14A5B_new_patch_expansion_gt_FIXED.gpkg'
DST=BASE/'annotations/14A5B_recovered_copy.gpkg'
QA=BASE/'14A7_validation_expansion/qa'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def q(s):return '"'+s.replace('"','""')+'"'

def main():
    if DST.exists():raise RuntimeError('Recovery copy already exists; never overwrite annotations automatically')
    if Path(str(SRC)+'-wal').exists() and Path(str(SRC)+'-wal').stat().st_size:raise RuntimeError('Nonempty source WAL')
    before=sha(SRC)
    source=sqlite3.connect(SRC.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    dest=sqlite3.connect(DST)
    source.backup(dest)
    audit=dict(source=str(SRC.relative_to(ROOT)),recovered_copy=str(DST.relative_to(ROOT)),source_sha256_before=before,
               sqlite_magic_header=SRC.read_bytes()[:16].decode('ascii',errors='replace'),application_id=source.execute('PRAGMA application_id').fetchone()[0],
               sqlite_integrity_before=source.execute('PRAGMA integrity_check').fetchone()[0],source_gpkg_contents=source.execute('SELECT table_name,data_type,srs_id FROM gpkg_contents').fetchall(),
               source_gpkg_geometry_columns=source.execute('SELECT * FROM gpkg_geometry_columns').fetchall(),layers=[],feature_count=0,geometry_count=0,invalid_geometries=0,wkb_unchanged=0,
               eligible_for_validation=False,dataset_role='HISTORICAL_TRAIN_ONLY')
    for table,col,declared_type,srs,z,m in source.execute('SELECT * FROM gpkg_geometry_columns'):
        rows=source.execute('SELECT fid,'+q(col)+' FROM '+q(table)).fetchall();types=Counter();valid=[];count=0
        for fid,blob in rows:
            if blob[:2]!=b'GP' or blob[2]!=0 or blob[3]!=1:raise RuntimeError('Unexpected source header; do not guess recovery')
            endian='<' if blob[3]&1 else '>'
            if struct.unpack(endian+'i',blob[4:8])[0]!=srs:raise RuntimeError('SRS mismatch')
            g=wkb.loads(blob[40:]);env=struct.unpack(endian+'4d',blob[8:40]);b=g.bounds
            if any(abs(a-b)>1e-7 for a,b in zip(env,(b[0],b[2],b[1],b[3]))):raise RuntimeError('Envelope does not match actual geometry')
            if g.geom_type not in ('Polygon','MultiPolygon') or g.is_empty or not g.is_valid or g.area<=0:raise RuntimeError('Unsafe/nonpolygon recovery')
            fixed=blob[:3]+bytes([3])+blob[4:]
            if fixed[40:]!=blob[40:]:raise RuntimeError('Geometry WKB must stay exact')
            dest.execute('UPDATE '+q(table)+' SET '+q(col)+'=? WHERE fid=?',(fixed,fid))
            types[g.geom_type]+=1;valid.append(g);count+=1
        typ=next(iter(types)).upper() if len(types)==1 else 'GEOMETRY'
        dest.execute('UPDATE gpkg_geometry_columns SET geometry_type_name=? WHERE table_name=?',(typ,table))
        bounds=[min(g.bounds[0] for g in valid),min(g.bounds[1] for g in valid),max(g.bounds[2] for g in valid),max(g.bounds[3] for g in valid)]
        dest.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?',(*bounds,table))
        audit['layers'].append(dict(layer=table,count=count,geometry_types=dict(types),schema_geometry_type=typ,srs_id=srs,old_flags=1,new_flags=3,wkb_unchanged=count))
        audit['feature_count']+=count;audit['geometry_count']+=count;audit['wkb_unchanged']+=count
    dest.commit();audit['sqlite_integrity_after']=dest.execute('PRAGMA integrity_check').fetchone()[0]
    for table,col,typ,srs,z,m in dest.execute('SELECT * FROM gpkg_geometry_columns'):
        for (blob,) in dest.execute('SELECT '+q(col)+' FROM '+q(table)):
            offset=8+{0:0,1:32,2:48,3:48,4:64}[(blob[3]>>1)&7]
            g=wkb.loads(blob[offset:])
            if not g.is_valid:audit['invalid_geometries']+=1
    source.close();dest.close();audit['source_sha256_after']=sha(SRC);audit['original_unchanged']=before==audit['source_sha256_after'];audit['copy_sha256']=sha(DST)
    if not audit['original_unchanged'] or audit['feature_count']!=85 or audit['geometry_count']!=85 or audit['wkb_unchanged']!=85 or audit['invalid_geometries']!=0:raise RuntimeError('Recovery validation failed')
    (QA/'14A5B_readonly_audit_and_recovery.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ('feature_count','geometry_count','invalid_geometries','wkb_unchanged','original_unchanged')},indent=2))

if __name__=='__main__':main()
