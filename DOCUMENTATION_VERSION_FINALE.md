# GeoRasterPortal — Documentation technique et fonctionnelle finale

> Référence officielle vérifiée sur le code du worktree `dev_v1` au 27 juillet 2026.
> HEAD observé : `3dfb953` (`Improve PDF imagery and bilingual legends`, 25 juillet 2026).
> Le worktree contient des modifications applicatives non commitées ; la présente documentation décrit ce code courant, sans le modifier.

## 1. Présentation

GeoRasterPortal est un prototype WebGIS full stack d’analyse raster. L’utilisateur définit une zone d’intérêt (AOI), recherche ou compose des images satellitaires, exécute une analyse avec Google Earth Engine (GEE), visualise les tuiles et statistiques, puis exporte le résultat.

Le projet combine :

- un frontend React 19 / TanStack Start / Vite / Leaflet ;
- une API FastAPI et des modèles Pydantic ;
- un moteur GEE avec repli mock ;
- une persistance SQLite locale ;
- des exports statistiques, GeoTIFF, PNG et PDF ;
- une interface anglais/arabe.

Il s’agit d’un prototype avancé et démontrable, pas d’une plateforme de production multi-utilisateur durcie.

## 2. Fonctionnalités réellement présentes

- Dashboard, carte analytique, catalogue, historique et paramètres.
- AOI rectangulaire ; points et polygones pour les échantillons supervisés.
- Catalogue asynchrone d’images/mosaïques.
- 13 analyses exposées dans l’interface :
  - NDVI, NDWI, NDBI, BSI, SAVI ;
  - CHANGE_NDVI, CHANGE_NDWI, CHANGE_NDBI, CHANGE_BSI, CHANGE_SAVI ;
  - OSI_SAR ;
  - classification supervisée ;
  - classification non supervisée.
- Capteurs/collections : Sentinel‑2, Landsat 8/9, Sentinel‑1 ; Dynamic World, ESA WorldCover et GHSL 2018 servent de données auxiliaires selon l’analyse.
- Cache de résultats et restauration depuis History.
- Personnalisation des noms/couleurs des groupes non supervisés.
- Exports CSV/JSON, URL de téléchargement GEE pour PNG/GeoTIFF, PNG cartographique et rapport PDF.
- Paramétrage KSA‑GRF17 et référence 3D expérimentale EPSG:9332.

## 3. Architecture générale

```text
Utilisateur
  ↓
Frontend TanStack / React (`frontend/src/routes/`)
  ↓
Carte Leaflet, AOI, paramètres, gestion des couches (`map.tsx`, `MapView.tsx`)
  ↓
Client HTTP canonique (`frontend/src/lib/georaster-api.ts`)
  ↓
API FastAPI (`backend/app/main.py`)
  ↓
Validation/normalisation Pydantic (`models.py`, `request_contracts.py`)
  ↓
Cache SQLite ── résultat compatible trouvé ──→ restitution immédiate
  ↓ sinon
Moteur d’analyse (`backend/app/gee_client.py`)
  ↓
Google Earth Engine ou repli mock (`mock_engine.py`)
  ↓
Mosaïque, indice/classification, tuiles, statistiques, classes
  ↓
SQLite (`analyses`, `runs`, `processing_cache`, `exports`, classification)
  ↓
Frontend : couche résultat, sous-couches, légende, graphiques, exports
```

Points d’entrée :

- frontend : `frontend/src/start.ts`, `frontend/src/router.tsx`, `frontend/src/routes/__root.tsx` ;
- page métier : `frontend/src/routes/map.tsx` ;
- backend : `backend/app/main.py`, application `app` servie par Uvicorn ;
- GEE : `backend/app/gee_client.py`.

## 4. Flux principal d’une analyse

1. L’utilisateur dessine l’AOI dans `MapView.tsx`.
2. `map.tsx::buildRasterPayload` construit le contrat canonique : `geometry`, dates, `sensor`, `resolution`, `cloud_max`, `index`, `analysis_type` et options spécialisées.
3. La recherche catalogue utilise `POST /api/gee/jobs/catalog`, puis interroge son statut.
4. Avant calcul, `POST /api/result-cache/search` cherche un résultat compatible.
5. À défaut : `POST /api/analyses`, puis `POST /api/analyses/{id}/run`.
6. `main.py::run_analysis` enrichit l’analyse avec le CRS, calcule une clé de cache et appelle `gee_client.compute_sentinel2_index`.
7. Le moteur route vers l’indice, la détection de changement, OSI‑SAR ou une classification.
8. `GET /api/runs/{run_id}/result` restitue statistiques, classes, tuiles, qualité, sous-couches et métadonnées.
9. Leaflet affiche la mosaïque source et la couche résultat ; la légende et les graphiques suivent la sous-couche active.
10. Les exports réutilisent le run stocké et, pour les sorties GEE, reconstruisent l’image finale depuis l’analyse persistée.

