# Audit de la copie GeoRaster — 19 octobre 2026

## Portée et méthode

Inspection statique de la copie dans son état d'arrivée, vérifications locales des fichiers et tentatives de tests/build demandées. Aucun fichier métier, checkpoint, configuration ou test n'a été modifié. Aucun modèle n'a été téléchargé. La copie ne contient pas `.git` : historique, diff et attribution des changements antérieurs ne sont pas disponibles. Ce rapport est un nouvel artefact d'audit.

## 1. Carte du projet

```text
backend/
  app/                         API FastAPI, moteur GeoRaster et services AI
    ai/{api,config,models,registry,schemas,services,sources}/
  exports/{map-layouts,reports}/ exports historiques présents
  gee_reference/               scripts GEE de référence
  scripts/                     outils diagnostics/validation
  tests/                       tests historiques, scalabilité et AI Building
  data/models/                 absent dans cette copie
frontend/
  src/routes/                  index, map, catalog, history, settings
  src/features/ai-building/    interface et contrats Building
  src/components/              carte Leaflet, overlay et composants partagés
  scripts/                     tests frontend et fixtures
docs/                          architecture, installation, analyses, AI et workflows
test-data/                     AOI, Maxar, vérité terrain, résultats et benchmarks
```

Les répertoires `scripts/` et `configurations/` à la racine n'existent pas. Les scripts sont sous `backend/scripts/`; aucune configuration autonome de ces noms n'a été trouvée. `exports/` est sous `backend/`. Des résultats de validation et benchmarks sont versionnés sous `test-data/validation-results/`.

**A — GeoRaster historique :** logique API dans `backend/app/main.py`, calculs/GEE dans `backend/app/gee_client.py`, UI carte et pages historiques dans `frontend/src/routes/`, données de test et exports. Les identifiants NDVI, NDWI, NDBI, BSI, SAVI, Change Detection et classifications figurent dans les sources actuelles.

**B — AI Object Detection :** `backend/app/ai/` et `frontend/src/features/ai-building/` avec route de carte et preview.

**C — Production :** `BuildingModelAdapter`, enregistré seul par `create_default_model_registry()` pour `building`.

**D — Expérimental :** `SpaceNet2DeepLabAdapter` existe mais n'est pas enregistré dans le registre par défaut. Le code porte l'étiquette expérimentale. Checkpoint MODEL_C absent.

## 2. Baseline historique et séparation

Les capacités demandées (GEE, Sentinel, indices NDVI/NDWI/NDBI/BSI/SAVI, Change Detection, classifications, AOI, exports et frontend historique) sont présentes dans la base de code. L'application comporte un mode mock/offline de repli lorsque GEE n'est pas disponible (décrit dans `docs/07_GOOGLE_EARTH_ENGINE.md`). Le module AI est séparé sous `backend/app/ai/`; l'intégration frontend est dans sa feature Building et la carte. Pas de refactor effectué.

Cette confirmation porte sur la présence dans le code, pas sur l'exécution des capacités : les dépendances du backend ne sont pas installées. Le répertoire `.git` manquant interdit une comparaison certaine avec une baseline antérieure ou la vérification des fichiers touchés par des changements passés.

## 3. Architecture AI Building : composants observés

