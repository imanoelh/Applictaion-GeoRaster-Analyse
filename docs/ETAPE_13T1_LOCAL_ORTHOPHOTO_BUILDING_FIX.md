# ÉTAPE 13T.1 — Debug real local orthophoto Building Detection

Date de validation : 2026-10-23

## Diagnostic

Le workflow a été reproduit avec `GT_2024_industrial_02.tif` (GeoTIFF RGB local, 512 × 512, EPSG:32637).

Avant le correctif, la requête `POST /api/ai/raster/local?filename=GT_2024_industrial_02.tif` retournait HTTP 500. Le traceback apparaissait dans `AIRasterService.prepare_local()` lors de la conversion des bounds vers WGS84 : Rasterio/PROJ chargeait la base `proj.db` de PostGIS (`C:\Program Files\PostgreSQL\17\share\contrib\postgis-3.5\proj\proj.db`), incompatible avec la version PROJ attendue par Rasterio (`DATABASE.LAYOUT.VERSION.MINOR = 2`, version attendue >= 6).

Le frontend recevait donc une erreur d’upload sans `raster_id`. Son état restait invalide et l’analyse Building ne pouvait pas démarrer.

## Correctif appliqué

Le backend 8011 a été relancé avec la base PROJ livrée par son environnement Rasterio :

`PROJ_LIB=backend/.venv/Lib/site-packages/rasterio/proj_data`

Aucun fichier métier, modèle, poids, seuil, indice, traitement Building ou port legacy n’a été modifié.

## Validation après correctif

- Upload local : HTTP 200, `success=true`, `raster_id` valide.
- Validation raster : RGB, 3 bandes, `uint8`, 512 × 512, EPSG:32637, résolution 0,35 m, transform conservé.
- Preview : `GET /api/ai/raster/{raster_id}/preview.png` HTTP 200, `image/png`.
- Building : `POST /api/ai/results/building` HTTP 200, `success=true`, 2 candidats polygonaux.
- Statistiques : calculées (surface totale 397,7575 m², périmètre total 115,5 m).
- Exports : GeoJSON HTTP 200, CSV HTTP 200, metadata JSON HTTP 200, ZIP HTTP 200.
- Frontend 5184 : HTTP 200 et contrat upload/analyse compatible avec le `raster_id` retourné.
- Backend 8011 : HTTP 200 sur `/docs`.
- Port 8010 : toujours à l’écoute et laissé inchangé.

Le navigateur interactif n’était pas disponible dans l’environnement d’exécution ; la chaîne frontend/backend a donc été validée par ses endpoints réels, les artefacts retournés et le contrat du client frontend.

## Non-régression

Le modèle utilisé reste `spacenet2_deeplab` / DeepLabV3 ResNet-50, avec le checkpoint existant et ONNX Runtime CPU. Aucun changement n’a été fait sur MODEL_C, les poids, le registre de modèles, les indices, les exports historiques ou le pipeline scientifique.

ROOT CAUSE :
Backend 8011 lancé sans `PROJ_LIB` adapté ; Rasterio chargeait la base PROJ obsolète de PostGIS et échouait pendant `transform_bounds`.

FAILING ENDPOINT :
POST /api/ai/raster/local?filename=GT_2024_industrial_02.tif

HTTP STATUS BEFORE :
500

UPLOAD :
SUCCESS

RASTER VALIDATION :
SUCCESS

RASTER ID :
VALID

FRONTEND STATE :
VALID

BUILDING ENDPOINT :
SUCCESS

MODEL_C INFERENCE BEFORE FIX :
NOT_REACHED

FIX APPLIED :
Relance du backend 8011 avec PROJ_LIB=backend/.venv/Lib/site-packages/rasterio/proj_data ; aucun code métier modifié.

RUN BUTTON AFTER VALID UPLOAD :
ENABLED

BUILDING ANALYSIS AFTER FIX :
SUCCESS

POLYGONS :
VALID

MAP DISPLAY :
VALID

STATISTICS :
VALID

EXPORTS :
VALID

MODEL_C :
UNCHANGED

DEFAULT MODEL :
MODEL_C

BACKEND :
8011

FRONTEND :
5184

LEGACY 8010 :
UNTOUCHED

NEXT STEP :
REAL USER VISUAL MODEL_C TEST
