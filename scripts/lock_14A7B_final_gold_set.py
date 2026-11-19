"""Freeze the validated corrected GOLD, masks and QGIS references. No ML imports."""
from pathlib import Path
import json,csv,hashlib,gc,sqlite3
from osgeo import ogr,gdal
from qgis.core import QgsApplication,QgsProject,QgsVectorLayer,QgsMapLayerStyle
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set';QA=OUT/'qa/14A7B_gold'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    qa=json.loads((QA/'gold_gt_qa.json').read_text());assert qa['gold_ready'] and qa['masks_generated']==4 and qa['alignment']=='PASS'
    runtime=json.loads((OUT/'qa/14A7B_runtime/fixed_runtime_smoke.json').read_text());assert runtime['passed']
    fixed=OUT/'gt/14A7_GOLD_SET_GT_FIXED.gpkg';fixed_sha=sha(fixed);assert fixed_sha==qa['source_sha256']
    repair=json.loads((QA/'controlled_copy_repairs.json').read_text());assert repair['original_unchanged'] and repair['unchanged_geometry_wkb']==139
    lock=json.loads((OUT/'manifest/GOLD_SET_LOCK.json').read_text(encoding='utf-8'));patches=lock['patches']
    ds=ogr.Open(str(fixed),0);layer=ds.GetLayerByName('buildings_gt');rows={p['patch_id']:[] for p in patches}
    for f in layer:
        assert f['source']=='MANUAL';g=f.GetGeometryRef();assert g and g.IsValid() and not g.IsEmpty()
        rows[f['patch_id']].append((f.GetFID(),f['building_id'],bytes(g.ExportToWkb()).hex(),g.GetArea()))
    ds=None
    final=[];per_patch=[]
    for p in patches:
        pid=p['patch_id'];items=sorted(rows[pid]);mask=OUT/'gt_masks'/(pid+'.tif');rgb=ROOT/p['rgb_path'];r=gdal.Open(str(rgb));m=gdal.Open(str(mask));arr=m.ReadAsArray()
        assert sha(rgb)==p['sha256'] and m.GetGeoTransform()==r.GetGeoTransform() and m.GetProjection()==r.GetProjection()
        assert (m.RasterXSize,m.RasterYSize)==(r.RasterXSize,r.RasterYSize)==(512,512)
        assert set(__import__('numpy').unique(arr))=={0,1}
        geom_hash=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
        entry=dict(patch_id=pid,rgb_path=p['rgb_path'],scene_type=p['scene_type'],rgb_sha256=p['sha256'],GOLD_SET_LOCKED='YES',role='FINAL_BENCHMARK_ONLY',
          FORBIDDEN_FOR_TRAINING='YES',FORBIDDEN_FOR_FINE_TUNING='YES',FORBIDDEN_FOR_THRESHOLD_CALIBRATION='YES',FORBIDDEN_FOR_PSEUDO_LABEL_TRAINING='YES',FORBIDDEN_FOR_HYPERPARAMETER_TUNING='YES',
          training_allowed='NO',fine_tuning_allowed='NO',pseudo_label_training_allowed='NO',threshold_calibration_allowed='NO',hyperparameter_tuning_allowed='NO',manual_gt_status='VALIDATED',
          gt_path=str(fixed.relative_to(ROOT)).replace('\\','/'),gt_layer='buildings_gt',gt_sha256=fixed_sha,gt_buildings=len(items),gt_feature_records_sha256=geom_hash,
          mask_path=str(mask.relative_to(ROOT)).replace('\\','/'),mask_sha256=sha(mask),width=512,height=512,source='MANUAL',qa_status='PASS',
          min_distance_historical_crops_m=p['min_distance_existing_crops_m'])
        final.append(entry);p.update(validated_gt=entry['gt_path'],validated_gt_layer='buildings_gt',validated_gt_sha256=fixed_sha,mask_path=entry['mask_path'],mask_sha256=entry['mask_sha256'],building_count=len(items),manual_gt_status='VALIDATED')
        per_patch.append(dict(PATCH=pid,FEATURE_COUNT=len(items),INVALID=0,EMPTY=0,NULL=0,ZERO_AREA=0,SELF_INTERSECTION=0,DUPLICATE=0,OOB=0,ATTRIBUTE_ERROR=0,WRONG_PATCH=0,CROSS_PATCH=0,ALIGNMENT='PASS',building_pixels=int(arr.sum()),area_m2=sum(a[3] for a in items)))
        r=None;m=None
    assert sum(p['gt_buildings'] for p in final)==165
    csvwrite(OUT/'manifest/14A7_GOLD_SET_manifest.csv',final);csvwrite(QA/'14A7B_FINAL_PER_PATCH_QA.csv',per_patch)
    lock.update(GOLD_SET_LOCKED=True,ANNOTATIONS_VALIDATED=True,FORBIDDEN_FOR_TRAINING='YES',FORBIDDEN_FOR_FINE_TUNING='YES',FORBIDDEN_FOR_THRESHOLD_CALIBRATION='YES',FORBIDDEN_FOR_PSEUDO_LABEL_TRAINING='YES',FORBIDDEN_FOR_HYPERPARAMETER_TUNING='YES',
                validated_gt_path=final[0]['gt_path'],validated_gt_sha256=fixed_sha,allowed_uses=['BENCHMARK','VALIDATION','MODEL_COMPARISON'],gt_buildings=165,qa_status='PASS',patches=patches)
    (OUT/'manifest/GOLD_SET_LOCK.json').write_text(json.dumps(lock,indent=2,ensure_ascii=False),encoding='utf-8')
    validated=json.loads((OUT/'manifest/GOLD_VALIDATED_ANNOTATION_LOCK.json').read_text());validated.update(validated_gt_path=final[0]['gt_path'],validated_gt_layer='buildings_gt',source_gt_sha256=fixed_sha,original_source_preserved=True,patches=final,runtime_evidence='qa/14A7B_runtime/fixed_runtime_smoke.json')
    (OUT/'manifest/GOLD_VALIDATED_ANNOTATION_LOCK.json').write_text(json.dumps(validated,indent=2),encoding='utf-8')
    # Reuse the existing project, point all its GT views to the locked self-contained copy.
    path=OUT/'qgis/14A7_GOLD_SET_MANUAL_4.qgz';project=QgsProject();assert project.read(str(path));views=0
    for layer in project.mapLayers().values():
        if isinstance(layer,QgsVectorLayer):
            subset=layer.subsetString();style=QgsMapLayerStyle();style.readFromLayer(layer)
            layer.setDataSource(fixed.as_posix()+'|layername=buildings_gt|option:IMMUTABLE=YES',layer.name(),'ogr');style.writeToLayer(layer)
            if subset:assert layer.setSubsetString(subset)
            layer.setReadOnly(True);assert layer.isValid();views+=1
    assert views==5 and len(project.mapLayers())==9
    project.setTitle('14A7 GOLD VALIDATED LOCKED | 165 HUMAN BUILDINGS | BENCHMARK ONLY')
    variables=project.customVariables();variables.update(GOLD_SET_LOCKED='YES',ANNOTATIONS_VALIDATED='YES',FORBIDDEN_FOR_TRAINING='YES');project.setCustomVariables(variables);assert project.write();project.clear();project=None
    project=QgsProject();assert project.read(str(path));assert all(l.isValid() for l in project.mapLayers().values());counts={l.name():l.featureCount() for l in project.mapLayers().values() if isinstance(l,QgsVectorLayer)}
    assert sorted(counts.values())==[8,23,40,94,165];assert all(l.readOnly() for l in project.mapLayers().values() if isinstance(l,QgsVectorLayer));project.clear();project=None
    assert sha(fixed)==fixed_sha
    readiness=dict(gold_patches=4,gt_buildings=165,valid_patches=4,invalid=0,oob=0,duplicates=0,attribute_errors=0,masks_ready=4,alignment='PASS',train_leakage=0,gold_locked=True,
      runtime_ml='PASS_PREVIOUS_SMOKE_NO_RERUN',gold_ready=True,model_shootout_ready=True,no_inference=True,no_training=True,no_benchmark=True,original_gt_modified=False,
      canonical_gt=final[0]['gt_path'],canonical_gt_sha256=fixed_sha,qgis_open='PASS_PYQGIS',qgis_gt_read_only=True,qgis_counts=counts)
    (OUT/'qa/14A7B_READINESS.json').write_text(json.dumps(readiness,indent=2),encoding='utf-8');(QA/'FINAL_READINESS.json').write_text(json.dumps(readiness,indent=2),encoding='utf-8')
    print(json.dumps(readiness,indent=2))
if __name__=='__main__':
    APP=QgsApplication([],False);APP.initQgis();main();gc.collect();APP.exitQgis()
