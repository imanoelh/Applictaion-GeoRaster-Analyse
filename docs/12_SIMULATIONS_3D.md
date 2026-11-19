# Simulations 3D

## État réel

Le projet ne contient aucun moteur de simulation, scène 3D, modèle numérique de terrain, extrusion, rendu Cesium/Three.js ou export 3D.

La fonctionnalité actuelle se limite à :

- un booléen `simulation_3d_enabled` dans Settings ;
- un CRS fixe EPSG:9332 ;
- un modèle Pydantic `Coordinate3D` ;
- des métadonnées `simulation_spatial_reference` attachées à l’analyse ;
- trois tests de contrat.

## EPSG:9332

Déclaré comme KSA‑GRF17 géographique 3D :

- axes géodésiques + hauteur ellipsoïdale ;
- unités horizontales en degrés, verticale en mètres ;
- statut `experimental` ;
- capacité `simulation_3d: true` ;
- capacités raster, surface, affichage web et GeoTIFF actuel à `false`.

## Comportement

Si EPSG:9332 est sélectionné manuellement :

- il reste la référence choisie ;
- l’analyse raster utilise quand même la zone KSA‑GRF17/UTM dérivée de l’AOI ;
- `height_available` vaut `false` ;
- le statut de simulation vaut `configured_not_applied`.

## Tests

`backend/tests/test_simulation_3d_crs.py` vérifie :

- le caractère isolé et expérimental ;
- l’impossibilité de l’utiliser comme CRS d’analyse raster ;
- la fixation stricte à EPSG:9332 ;
- les bornes latitude/longitude de `Coordinate3D`.

## Suite nécessaire

Avant de parler de simulation 3D opérationnelle :

- définir le cas d’usage et les données d’altitude ;
- choisir le moteur de visualisation ;
- gérer transformations verticale/horizontale ;
- définir les formats d’entrée/sortie ;
- ajouter API, persistance, tests et validation géodésique.
