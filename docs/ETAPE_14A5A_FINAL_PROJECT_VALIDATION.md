# GeoRaster — 14A.5A final QGIS project

Le projet final a été reconstruit en reprenant la structure XML du projet fonctionnel `14A3E2_TARGETED_REVIEW.qgz` : CRS WKT complet, blocs maplayer QGIS 3.40, styles raster/vector, layer tree et propriétés compatibles. Seules les 10 sources 14A.5A ont été remplacées.

Le fichier final contient exactement 5 RGB et 5 couches Ground Truth Polygon, avec la première paire visible et les autres masquées. Les sources et le GeoPackage n’ont pas été modifiés.

Le script PyQGIS a également été corrigé avec `QgsSingleSymbolRenderer`; il n’est pas nécessaire pour ouvrir le fichier final.

PROJECT FILE :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/qgis/14A5A_ANNOTATION_FINAL_VALIDATED.qgz

RGB :
5/5

GT :
5/5

BROKEN SOURCES :
0

QGIS PROJECT STRUCTURE :
PASS

QGIS DESKTOP OPEN TEST :
NOT_EXECUTED — QGIS Desktop 3.40.14 n’est pas accessible dans l’environnement Codex

QGIS EDITING TEST :
NOT_EXECUTED

ROOT CAUSE IDENTIFIED :
YES — script initial non appelé et structure XML minimale différente du projet QGIS fonctionnel

READY_FOR_MANUAL_ANNOTATION :
NO — ouverture et édition QGIS Desktop locales encore à confirmer
