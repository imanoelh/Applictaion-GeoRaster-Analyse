# ÉTAPE 14A.1D3-R — Repair empty QGIS surgical review project

## Diagnostic

Le QGZ original était une archive ZIP valide et contenait 9 `maplayer` sérialisés ainsi que 6 bookmarks. La cause de l’interface vide était l’absence totale de nœuds `layer-tree-layer` : les couches existaient dans `projectlayers`, mais aucune n’était inscrite dans l’arbre de légende QGIS. Le panneau Layers restait donc vide malgré un projet lisible.

## Reconstruction

Le projet reconstruit a été créé sans toucher aux données. Les 9 couches ont été ajoutées explicitement à l’arbre QGIS :

- 2 RGB visibles ;
- 2 anciennes couches WORKING GT orange ;
- 2 couches Candidate vertes ;
- `SURGICAL_CORRECTIONS` (6 features) ;
- `SELF_INTERSECTION_POINTS` (2 points) ;
- `RASTER_BOUNDS` (6 emprises).

Les six bookmarks de revue sont présents et utilisent le CRS projet EPSG:32637. Les sources relatives sont toutes valides. Le projet a été ouvert, sauvegardé, fermé et rouvert avec QGIS 3.40.14/PyQGIS : 9 couches dans le panneau après chaque lecture.

Le Candidate GPKG n’a pas été modifié : les 6 WKB ciblés correspondent aux WKB attendus et les 41 features non ciblées restent inchangées. Le WORKING GT et MODEL_C restent inchangés.

OLD REVIEW PROJECT LAYERS :
9 sérialisés, 0 dans le layer tree

EMPTY PROJECT CAUSE :
ABSENCE DES NŒUDS LAYER-TREE-LAYER DANS LE PROJECT.QGS

NEW REVIEW PROJECT :
qgis/14A1D3_SURGICAL_CORRECTION_REVIEW_REBUILT.qgz

PROJECT OPEN :
SUCCESS

PROJECT REOPEN :
SUCCESS

RGB LAYERS :
2 / 2

OLD GT LAYERS :
2 / 2

CANDIDATE GT LAYERS :
2 / 2

DIAGNOSTIC LAYERS :
3 (SURGICAL_CORRECTIONS, SELF_INTERSECTION_POINTS, RASTER_BOUNDS)

BOOKMARKS :
6 / 6

BROKEN SOURCES :
0 / 9

CRS :
EPSG:32637

CANDIDATE GEOMETRIES MODIFIED :
NO

WORKING GT MODIFIED :
NO

MODEL_C :
UNCHANGED

READY_FOR_FINAL_VISUAL_REVIEW :
YES

NEXT STEP :
14A.1D4 FINAL VISUAL APPROVAL
