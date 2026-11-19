# Flux fonctionnels

## 1. Sélection de zone

- UI : outils rectangle dans `map.tsx`, interaction `MapView::DrawHandler`.
- Transformation : `bboxToGeometry`.
- Backend : validation AOI/geometry dans `models.py` et `request_contracts.py`.
- Surface : `main.py::area_from_bbox_ha`.

Les points/polygones servent aux échantillons supervisés, pas à remplacer l’AOI principale.

## 2. Choix analyse, dates, source et projection

- Analyses : `frontend/src/data/mock.ts::indices`.
- Compatibilité : `georaster-contract.ts::supportedSensorsForIndex`.
- Dates : calendriers localisés ; deux paires pour Change Detection.
- Source : Sentinel‑2/Landsat, Sentinel‑1 forcé pour OSI‑SAR.
- Projection : réglage global Settings, enrichissement au moment de créer/exécuter l’analyse.

## 3. Recherche d’images

```text
Map → startGeeCatalogJob
→ POST /api/gee/jobs/catalog
→ thread _run_gee_catalog_job
→ gee_client.search_sentinel2
→ polling GET /api/gee/jobs/{id}/status
→ scènes/mosaïque → sélection frontend → couche RGB
```

En échec GEE, un catalogue mock peut être retourné.

## 4. Lancement

```text
buildRasterPayload
→ POST /api/result-cache/search
→ cache trouvé : activation directe
→ sinon POST /api/analyses
→ POST /api/analyses/{id}/run
→ compute_sentinel2_index
→ GET /api/runs/{run_id}/result
```

Le bouton Recalculate ajoute `force=true`.

## 5. Calcul

Le backend :

1. enrichit avec le CRS ;
2. calcule surface et clé/version de cache ;
3. réutilise ou calcule ;
4. persiste résultat/run/cache ;
5. persiste les artefacts de classification ;
6. met à jour le statut d’analyse.

## 6. Affichage, couches et légende

- résultat principal : `tiles.index_tile_url` ;
- source : `tiles.rgb_tile_url` ;
- sous-couches : `comparison_layers` ;
- légende/classes : résultat backend, avec fallback catalogue UI ;
- graphiques : Recharts ;
- URL expirée : `GET /api/runs/{run_id}/tiles?refresh=true`.

## 7. Statistiques

Indices : min/max/moyenne/écart-type, pixels, surface, histogramme et classes.
Classifications : classes/surfaces, échantillons et métriques.
OSI‑SAR : surfaces suspectes et contexte radar/vent.
Change : mêmes statistiques pour T1, T2 et delta.

## 8. Historique

```text
GET /api/history
→ clic œil
→ GET /api/runs/{id}/result
→ sessionStorage
→ /map?run_id=...
→ restauration sans calcul
```

La suppression appelle `DELETE /api/analyses/{id}` et efface runs, exports, cache associé et fichiers export locaux.

## 9. Export et rapport

- CSV/GeoTIFF : création d’un export lié au run, puis download ;
- PNG layout : capture/reconstruction et route dédiée ;
- Map PDF : route par run et sous-couche ;
- History : télécharge le premier export existant.

## Fichiers impliqués

Frontend : `routes/map.tsx`, `history.tsx`, `components/MapView.tsx`, `lib/georaster-api.ts`, `georaster-contract.ts`.
Backend : `main.py`, `models.py`, `request_contracts.py`, `gee_client.py`, `mock_engine.py`, `db.py`.
