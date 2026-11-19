# ÉTAPE 14A.3E — Balanced Dataset Expansion Strategy

## Périmètre

Cette étape prépare les éléments nécessaires à une future expansion équilibrée du dataset. Aucun entraînement n'a été lancé et aucun poids ou modèle n'a été modifié. MODEL_C reste la production ; MODEL_C2, MODEL_C3 et MODEL_C4 restent inchangés.

## Analyse des faux positifs MODEL_C4

Le benchmark verrouillé a été rejoué avec le même checkpoint ONNX, les mêmes deux rasters, les masques GT finaux et le seuil 0,30. Le matching est one-to-one avec IoU >= 0,30 ; une prédiction non appariée est comptée comme faux positif, y compris lorsqu'elle recouvre partiellement un bâtiment mais ne satisfait pas le seuil.

Résultat reproductible : 96 prédictions, 14 appariées, 82 non appariées. Les 82 prédictions non appariées ont été caractérisées dans `qa/14A3E_model_c4_false_positive_analysis.csv`. Les catégories sont heuristiques et servent à orienter la revue humaine : elles ne constituent pas une vérité terrain.

Catégories principales : ROOF_LIKE_TEXTURE (53), BRIGHT_SURFACE (9), OTHER (9), BARE_SOIL (5), ROAD (3), PARKING (2), SHADOW (1).

## Expansion proposée

Les 11 patches TRAIN restants ont été conservés comme seule source pour les nouveaux négatifs. Quatre patches prioritaires ont été sélectionnés : `14A2_2025_15`, `14A2_2024_14`, `14A2_2025_12` et `14A2_2024_11`. Les crops 256x256 générés dans `balanced_dataset_14A3E/hard_negatives/` sont des propositions `HARD_NEGATIVE_PENDING_REVIEW`; ils doivent être validés humainement avant toute utilisation pour l'entraînement.

Le sous-ensemble de 20 positifs difficiles est un sous-ensemble de crops positifs déjà présents. Il n'ajoute pas de géométrie inventée. Les masques et les annotations existants restent inchangés.

Trois configurations de sampling sont préparées : 60/40, 50/50 et 40/60 positif/négatif. Le sur-échantillonnage est explicitement indiqué pour les négatifs lorsque le nombre de fichiers uniques ne suffit pas.

## Projet QGIS

`qgis/14A3E_TARGETED_DATASET_EXPANSION.qgz` contient uniquement les quatre RGB TRAIN prioritaires et quatre couches `TARGET_GT` polygonales vides en EPSG:32637. Les couches de prédiction ne sont pas chargées. Les couches TARGET_GT sont volontairement vides et éditables pour la complétion manuelle.

## Décision

Le dataset n'est pas déclaré prêt pour fine-tuning : les hard negatives proposés n'ont pas encore reçu une validation humaine et les couches TARGET_GT sont vides. La prochaine étape est donc la complétion manuelle ciblée, puis une QA d'alignement et de séparation avant tout entraînement.

REMAINING TRAIN PATCHES :
11
PATCHES SELECTED FOR TARGETED EXPANSION :
14A2_2025_15, 14A2_2024_14, 14A2_2025_12, 14A2_2024_11
MODEL_C4 FALSE POSITIVES ANALYZED :
82
MAIN FALSE POSITIVE CATEGORIES :
ROOF_LIKE_TEXTURE (53), BRIGHT_SURFACE (9), OTHER (9), BARE_SOIL (5), ROAD (3), PARKING (2), SHADOW (1)
CURRENT POSITIVE CROPS :
196
CURRENT NEGATIVE CROPS :
3
PROPOSED POSITIVE CROPS :
216
PROPOSED NEGATIVE CROPS :
44
HARD POSITIVE CROPS :
20
HARD NEGATIVE CROPS :
44
SAMPLING CONFIG A :
60% POSITIVE / 40% NEGATIVE (216 / 144)
SAMPLING CONFIG B :
50% POSITIVE / 50% NEGATIVE (216 / 216)
SAMPLING CONFIG C :
40% POSITIVE / 60% NEGATIVE (144 / 216)
VAL LEAKAGE :
0
LOCKED TEST LEAKAGE :
0
MODEL_C :
UNCHANGED
MODEL_C2 :
UNCHANGED
MODEL_C3 :
UNCHANGED
MODEL_C4 :
UNCHANGED
TRAINING STARTED :
NO
BALANCED_DATASET_READY :
NO
NEXT STEP :
14A.3F MODEL_C5 BALANCED FINE-TUNING /
14A.3E2 TARGETED MANUAL DATA COMPLETION
