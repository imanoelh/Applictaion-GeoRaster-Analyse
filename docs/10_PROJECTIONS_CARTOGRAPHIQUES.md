# Projections cartographiques

Sources : `backend/app/main.py::CRS_CATALOG`, `_effective_spatial_reference`, `gee_client.py::_gee_metric_crs`, `frontend/src/routes/settings.tsx`.

## Catalogue

| CRS | Définition/usage | Analyse | Export | GEE |
| --- | --- | --- | --- | --- |
| EPSG:4326 | coordonnées GeoJSON d’entrée | géométrie source | emprise | natif |
| EPSG:3857 | WGS84 / Web Mercator | non | capture écran seulement | affichage Leaflet |
| EPSG:9333 | KSA‑GRF17 géographique 2D | manuel, unité degré | accepté avec avertissement | transmis tel quel |
| EPSG:9356 | KSA‑GRF17 / UTM 36N | automatique/manuel | métrique | EPSG:32636 |
| EPSG:9357 | KSA‑GRF17 / UTM 37N | automatique/manuel | métrique | EPSG:32637 |
| EPSG:9358 | KSA‑GRF17 / UTM 38N | automatique/manuel | métrique | EPSG:32638 |
| EPSG:9359 | KSA‑GRF17 / UTM 39N | automatique/manuel | métrique | EPSG:32639 |
| EPSG:9360 | KSA‑GRF17 / UTM 40N | automatique/manuel | métrique | EPSG:32640 |
| EPSG:9332 | KSA‑GRF17 géographique 3D | interdit aux rasters | interdit actuellement | simulation future uniquement |

## Sélection automatique

À partir de la longitude centrale :

- `< 36°` → 9356 ;
- `< 42°` → 9357 ;
- `< 48°` → 9358 ;
- `< 54°` → 9359 ;
- sinon → 9360.

Si l’AOI croise une limite de zone, le backend choisit la zone de longitude centrale et renvoie un avertissement. Sans AOI : `analysis_crs = null`.

## Sélection manuelle

Settings persiste `projection_mode=manual` et `manual_crs`. Valeurs raster admises : EPSG:9333, 9356–9360. EPSG:9332 est accepté comme référence de simulation mais une zone UTM effective est tout de même calculée pour le raster.

## Métadonnées attachées au run

`spatial_reference` contient :

- système SANSRS, frame KSA‑GRF17 ;
- CRS d’entrée, de carte et d’analyse ;
- CRS choisi et CRS effectif ;
- équivalent GEE ;
- centre, zone UTM, unité, mode/méthode ;
- échelle déclarée et signature de grille ;
- avertissement éventuel.

## Analyses et statistiques

- Change Detection aligne les deux périodes avec `setDefaultProjection`.
- Les réductions métriques traduisent les CRS KSA vers UTM WGS84.
- Pour une AOI hors KSA, certaines statistiques non supervisées basculent vers l’UTM local calculé depuis le centre ; ce comportement est testé pour le Maroc.

## Exports

GeoTIFF utilise `effective_analysis_crs`, puis son équivalent GEE. L’emprise reste l’AOI. Les captures PNG/PDF sont des rendus Web Mercator mais transportent les métadonnées du CRS analytique.

## Compatibilité formats

- GeoJSON : EPSG:4326 implicite ;
- tuiles web : EPSG:3857 ;
- GeoTIFF : CRS demandé/équivalent GEE ;
- CSV/JSON : métadonnées textuelles ;
- PNG/PDF : image sans géoréférencement natif, métadonnées dans la mise en page.

## Anomalies

- le code ne reprojette pas toutes les images avec `reproject`; il fixe surtout les paramètres de réduction/export ;
- EPSG:9333, en degrés, est accepté malgré les usages métriques ;
- le choix `20m` n’est pas appliqué comme échelle de calcul ;
- la signature de grille est informative et n’impose pas une grille export complète (`crsTransform` absent).
