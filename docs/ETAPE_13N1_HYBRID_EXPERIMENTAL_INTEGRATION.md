# ÉTAPE 13N.1 — Intégration expérimentale du modèle hybride C + D

## Résumé

MODEL_E est ajouté comme moteur Building expérimental, sous l’identifiant `hybrid_model_c_model_d` et le nom « Hybrid DeepLabV3 + WHU ». Le registre conserve `spacenet2_deeplab` (MODEL_C) comme modèle Building par défaut. MODEL_D reste expérimental. Aucun checkpoint n’a été modifié et aucune promotion en production n’a eu lieu.

MODEL_E infère MODEL_C et MODEL_D sur les mêmes tuiles 512 px, avec un recouvrement de 50 %. Chaque moteur utilise son prétraitement propre. Le backend fusionne ensuite leurs masques binaires globaux avec un OR, contrôle la grille et la couverture, puis appelle une seule fois le post-traitement et la polygonisation existants. Une erreur de l’un des composants ou une divergence d’alignement interrompt le traitement; il n’y a pas de repli silencieux.

La vérité terrain 13N reste approximative et destinée à l’ingénierie. Les chiffres ci-dessous décrivent l’exécution et les sorties, pas une mesure scientifique de précision.

## Composants intégrés

- `backend/app/ai/models/hybrid_building_adapter.py` — adaptateur MODEL_E; charge obligatoirement C et D, conserve leurs identités et timings, et propage leurs erreurs.
- `backend/app/ai/registry/model_registry.py` — enregistrement de MODEL_E en expérimental; MODEL_C demeure le défaut.
- `backend/app/ai/api/ai_postprocessing_routes.py` — deux passes de prédiction, validation des grilles/couvertures, union raster binaire et appel unique au nettoyage.
- `backend/app/ai/services/postprocessing_service.py` — fusion des prédictions par moteur sur la grille globale et post-traitement unique du masque union. La comparaison des bounds utilise désormais le modèle typé `TileBounds`; le contrôle des valeurs binaires se fait par fenêtres bornées.
- `backend/app/ai/api/ai_vectorization_routes.py`, `backend/app/ai/services/building_polygonization_service.py`, `backend/app/ai/services/building_results_service.py` — polygonisation et résultat standard GeoRaster avec métriques et temps composant.
- `backend/app/ai/services/building_export_service.py` — état hybride propagé dans GeoJSON, CSV, metadata JSON et ZIP.
- `frontend/src/features/ai-building/model.ts`, `frontend/src/features/ai-building/BuildingDetectionPanel.tsx` — choix de modèle, libellé expérimental et contrat de résultat.
- `frontend/src/components/MapView.tsx` — rendu Leaflet de `feature_collection` utilisé aussi par les résultats MODEL_E.

MODEL_C applique son prétraitement SpaceNet existant (statistiques RGB globales au raster et normalisation propre à l’adaptateur). MODEL_D reçoit RGB en float32 dans [0,1], sans moyenne/écart-type ImageNet. Les seuils C et D sont identiques dans cette intégration (0,50), conformément à la définition du masque union.

## Exécutions réelles

Les quatre appels ont utilisé le contrat HTTP `/api/ai/results/building` via FastAPI TestClient et les rasters déjà présents dans le cache local. Le comparatif 2048×2048 utilise le même raster `ai-ortho-8a2cfdde5ede-001127b57045-ff17132850b4` (EPSG:32637, résolution 0,35 m) pour C, D et E. Les bounds et le CRS retournés sont identiques pour les trois sorties.

| Cas | HTTP | Candidats | Surface totale | Temps écoulé | Détail mesuré |
|---|---:|---:|---:|---:|---|
| MODEL_E, 512×512 | 200 | 60 | 4 965,66 m² | 15,56 s | C 2,65 s; D 2,01 s; union 0,094 ms; polygonisation 37,11 ms |
| MODEL_C, 2048×2048 | 200 | 68 | 7 094,10 m² | 138,61 s | polygonisation 118,96 ms |
| MODEL_D, 2048×2048 | 200 | 31 | 788,17 m² | 105,27 s | polygonisation 93,18 ms |
| MODEL_E, 2048×2048 | 200 | 96 | 7 839,26 m² | 246,54 s | C 130,76 s; D 101,45 s; union 2,94 ms; polygonisation 127,27 ms |

Les temps sont des mesures locales CPU, incluant le chargement froid des modèles au premier usage de ce processus et la construction complète du résultat. Le temps hybride confirme le coût des deux inférences. Le pic RAM corrigé, mesuré dans le processus pendant l’appel MODEL_E 2048×2048, est de **2 322,6 MiB**. La consommation dépendra de la machine et du fait que les modèles soient déjà chargés.

Les masques C et D sont seuillés indépendamment à 0,50, puis réunis par OR au niveau raster. Le test unitaire vérifie que le résultat binaire remis au nettoyage est bien cette union. Le traitement réel 2048×2048 a renvoyé 96 candidats E, contre 68 C et 31 D; la somme des candidats n’est pas une métrique de qualité et ne permet pas à elle seule de conclure sur les faux positifs.

## Exports et affichage

