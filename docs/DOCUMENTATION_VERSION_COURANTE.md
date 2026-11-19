# Documentation Claire - Version Courante GeoRasterPortal

## 1. Vue d'ensemble

Cette version de **GeoRasterPortal** est une application WebGIS full stack composee de :

- un **frontend** React/TanStack Start/Vite pour l'interface utilisateur,
- un **backend** FastAPI pour les traitements raster, le catalogue, l'historique, les exports et la persistance,
- une integration **Google Earth Engine (GEE)** lorsque l'environnement est configure,
- un **mode mock** de secours lorsque GEE n'est pas disponible.

L'objectif fonctionnel principal est de permettre :

- la selection d'une image ou d'une periode d'imagerie,
- la definition d'une zone d'interet (AOI),
- l'execution d'analyses raster,
- la visualisation cartographique des resultats,
- l'export des sorties techniques et cartographiques.

---

## 2. Cartographie du projet

```text
GeoRasterPortal-dev_v1/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── gee_client.py
│   │   ├── mock_engine.py
│   │   ├── db.py
│   │   ├── models.py
│   │   └── catalog.py
│   ├── data/
│   │   ├── georaster.db
│   │   └── platform_settings.json
│   ├── uploads/
│   │   └── platform/
│   ├── exports/
│   │   ├── reports/
│   │   └── map-layouts/
│   ├── README.md
│   ├── API_CONTRACT.md
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── data/
│   │   ├── router.tsx
│   │   ├── start.ts
│   │   └── server.ts
│   ├── package.json
│   └── vite.config.ts
├── README.md
└── DOCUMENTATION_VERSION_COURANTE.md
```

---

## 3. Composants Frontend

## 3.1 Stack frontend

- **React 19**
- **TanStack Start**
- **TanStack Router**
- **TanStack Query**
- **Vite**
- **Leaflet / React-Leaflet**
- **Tailwind CSS**
- **Radix UI**

## 3.2 Roles des dossiers frontend

### `frontend/src/routes/`

Contient les pages principales :

- `index.tsx` : tableau de bord
- `map.tsx` : ecran principal d'analyse raster
- `catalog.tsx` : catalogue d'images
- `history.tsx` : historique des analyses
- `settings.tsx` : parametres de plateforme
- `__root.tsx` : shell global de l'application

### `frontend/src/components/`

Contient les composants UI reutilisables :

- `MapView.tsx` : composant cartographique Leaflet principal
- `AppSidebar.tsx` : navigation laterale
- `PlatformBrand.tsx` : identite visuelle de la plateforme
- `components/ui/*` : briques UI generiques

### `frontend/src/lib/`

Contient la logique transverse :

- `georaster-api.ts` : client API frontend vers le backend
- `error-page.ts`, `error-capture.ts` : gestion des erreurs
- `utils.ts` : helpers utilitaires

### `frontend/src/data/mock.ts`

Jeu de donnees mock pour affichage fallback si le backend ou certaines ressources ne sont pas disponibles.

---

## 4. Modules fonctionnels Frontend

## 4.1 Dashboard

La page `/` affiche :

- les statistiques globales,
- les analyses recentes,
- les indices disponibles,
- les acces rapides vers les modules.

Source backend utilisee :

- `GET /api/dashboard`

Fallback :

- donnees mock frontend si l'API ne repond pas.

## 4.2 Map & Analysis

La page `/map` est le coeur applicatif. Elle permet :

- le choix du capteur,
- le choix de l'indice ou du type d'analyse,
- la recherche d'images GEE,
- le dessin de l'AOI,
- le lancement du traitement,
- la visualisation des couches raster et resultats,
- la consultation des statistiques et classes,
- l'export PDF/PNG/GeoTIFF/CSV.

Fonctions majeures :

- gestion du workflow d'analyse,
- interrogation du cache de resultats,
- support des classifications supervisees et non supervisees,
- renommage des clusters non supervises,
- capture cartographique pour les exports.

## 4.3 Image Catalog

La page `/catalog` permet :

- de lister les scenes disponibles,
- filtrer par capteur, region, nuages, texte,
- previsualiser les images,
- ouvrir rapidement une analyse.

Source backend :

- `GET /api/catalog/images`

Fallback :

- catalogue mock local.

## 4.4 History

La page `/history` permet :

- de consulter les analyses executees,
- filtrer par statut,
- supprimer une analyse,
- telecharger un export existant.

Source backend :

- `GET /api/history`
- `DELETE /api/analyses/{analysis_id}`

## 4.5 Settings

La page `/settings` centralise :

