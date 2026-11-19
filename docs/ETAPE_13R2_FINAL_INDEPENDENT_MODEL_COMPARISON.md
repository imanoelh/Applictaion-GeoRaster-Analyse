# ÉTAPE 13R.2 — Final independent MODEL_C / MODEL_F / MODEL_F2 test

## Protocole figé

Les six patches TEST historiques 13M ont été utilisés exclusivement pour ce test final. Leurs SHA-256, source raster, bounds et split ont été vérifiés avant calcul : aucun hash TEST ne figure dans le manifeste 13R et aucune donnée TEST n'a été utilisée pour l'entraînement, la validation ou le choix du seuil. `TEST_LEAKAGE = 0`.

Paramètres figés : MODEL_C production avec seuil 0,50 et min/max global ; MODEL_F original avec son seuil 0,35 ; MODEL_F2 `best_model_f2.pth` avec le seuil 0,35 enregistré dans `model_f2_threshold_candidate.json`. Aucun tuning ou post-traitement n'a été appliqué sur les résultats TEST.

Les sorties sont dans `backend/data/models/building/experimental/benchmark_13R2_FINAL/` : probability map, masque, GeoJSON, overlay et contact sheet par patch, plus `global_contact_sheet.png` et `summary.json`.

## Résultats

MODEL_F2 ne satisfait pas les critères de remplacement général sur ce TEST indépendant : IoU globale et recall globale inférieurs à MODEL_C/MODEL_F, IoU industrielle très inférieure à MODEL_C, et qualité de contour inférieure. MODEL_F reste le meilleur sur les scènes résidentielles. MODEL_C reste le meilleur moteur industriel et possède les meilleurs contours globaux. F2 est le plus rapide, mais sa vitesse ne compense pas la perte de qualité.

Le comptage d'objets utilise la même règle pour les trois moteurs : composantes 8-connexes, une composante prédite est associée à un bâtiment GT lorsqu'elle intersecte sa composante GT. Les résultats servent à la comparaison relative, pas à une nouvelle calibration.

TEST LEAKAGE :
0

TEST PATCHES :
6

TEST GT BUILDINGS :
66 composantes GT

MODEL_C GLOBAL IOU :
0.447679

MODEL_F GLOBAL IOU :
0.459497

MODEL_F2 GLOBAL IOU :
0.384393

MODEL_C GLOBAL DICE :
0.556622

MODEL_F GLOBAL DICE :
0.585606

MODEL_F2 GLOBAL DICE :
0.511796

MODEL_C GLOBAL PRECISION :
0.586188

MODEL_F GLOBAL PRECISION :
0.690218

MODEL_F2 GLOBAL PRECISION :
0.745785

MODEL_C GLOBAL RECALL :
0.573298

MODEL_F GLOBAL RECALL :
0.673049

MODEL_F2 GLOBAL RECALL :
0.478381

MODEL_C INDUSTRIAL IOU :
0.810741

MODEL_F INDUSTRIAL IOU :
0.372109

MODEL_F2 INDUSTRIAL IOU :
0.274278

MODEL_C RESIDENTIAL IOU :
0.144758

MODEL_F RESIDENTIAL IOU :
0.514684

MODEL_F2 RESIDENTIAL IOU :
0.395999

MODEL_C BOUNDARY F1 :
0.356919

MODEL_F BOUNDARY F1 :
0.292849

MODEL_F2 BOUNDARY F1 :
0.238991

MODEL_C DETECTED BUILDINGS :
44

MODEL_F DETECTED BUILDINGS :
61

MODEL_F2 DETECTED BUILDINGS :
57

MODEL_C MISSED BUILDINGS :
22

MODEL_F MISSED BUILDINGS :
5

MODEL_F2 MISSED BUILDINGS :
9

MODEL_C EXTRA COMPONENTS :
42

MODEL_F EXTRA COMPONENTS :
55

MODEL_F2 EXTRA COMPONENTS :
28

BEST INDUSTRIAL :
MODEL_C

BEST RESIDENTIAL :
MODEL_F

BEST SMALL BUILDINGS :
MODEL_F (highest detected GT component count)

BEST LARGE BUILDINGS :
MODEL_C on industrial roofs; MODEL_F on residential roofs

BEST BUILDING SEPARATION :
MODEL_C for industrial contours; MODEL_F2 has the fewest extra components

BEST BOUNDARY QUALITY :
MODEL_C

LOWEST FALSE POSITIVES :
MODEL_F2 by extra component count

BEST SPEED :
MODEL_F2 (~0.94 s/patch; MODEL_F ~1.05; MODEL_C ~3.29)

BEST OVERALL BUILDING FOOTPRINT QUALITY :
MODEL_C for the GeoRaster production industrial use case

FINAL DECISION :
MODEL_C_REMAINS_BEST_GENERAL_MODEL

PRODUCTION MODIFIED :
NO

MODEL_C DEFAULT :
YES

NEXT STEP :
KEEP MODEL_C PRODUCTION
