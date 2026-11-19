# ÉTAPE 14A.1C — Assisted Pilot Ground Truth Correction

## Périmètre

Cette étape prépare la correction humaine assistée des deux patches pilotes du dataset `maxar_v2_high_precision`. Le GeoPackage original `annotations/ground_truth_14A.gpkg` n’a pas été modifié. Aucune inférence MODEL_C/MODEL_D, aucun benchmark et aucun fine-tuning n’a été lancé.

## État audité

| Patch | Features originales | Géométries invalides | Auto-intersections | Hors bounds | Doublons |
|---|---:|---:|---:|---:|---:|
| 14A_001_residential | 25 | 1 | 1 | 3 | 0 |
| 14A_003_dense_urban | 22 | 5 | 5 | 3 | 0 |
| **Total** | **47** | **6** | **6** | **6** | **0** |

Les 11 features uniques nécessitant une intervention sont :

- `14A_001_residential`: bâtiments 6, 24 et 25 ; le bâtiment 6 cumule auto-intersection et sortie de bounds.
- `14A_003_dense_urban`: bâtiments 3, 8, 11, 12, 13, 15, 20 et 22.

Les 36 autres features sont conservées sans modification. Une comparaison WKB entre l’original et la copie de travail donne 47/47 géométries identiques.

## Artefacts créés

- Copie de travail : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1C_WORKING.gpkg`.
- Projet QGIS : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/qgis/14A1C_ground_truth_FIX.qgz`.
- Diagnostics : `qa/14A1C_diagnostics.gpkg` avec les couches `INVALID_DIAGNOSTIC`, `OUT_OF_BOUNDS_DIAGNOSTIC` et `ERROR_POINTS`.
- Suggestions séparées de clipping : `qa/14A1C_suggested_clips.geojson`. Elles ne remplacent pas la vérité terrain.
- Liste d’actions : `qa/14A1C_manual_correction_list.csv`.
- Script de revalidation post-correction : `scripts/qa_14A1C_ground_truth.py`.

Le projet QGIS conserve les deux RGB 512×512, les deux couches Ground Truth de travail et les deux pseudo-labels MODEL_C existants. Les couches diagnostiques sont regroupées et les 12 signets d’erreur sont nommés selon `PATCH__BUILDING_ID__ERROR_TYPE`. Le XML du projet extrait du QGZ est syntaxiquement valide.

## Procédure suivante

Ouvrir `14A1C_ground_truth_FIX.qgz`, activer l’édition uniquement sur les couches Ground Truth WORKING, corriger visuellement les features signalées par les signets, puis exécuter `python scripts/qa_14A1C_ground_truth.py`. Une feature ne doit être considérée corrigée qu’après validation de sa géométrie, de sa surface, de son inclusion dans les bounds et de l’absence de doublon. Le script retourne un code non nul tant qu’une anomalie reste présente.

PATCH 14A_001 FEATURES :
25
PATCH 14A_003 FEATURES :
22
UNIQUE FEATURES REQUIRING CORRECTION :
11
INVALID FEATURES :
6
OUT_OF_BOUNDS FEATURES :
6
FEATURES WITH MULTIPLE ERRORS :
1
VALID FEATURES PRESERVED :
36
QGIS FIX PROJECT :
CREATED
BOOKMARKS CREATED :
12
WORKING GPKG :
CREATED
ORIGINAL GT MODIFIED :
NO
MODEL_C :
UNCHANGED
BENCHMARK RERUN :
NO
READY_FOR_MANUAL_FIX :
YES
NEXT STEP :
14A.1D FINAL CORRECTED GT QA