| Composant | Fichier(s) | Rôle et état statique |
|---|---|---|
| RasterSource / BaseRasterSource | `backend/app/ai/sources/base_raster_source.py` | Contrat de source raster local, indépendant du fournisseur; présent. |
| GeeRasterSource | `backend/app/ai/sources/gee_raster_source.py` | Matérialisation depuis GEE; présent, non exécuté ici. |
| LocalRasterSource | `backend/app/ai/sources/local_raster_source.py` | Orthophoto locale; présent, non exécuté ici. |
| Maxar profile | `backend/app/ai/services/maxar_multispectral_profile.py` | Détection/conversion Maxar native; présent avec tests dédiés. |
| ImageValidator | `backend/app/ai/services/image_validator.py` | Contrôles format, bandes, géoréférencement; présent. |
| Preprocessing profiles | `backend/app/ai/services/preprocessing_profiles.py`, `preprocessing_service.py` | RGB orthophoto et Sentinel SR déterministes; présents. |
| TilingService | `backend/app/ai/services/tiling_service.py` | Découpage et métadonnées de tuiles; présent. |
| BaseModelAdapter / BuildingModelAdapter | `backend/app/ai/models/` | Interface modèle et adapter U-Net; présent, checkpoint de production absent. |
| SpaceNet2DeepLabAdapter | `backend/app/ai/models/spacenet2_deeplab_adapter.py` | Adapter MODEL_C expérimental, construit Torchvision DeepLabV3-ResNet50; code d'architecture corrigé présent, chargement non validé faute de checkpoint et torch. |
| ModelRegistry | `backend/app/ai/registry/model_registry.py` | Registre lazy; modèle par défaut `BuildingModelAdapter` seulement. |
| InferenceService | `backend/app/ai/services/inference_service.py` | Streaming des prédictions via adapter; présent. |
| PostProcessingService | `backend/app/ai/services/postprocessing_service.py` | Fusion spatiale, seuil et masque; présent, prise en charge memmap observée. |
| BuildingPolygonizationService | `backend/app/ai/services/building_polygonization_service.py` | Polygones et mesures; présent. |
| BuildingResultsService | `backend/app/ai/services/building_results_service.py` | GeoJSON/statistiques; présent. |
| BuildingExportService | `backend/app/ai/services/building_export_service.py` | CSV, métadonnées et ZIP avec GeoJSON; présent. |
| Preview orthophoto | `backend/app/ai/api/ai_raster_routes.py` | GET `/api/ai/raster/{raster_id}/preview.png`, lit une preview bornée; présent. |
| Frontend Building | `frontend/src/features/ai-building/BuildingDetectionPanel.tsx`, `model.ts`, `frontend/src/components/MapView.tsx` | UI, validation des contrats et ImageOverlay Leaflet; présents. |

## 4. Workflow actuel relevé dans le code

`RasterSource` (GEE ou local) → matérialisation et validation par `AIRasterService`/`ImageValidator` → profil RGB/normalisation → `TilingService` → `InferenceService` → `ModelRegistry["building"]` → adapter → cartes de probabilité par tuile → `PostProcessingService` fusionne les recouvrements par accumulation pondérée et seuillage → polygonisation → `BuildingResultsService`/statistiques/GeoJSON → frontend carte, overlay de l'orthophoto et polygones → exports GeoJSON, CSV, JSON de métadonnées et ZIP.

Le chemin d'inférence effectivement enregistré par défaut est MODEL_A, pas MODEL_C. Un passage complet de ce workflow n'a pas pu être exécuté dans cet environnement.

## 5–10. Checkpoints, MODEL_C et étape 13B.2.8

| Vérification | Constat |
|---|---|
| MODEL_A `backend/data/models/building/kastela-dof5/unet_best.pt` | Absent. Taille/hash/architecture du checkpoint réel invérifiables. Le code et les métadonnées d'env définissent U-Net/ResNet34 avec hash attendu `6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987`; ce n'est pas une validation du fichier. `MODEL_A_STATUS = MISSING`. |
| MODEL_C `backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth` | Absent. Taille et SHA-256 non calculables; aucun téléchargement effectué. `MODEL_C CHECKPOINT = MISSING`. |
| Architecture checkpoint MODEL_C | Impossible de confirmer les 370 tensors ni les clés `model.backbone.*`, `model.classifier.*`, `model.aux_classifier.*` dans cette copie puisque le checkpoint manque. L'information historique n'est pas une inspection actuelle du checkpoint. |
| Adapter MODEL_C | `SpaceNet2DeepLabAdapter` construit `torchvision.models.segmentation.deeplabv3_resnet50`, remplace le classifier, exige sortie principale 1 canal et auxiliaire 21 canaux, puis appelle `load_state_dict(..., strict=True)`. **`MODEL_C_ADAPTER_ARCHITECTURE = TORCHVISION_DEEPLABV3_RESNET50`.** Pas de référence SMP DeepLabV3Plus dans cet adapter. |
| Sortie | Consomme le dictionnaire `output["out"]`; l'auxiliaire `output["aux"]` n'est pas consommé à l'inférence. Logits 1 canal → sigmoid → probabilité; interpolation vers taille de tuile. Le code redimensionne l'entrée 640×640 à 512×512. |
| Strict load | Implémentation stricte présente, mais non exécutée. La cause historique `segmentation_head.*` contre les clés torchvision ne correspond plus à l'architecture explicitement construite dans le code actuel; seul un checkpoint réel peut trancher. `STRICT LOAD = NOT RUN`. |
| Étape 13B.2.8 | Le changement d'architecture est **présent dans le code**, sans preuve Git, sans checkpoint et sans validation runtime. `STEP_13B_2_8 = PARTIAL` (implémentée côté source, pas validée). |

## 11. Preprocessing MODEL_C

