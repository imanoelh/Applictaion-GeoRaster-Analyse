# ÉTAPE 14A.1D3 — Surgical Ground Truth geometry correction

## Candidate isolé

Une nouvelle copie a été créée à partir du WORKING courant :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1D3_CANDIDATE.gpkg`

Le WORKING, l’original et les 41 features non ciblées n’ont pas été modifiés. La comparaison WKB donne `41 / 41` features non ciblées identiques.

## Corrections appliquées au Candidate uniquement

Les quatre features hors bounds ont reçu une intersection stricte avec les bounds raster EPSG:32637. Les pertes de surface sont faibles : 0,0578 %, 0,0028 %, 0,0013 % et 0,1785 %. Les déplacements de centroïde restent inférieurs à 0,022 m ; les quatre clips sont donc marqués `SAFE_CLIP=YES`.

Les bâtiments 3 et 15 ont reçu `make_valid` GEOS. Le résultat est un MultiPolygon valide à deux composants dans chaque cas, conservé sans fusion arbitraire. Les variations de surface sont respectivement +0,0063 % et +0,0438 %, avec des déplacements de centroïde inférieurs à 0,005 m. Les deux corrections sont marquées `SAFE_SELF_INTERSECTION_FIX=YES`.

Le type de géométrie de la couche 14A_003 candidate accepte explicitement le mélange Polygon/MultiPolygon afin de conserver les WKB des features non ciblées.

## QA Candidate

La QA complète du Candidate passe : 25 features pour 14A_001, 22 pour 14A_003, géométries valides, non vides, surfaces positives, zéro auto-intersection, zéro hors bounds et zéro doublon.

Le projet QGIS `qgis/14A1D3_SURGICAL_CORRECTION_REVIEW.qgz` a été créé et rouvert avec QGIS 3.40.14. Il contient les RGB, l’ancien WORKING GT, le Candidate GT, les six corrections, les deux points d’auto-intersection, les bounds raster et six bookmarks de revue.

Artefacts :

- `qa/14A1D3_correction_summary.json`
- `qa/14A1D3_out_of_bounds_vertices.csv`
- `qa/14A1D3_self_intersection_details.csv`
- `qa/14A1D3_candidate_geometry_qa.json`

MODEL_C n’a pas été exécuté. Aucun benchmark ni fine-tuning n’a été lancé. Une approbation visuelle finale reste recommandée avant tout rebenchmark.

TARGET FEATURES :
6

OUT_OF_BOUNDS TARGETS :
4

SELF_INTERSECTION TARGETS :
2

SAFE CLIPS :
4 / 4

SAFE SELF-INTERSECTION FIXES :
2 / 2

INVALID GEOMETRIES AFTER :
0

SELF INTERSECTIONS AFTER :
0

OUT OF BOUNDS AFTER :
0

EMPTY GEOMETRIES AFTER :
0

ZERO AREA AFTER :
0

EXACT DUPLICATES AFTER :
0

NON-TARGET FEATURES CHANGED :
0

CANDIDATE GPKG :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1D3_CANDIDATE.gpkg

QGIS REVIEW PROJECT :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/qgis/14A1D3_SURGICAL_CORRECTION_REVIEW.qgz

MODEL_C :
UNCHANGED

MODEL_C RE-RUN :
NO

READY_FOR_FINAL_VISUAL_REVIEW :
YES

READY_FOR_MODEL_C_REBENCHMARK :
NO

NEXT STEP :
14A.1D4 FINAL VISUAL APPROVAL
