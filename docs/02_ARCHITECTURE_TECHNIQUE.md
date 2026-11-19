# Architecture technique

## Composants

```text
Navigateur
├─ TanStack Start / React
├─ Leaflet / React-Leaflet
├─ Recharts
└─ client API
      ↓ HTTP JSON
FastAPI
├─ validation Pydantic
├─ orchestration, cache, exports
├─ moteur GEE
├─ moteur mock
└─ SQLite + fichiers locaux
      ↓ API Earth Engine
Collections GEE, tuiles et URL d’export temporaires
```

## Frontend

- Démarrage : `src/start.ts`.
- Routeur : `src/router.tsx`, arbre généré `routeTree.gen.ts`.
- Shell SSR/erreurs : `src/routes/__root.tsx`, `src/server.ts`.
- Workflow métier : `src/routes/map.tsx`.
- Carte : `src/components/MapView.tsx`.
- Contrat/API : `src/lib/georaster-contract.ts`, `georaster-api.ts`.
- Catalogue UI/fallback : `src/data/mock.ts`.
- i18n : `src/i18n/en.json`, `ar.json`, `src/lib/i18n.tsx`.

## Backend

- `main.py` : application, CORS, routes, cache, persistance, exports, PDF/PNG et CRS.
- `gee_client.py` : collections, masques, mosaïques, analyses, statistiques, tuiles et URL GEE.
- `models.py` : modèles d’entrée/sortie.
- `request_contracts.py` : normalisation canonique/legacy et compatibilité capteurs.
- `db.py` : SQLite et création du schéma.
- `catalog.py` : sources, indices et images mock.
- `mock_engine.py` : résultats sans GEE.
- `platform_store.py` : paramètres et logo.
- `run_tile_cache.py` : cache mémoire court des tuiles régénérées.

## Persistance

SQLite crée neuf tables :

- `analyses`, `runs`, `exports`, `processing_cache` ;
- `landcover_classes`, `training_samples` ;
- `classification_models`, `classification_results`, `validation_metrics`.

`main.py::run_analysis` persiste l’analyse, le résultat complet et le dernier run. Les classifications ajoutent des artefacts et métriques spécialisés.

## Caches

- `processing_cache` : clé SHA liée au contexte et à une version de traitement par analyse.
- `RUN_TILE_CACHE` : tuiles régénérées, durée maximale utilisée de 1 800 secondes.
- `GEE_CATALOG_JOBS` : jobs asynchrones en mémoire du processus.
- `sessionStorage` frontend : transfert History → Map.
- `localStorage` frontend : langue, utilisateur et paramètres de plateforme.

## Dépendances critiques

Backend : FastAPI, Uvicorn, Pydantic, Earth Engine API, Pillow. `certifi` est utilisé si disponible mais absent de `requirements.txt`.

Frontend : React 19, TanStack Start/Router/Query, Vite, Leaflet, Recharts, Radix UI et Tailwind.

## Limites structurelles

- `main.py` (~4 200 lignes) et `gee_client.py` (~3 500 lignes) concentrent plusieurs domaines.
- Les jobs et caches mémoire ne sont ni distribués ni persistants.
- SQLite convient au prototype local, pas à une forte concurrence.
- Le frontend `map.tsx` (~3 300 lignes) combine formulaire, capture cartographique et orchestration.
