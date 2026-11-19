# ETAPE 14A.1 - High precision Ground Truth QA

Date : 2026-10-26

## Audit des deux patches pilotes

Le manifest contient exactement deux patches propres :

| Patch | Source | Scene | Difficulte | MODEL_C candidates | Raster |
|---|---|---|---:|---:|---|
| 14A_001_residential | zone_1_residential.tif | RESIDENTIAL | MEDIUM | 17 | 512x512, EPSG:32637 |
| 14A_003_dense_urban | zone_3_dense_roofs.tif | DENSE_URBAN | HARD | 17 | 512x512, EPSG:32637 |

Les transforms, resolutions 0,35 m, CRS et bounds des RGB et pseudo-masques sont identiques. Les pseudo-masques contiennent uniquement 0/1.

## Etat de la Ground Truth humaine

Les deux couches du GeoPackage `annotations/ground_truth_14A.gpkg` sont de type Polygon EPSG:32637, mais leur nombre de features est encore zero. Aucune annotation humaine n'a donc pu etre controlee, corrigee ou validee. Les pseudo-labels MODEL_C restent des pre-annotations et ne sont pas convertis automatiquement en Ground Truth.

Le projet QGIS `qgis/14A_building_ground_truth.qgz` reference pour chaque patch le RGB, le masque pseudo-label MODEL_C et la couche Ground Truth editable. La possibilite de masquer le pseudo-label est preparee dans le projet. La persistence d'une feature apres edition n'est pas validee tant qu'aucune annotation humaine n'est saisie.

## QA et metriques

L'alignement technique RGB / pseudo-masque / masque GT vide est valide. Les tests de geometrie GT, les masques GT de batiments, IoU, Dice, Precision, Recall et Boundary F1 restent non calculables tant que les deux patches ne sont pas annotés humainement. Aucun score n'est invente.

L'expansion 20-30 patches n'a pas ete lancee : elle depend de la validation des deux pilotes. Les deux sources qui recoupaient 13M/13Q restent exclues et documentees ; aucune source legacy n'est reutilisee.

PILOT PATCHES :
2

PILOT PATCHES ANNOTATED :
0

PILOT PATCHES VALIDATED :
0

INVALID GEOMETRIES :
0 (aucune feature GT presente)

OUT_OF_BOUNDS :
0 (aucune feature GT presente)

DUPLICATES :
0 (aucune feature GT presente)

GT MASKS :
0 / 2

MASK ALIGNMENT :
VALIDATED

ANNOTATION WORKFLOW :
FAILED (annotation humaine et persistence non encore testees)

MODEL_C PILOT IOU :
NOT_COMPUTED - Ground Truth absente

MODEL_C PILOT DICE :
NOT_COMPUTED - Ground Truth absente

MODEL_C PILOT BOUNDARY F1 :
NOT_COMPUTED - Ground Truth absente

DOMINANT MODEL_C ERRORS :
NOT_CLASSIFIED - Ground Truth absente

NEW PATCHES GENERATED :
0

NEW PATCHES AFTER LEAKAGE FILTER :
0

RESIDENTIAL :
1 pilote non annote

INDUSTRIAL :
0

DIFFICULT/MIXED :
1 pilote non annote (DENSE_URBAN)

SMALL BUILDINGS :
NOT_CLASSIFIED

LARGE ROOFS :
NOT_CLASSIFIED

DARK ROOFS :
NOT_CLASSIFIED

LEGACY TEST LEAKAGE :
0

DATASET TOTAL PATCHES :
2

DATASET STATUS :
NEEDS_CORRECTION

PRODUCTION MODIFIED :
NO

MODEL_C :
UNCHANGED

NEXT STEP :
14A.2 BATCH GROUND TRUTH ANNOTATION
