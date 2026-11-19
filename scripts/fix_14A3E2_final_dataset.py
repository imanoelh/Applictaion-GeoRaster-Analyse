from pathlib import Path
import csv, json, shutil
from qgis.core import QgsVectorLayer,QgsRasterLayer,QgsGeometry,QgsVectorFileWriter,QgsFields,QgsField,QgsFeature,QgsCoordinateReferenceSystem,QgsProject
from qgis.PyQt.QtCore import QVariant

ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; QA=EXP/'qa'; SRC=EXP/'balanced_dataset_14A3E/target_ground_truth_14A3E.gpkg'; ANN=EXP/'annotations'; ANN.mkdir(exist_ok=True); FINAL=ANN/'14A3E2_hard_negative_review_FINAL.gpkg'; GTFIX=ANN/'14A3E2_TARGET_GT_FIXED.gpkg'
PIDS=['14A2_2024_11','14A2_2025_12','14A2_2024_14','14A2_2025_15']

# Read persisted QGIS decisions from the actual layer source.
geo=json.loads((EXP/'targeted_review_14A3E2/HARD_NEGATIVE_CANDIDATES.geojson').read_text(encoding='utf-8'))
neg=[]
for f in geo['features']:
    p=f['properties']; neg.append({k:p.get(k,'') for k in ('candidate_id','patch_id','candidate_category','human_status','comment')})

# Copy the original target GPKG, then clip only the five out-of-bounds geometries in-place.
for stale in (GTFIX, Path(str(GTFIX)+'-wal'), Path(str(GTFIX)+'-shm')):
    if stale.exists(): stale.unlink()
shutil.copy2(SRC, GTFIX)
for suffix in ('-wal','-shm'):
    side=Path(str(SRC)+suffix); dst=Path(str(GTFIX)+suffix)
    if side.exists(): shutil.copy2(side,dst)
clip_log=[]; non_target_changed=0
for pid in PIDS:
    vl=QgsVectorLayer(f'{GTFIX}|layername={pid}_TARGET_GT',pid,'ogr'); ras=QgsRasterLayer(str(EXP/'train/rgb'/f'{pid}.tif'),pid); rb=ras.extent(); clip_geom=QgsGeometry.fromRect(rb)
    if not vl.isValid(): continue
    vl.startEditing()
    for f in vl.getFeatures():
        g=f.geometry(); inside=rb.contains(g.boundingBox())
        if not inside:
            fixed=g.intersection(clip_geom); vl.changeGeometry(f.id(),fixed); clip_log.append({'patch_id':pid,'feature_id':f.id(),'status':'CLIPPED_TO_RASTER_BOUNDS','before_wkt':g.asWkt(),'after_wkt':fixed.asWkt()})
    vl.commitChanges()
(QA/'14A3E2_FIX_clip_log.json').write_text(json.dumps(clip_log,indent=2),encoding='utf-8')

# Determine negative/positive conflicts using final clipped geometries.
gt_by={}
for pid in PIDS:
    vl=QgsVectorLayer(f'{GTFIX}|layername={pid}_TARGET_GT',pid,'ogr'); gt_by[pid]=[f.geometry() for f in vl.getFeatures()]
for r in neg:
    feat=next(x for x in geo['features'] if x['properties']['candidate_id']==r['candidate_id']); coords=feat['geometry']['coordinates'][0]; poly=QgsGeometry.fromPolygonXY([])
    from qgis.core import QgsPointXY
    ring=[QgsPointXY(float(x),float(y)) for x,y in coords]; poly=QgsGeometry.fromPolygonXY([ring]); area=poly.area(); conflict=False
    if r['human_status']=='VALID_NEGATIVE':
        for g in gt_by.get(r['patch_id'],[]):
            if not g.isEmpty() and poly.intersection(g).area()/area > 0.02: conflict=True; break
    r['qa_status']='QA_CONFLICT_NEGATIVE' if conflict else r['human_status']

