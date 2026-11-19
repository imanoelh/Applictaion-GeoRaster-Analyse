# ÉTAPE 14A.6C — Benchmark reproductible C3/C6

Le pipeline historique a été restauré à partir de `14A3C_final_config.json` : seuil 0,30, composante minimale 479 pixels, morphologie nulle, min-max RGB par raster, sortie sigmoid, composantes 4-connexes et matching Hungarian strict one-to-one.

La cause de l'écart 14A.6B est identifiée : le run précédent utilisait seuil 0,50 et aucun filtre effectif à 479 pixels. Avec la configuration historique, MODEL_C3 retrouve FP=14 et Missed=37. La reproduction est donc PASS.

Le même pipeline commun a ensuite été appliqué à MODEL_C6 sans nouveau training ni modification des poids. C6 améliore nettement le rappel, le F1 objet, l'IoU pixel et les contours, mais ajoute 6 faux positifs et reste plus lent. La décision est donc une amélioration partielle. MODEL_C reste la production.

HISTORICAL C3 CHECKPOINT :
D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10\backend\data\models\model_c3_experimental\model_c3.onnx

CURRENT C3 CHECKPOINT :
D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10\backend\data\models\model_c3_experimental\model_c3.onnx

CHECKPOINT MATCH :
YES

HISTORICAL THRESHOLD :
0.30

CURRENT THRESHOLD :
0.30

HISTORICAL MIN AREA :
479

CURRENT MIN AREA :
479

PIPELINE DIFFERENCE IDENTIFIED :
14A6B utilisait threshold=0.50 et min-area=4/no filter effectif ; la configuration historique est threshold=0.30 et min-area=479.

C3 REPRODUCTION :
PASS

C3 OBJECT RECALL :
0.2128

C3 OBJECT F1 :
0.2817

C3 FALSE POSITIVES :
14

C3 MISSED :
37

C6 OBJECT RECALL :
0.4468

C6 OBJECT F1 :
0.4773

C6 FALSE POSITIVES :
20

C6 MISSED :
26

C6 PIXEL IOU :
0.3602

C6 BOUNDARY F1 @1PX :
0.3819

BEST OBJECT MODEL :
MODEL_C6 (expérimental, FP plus élevés)

BEST BOUNDARY MODEL :
MODEL_C6 (expérimental)

BEST OVERALL EXPERIMENTAL MODEL :
MODEL_C6 avec compromis faux positifs/vitesse

PRODUCTION :
MODEL_C UNCHANGED

DECISION :
MODEL_C6_PARTIAL_IMPROVEMENT

NEXT STEP :
CONFIRM_MODEL_C6_ON_EXPANDED_INTERNAL_VALIDATION