## 5. Analyses et données

| Famille | Analyses | Collections principales | Résolution native de calcul |
| --- | --- | --- | --- |
| Indices optiques | NDVI, NDWI, NDBI, BSI, SAVI | `COPERNICUS/S2_SR_HARMONIZED`, Landsat 8/9 Collection 2 L2 | 10 m / 30 m |
| Changement | cinq variantes `CHANGE_*` | mêmes collections optiques, deux mosaïques | 10 m / 30 m |
| OSI‑SAR | `OSI_SAR` | `COPERNICUS/S1_GRD`, JRC Global Surface Water, ERA5 optionnel | classes 10 m, statistiques 30 m par défaut |
| Supervisée | `SUPERVISED_CLASSIFICATION` | mosaïque optique + échantillons utilisateur ou ESA WorldCover v200 | 10 m / 30 m |
| Non supervisée | `UNSUPERVISED_CLASSIFICATION` | mosaïque optique, bandes + cinq indices | 10 m / 30 m |

Les formules, bandes, seuils, classes et palettes vérifiés sont détaillés dans [08_ANALYSES_GEOSPATIALES.md](docs/08_ANALYSES_GEOSPATIALES.md). Les trois couches de chaque détection de changement sont détaillées dans [09_CHANGE_DETECTION.md](docs/09_CHANGE_DETECTION.md).

## 6. Google Earth Engine

Le backend initialise GEE avec `GEE_PROJECT_ID` ou `GOOGLE_CLOUD_PROJECT`. `GEE_ACCOUNT_EMAIL` est informatif dans le statut. En absence de GEE, les calculs utilisent `mock_engine.py`; les exports GEE PNG/GeoTIFF ne sont alors pas disponibles.

La politique backend force actuellement :

- composite médian (`median_composite`) ;
- seuil de probabilité nuage Sentinel‑2 à 40 ;
- filtrage de métadonnée par `cloud_max` ;
- masques nuages Sentinel‑2/Landsat ;
- découpage à l’AOI.

Voir [07_GOOGLE_EARTH_ENGINE.md](docs/07_GOOGLE_EARTH_ENGINE.md).

## 7. Projections et simulations

- Entrée AOI : EPSG:4326.
- Affichage Leaflet : EPSG:3857.
- Analyse/export KSA : choix automatique EPSG:9356 à EPSG:9360 selon la longitude centrale, ou choix manuel.
- EPSG:9333 : KSA‑GRF17 géographique 2D, accepté mais déconseillé pour les opérations métriques.
- GEE remplace les EPSG KSA UTM par leurs équivalents WGS84 UTM EPSG:32636–32640.
- EPSG:9332 : référence géographique 3D expérimentale. Elle est configurée mais n’est appliquée ni aux rasters, ni aux surfaces, ni aux exports. Aucun moteur de simulation 3D n’existe.

Voir [10_PROJECTIONS_CARTOGRAPHIQUES.md](docs/10_PROJECTIONS_CARTOGRAPHIQUES.md) et [12_SIMULATIONS_3D.md](docs/12_SIMULATIONS_3D.md).

## 8. Couches et exports

Le gestionnaire de couches contrôle fond de carte, image source, AOI et résultat. Pour NDBI, le backend conserve `ndbi_raw` et `ndbi_built_detection`, mais l’interface montre uniquement la détection Built-up. La version `v14` utilise GHSL 2018 avec un seuil conservateur de 50 m² bâtis par cellule de 100 m² uniquement pour récupérer des pixels Sentinel‑2 encore sans évidence ; cette référence ne peut pas créer une classe haute confiance. Chaque `CHANGE_*` expose période 1, période 2 et delta ; une seule sous-couche résultat est active à la fois.

Exports accessibles dans l’interface :

- GeoTIFF : URL GEE de l’image finale, limitée à l’AOI, à l’échelle native et au CRS effectif ;
- PNG : composition cartographique 1800 × 1280 ;
- Map PDF : rapport multi-pages ;
- CSV statistiques.

L’API prend aussi en charge `stats_json`, `report_pdf` simple et `map_png` sous forme d’URL GEE. Le code ne fixe explicitement ni valeur NoData, ni `filePerBand`, ni type numérique pour le GeoTIFF : il hérite du masque et du type de l’image GEE. Ce point doit être validé avant un usage SIG contractuel.

