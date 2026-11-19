# Contrat Canonique Frontend / Backend

Ce document fixe le payload canonique a utiliser avant toute nouvelle evolution.

## 1. Payload canonique raster

Le frontend doit privilegier les champs suivants pour:

- `POST /api/gee/preview`
- `POST /api/catalog/images/search`
- `POST /api/gee/jobs/catalog`
- `POST /api/analyses`
- `POST /api/result-cache/search`

```json
{
  "geometry": { "type": "Polygon", "coordinates": [[[...]]]},
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "sensor": "sentinel-2",
  "resolution": "auto",
  "cloud_max": 25,
  "index": "NDVI",
  "analysis_type": "spectral_index"
}
```

Champs conditionnels:

- `period_1` et `period_2` pour le change detection
- `supervised_options` pour la classification supervisee
- `unsupervised_options` pour la classification non supervisee
- `osi_sar_options` pour OSI-SAR

## 2. Compatibilite legacy

Le backend continue de deriver automatiquement les champs legacy:

- `aoi`
- `date_start`
- `date_end`
- `max_cloud_pct`
- `source`
- `image_method`
- `cloud_probability_threshold`

Cette compatibilite est maintenue pour eviter toute regression interne, mais elle ne doit plus etre la source principale cote frontend.

## 3. Compatibilite capteur / analyse

- `NDVI`, `NDWI`, `NDBI`, `BSI`, `SAVI`: `sentinel-2`, `landsat-8-9`
- `CHANGE_*`: `sentinel-2`, `landsat-8-9`
- `SUPERVISED_CLASSIFICATION`: `sentinel-2`, `landsat-8-9`
- `UNSUPERVISED_CLASSIFICATION`: `sentinel-2`, `landsat-8-9`
- `OSI_SAR`: `sentinel-1`

## 4. Mode mock vs mode GEE

- si GEE est disponible: calculs et tuiles dynamiques reelles
- sinon: fallback `mock` sans casser le workflow applicatif

## 5. Regle projet

Toute nouvelle fonctionnalite doit partir du contrat canonique ci-dessus.
La retrocompatibilite backend est toleree, mais ne doit plus piloter les nouveaux developpements frontend.