Le profil RGB orthophoto fixe RGB explicite, entrée uint8 bornée `[0,255]`, conversion float32 et division par 255 en `[0,1]`; masque NoData à zéro. L'adapter vérifie une entrée `[0,1]`, reçoit des tuiles de 640×640 et les redimensionne à 512×512. Il annonce `model_normalization: undocumented_source_preprocessing`; aucune moyenne/écart-type n'est appliqué par lui. Aucun checkpoint/dataset loader MODEL_C ni preuve suffisante d'entraînement n'est présent pour établir la normalisation attendue par le modèle. RGB/range source confirmés, resize d'inférence observable, mean/std du modèle inconnus. `MODEL_C_PREPROCESSING = PARTIAL`.

## 12–17. Registry, raster, statistiques, preview et exports

- **Registry :** MODEL_A adapter est le seul défaut `building`; MODEL_C reste expérimental, non enregistré en production. `PRODUCTION_BUILDING_MODEL = MODEL_A` (code; checkpoint manquant).
- **Grand raster :** `np.memmap` pour accumulation disque de probabilité/poids/validité/masque et seuillage en fenêtres de lignes de 1024 observés dans `postprocessing_service.py`. Correctifs 10J présents statiquement; pas retestés dans ce runtime.
- **Statistiques :** calcul des comptages, aires (total, moyenne, médiane, min/max) et périmètres en unités de carte et métriques dans `building_results_service.py`; valeurs métriques nulles si CRS/mesures ne sont pas métriques. Conversion pixel→coordonnées utilise `inverse_transform * (point.x, point.y)`. Aucun `Affine @ (x,y)` incompatible trouvé dans le service de polygonisation. Tests existent, non exécutés.
- **Preview :** route preview et `ImageOverlay` présents; l'overlay est conditionnel au résultat Building et à des bounds valides. Orthophoto + polygones sont supportés dans l'interface.
- **Exports AI :** services/routes/schema contiennent GeoJSON, CSV, JSON de résultat/métadonnées et ZIP. Exports historiques présents sous `backend/exports/`. Présence statique seulement.
- **Maxar :** profil d'ingestion native et tests présents; validation d'ingestion actuelle non exécutée.
- **Indices, TilingService, PostProcessingService, Polygonization, Results, exports historiques :** aucune modification de cette mission. En raison de l'absence de `.git`, impossible d'attester l'absence d'une modification antérieure dans cette copie.

## 18–20. Tests, versions et lancement local

- Environnement observé : Python 3.12.10, Node 22.23.3, npm 10.9.9.
- Import probing Python : `pytest`, `torch`, `torchvision`, `rasterio`, `affine`, `segmentation_models_pytorch`, `ee` absents. `python -m pytest -q` s'arrête sur `No module named pytest`; suite backend non exécutée. Baseline historique annoncée 216 tests, non vérifiable ici.
- `frontend/node_modules` absent. `npm.cmd test` : contrôle i18n réussi (13 analyses, catalogues bilingues), puis échec car `jszip` manque; les étapes suivantes ne s'exécutent pas. `npm.cmd run build` échoue car Vite absent.
- `npm run build:ssr` : script non défini dans `frontend/package.json`; aucun build SSR actuel n'est configuré par ce nom.
- GEE : noms des variables `GEE_ACCOUNT_EMAIL` et `GEE_PROJECT_ID` présents dans l'environnement, leurs valeurs ne sont pas reproduites ici. Le paquet `earthengine-api` (`ee`) est absent; aucune authentification ni requête GEE effective n'a été vérifiée. Le code utilise credentials Earth Engine locaux et `ee.Initialize` avec le projet configuré. Pas d'authentification d'application GeoRaster complète; la documentation décrit le prototype comme sans auth utilisateur de production.
- **Lancement demandé :** frontend/backend non démarrés car leurs dépendances runtime sont manquantes. L'authentification avec le compte GEE ne peut pas être validée dans cet environnement. Aucun package n'a été installé et aucune commande de démarrage ne reste active.

## 21–24. Statut par catégorie et reprise

