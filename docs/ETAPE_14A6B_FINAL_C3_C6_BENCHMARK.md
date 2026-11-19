# ÉTAPE 14A.6B — Benchmark strict MODEL_C3 vs MODEL_C6

Le benchmark a été exécuté sur les deux patches verrouillés `14A_001_residential` et `14A_003_dense_urban`, sans modifier les modèles, les seuils, les Ground Truth ou la production.

Le protocole utilise un seuil binaire de 0,50, une matrice IoU complète et une affectation Hungarian one-to-one. Les métriques pixel et contour ont été calculées pour chaque patch. Les fichiers CSV et la planche comparative ont été produits.

Le contrôle obligatoire de reproduction MODEL_C3 échoue avec le protocole actuellement disponible. La référence historique attend `Object Recall=0.2190`, `Object F1=0.2585`, `FP=14`, `Missed=37`. Le run actuel obtient `Recall=0.2128`, `F1=0.2105`, `FP=38`, `Missed=37`. Le rappel et les bâtiments manqués sont proches, mais la différence de faux positifs et de F1 est trop importante pour déclarer la comparaison C6 valide.

Le résultat C6 observé dans ce run est donc indicatif uniquement : Recall 0.5319, F1 0.4673, FP 35, Missed 22, Pixel IoU 0.3561 et Boundary F1 @1px 0.3941. Il ne peut pas être utilisé pour une promotion ou une conclusion scientifique avant alignement exact du post-traitement historique MODEL_C3.

Livrables :

- `qa/14A6B_c3_c6_object_metrics.csv`
- `qa/14A6B_c3_c6_pixel_metrics.csv`
- `qa/14A6B_c3_c6_boundary_metrics.csv`
- `qa/14A6B_c3_c6_performance.json`
- `qa/14A6B_c3_c6_contact_sheet.png`

MODEL_C3 REPRODUCTION :
FAIL

MODEL_C3 OBJECT RECALL :
0.2128 (référence 0.2190)

MODEL_C6 OBJECT RECALL :
0.5319 (indicatif, benchmark invalide)

MODEL_C3 OBJECT F1 :
0.2105 (référence 0.2585)

MODEL_C6 OBJECT F1 :
0.4673 (indicatif, benchmark invalide)

MODEL_C3 FALSE POSITIVES :
38 (référence 14)

MODEL_C6 FALSE POSITIVES :
35 (indicatif)

MODEL_C3 MISSED :
37

MODEL_C6 MISSED :
22 (indicatif)

MODEL_C3 BOUNDARY F1 @1PX :
0.2140

MODEL_C6 BOUNDARY F1 @1PX :
0.3941 (indicatif)

MODEL_C3 PIXEL IOU :
0.1819

MODEL_C6 PIXEL IOU :
0.3561 (indicatif)

MODEL_C3 CPU INFERENCE :
4.356 s/patch

MODEL_C6 CPU INFERENCE :
6.878 s/patch

BEST OBJECT MODEL :
NOT_DECLARED — reproduction C3 échouée

BEST BOUNDARY MODEL :
NOT_DECLARED — reproduction C3 échouée

BEST OVERALL EXPERIMENTAL MODEL :
NOT_DECLARED — reproduction C3 échouée

PRODUCTION :
MODEL_C UNCHANGED

DECISION :
BENCHMARK_INVALID

NEXT STEP :
ALIGNER_LE_POSTPROCESSING_HISTORIQUE_MODEL_C3_AVANT_REBENCHMARK
