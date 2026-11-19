# ÉTAPE 14A.5A-QGIS-FIX — DIAGNOSE AND REBUILD QGIS PROJECT

## Audit du projet original

L’archive QGZ originale était lisible et son XML était bien formé. Les cinq rasters existent, sont lisibles avec Rasterio, mesurent 512x512, ont trois bandes et sont en EPSG:32637. Les cinq couches Ground Truth existent et sont vides.

La cause bloquante était la structure GeoPackage minimale non conforme attendue par le provider OGR/QGIS : absence de `gpkg_ogr_contents`, contraintes GeoPackage incomplètes et définition de colonne géométrique simplifiée. Le projet XML minimal marquait aussi toutes les couches visibles au démarrage et ne définissait pas d’emprise initiale explicite. Ces deux facteurs pouvaient bloquer le chargement du provider autour de 10%.

Le GeoPackage a été reconstruit dans la nouvelle copie uniquement, avec un schéma polygonal GeoPackage complet, sans modifier les données originales. Le nouveau projet contient uniquement 10 couches, utilise des chemins absolus et n’a aucune couche mémoire.

Le démarrage active seulement `14A2_2024_06_RGB` et `14A2_2024_06_GROUND_TRUTH`; les huit autres couches sont désactivées. L’emprise initiale est limitée au raster 14A2_2024_06.

ORIGINAL PROJECT VALID :
NO

BLOCKING CAUSE :
GeoPackage Ground Truth non conforme au schéma OGR/QGIS complet + XML minimal sans emprise initiale et toutes les couches activées

RGB SOURCES VALID :
5 / 5

GT SOURCES VALID :
5 / 5

BROKEN LAYERS :
0

MISSING SOURCES :
0

NEW PROJECT CREATED :
YES

NEW PROJECT PATH :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/qgis/14A5A_NEW_PATCH_EXPANSION_GT_FIXED.qgz

PROJECT LOAD TEST :
PASS

READY_FOR_MANUAL_ANNOTATION :
YES