Sur les résultats E 512×512 et 2048×2048, les quatre exports ont renvoyé HTTP 200 : GeoJSON, CSV, metadata JSON et ZIP. Les propriétés GeoJSON et la ligne CSV portent `HYBRID_EXPERIMENTAL`; les metadata JSON et celles incluses dans le ZIP indiquent `HYBRID_EXPERIMENTAL` et `fusion_method=UNION`.

La réponse standard contient le FeatureCollection géoréférencé en EPSG:4326 pour affichage. Le contrat frontend, le choix MODEL_E et les tests d’intégration frontend passent; `MapView.tsx` affiche les bâtiments avec son calque Leaflet GeoJSON partagé. Un contrôle visuel interactif dans un navigateur n’a pas été exécuté pour cette étape.

## Non-régression et limites

- MODEL_A, son adaptateur et son checkpoint n’ont pas été touchés.
- Le code et les poids propres de MODEL_C et MODEL_D n’ont pas été modifiés; seul le registre ajoute MODEL_E et le pipeline ajoute le point de fusion commun.
- MODEL_C reste le défaut du registre. MODEL_E et MODEL_D sont expérimentaux.
- Les fonctionnalités GEE, indices, classifications, Change Detection et exports historiques n’ont pas été modifiés par cette intégration.
- Le grand raster d’environ 96,5 MP n’a pas été lancé. Son exécution reste conditionnée à un arbitrage ultérieur sur le temps et la mémoire observés.
- Aucun fine-tuning n’a été exécuté. Aucun score Precision/Recall/F1 n’est revendiqué.

## Vérifications

- Backend : `234 passed`, `0 failed`, `19 subtests passed` (suite complète; exécution avec le répertoire temporaire projet-local pour contourner l’accès refusé au dossier Temp Windows).
- Tests ciblés MODEL_E : `4 passed` — fusion des deux sorties, propagation sans fallback, union raster suivie d’un seul nettoyage, registre et défaut MODEL_C.
- Frontend : `npm.cmd test` réussi (tests i18n, import AOI et contrat/intégration AI Building).
- Build frontend : `npm.cmd run build` réussi pour la cible client **et** la cible SSR (`vite build` les produit successivement). Avertissement de taille sur certains chunks JavaScript, sans échec du build.
- Registry : MODEL_C (`spacenet2_deeplab`) est toujours `default=true`; MODEL_E (`hybrid_model_c_model_d`) et MODEL_D (`whu_unetplusplus_effb4`) sont `default=false`, statut `experimental`.

## Conclusion

MODEL_E est techniquement intégré et a passé les appels réels 512×512 et 2048×2048, les statistiques, la géoréférence, l’affichage via le contrat frontend, et les quatre formats d’export. Son temps 2048×2048 (environ 4 min 7 s) et son pic RAM (environ 2,27 GiB) le rendent exploitable pour un essai utilisateur contrôlé sur des rasters de cette taille, mais le cas 96,5 MP reste non testé et ne doit pas être déduit de ces mesures. Garder MODEL_C comme défaut de production.

MODEL_E :
hybrid_model_c_model_d

COMPONENT MODELS :
MODEL_C + MODEL_D

FUSION METHOD :
BINARY MASK UNION

STATUS :
EXPERIMENTAL

SMALL RASTER :
SUCCESS (512×512, HTTP 200)

MEDIUM RASTER :
SUCCESS (2048×2048, HTTP 200 pour C, D et E)

MODEL_C CANDIDATES :
68 (2048×2048)

MODEL_D CANDIDATES :
31 (2048×2048)

MODEL_E CANDIDATES :
96 (2048×2048)

MODEL_C TOTAL AREA :
7094.10 m²

MODEL_D TOTAL AREA :
788.17 m²

MODEL_E TOTAL AREA :
7839.26 m²

MODEL_C TIME :
138.61 s

MODEL_D TIME :
105.27 s

MODEL_E TOTAL TIME :
246.54 s (C 130.76 s; D 101.45 s; union 2.94 ms; polygonisation 127.27 ms)

MODEL_E RAM PEAK :
2322.62 MiB

GEOREFERENCE :
VALIDATED

MAP DISPLAY :
VALIDATED (frontend contract and Leaflet GeoJSON path; interactive browser visual NOT_RUN)

GEOJSON EXPORT :
VALIDATED (HTTP 200, HYBRID_EXPERIMENTAL properties)

CSV EXPORT :
VALIDATED (HTTP 200, HYBRID_EXPERIMENTAL row)

METADATA EXPORT :
VALIDATED (HTTP 200, HYBRID_EXPERIMENTAL and UNION)

ZIP EXPORT :
VALIDATED (HTTP 200, includes GeoJSON, CSV and metadata JSON)

MODEL_A :
UNCHANGED

MODEL_C :
UNCHANGED

MODEL_D :
UNCHANGED

DEFAULT MODEL :
MODEL_C

BACKEND TESTS :
234 PASSED / 0 FAILED (19 subtests passed)

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS

READY_FOR_HYBRID_USER_TEST :
YES (512 and 2048 CPU runs passed; large raster not tested)

NEXT STEP :
13N.2 REAL ORTHOPHOTO HYBRID TEST /
KEEP MODEL_C /
KEEP MODEL_D EXPERIMENTAL
