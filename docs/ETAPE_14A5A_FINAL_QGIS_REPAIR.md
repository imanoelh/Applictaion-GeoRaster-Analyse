# ÉTAPE 14A.5A — RÉPARATION DÉFINITIVE DU PROJET QGIS

## Cause identifiée

Le script `load_14A5A_direct_qgis.py` définissait `load_14a5a_direct_qgis()` mais ne l’appelait jamais. Une exécution du fichier pouvait donc se terminer sans exception et sans ajouter une seule couche. Le script a été corrigé avec journal détaillé, contrôle de chaque source, gestion explicite des exceptions et appel final de la fonction.

Les projets générés précédemment utilisaient aussi un XML QGIS très minimal différent du projet fonctionnel 14A3E2, dont le CRS est sérialisé en WKT complet et dont le GeoPackage suit le schéma OGR complet. Le GeoPackage 14A5A est maintenant conforme avec `gpkg_contents`, `gpkg_geometry_columns`, `gpkg_ogr_contents` et les métadonnées spatiales nécessaires.

## Validation

Les cinq RGB et les cinq couches GT ont été vérifiés indépendamment. Le projet final contient exactement 10 couches, une paire visible au démarrage, EPSG:32637 et des URI absolues. Aucun ancien projet, raster, Ground Truth ou modèle n’a été modifié.

Aucun exécutable QGIS Desktop n’est disponible dans l’environnement Codex. Le test d’ouverture réelle QGIS local est donc explicitement non exécuté ; le script journalisé est la méthode déterministe à utiliser dans QGIS 3.40.14.

ROOT CAUSE :
Fonction de chargement jamais appelée dans le script initial ; incompatibilité possible des projets XML minimaux avec le provider QGIS local

WORKING PROJECT REFERENCE :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/qgis/14A3E2_TARGETED_REVIEW.qgz

SCRIPT ERROR IDENTIFIED :
Absence d’appel à load_14a5a_direct_qgis(); journal et exceptions insuffisants

RGB LOAD :
5/5

GT LOAD :
5/5

TOTAL LAYERS :
10/10

PROJECT VALIDATION :
PASS (structure, sources et providers)

REAL QGIS DESKTOP TEST :
NOT_EXECUTED (QGIS Desktop absent de l’environnement Codex)

FINAL PROJECT PATH :
backend/data/fine_tuning/buildings/maxar_v2_high_precision/qgis/14A5A_ANNOTATION_FINAL_VALIDATED.qgz

READY FOR MANUAL ANNOTATION :
NO — confirmer d’abord l’ouverture locale QGIS 3.40.14