Voir [13_EXPORTS_GEOSPATIAUX.md](docs/13_EXPORTS_GEOSPATIAUX.md) et [14_RAPPORTS_PDF.md](docs/14_RAPPORTS_PDF.md).

## 9. Authentification et utilisateurs

Il n’existe pas de système d’authentification applicative. Le profil des paramètres est déclaratif. L’upload/reset du logo vérifie seulement `X-User-Role: admin`, dont la valeur par défaut côté route est déjà `admin`. Ce mécanisme n’est pas une protection de production. La clé API visible dans Settings est persistée, mais n’est pas utilisée pour protéger les routes.

## 10. Installation et tests

Guide vérifié : [04_INSTALLATION_CONFIGURATION.md](docs/04_INSTALLATION_CONFIGURATION.md).

Validation exécutée le 27 juillet 2026 :

```powershell
C:\Users\Imane_C4E\anaconda3\python.exe -m pytest -q backend\tests
npm.cmd --prefix frontend run test:legend-i18n
npm.cmd --prefix frontend run build
```

Résultats :

- backend : 37 tests réussis, 2 avertissements de dépréciation FastAPI ;
- légendes : 13 analyses et 130 termes anglais/arabe validés ;
- build frontend client + SSR : réussi ;
- avertissement de taille de chunks ;
- avertissement du générateur Lovable sur l’écrasement de `MAPTILER_KEY`, alors que cette variable n’est pas utilisée dans le dépôt.

Les tests GEE réels, les téléchargements réseau et l’exactitude scientifique terrain ne sont pas couverts par cette validation locale.

## 11. État actuel et problèmes connus

État : prototype avancé, fonctionnel en local, avec tests automatisés utiles. Limites majeures :

- backend très monolithique (`main.py`, `gee_client.py`) ;
- persistance SQLite locale et jobs en mémoire ;
- sécurité minimale ;
- dépendance à GEE et aux URL temporaires de tuiles/export ;
- documentation historique contradictoire ;
- configuration de résolution demandée non systématiquement appliquée au calcul : le moteur utilise 10 m pour Sentinel‑2 et 30 m pour Landsat ;
- sortie GeoTIFF insuffisamment spécifiée (NoData, dtype, métadonnées embarquées) ;
- Dynamic World/ESA WorldCover visibles comme capteurs de catalogue mais incompatibles avec les 13 analyses exécutables ;
- simulation 3D non implémentée.

Liste complète : [20_PROBLEMES_CONNUS.md](docs/20_PROBLEMES_CONNUS.md).

## 12. Règles avant modification

1. Considérer le code et les tests comme source de vérité.
2. Ne jamais modifier simultanément formule, seuil, palette, contrat API et rendu sans tests dédiés.
3. Préserver le contrat canonique et sa rétrocompatibilité.
4. Tester cache froid, cache chaud, History et régénération de tuiles.
5. Vérifier les trois sous-couches de chaque `CHANGE_*`.
6. Vérifier CRS, AOI, échelle, type de pixel et NoData pour tout changement d’export.
7. Ne pas traiter EPSG:9332 comme CRS raster.
8. Ne jamais committer credentials GEE, base SQLite, exports, uploads ou logs.
9. Exécuter les tests backend, le contrôle i18n et le build.
10. Documenter toute anomalie au lieu de corriger la logique scientifique sans validation explicite.

Voir [19_REGLES_DE_MODIFICATION.md](docs/19_REGLES_DE_MODIFICATION.md).

## 13. Navigation documentaire

Le sommaire officiel et l’ordre de lecture sont dans [docs/00_INDEX_DOCUMENTATION.md](docs/00_INDEX_DOCUMENTATION.md).

Documents clés :

- [Architecture](docs/02_ARCHITECTURE_TECHNIQUE.md)
- [Structure du dépôt](docs/03_STRUCTURE_DU_DEPOT.md)
- [Frontend](docs/05_FRONTEND.md)
- [API backend](docs/06_BACKEND_API.md)
- [Analyses](docs/08_ANALYSES_GEOSPATIALES.md)
- [Projections](docs/10_PROJECTIONS_CARTOGRAPHIQUES.md)
- [Exports](docs/13_EXPORTS_GEOSPATIAUX.md)
- [Tests](docs/17_TESTS_ET_VALIDATION.md)
- [Cartographie de l’ancienne documentation](docs/CARTOGRAPHIE_DOCUMENTATION_EXISTANTE.md)
