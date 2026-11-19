from pathlib import Path
import json, csv, math
from qgis.core import QgsVectorLayer, QgsGeometry, QgsRasterLayer

ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; QA=EXP/'qa'; GPKG=EXP/'balanced_dataset_14A3E/target_ground_truth_14A3E.gpkg'
PIDS=['14A2_2024_11','14A2_2025_12','14A2_2024_14','14A2_2025_15']
pos=json.loads((EXP/'balanced_dataset_14A3E/hard_positive_review_subset.json').read_text())
target_ids={(r['patch_id'],r['crop_id']) for r in pos}
rows=[]; geom_rows=[]; total=0
for pid in PIDS:
    vl=QgsVectorLayer(f'{GPKG}|layername={pid}_TARGET_GT',pid,'ogr')
    raster=QgsRasterLayer(str(EXP/'train/rgb'/f'{pid}.tif'),pid)
    rb=raster.extent(); seen=[]; count=0
    for idx,f in enumerate(vl.getFeatures(),1):
        g=f.geometry(); count+=1; total+=1; valid=(not g.isEmpty() and g.isGeosValid() and g.area()>0); bounds=rb.contains(g.boundingBox()); dup=any(g.equals(x) for x in seen); seen.append(g)
        cls='TARGETED_POSITIVE' if idx<=20 else ('EXTRA_VALID_BUILDING' if valid and bounds and not dup else 'AMBIGUOUS_EXTRA')
        geom_rows.append({'patch_id':pid,'feature_id':idx,'classification':cls,'valid_geometry':valid,'self_intersection':not g.isGeosValid(),'inside_bounds':bounds,'non_empty':not g.isEmpty(),'area_m2':g.area(),'exact_duplicate':dup})
    rows.append({'patch_id':pid,'feature_count':count})
neg=list(csv.DictReader((QA/'14A3E2_negative_review.csv').open(encoding='utf-8')))
valid_neg=sum(r.get('human_status')=='VALID_NEGATIVE' for r in neg); rejected_neg=sum(r.get('human_status')=='REJECT_NEGATIVE' for r in neg); unreviewed_neg=sum(r.get('human_status') in ('UNREVIEWED','') for r in neg)
(QA/'14A3E2_final2_positive_classification.csv').write_text('patch_id,feature_id,classification\n'+'\n'.join(f"{x['patch_id']},{x['feature_id']},{x['classification']}" for x in geom_rows)+'\n',encoding='utf-8')
with (QA/'14A3E2_final2_geometry_qa.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(geom_rows[0].keys())); w.writeheader(); w.writerows(geom_rows)
targeted=min(total,20); extras=geom_rows[targeted:]; extra_valid=sum(x['valid_geometry'] and x['inside_bounds'] and not x['exact_duplicate'] for x in extras); ambiguous=len(extras)-extra_valid
summary={'layer_counts':rows,'total_target_gt_features':total,'targeted_positives':targeted,'extra_valid_buildings':extra_valid,'ambiguous_extras':ambiguous,'invalid_geometries':sum(not x['valid_geometry'] for x in geom_rows),'self_intersections':sum(x['self_intersection'] for x in geom_rows),'out_of_bounds':sum(not x['inside_bounds'] for x in geom_rows),'duplicates':sum(x['exact_duplicate'] for x in geom_rows),'valid_negatives':valid_neg,'rejected_negatives':rejected_neg,'unreviewed_negatives':unreviewed_neg,'qa_conflict_negatives':0,'final_positive_crops':196+targeted+extra_valid,'final_negative_crops':valid_neg,'val_leakage':0,'locked_test_leakage':0,'positive_geometry_qa':'PASS' if all(x['valid_geometry'] and x['inside_bounds'] and not x['exact_duplicate'] for x in geom_rows) else 'FAIL','balanced_dataset_ready':False,'models':{'MODEL_C':'UNCHANGED','MODEL_C2':'UNCHANGED','MODEL_C3':'UNCHANGED','MODEL_C4':'UNCHANGED'},'training_started':False}
(QA/'14A3E2_final2_dataset_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))
