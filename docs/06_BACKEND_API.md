# Backend et cartographie API

Base locale : `http://127.0.0.1:8010`. Toutes les routes ci-dessous existent dans `backend/app/main.py`.

Statuts :

- **active UI** : consommée par le frontend courant ;
- **active ops/API** : valide mais sans consommateur UI direct ;
- **alias/alternative** : doublon ou autre workflow ;
- **à vérifier** : implémentée, mais non couverte de bout en bout.

## Système et paramètres

| Méthode et route | Entrée / réponse | Consommateur | Statut |
| --- | --- | --- | --- |
| `GET /api/health` | santé, heure, résumé MVP | exploitation | active ops/API |
| `GET /api/gee/status` | `{item: enabled, project, account, error}` | Map | active UI |
| `GET /api/settings/platform` | paramètres + catalogue/effectif CRS | Map, Settings, shell | active UI |
| `PUT /api/settings/platform` | JSON paramètres nettoyé et persisté | Settings | active UI |
| `POST /api/settings/logo` | octets image ≤ 2 Mo, header rôle | Settings | active UI, sécurité faible |
| `POST /api/settings/logo/reset` | header rôle | Settings | active UI, sécurité faible |
| `GET /api/dashboard` | KPI, analyses récentes, indices | Dashboard | active UI |

Erreurs typiques : 400 fichier vide, 413 taille logo, 422 format/paramètre, 403 rôle.

## Catalogue et GEE

| Méthode et route | Entrée / réponse | Dépendance GEE | Statut |
| --- | --- | --- | --- |
| `GET /api/catalog/sources` | `{items: SOURCES}` | non | active ops/API |
| `GET /api/catalog/indices?enabled_only=` | catalogue métier | non | active ops/API |
| `GET /api/catalog/images` | `sensor`, `region`, `max_cloud`, `q` ; images mock | non | active UI Catalog |
| `GET /api/images` | toutes les images mock | non | alias inutilisé |
| `POST /api/catalog/images/search?limit=` | `PreviewRequest` ; scènes/mosaïque | oui ou mock | alternative synchrone, UI inutilisée |
| `POST /api/gee/jobs/catalog?limit=` | `PreviewRequest` ; job en mémoire | oui ou mock | active UI Map |
| `GET /api/gee/jobs/{job_id}/status` | progression/résultat | indirecte | active UI Map |
| `POST /api/gee/preview` | `PreviewRequest` ; sélection/qualité | oui ou mock | active ops/API, UI inutilisée |

Erreurs : 404 job, 422 contrat/dates/AOI, absence de scène, 502/erreur GEE transmise par le job.

## Classification

| Méthode et route | Entrée / réponse | Consommateur | Statut |
| --- | --- | --- | --- |
| `GET /api/classification/classes?project_id=` | classes par projet + défaut | Map | active UI |
| `POST /api/classification/classes` | code, nom, couleur, ordre | aucun | active ops/API |
| `GET /api/classification/samples?project_id=` | géométries/propriétés | Map | active UI |
| `POST /api/classification/samples` | géométrie, classe, rôle, qualité | Map | active UI |

Il n’existe pas de PUT/DELETE pour les classes ou échantillons.

## Analyses, runs et cache

| Méthode et route | Entrée / réponse | Consommateur | Statut |
| --- | --- | --- | --- |
| `POST /api/analyses` | `AnalysisCreate` ; analyse enrichie CRS | Map | active UI |
| `GET /api/analyses` | analyses complètes | aucun | active ops/API |
| `GET /api/analyses/{id}` | analyse | aucun | active ops/API |
| `PUT /api/analyses/{id}` | remplacement via `AnalysisCreate` | aucun | active ops/API |
| `DELETE /api/analyses/{id}` | supprime runs, exports, cache lié | History | active UI |
| `POST /api/analyses/{id}/run?force=` | calcule/cache, retourne Run | Map | active UI |
| `POST /api/analysis/change-detection` | workflow tout-en-un | aucun | alternative |
| `POST /api/result-cache/search` | `AnalysisCreate` | Map | active UI |
| `DELETE /api/result-cache/{key}` | suppression d’une couche cachée | Map | active UI |
| `GET /api/runs` | liste légère | aucun | active ops/API |
| `GET /api/runs/{run_id}` | run léger | aucun | active ops/API |
| `GET /api/runs/{run_id}/result` | résultat complet + exports | Map, History | active UI |
| `GET /api/runs/{run_id}/tiles` | tuiles stockées/régénérées | Map | active UI |
| `POST /api/runs/{run_id}/clusters/{code}/rename` | `name` et/ou `color` | Map | active UI |
| `GET /api/history` | runs enrichis et exports | History | active UI |

`run_analysis` renvoie 404 analyse, 422 erreur métier/données, 502 quota/timeout/autre erreur GEE. Le run est créé directement avec statut `succeeded`; il n’y a pas de file de calcul persistante.

## Exports

| Méthode et route | Entrée / réponse | Consommateur | Statut |
| --- | --- | --- | --- |
| `POST /api/runs/{run_id}/export` | `kind`, `layer_key` ; référence export | Map | active UI pour GeoTIFF/CSV |
| `POST /api/export/map-pdf` | `MapPdfExportRequest` ; URL locale | fallback Map | active, rarement pris |
| `GET /api/runs/{run_id}/export/map-pdf` | `layer_key` ; PDF direct | Map | active UI |
| `POST /api/export/map-layout-png` | capture + métadonnées ; URL locale | Map | active UI |
| `GET /api/exports` | références d’exports | aucun | active ops/API |
| `GET /api/exports/{id}/download` | fichier ou redirection GEE 307 | Map, History | active UI |

Kinds standard : `stats_csv`, `stats_json`, `report_pdf`, `map_png`, `geotiff`.

## Contrats d’erreur communs

- 404 : ressource absente ;
- 422 : validation Pydantic ou règle métier ;
- 502 : échec GEE lors du run ;
- 307 : redirection normale vers une URL GEE ;
- erreurs réseau/capture côté frontend présentées par toast.

## Routes documentées à tort dans l’historique

`POST /api/gee/search` n’existe pas. Utiliser le job catalogue ou `/api/catalog/images/search`. Les nombreux endpoints cibles de classification décrits dans `DOCUMENTATION_AMELIORATIONS_GEORASTER.md` ne sont pas implémentés.
