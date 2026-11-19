# ÉTAPE 14A.5A-QGIS-VALIDATION — VALIDATE AND TEST QGIS PROJECT BEFORE USE

## Résultats techniques

Les cinq rasters RGB ont été ouverts indépendamment avec Rasterio. Chaque fichier existe, est lisible, mesure 512x512, contient trois bandes et possède un WKT explicite `WGS 84 / UTM zone 37N`, correspondant à EPSG:32637. Une installation PROJ externe PostgreSQL génère un avertissement de version et empêche `to_epsg()` de renvoyer automatiquement 32637 ; cela concerne l’environnement Python de contrôle, pas les fichiers raster.

Le GeoPackage est SQLite valide et contient les métadonnées `gpkg_contents`, `gpkg_geometry_columns`, `gpkg_ogr_contents`, les références spatiales et cinq couches Polygon EPSG:32637. Les cinq couches sont vides et chargeables par SQLite/provider metadata.

Les cinq tests de paires RGB + GT sont PASS au niveau fichiers/providers. Cinq archives temporaires `TEST_1PAIR.qgz` à `TEST_5PAIR.qgz` ont été créées dans le répertoire temporaire utilisateur pour isoler le niveau de chargement ; elles ne font pas partie du projet métier.

Le QGZ corrigé est une archive ZIP valide, son XML interne est bien formé et contient exactement 10 maplayers et 10 entrées layer tree. Aucun exécutable `qgis`, `qgis-bin` ou `qgis_process` n’est accessible dans cette session ; le chargement réel de l’interface QGIS ne peut donc pas être déclaré exécuté ici. La procédure sûre recommandée est d’ouvrir le QGZ corrigé avec QGIS 3.40.14 via l’API `QgsProject.read()` ou depuis l’interface, puis de vérifier les messages du panneau Log.

RGB LOAD :
5 / 5

GT LOAD :
5 / 5

GPKG VALID :
YES

PAIR TESTS :
5 / 5 PASS

QGZ STRUCTURE VALID :
YES

QGIS REAL LOAD TEST :
NOT AVAILABLE — QGIS executable absent

FIRST FAILING TEST :
Aucun test fichier/provider échoué ; chargement GUI non exécuté

BLOCKING COMPONENT :
Environnement PROJ externe pour l’identification EPSG automatique ; aucun composant de données bloquant

ROOT CAUSE :
Avertissement de version proj.db PostgreSQL lors de `to_epsg()` ; QGZ et sources restent structurellement valides

SAFE PROJECT METHOD :
QgsProject API dans QGIS 3.40.14, avec sources validées puis activation progressive des paires

READY_FOR_MANUAL_ANNOTATION :
NO — validation QGIS GUI locale encore requise