- les parametres d'interface,
- le logo de plateforme,
- la configuration de connexion backend,
- les preferences cartographiques et d'export.

Fonctions backend actives dans cette version :

- lecture du nom/logo plateforme,
- upload du logo,
- reset du logo.

---

## 5. Composants Backend

## 5.1 Stack backend

- **FastAPI**
- **Pydantic v2**
- **SQLite**
- **Pillow**
- **Google Earth Engine API**

## 5.2 Roles des modules backend

### `backend/app/main.py`

Point d'entree principal du backend.

Responsabilites :

- declaration de l'application FastAPI,
- exposition des routes REST,
- orchestration des analyses,
- gestion du cache,
- gestion des exports,
- gestion des jobs GEE asynchrones pour le catalogue,
- gestion des parametres de plateforme.

### `backend/app/gee_client.py`

Moteur de traitement principal pour le mode reel GEE.

Responsabilites :

- initialisation Earth Engine,
- recherche d'images par capteur et periode,
- creation de mosaiques,
- calcul des indices spectraux,
- calcul du change detection,
- classification supervisee,
- classification non supervisee,
- detection OSI-SAR,
- production des tuiles raster,
- generation d'URL PNG/GeoTIFF GEE.

### `backend/app/mock_engine.py`

Moteur fallback hors GEE.

Responsabilites :

- simulation des resultats pour NDVI, NDWI, NDBI, BSI, SAVI,
- simulation des classifications,
- simulation du change detection,
- simulation OSI-SAR.

Ce module permet de garder l'application demonstrable meme sans authentification GEE.

### `backend/app/db.py`

Couche SQLite minimale.

Responsabilites :

- connexion base,
- creation du schema,
- helpers JSON,
- helpers de lecture SQL.

### `backend/app/models.py`

Modeles Pydantic de l'API.

Responsabilites :

- validation des entrees analyses,
- normalisation des anciens et nouveaux formats de payload,
- definition des modeles d'export, run, preview et AOI.

### `backend/app/catalog.py`

Catalogues statiques metier.

Contient :

- les sources de donnees,
- les indices disponibles,
- un jeu d'images mock.

---

## 6. Base de donnees et persistance

La base SQLite est stockee dans :

- `backend/data/georaster.db`

Tables principales identifiees :

- `analyses`
- `runs`
- `exports`
- `processing_cache`
- `landcover_classes`
- `training_samples`
- `classification_models`
- `classification_results`
- `validation_metrics`

### Usage metier des tables

- `analyses` : definition fonctionnelle des analyses creees
- `runs` : executions effectives des analyses
- `exports` : fichiers ou references exportees
- `processing_cache` : resultats reutilisables pour eviter des recalculs
- `landcover_classes` : nomenclature de classes d'occupation du sol
- `training_samples` : echantillons utilisateur pour apprentissage
- `classification_models` et `classification_results` : structure prevue pour la classification
- `validation_metrics` : metriques d'evaluation des classifications

---

## 7. Analyses supportees dans cette version

### Indices spectraux

- NDVI
- NDWI
- NDBI
- BSI
- SAVI

### Analyses avancees

