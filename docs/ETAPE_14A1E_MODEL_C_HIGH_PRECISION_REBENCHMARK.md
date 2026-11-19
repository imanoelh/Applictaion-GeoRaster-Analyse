# ÉTAPE 14A.1E — MODEL_C high-precision rebenchmark

MODEL_C a été relancé uniquement sur `14A_001_residential` et `14A_003_dense_urban` avec l’adapter de production, DeepLabV3 ResNet-50, ONNX Runtime CPU, preprocessing `full_raster_global_rgb_minmax_v1` et seuil 0,50. Les entrées RGB sont les mêmes rasters 512×512, sans augmentation ni redimensionnement.

Les sorties brutes sont dans `qa/14A1E_model_c_rebenchmark/` : probability maps, masks binaires, GeoJSON, overlays et temps d’inférence. Les métriques comparent directement ces sorties aux masques `masks/ground_truth_final/` de la GT approuvée 14A.1D4.

## Résultats

Le score pixel global est IoU 0,1312, Dice/F1 0,2319, précision 0,5572 et rappel 0,1465. La qualité des contours reste faible : Boundary F1 @1 px 0,0640, @2 px 0,1078, @3 px 0,1452, distance moyenne 45,53 px (15,93 m) et Hausdorff 191,86 px (67,15 m).

Le matching objet à IoU 0,30 donne 7 bâtiments correspondants sur 47, 27 faux positifs et un F1 objet de 0,1728. À IoU 0,50, 6 correspondances, 28 faux positifs et F1 objet 0,1481. Les catégories dominantes sont les bâtiments manqués et les faux positifs ; les indicateurs de fusion/fragmentation sont nuls avec la règle de matching employée.

Comparaison avec l’ancienne QA 14A.1B : IoU 0,1296 → 0,1312, Dice 0,2295 → 0,2319, Boundary F1 @1 px 0,0532 → 0,0640. MODEL_C WEIGHTS CHANGED : NO. L’écart provient de la Ground Truth nettoyée et de la qualité de mesure, pas d’une amélioration des poids.

Diagnostic prudent sur deux patches : pixel quality WEAK, boundary quality WEAK, object detection WEAK, small buildings WEAK, dense urban WEAK. Generalization : INSUFFICIENT DATA. La décision est `MODEL_C_NEEDS_FINETUNING`, mais aucun fine-tuning n’est lancé dans cette étape. Une extension de Ground Truth reste nécessaire avant une décision de production générale.

MODEL :
MODEL_C

ENGINE :
ONNX_RUNTIME_CPU

THRESHOLD :
0.50

PATCHES :
2

GT BUILDINGS :
47

PIXEL IOU :
0.1312

DICE :
0.2319

PRECISION :
0.5572

RECALL :
0.1465

F1 :
0.2319

BOUNDARY IOU :
0.0108

BOUNDARY F1 @1PX :
0.0640

BOUNDARY F1 @2PX :
0.1078

BOUNDARY F1 @3PX :
0.1452

MEAN BOUNDARY DISTANCE PX :
45.53

MEAN BOUNDARY DISTANCE M :
15.93

HAUSDORFF PX :
191.86

HAUSDORFF M :
67.15

OBJECT PRECISION :
0.2059 (IoU 0.30)

OBJECT RECALL :
0.1489 (IoU 0.30)

OBJECT F1 :
0.1728 (IoU 0.30)

MISSED BUILDINGS :
40 (IoU 0.30)

FALSE POSITIVE BUILDINGS :
27 (IoU 0.30)

MERGED BUILDINGS :
0

FRAGMENTED BUILDINGS :
0

PIXEL QUALITY :
WEAK

BOUNDARY QUALITY :
WEAK

OBJECT DETECTION :
WEAK

SMALL BUILDINGS :
WEAK

DENSE URBAN :
WEAK

MODEL_C WEIGHTS CHANGED :
NO

GROUND TRUTH :
FINAL APPROVED 14A.1D4

DECISION :
MODEL_C_NEEDS_FINETUNING

FINE_TUNING REQUIRED :
YES

READY_FOR_BATCH_EXPANSION :
NO

NEXT STEP :
PREPARE CONTROLLED MODEL_C FINE-TUNING PLAN WITH MORE GROUND TRUTH