| Sujet | Classement | Motif |
|---|---|---|
| GeoRaster historique | B — implémenté, à revalider | Sources présentes; environnement d'exécution absent. |
| MODEL_A | D — bloqué | Checkpoint absent; impossible de charger le modèle production. |
| MODEL_C checkpoint | D — bloqué | Fichier absent; aucune inspection/hash actuelle. |
| MODEL_C adapter | C — expérimental | Adapter Torchvision présent mais non branché au registry et non exécuté. |
| Strict load MODEL_C | D — bloqué | Code strict présent, checkpoint et PyTorch absents; non exécuté. |
| Preprocessing MODEL_C | B/C — partiel/expérimental | RGB et `[0,1]` visibles; mean/std entraînement inconnus. |
| MODEL_C smoke, petit et grand raster | E — pas validé | Aucun checkpoint/runtime; résultats historiques ne prouvent pas cette version du modèle. |
| Maxar ingestion | B — implémenté à revalider | Code et tests présents, non exécutés. |
| Grand raster | B — implémenté à revalider | memmap et fenêtres visibles; aucun test runtime actuel. |
| Statistics | B — implémenté à revalider | Mesures présentes dans code/tests; tests non exécutés. |
| Orthophoto preview | B — implémenté à revalider | Route et overlay présents; pas de session active. |
| AI exports | B — implémenté à revalider | GeoJSON/CSV/JSON/ZIP dans services; non exécutés ici. |
| Fine-tuning | E — pas développé/exécuté dans cette copie | Aucun fine-tuning lancé; traces/data d'annotation présentes ne démontrent pas un entraînement fini. |
| Building Change Detection | E — pas développé | Pas de pipeline dédié observé. |

**LAST_CONFIRMED_COMPLETED_STEP :** pipeline AI Building jusqu'aux composants d'exports et correctifs grand raster/statistiques documentés (10J/10K) — présence de code et artefacts, mais non revalidés dans cette copie. L'architecture source de l'étape 13B.2.8 est également déjà corrigée vers Torchvision.

**CURRENT_BLOCKER :** checkpoints MODEL_A et MODEL_C absents; dépendances Python/frontend manquantes; impossibilité de valider strict load, smoke test, builds ou l'authentification GEE. Pas de `.git` pour retrouver les commits/diffs.

**NEXT_REQUIRED_STEP :** rétablir les dépendances runtime et rendre disponibles localement les checkpoints autorisés attendus (sans téléchargement automatique), puis exécuter l'audit strict-load MODEL_C sur le checkpoint attendu, enregistrer le résultat et seulement après décider si 13B.2.8 est validée. Pour l'application, installer l'environnement prévu et vérifier credentials GEE avant le démarrage supervisé des deux services.

### Résumé du point de vigilance

Les sources courantes gardent MODEL_A en défaut; MODEL_C n'est pas promu. Tiling, post-traitement, polygonisation, résultats, indices et exports historiques sont présents. Une absence de régression historique **ne peut pas être certifiée** sans dépôt Git/diff; aucun changement effectué pendant l'audit.

CURRENT GEO RASTER AI BUILDING STATUS
=====================================

PROJECT AUDIT :
PARTIAL

BASELINE :
BROKEN

BACKEND TESTS :
NOT RUN — pytest et dépendances backend absents

FRONTEND TESTS :
PARTIAL — i18n PASS; reste bloqué par jszip absent

CLIENT BUILD :
FAILED — Vite absent

SSR BUILD :
NOT CONFIGURED — script build:ssr absent

MODEL_A :
MISSING

MODEL_A PRODUCTION :
YES

MODEL_C CHECKPOINT :
MISSING

MODEL_C SIZE :
N/A — fichier absent

MODEL_C SHA256 :
N/A — fichier absent

MODEL_C CHECKPOINT ARCHITECTURE :
NOT VERIFIED — checkpoint absent

MODEL_C ADAPTER ARCHITECTURE :
TORCHVISION_DEEPLABV3_RESNET50

MODEL_C PREPROCESSING :
PARTIAL

MODEL_C STRICT LOAD :
NOT RUN

MODEL_C SMOKE TEST :
NOT RUN

MODEL_C SMALL RASTER :
NOT RUN

MODEL_C LARGE RASTER :
NOT RUN

MODEL_C STATUS :
EXPERIMENTAL ONLY

STEP_13B_2_8 :
PARTIAL

MAXAR INGESTION :
PARTIAL

LARGE RASTER SUPPORT :
PARTIAL

STATISTICS :
PARTIAL

ORTHOPHOTO PREVIEW :
PARTIAL

EXPORTS :
PARTIAL

FINE_TUNING :
NOT_STARTED

BUILDING CHANGE DETECTION :
NOT_STARTED

LAST_CONFIRMED_COMPLETED_STEP :
Présence statique du pipeline jusqu'aux exports et correctifs 10J/10K; adaptateur MODEL_C de type Torchvision présent mais non validé

CURRENT_BLOCKER :
Checkpoints attendus absents, dépendances Python/frontend absentes, authentification GEE non vérifiable

NEXT_REQUIRED_STEP :
Rétablir l'environnement et les checkpoints locaux autorisés, puis exécuter et consigner le strict load MODEL_C avant smoke test et tests raster