- Change Detection : `CHANGE_NDVI`, `CHANGE_NDWI`, `CHANGE_NDBI`, `CHANGE_BSI`, `CHANGE_SAVI`
- Supervised Classification
- Unsupervised Classification
- OSI-SAR (detection de suspicion de nappe d'hydrocarbures)

---

## 8. Flux fonctionnel principal

## 8.1 Flux d'analyse raster

1. L'utilisateur ouvre `/map`
2. Il choisit un capteur, une periode et une analyse
3. Il dessine un AOI sur la carte
4. Le frontend interroge le backend pour rechercher les images disponibles
5. Le frontend cree une analyse via `/api/analyses`
6. Le backend lance le traitement via `/api/analyses/{id}/run`
7. Le backend :
   - verifie le cache,
   - calcule le resultat via GEE ou mock,
   - enregistre le run,
   - stocke le resultat dans le cache,
   - renvoie les tuiles, statistiques, classes et metadonnees
8. Le frontend affiche la couche resultat, les statistiques et les options d'export

## 8.2 Flux catalogue GEE

1. Le frontend soumet une recherche
2. Le backend peut demarrer un job via `/api/gee/jobs/catalog`
3. Le frontend poll `/api/gee/jobs/{job_id}/status`
4. Les scenes disponibles et la mosaique sont retournees

## 8.3 Flux export cartographique

1. Le frontend capture la carte Leaflet en image
2. Il envoie le screenshot et les metadonnees au backend
3. Le backend genere :
   - un PDF cartographique,
   - ou une composition PNG
4. Le fichier est enregistre dans `backend/exports/`

---

## 9. Routes API principales

## 9.1 Systeme et configuration

- `GET /api/health`
- `GET /api/gee/status`
- `GET /api/settings/platform`
- `POST /api/settings/logo`
- `POST /api/settings/logo/reset`
- `GET /api/dashboard`

## 9.2 Catalogue

- `GET /api/catalog/sources`
- `GET /api/catalog/indices`
- `GET /api/catalog/images`
- `POST /api/catalog/images/search`
- `POST /api/gee/jobs/catalog`
- `GET /api/gee/jobs/{job_id}/status`
- `POST /api/gee/preview`

## 9.3 Analyses

- `POST /api/analyses`
- `GET /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `PUT /api/analyses/{analysis_id}`
- `DELETE /api/analyses/{analysis_id}`
- `POST /api/analyses/{analysis_id}/run`
- `POST /api/analysis/change-detection`

## 9.4 Resultats et historique

- `GET /api/history`
- `POST /api/result-cache/search`
- `DELETE /api/result-cache/{cache_key}`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/result`
- `GET /api/runs/{run_id}/tiles`
- `POST /api/runs/{run_id}/clusters/{cluster_code}/rename`

## 9.5 Classification

- `GET /api/classification/classes`
- `POST /api/classification/classes`
- `GET /api/classification/samples`
- `POST /api/classification/samples`

## 9.6 Exports

- `POST /api/runs/{run_id}/export`
- `POST /api/export/map-pdf`
- `POST /api/export/map-layout-png`
- `GET /api/exports`
- `GET /api/exports/{export_id}/download`

---

## 10. Fichiers generes par l'application

### Base et configuration

- `backend/data/georaster.db`
- `backend/data/platform_settings.json`

### Uploads

- `backend/uploads/platform/logo.*`

### Exports

- `backend/exports/reports/*.pdf`
- `backend/exports/map-layouts/*.png`

Remarque :

- certains exports standards sont aussi stockes en base SQLite dans la table `exports`.

---

## 11. Modes de fonctionnement

## 11.1 Mode GEE

Utilise Earth Engine pour :

- rechercher les scenes reelles,
- produire les mosaiques,
- calculer les indices,
- calculer les classifications,
- produire les tuiles d'affichage,
- generer des liens GeoTIFF/PNG.

Prerequis :

- authentification GEE,
- variables d'environnement de projet configurees.

## 11.2 Mode Mock

Utilise `mock_engine.py` lorsque GEE n'est pas disponible.

Avantages :

- permet de continuer les demonstrations,
- permet de tester l'UI sans dependre de GEE.

Limites :

- les resultats ne sont pas scientifiquement reels,
- les cartes raster sont simulees ou simplifiees.

---

## 12. Points forts de cette version

- architecture frontend/backend bien separee
- mode degrade mock utile pour les tests et demos
- cache de traitement pour eviter les recalculs couteux
- support de plusieurs familles d'analyses
- exports techniques et cartographiques
- base SQLite suffisante pour un MVP evolutif
- socle deja present pour les echantillons d'apprentissage et la validation

---

## 13. Limites observees sur cette version

- une partie du frontend reste hybride entre mock local et backend reel
- certains textes et libelles restent partiellement heterogenes entre francais et anglais
- la capture cartographique pour export depend du rendu navigateur
- la securite est minimale pour l'admin logo via header `X-User-Role`
- la persistance reste locale SQLite, donc adaptee au prototype plus qu'a la production multi-utilisateur
- certaines configurations visibles dans `settings` sont encore surtout declaratives cote UI

---

## 14. Resume d'architecture

Cette version peut etre lue comme un **prototype WebGIS analytique avance** structure en trois couches :

### Couche presentation

- React
- TanStack Router
- Leaflet
- ecrans dashboard, analyse, catalogue, historique, settings

### Couche services

- client API frontend `georaster-api.ts`
- backend FastAPI
- logique de workflow d'analyse
- generation d'exports

### Couche traitement et persistance

- moteur GEE
- moteur mock
- cache SQLite
- historique des analyses
- fichiers exportes sur disque

---

## 15. Recommandation pour la suite

Pour la prochaine etape du projet, les axes les plus naturels sont :

- unifier completement le frontend autour du backend reel,
- documenter les payloads par cas d'usage metier,
- renforcer l'authentification et les roles,
- separer plus finement les services backend par domaine,
- preparer une version deploiement avec stockage et fichiers externalises.
