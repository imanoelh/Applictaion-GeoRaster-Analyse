# ÉTAPE 14A.1C-R — Repair corrupted QGIS fix project

## Diagnostic

Le fichier original `14A1C_ground_truth_FIX.qgz` faisait 16 548 octets et commençait par la signature `1F 8B 08`, qui correspond à une archive **GZIP**, pas à une archive ZIP/QGZ. La lecture ZIP échouait avec `End of Central Directory record could not be found`. Son contenu était un tar.gz contenant `14A1C_ground_truth_FIX.qgs` et `JDdLfu_styles.db`, d’où l’erreur QGIS « Unable to unzip file ».

Le fichier original a été conservé pour diagnostic. Le nouveau paquet a été reconstruit en ZIP QGIS valide et ensuite réécrit par QGIS 3.40.14 afin de produire le format QGZ natif.

## Validation QGIS 3.40.14

Le projet reconstruit a été ouvert avec l’interpréteur PyQGIS de QGIS 3.40.14, puis fermé et rouvert. Résultats :

- lecture initiale : succès, sans erreur QGIS ;
- relecture après fermeture : succès ;
- 9 couches valides : 2 RGB, 2 pseudo-masques MODEL_C, 2 Ground Truth WORKING, 3 diagnostics ;
- projet et couches en EPSG:32637 ;
- les deux couches Ground Truth passent `startEditing()` puis `rollBack()` sans modifier de géométrie ;
- les 12 bookmarks d’assistance sont présents avec un cadrage autour de la feature concernée ;
- archive ZIP testée avec `ZipFile.testzip()`: aucune erreur ;
- aucune source de couche cassée.

Les styles ont été appliqués : Ground Truth vert transparent, invalides rouges, hors bounds orange, points d’erreur rouge vif et pseudo-masques MODEL_C violets semi-transparents. Les rasters RGB sont visibles par défaut et les pseudo-masques restent disponibles dans l’arbre des couches.

OLD PROJECT ZIP VALID :
NO

CORRUPTION CAUSE :
FICHIER GZIP/TAR RENOMMÉ .QGZ AU LIEU D’UNE ARCHIVE ZIP QGIS

NEW PROJECT :
qgis/14A1C_ground_truth_FIX_REBUILT.qgz

PROJECT OPEN :
SUCCESS

RGB LAYERS :
2 / 2

GROUND TRUTH WORKING :
2 / 2

PSEUDO MASKS :
2 / 2

DIAGNOSTIC LAYERS :
3 (INVALID, OUT_OF_BOUNDS, ERROR_POINTS)

BOOKMARKS :
12 / 12

GROUND TRUTH EDITABLE :
YES

CRS :
EPSG:32637

BROKEN LAYERS :
0 / 9

ORIGINAL GT MODIFIED :
NO

WORKING GT MODIFIED :
NO

MODEL_C :
UNCHANGED

READY_FOR_MANUAL_FIX :
YES
