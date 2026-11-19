# ÉTAPE 14A.1C-B — Repair 14A_003 correction bookmarks only

Les huit signets `14A_003_dense_urban` ont été recréés dans une nouvelle copie du projet à partir des bounding boxes réelles des features Ground Truth. Les emprises sont en EPSG:32637 et utilisent une marge de 50 % autour de chaque bâtiment.

Contrôles PyQGIS/QGIS 3.40.14 :

- projet V2 ouvert puis rouvert avec succès ;
- 9 couches valides et aucune source cassée ;
- RGB 14A_003 visible après chaque signet ;
- la bounding box de la feature ciblée est incluse dans les 8 emprises ;
- les 8 signets ont le CRS EPSG:32637 ;
- les quatre signets 14A_001 existants ont été conservés avec noms et extents identiques ;
- aucune géométrie, couche, diagnostic ou pseudo-label n’a été modifié.

14A_001 BOOKMARKS PRESERVED :
YES

14A_003 BOOKMARKS TESTED :
8 / 8

14A_003 RGB VISIBLE AFTER BOOKMARK :
YES

TARGET FEATURE VISIBLE :
8 / 8

BOOKMARK CRS :
EPSG:32637

GROUND TRUTH MODIFIED :
NO

MODEL_C MODIFIED :
NO

READY_FOR_MANUAL_FIX :
YES
