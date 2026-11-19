# ETAPE 14A - High precision local Building dataset

Date : 2026-10-26

## Etat de preparation

Le dataset experimental a ete cree dans :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/`

Les sous-dossiers demandes sont presents : `images`, `masks`, `annotations`, `pseudo_labels`, `qa`, `manifests`, `splits`, `qgis` et `diagnostics`.

Deux scenes Maxar propres etaient disponibles sans intersection spatiale avec les sources 13M/13Q/13R :

- `14A_001_residential` : RESIDENTIAL, difficulte MEDIUM ;
- `14A_003_dense_urban` : DENSE_URBAN, difficulte HARD.

Deux autres sources disponibles ont ete exclues apres controle des bounds : `14A_002_difficult_sparse` recouvre une zone 13M/13Q et `14A_004_road_confusion` recouvre une zone 13M. Elles sont documentees dans `diagnostics/excluded_legacy_patches.json` et ne figurent ni dans le manifest final ni dans les splits.

La cible de 100 a 300 patches n'a pas ete inventee : aucune autre zone Maxar independante n'est presente dans cette copie. Il faut fournir de nouvelles zones source avant d'atteindre cette cible.

## Integrite raster et pseudo-labels

Les deux patches retenus sont des GeoTIFF RGB 512 x 512, EPSG:32637, pixel size 0,35 m. Les transforms, bounds et CRS sont conserves sans resampling.

MODEL_C production a ete utilise uniquement pour generer les pre-annotations dans `pseudo_labels/model_c/`. Pour chaque patch retenu sont presents :

- une carte de probabilite float32 ;
- un masque binaire 0/1 ;
- un GeoJSON de pre-annotation ;
- un overlay QA.

Les masques `masks/` restent vides (zero) car aucune verite terrain humaine n'est encore validee. Les pseudo-labels ne sont jamais ecrits dans `annotations/`.

## Annotation et QGIS

Le GeoPackage `annotations/ground_truth_14A.gpkg` contient deux couches Polygon EPSG:32637, vides et editables, avec les champs `patch_id`, `building_id`, `scene_type`, `annotation_status`, `review_status`, `annotator` et `label_source`.

Le projet `qgis/14A_building_ground_truth.qgz` reference les deux rasters RGB et les deux couches Ground Truth. Les pseudo-labels sont conserves separement et peuvent etre masques pendant la revue.

## Splits et QA

Les patches restent `UNASSIGNED`. Aucun split TRAIN/VAL/TEST_NEW n'est cree avant validation humaine et separation geographique. Le manifest d'exclusion contient les hashes et bounds des sources legacy controlees. Pour les patches retenus : fuite legacy = 0 et fuite spatiale TRAIN/VAL/TEST = 0.

Le diagnostic `qa/model_c_error_analysis.json` est cree mais reste en attente de Ground Truth humaine. Aucun fine-tuning et aucun entrainement n'a ete lance.

## Non-regression

MODEL_C, ses poids, son threshold, son preprocessing, le registry production, MODEL_D/E/F/F2, GEE, les indices, les classifications, les exports, l'API et le frontend n'ont pas ete modifies.

TOTAL PATCHES GENERATED :
2

TARGET PATCHES :
100-300

RESIDENTIAL PATCHES :
1

INDUSTRIAL PATCHES :
0

DIFFICULT/MIXED PATCHES :
1

SMALL BUILDING PATCHES :
0 (non classe avant Ground Truth humaine)

MEDIUM BUILDING PATCHES :
0 (non classe avant Ground Truth humaine)

LARGE BUILDING PATCHES :
0 (non classe avant Ground Truth humaine)

MODEL_C PSEUDO LABELS :
2

GROUND TRUTH NOT REVIEWED :
2

GROUND TRUTH ACCEPTED :
0

GROUND TRUTH VALIDATED :
0

GROUND TRUTH REJECTED :
0

VALID GT MASKS :
0 (aucune annotation humaine validee)

TRAIN PATCHES :
0

VAL PATCHES :
0

TEST_NEW PATCHES :
0

LEGACY TEST LEAKAGE :
0

TRAIN/VAL/TEST SPATIAL LEAKAGE :
0

GEOMETRY QA :
VALIDATED (couches Ground Truth Polygon vides, aucun objet invalide)

MASK ALIGNMENT :
VALIDATED (pseudo-labels 512x512 alignes ; masques GT en attente)

MODEL_C ERROR ANALYSIS :
CREATED (en attente de Ground Truth)

DATASET STATUS :
READY_FOR_ANNOTATION

PRODUCTION MODIFIED :
NO

MODEL_C :
PRODUCTION UNCHANGED

NEXT STEP :
14A.1 HIGH-PRECISION GROUND TRUTH QA