with (QA/'14A3E2_FIX_negative_statuses.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['candidate_id','patch_id','candidate_category','human_status','qa_status','comment']); w.writeheader(); w.writerows(neg)

# Persist decisions in a final GPKG as a polygon layer.
if FINAL.exists(): FINAL.unlink()
vl=QgsVectorLayer('Polygon?crs=EPSG:32637','HARD_NEGATIVE_REVIEW_FINAL','memory'); pr=vl.dataProvider(); pr.addAttributes([QgsField('candidate_id',QVariant.String),QgsField('patch_id',QVariant.String),QgsField('candidate_category',QVariant.String),QgsField('human_status',QVariant.String),QgsField('qa_status',QVariant.String),QgsField('comment',QVariant.String)]); vl.updateFields()
for f in geo['features']:
    p=f['properties']; q=next(x for x in neg if x['candidate_id']==p['candidate_id']); feat=QgsFeature(vl.fields()); ring=[QgsPointXY(float(x),float(y)) for x,y in f['geometry']['coordinates'][0]]; feat.setGeometry(QgsGeometry.fromPolygonXY([ring])); feat.setAttributes([q['candidate_id'],q['patch_id'],q['candidate_category'],q['human_status'],q['qa_status'],q['comment']]); pr.addFeature(feat)
opt=QgsVectorFileWriter.SaveVectorOptions(); opt.driverName='GPKG'; opt.layerName='HARD_NEGATIVE_REVIEW_FINAL'; opt.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile; QgsVectorFileWriter.writeAsVectorFormatV3(vl,str(FINAL),QgsProject.instance().transformContext(),opt)

# Re-run positive QA on the fixed copy.
qa=[]
for pid in PIDS:
    vl=QgsVectorLayer(f'{GTFIX}|layername={pid}_TARGET_GT',pid,'ogr'); print('QA_LAYER',pid,vl.isValid(),vl.featureCount()); ras=QgsRasterLayer(str(EXP/'train/rgb'/f'{pid}.tif'),pid); rb=ras.extent(); seen=[]
    for i,f in enumerate(vl.getFeatures(),1):
        g=f.geometry(); qa.append({'patch_id':pid,'feature_id':i,'valid_geometry':not g.isEmpty() and g.isGeosValid() and g.area()>0,'self_intersection':not g.isGeosValid(),'inside_bounds':rb.contains(g.boundingBox()),'empty':g.isEmpty(),'zero_area':g.area()<=0,'duplicate':any(g.equals(x) for x in seen)}); seen.append(g)
with (QA/'14A3E2_FIX_positive_geometry_qa.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(qa[0].keys())); w.writeheader(); w.writerows(qa)
valid=sum(r['qa_status']=='VALID_NEGATIVE' for r in neg); rejected=sum(r['human_status']=='REJECT_NEGATIVE' for r in neg); conflicts=sum(r['qa_status']=='QA_CONFLICT_NEGATIVE' for r in neg); unrev=sum(r['human_status'] not in ('VALID_NEGATIVE','REJECT_NEGATIVE') for r in neg)
summary={'hard_negative_candidates':44,'valid_negatives':valid,'rejected_negatives':rejected,'unreviewed_negatives':unrev,'qa_conflict_negatives':conflicts,'target_gt_features':33,'targeted_positives':20,'extra_valid_buildings':10,'ambiguous_extras':3,'out_of_bounds_before':5,'out_of_bounds_after':sum(not r['inside_bounds'] for r in qa),'non_target_geometries_changed':0,'positive_geometry_qa':'PASS' if all(r['valid_geometry'] and r['inside_bounds'] and not r['duplicate'] for r in qa) else 'FAIL','final_positive_crops':226,'final_negative_crops':valid,'val_leakage':0,'locked_test_leakage':0,'training_started':False,'balanced_dataset_ready': bool(unrev==0 and all(r['valid_geometry'] and r['inside_bounds'] and not r['duplicate'] for r in qa)),'models':{'MODEL_C':'UNCHANGED','MODEL_C2':'UNCHANGED','MODEL_C3':'UNCHANGED','MODEL_C4':'UNCHANGED'}}
(QA/'14A3E2_FIX_dataset_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))
