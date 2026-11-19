# GeoRaster MVP API Contract

Base URL local:

```text
http://127.0.0.1:8010
```

## Workflow CPS V1

1. Creer une analyse: `POST /api/analyses`
2. Definir AOI, source, periode, seuil nuage et indice dans le payload.
3. Controler la disponibilite image: `POST /api/gee/preview`
4. Lancer le calcul: `POST /api/analyses/{analysis_id}/run`
5. Lire les resultats: `GET /api/runs/{run_id}/result`
6. Exporter: `POST /api/runs/{run_id}/export`
7. Historique: `GET /api/history`

## Catalogue

- `GET /api/catalog/sources`
- `GET /api/catalog/indices`
- `GET /api/catalog/indices?enabled_only=true`
- `GET /api/catalog/images`
- `POST /api/catalog/images/search`
- `GET /api/images`

Filtres image:

```text
GET /api/catalog/images?sensor=Sentinel-2&region=Riyadh&max_cloud=20&q=riyadh
```

Recherche Sentinel-2 reelle par AOI (GEE si authentifie, mock sinon):

```http
POST /api/catalog/images/search?limit=10
```

```json
{
  "source": "S2_SR_HARMONIZED",
  "date_start": "2025-04-01",
  "date_end": "2025-05-30",
  "max_cloud_pct": 20,
  "image_method": "least_cloudy",
  "aoi": {
    "bbox": [[24.60, 46.60], [24.80, 46.85]]
  }
}
```

Chaque image GEE retourne notamment:

- `id` / `gee_id`
- `date`
- `cloud`
- `bbox`
- `tile_url` pour affichage RGB Leaflet/MapLibre

## Google Earth Engine

- `GET /api/gee/status`
- `POST /api/gee/preview`

Variables locales conseillees:

```powershell
$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"
```

Authentification developpement:

```powershell
python -m ee authenticate
```

## Dashboard

- `GET /api/dashboard`

Retourne:

- `stats.images`
- `stats.analyses`
- `stats.indices`
- `stats.exports`
- `recent_analyses`
- `indices`

## Analyse

Payload minimal:

```json
{
  "name": "NDVI Riyadh",
  "objective": "vegetation",
  "description": "Analyse test",
  "source": "S2_SR_HARMONIZED",
  "image_id": "s2-riyadh-2025-04-12",
  "date_start": "2025-04-01",
  "date_end": "2025-04-30",
  "max_cloud_pct": 20,
  "image_method": "least_cloudy",
  "index": "NDVI",
  "aoi": {
    "bbox": [[24.60, 46.60], [24.80, 46.85]]
  }
}
```

Endpoints:

- `POST /api/analyses`
- `GET /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `PUT /api/analyses/{analysis_id}`
- `DELETE /api/analyses/{analysis_id}`

## Preview GEE

- `POST /api/gee/preview`

Retour MVP:

- image selectionnee
- nombre d'images disponibles
- taux de nuages minimal
- date meilleure image
- methode utilisee
- `preview.tile_url` contient une tuile RGB Earth Engine si GEE est configure

## Runs

- `POST /api/analyses/{analysis_id}/run`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/result`
- `GET /api/runs/{run_id}/tiles`

Resultat V1:

- `stats`
- `histogram`
- `classes`
- `quality`
- `palette`
- `tiles.rgb_tile_url`
- `tiles.index_tile_url`

## Exports

- `POST /api/runs/{run_id}/export`
- `GET /api/exports`
- `GET /api/exports/{export_id}/download`

Kinds V1:

- `stats_csv`
- `stats_json`
- `report_pdf`
- `map_png` (placeholder)
- `geotiff` (placeholder)
