# Architecture globale

## Vue d'ensemble

GeoRasterPortal est organise en deux parties principales:

- `backend`: API FastAPI, logique GEE, cache, historique, exports, rapports et persistance SQLite.
- `frontend`: interface React/TanStack, carte Leaflet, panneaux de configuration, affichage resultats, History et exports.

## Backend

Le backend fournit:

- les endpoints d'analyse;
- la recherche catalogue GEE;
- l'execution des runs;
- la generation des tuiles GEE;
- les statistiques et classes;
- la gestion du cache;
- l'historique;
- les exports CSV, JSON, GeoTIFF, PNG et PDF;
- les workflows mock lorsque GEE n'est pas disponible.

Fichiers principaux:

- `backend/app/main.py`: routes API, historique, cache, exports, runs.
- `backend/app/gee_client.py`: logique Google Earth Engine, indices, classes, palettes, tuiles.
- `backend/app/mock_engine.py`: resultats de fallback/mock.
- `backend/app/models.py`: schemas de payload et modeles API.

## Frontend

Le frontend fournit:

- page Map & Analysis;
- page History;
- page Catalog;
- page Dashboard;
- page Settings;
- composant carte Leaflet;
- appels API backend;
- affichage des legendes, statistiques, histogrammes et exports.

Fichiers principaux:

- `frontend/src/routes/map.tsx`: workflow carte et analyse.
- `frontend/src/routes/history.tsx`: historique et restauration rapide.
- `frontend/src/components/MapView.tsx`: affichage Leaflet et tuiles GEE.
- `frontend/src/lib/georaster-api.ts`: client API.
- `frontend/src/data/mock.ts`: definitions UI des indices et legendes.

## Persistance

Les analyses, runs, caches et exports sont stockes cote backend. Le run contient le `result_json`, qui preserve:

- analyse source;
- AOI;
- dates;
- capteur;
- index;
- statistiques;
- classes;
- palettes;
- tuiles GEE;
- qualite;
- exports associes.

## Google Earth Engine

GEE est utilise pour:

- charger les collections satellites;
- construire les mosaics;
- calculer les indices;
- classer les pixels;
- produire les URLs de tuiles;
- produire les exports raster lorsque disponible.

## Frontend / Backend contract

Le payload canonique contient notamment:

- `geometry`;
- `start_date`;
- `end_date`;
- `sensor`;
- `resolution`;
- `cloud_max`;
- `index`;
- `analysis_type`;
- options specialisees pour Change Detection, classifications et OSI-SAR.

