# Intégration Google Earth Engine

## Initialisation

`gee_client.py::_ensure_gee` initialise le module `ee` avec `GEE_PROJECT_ID` ou `GOOGLE_CLOUD_PROJECT`. L’état et la dernière erreur sont conservés en mémoire. En échec, le moteur retourne des résultats mock lorsque le workflow le permet.

## Collections

| Identifiant | Usage |
| --- | --- |
| `COPERNICUS/S2_SR_HARMONIZED` | indices, classifications, mosaïques |
| `COPERNICUS/S2_CLOUD_PROBABILITY` | masque de probabilité nuage |
| `LANDSAT/LC08/C02/T1_L2` + `LC09` | analyses optiques Landsat |
| `COPERNICUS/S1_GRD` | OSI‑SAR |
| `GOOGLE/DYNAMICWORLD/V1` | catalogue générique |
| `ESA/WorldCover/v200` | catalogue et référence supervisée |
| `JRC/GSW1_4/GlobalSurfaceWater` | masque eau OSI‑SAR |
| ERA5 daily | contexte de vent OSI‑SAR |

## Sélection et préparation

Le contrat externe accepte une résolution et une méthode, mais la normalisation backend impose actuellement :

- méthode `median_composite` ;
- seuil cloud probability 40.

Sentinel‑2 :

- filtre AOI, dates et `CLOUDY_PIXEL_PERCENTAGE <= cloud_max` ;
- jointure S2 Cloud Probability ;
- masque pixels avec probabilité sous le seuil ;
- sélection B2/B3/B4/B8/B11/B12.

Landsat :

- fusion LC08/LC09 ;
- filtre `CLOUD_COVER` ;
- masque QA_PIXEL ;
- facteurs d’échelle Collection 2 L2 ;
- bandes SR_B2 à SR_B7.

Sentinel‑1 :

- filtre AOI/dates, mode IW, VV et selon le workflow VH ;
- composite médian.

## Mosaïques

- Composite médian pour les analyses.
- Pour une grande AOI Sentinel‑2 (> 350 km²), le catalogue peut construire une grille de tuiles de 20 km, jusqu’à 80 tuiles.
- La qualité inclut nombre d’images, couverture estimée, tuiles vides/faibles et avertissements.
- L’AOI recommandée par l’interface est limitée à 15 000 km² ; cette limite est surtout UX, pas une validation Pydantic stricte.

## Calculs et statistiques

Les images d’indice sont découpées à l’AOI. Les statistiques utilisent `reduceRegion`, `bestEffort`, `maxPixels` et `tileScale`. Les surfaces utilisent `pixelArea()/10000`.

Échelles :

- Sentinel‑2 : 10 m ;
- Landsat : 30 m ;
- OSI‑SAR : raster 10 m, statistiques 30 m par défaut.

Le choix UI `20m` n’est donc pas appliqué comme échelle de calcul générale.

## Tuiles et durée de vie

`getMapId` fournit des modèles d’URL temporaires. Le frontend peut appeler `GET /api/runs/{run_id}/tiles?refresh=true` pour régénérer les tuiles. Le résultat et le cache SQLite sont alors mis à jour.

## Exports GEE

- `getThumbURL` : PNG 1 800 px.
- `getDownloadURL` : GeoTIFF limité à l’AOI, avec échelle et CRS.
- Les EPSG KSA UTM sont traduits en EPSG WGS84 UTM acceptés par GEE.

## Mode mock

`mock_engine.py` reproduit la structure des statistiques/classes/palettes. Il ne produit pas de tuiles réelles et ne peut pas fournir de PNG/GeoTIFF GEE. Un résultat mock n’est pas réutilisé si GEE redevient disponible.

## Points non vérifiés pendant cette mission

- authentification et quotas du projet GEE ;
- exactitude des scènes renvoyées en ligne ;
- durée réelle des URL ;
- résultat binaire et métadonnées du GeoTIFF téléchargé ;
- validation scientifique terrain.
