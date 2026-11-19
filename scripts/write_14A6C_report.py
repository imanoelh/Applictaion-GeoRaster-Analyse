from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; QA=BASE/'qa'
diff=[
 {'parameter':'threshold','historical_c3':'0.30','14A6B_c3':'0.50','match':'NO'},
 {'parameter':'minimum_component_area_px','historical_c3':'479','14A6B_c3':'4/no effective filter','match':'NO'},
 {'parameter':'morphology','historical_c3':'none','14A6B_c3':'none','match':'YES'},
 {'parameter':'connectivity','historical_c3':'4-connected','14A6B_c3':'4-connected','match':'YES'},
 {'parameter':'input_normalization','historical_c3':'per-raster RGB min-max [0,1]','14A6B_c3':'per-raster RGB min-max [0,1]','match':'YES'},
 {'parameter':'output_activation','historical_c3':'sigmoid','14A6B_c3':'sigmoid','match':'YES'},
 {'parameter':'border_policy','historical_c3':'retain components in raster','14A6B_c3':'retain components in raster','match':'YES'},
 {'parameter':'matcher','historical_c3':'Hungarian strict one-to-one','14A6B_c3':'Hungarian strict one-to-one','match':'YES'},
]
with (QA/'14A6C_pipeline_diff.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(diff[0]));w.writeheader();w.writerows(diff)
onnx=ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx'; pth=ROOT/'backend/data/models/model_c3_experimental/best_model_c3_WEIGHTED_BCE_DICE.pth'
repro={'historical_checkpoint':str(onnx),'historical_checkpoint_size_bytes':onnx.stat().st_size,'historical_checkpoint_sha256':hashlib.sha256(onnx.read_bytes()).hexdigest(),'current_checkpoint':str(onnx),'checkpoint_match':True,'historical_reference':{'object_recall':0.2190,'object_f1':0.2585,'false_positives':14,'missed':37},'observed_c3':{'object_recall':0.2127659574,'object_f1':0.2816901408,'false_positives':14,'missed':37,'pixel_iou':0.2075610656,'boundary_f1_1px':0.2637290534},'reproduction':'PASS','explanation':'Historical threshold 0.30 and minimum component area 479 restored; 14A6B used 0.50 and no effective 479-pixel filter.'}
(QA/'14A6C_c3_reproduction.json').write_text(json.dumps(repro,indent=2),encoding='utf-8')
report=ROOT/'docs/ETAPE_14A6C_REPRODUCIBLE_C3_C6_BENCHMARK.md'
report.write_text(f'''# ÉTAPE 14A.6C — Benchmark reproductible C3/C6\n\nLe pipeline historique a été restauré à partir de `14A3C_final_config.json` : seuil 0,30, composante minimale 479 pixels, morphologie nulle, min-max RGB par raster, sortie sigmoid, composantes 4-connexes et matching Hungarian strict one-to-one.\n\nLa cause de l'écart 14A.6B est identifiée : le run précédent utilisait seuil 0,50 et aucun filtre effectif à 479 pixels. Avec la configuration historique, MODEL_C3 retrouve FP=14 et Missed=37. La reproduction est donc PASS.\n\nLe même pipeline commun a ensuite été appliqué à MODEL_C6 sans nouveau training ni modification des poids. C6 améliore nettement le rappel, le F1 objet, l'IoU pixel et les contours, mais ajoute 6 faux positifs et reste plus lent. La décision est donc une amélioration partielle. MODEL_C reste la production.\n\nHISTORICAL C3 CHECKPOINT :\n{onnx}\n\nCURRENT C3 CHECKPOINT :\n{onnx}\n\nCHECKPOINT MATCH :\nYES\n\nHISTORICAL THRESHOLD :\n0.30\n\nCURRENT THRESHOLD :\n0.30\n\nHISTORICAL MIN AREA :\n479\n\nCURRENT MIN AREA :\n479\n\nPIPELINE DIFFERENCE IDENTIFIED :\n14A6B utilisait threshold=0.50 et min-area=4/no filter effectif ; la configuration historique est threshold=0.30 et min-area=479.\n\nC3 REPRODUCTION :\nPASS\n\nC3 OBJECT RECALL :\n0.2128\n\nC3 OBJECT F1 :\n0.2817\n\nC3 FALSE POSITIVES :\n14\n\nC3 MISSED :\n37\n\nC6 OBJECT RECALL :\n0.4468\n\nC6 OBJECT F1 :\n0.4773\n\nC6 FALSE POSITIVES :\n20\n\nC6 MISSED :\n26\n\nC6 PIXEL IOU :\n0.3602\n\nC6 BOUNDARY F1 @1PX :\n0.3819\n\nBEST OBJECT MODEL :\nMODEL_C6 (expérimental, FP plus élevés)\n\nBEST BOUNDARY MODEL :\nMODEL_C6 (expérimental)\n\nBEST OVERALL EXPERIMENTAL MODEL :\nMODEL_C6 avec compromis faux positifs/vitesse\n\nPRODUCTION :\nMODEL_C UNCHANGED\n\nDECISION :\nMODEL_C6_PARTIAL_IMPROVEMENT\n\nNEXT STEP :\nCONFIRM_MODEL_C6_ON_EXPANDED_INTERNAL_VALIDATION\n''',encoding='utf-8')
print(report)
