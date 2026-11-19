# ÉTAPE 13M.1A.1 — ASSISTED GROUND TRUTH CORRECTION

## Portée et résultat

Les erreurs ont été réauditées depuis `ground_truth_layers.gpkg`. Aucune feature, géométrie, statistique, annotation_status ou review_status de la source n’a été modifiée. Les corrections des sommets et le clipping des bâtiments réellement coupés au bord doivent être réalisés manuellement avec Vertex Tool dans QGIS, en comparant chaque feature au RGB.

La préparation de correction est disponible :

- CSV : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qa_13M1A/ground_truth_errors.csv` (25 features uniques; `BOTH` signifie auto-intersection et dépassement des bounds).
- GeoPackage diagnostique séparé : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qa_13M1A/ground_truth_errors.gpkg`.
- Projet QGIS : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_ground_truth_FIX.qgz`.

Le GeoPackage diagnostic contient `self_intersections` (12 polygones), `out_of_bounds` (14 polygones) et `error_points` (25 points identifiants). Il conserve `patch_id`, `layer_name`, `fid`, `building_id`, `error_type`, `error_detail`, `x`, `y`. Le projet de correction conserve les six groupes avec RGB et Ground Truth; chaque groupe contient un groupe `ERROR_LAYER` avec symboles distincts. Les erreurs sont accessibles par identification des points et par 25 bookmarks, nommés avec patch, building_id, fid et type d’erreur. Les couches diagnostiques ne modifient pas les features Ground Truth.

Le projet `13M_ground_truth_FIX.qgz` a été rouvert et contrôlé par l’API QGIS 3.40.14 : les 18 instances de couches d’erreur sont valides, les six RGB sont visibles, les six couches Ground Truth et leurs comptes sont conservés, et les 31 bookmarks (6 d’origine + 25 erreurs) sont présents. Le projet a été lancé dans QGIS Desktop pour la correction humaine.

## Résultats de l’audit avant/après

La correction humaine n’a pas encore été appliquée. Les valeurs « après » restent donc identiques aux valeurs « avant » : 12 auto-intersections, 14 features hors bounds, zéro doublon exact, 68 bâtiments. Le CSV compte 25 features uniques car une feature cumule les deux erreurs.

Couches non validables :

- Patch 01 `GT_2024_difficult_02`: 5 géométries auto-intersectées (building_id 3, 4, 6, 11, 12); hors bounds (10, 15, 16).
- Patch 02 `GT_2024_industrial_02`: hors bounds (building_id 1).
- Patch 03 `GT_2024_residential_02`: auto-intersections (2, 7); hors bounds (4, 6, 7, 13, 15). Le building_id 7 cumule les deux erreurs.
- Patch 04 `GT_2025_difficult_02`: auto-intersections (2, 5, 6, 7); hors bounds (3, 10, 19).
- Patch 05 `GT_2025_industrial_02`: hors bounds (building_id 1).
- Patch 06 `GT_2025_residential_02`: auto-intersection (building_id 6); hors bounds (building_id 7).

Les 6 masques `qa_13M1A/masks/*` produits lors de l’étape antérieure restent des aperçus QA provisoires uniquement. Aucun masque final n’a été régénéré, puisque les contrôles de géométrie échouent. Ils ne doivent pas être utilisés pour l’entraînement ou l’évaluation.

## Métadonnées et verrou TEST

Le manifeste confirme `TEST_LOCKED`, `training_use_prohibited=true` et `augmentation_training_prohibited=true`. Le split n’a pas été modifié. Les métadonnées existantes restent désynchronisées (elles déclarent 0 feature / NOT_ANNOTATED); elles ne sont pas synchronisées tant que les géométries ne passent pas la QA et que les statuts ne peuvent pas être validés.

Les statuts Ground Truth restent `ANNOTATED` / `NOT_REVIEWED`. Aucun patch n’est `VALIDATED`. Après édition humaine, enregistrer les edits, sortir du mode édition, rouvrir le projet et relancer la QA avant de générer les masques finaux et synchroniser les metadata.

MODEL_C : NOT RUN
MODEL_D : NOT RUN
FINE TUNING : NOT RUN

TOTAL GT BUILDINGS BEFORE :
68

SELF_INTERSECTIONS BEFORE :
12

OUT_OF_BOUNDS BEFORE :
14

SELF_INTERSECTIONS AFTER :
12 (aucune correction humaine appliquée)

OUT_OF_BOUNDS AFTER :
14 (aucune correction humaine appliquée)

DUPLICATES AFTER :
0

TOTAL GT BUILDINGS AFTER :
68

PATCH 01 :
NEEDS_CORRECTION

PATCH 02 :
NEEDS_CORRECTION

PATCH 03 :
NEEDS_CORRECTION

PATCH 04 :
NEEDS_CORRECTION

PATCH 05 :
NEEDS_CORRECTION

PATCH 06 :
NEEDS_CORRECTION

GT MASKS :
0 / 6 finals (6 aperçus provisoires antérieurs)

MASK ALIGNMENT :
FAILED

METADATA SYNC :
FAILED

TEST SPLIT :
LOCKED

MODEL_C :
NOT RUN

MODEL_D :
NOT RUN

READY_FOR_MODEL_C_VS_MODEL_D_BENCHMARK :
NO

NEXT STEP :
CORRECT REMAINING GROUND TRUTH
