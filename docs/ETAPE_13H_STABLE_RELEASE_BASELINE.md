# ÉTAPE 13H — Stable release baseline

Date de validation : 19 octobre 2026  
Identifiant de release : **GeoRaster-19-10-stable**  
Révision Git : indisponible; cette copie ne contient pas de métadonnées `.git`. L’identifiant et l’état de référence sont consignés dans ce document, aucun tag Git n’a été créé.

## Résumé de validation

Cette copie a été validée avec les services actifs sur `http://127.0.0.1:5184/map` et `http://127.0.0.1:8011`. Le port 8010 appartient à l’autre instance et n’a pas été modifié.

- Backend : **227 tests réussis, 0 échec**.
- Frontend : tests réussis; build client et build SSR réussis. Vite signale des chunks client de plus de 500 kB; le build reste réussi.
- Earth Engine : authentifié et activé sur le projet `gee-satellite-project-123456`.
- Sentinel‑2 : recherche légère réelle depuis le contexte navigateur réussie; mode `gee`, 12 images et une scène disponible.
- Building local : upload de l’orthophoto 512×512 et inférence MODEL_C réussis; 17 polygones et statistiques affichés.
- Exports Building UI : GeoJSON, CSV, Metadata JSON et ZIP téléchargés et leur contenu validé.

Aucun modèle, traitement scientifique, fichier frontend ou fonctionnalité GeoRaster historique n’a été modifié pendant cette validation. Le changement de dépendances concerne l’installation d’`earthengine-api` et de ses dépendances déclarées dans le Python 3.12 utilisé par le backend 8011. PyTorch, Torchvision, NumPy et Rasterio n’ont pas été mis à niveau.

## Environnement backend

Processus 8011 : `C:\Users\Imane_C4E\AppData\Local\Programs\Python\Python312\python.exe`, Python **3.12.10**. `sys.prefix` est l’installation Python globale; le `.venv` local de cette copie ne contient pas les dépendances backend. Pour lancer l’application dans cette copie, `PYTHONPATH` ajoute les dépendances runtime déjà installées sous `Georaster-03-10\backend\.venv\Lib\site-packages`. Conserver ce chemin runtime disponible tant qu’un environnement backend autonome n’a pas été préparé.

| Dépendance | Version utilisée |
| --- | --- |
| Python | 3.12.10 |
| earthengine-api | 1.7.48 (installée dans Python 3.12) |
| PyTorch | 2.8.0+cpu |
| Torchvision | 0.23.0+cpu |
| NumPy | 2.5.4 |
| Rasterio | 1.5.2 |
| Affine | 3.0.1 |
| Shapely | 2.2.0 |
| FastAPI | 0.115.6 |
| Uvicorn | 0.32.1 |
| Pydantic | 2.12.4 |
| pytest | 7.4.0 |
| segmentation-models-pytorch | 0.5.0 |
| Pillow | 12.3.0 |
| httpx | 0.28.1 |
| google-auth | 2.62.0 |

Aucun upgrade de PyTorch, Torchvision, NumPy ou Rasterio n’a été fait. Le fichier credentials Earth Engine est à `C:\Users\Imane_C4E\.config\earthengine\credentials`; son contenu n’est pas inclus dans ce rapport. `GET /api/gee/status` renvoie `enabled: true`, le projet configuré, et aucune erreur.

## Modèles

### MODEL_A — conservé dans le backend

- Fichier : `backend/data/models/building/kastela-dof5/unet_best.pt`
- Taille : **97 919 546 octets**
- SHA256 : `6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987`
- Architecture : U‑Net avec encodeur ResNet‑34.
- Configuration conservée : entrée 512×512, seuil 0,50, normalisation z-score par canal.
- Rôle dans cette baseline : modèle legacy disponible explicitement; il n’est pas le modèle Building par défaut.

### MODEL_C — modèle Building par défaut

- Fichier : `backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth`
- Taille : **168 357 171 octets**
- SHA256 : `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555`
- Architecture : Torchvision DeepLabV3 / ResNet‑50, chargement strict; sortie principale à un canal et activation sigmoid pour la carte de probabilités.
- Registre : `spacenet2_deeplab` est le modèle par défaut Building. L’état « default » décrit la sélection de cette copie; les candidats n’ont pas de validation scientifique complète.
- Entrée : RGB, NCHW float32, 512×512, valeurs [0, 1]. Le profil d’adaptation calcule un min–max RGB global sur le raster, puis ramène les pixels à [0, 1]. Pas de moyenne/écart‑type fixe. Le statut de compatibilité de l’interpolation de redimensionnement reste partiel.
- Paramètres de référence : tuiles 512×512, batch maximal 4, chevauchement 20 %, seuil 0,50.

## Workflow Building validé

Orthophoto locale → validation et préparation raster → lecture RGB → tuilage 512×512 → normalisation min–max globale MODEL_C → inférence batch → fusion des probabilités de tuiles superposées → post-traitement → polygonisation → statistiques → affichage Leaflet sur l’aperçu orthophoto → exports.

Le smoke test après redémarrage du backend a chargé `zone_1_residential.tif` (512×512, uint8), utilisé `spacenet2_deeplab`, renvoyé HTTP 200 et produit **17 candidats**. L’interface affichait les 17 géométries et l’ImageOverlay orthophoto. Statistiques observées : aire totale **1 242,03 m²**, moyenne **73,06 m²**, médiane **50,47 m²**, minimum **1,35 m²**, maximum **425,20 m²**.

Les quatre boutons d’export ont été déclenchés dans l’interface; les fichiers non vides et le contenu ont été contrôlés : GeoJSON (FeatureCollection), CSV, metadata JSON liée au modèle/hash, et ZIP valide.

## Earth Engine et Sentinel‑2

- Interpréteur backend : Python 3.12.10 indiqué ci-dessus.
- earthengine-api : 1.7.48.
- Projet : `gee-satellite-project-123456`.
- Compte configuré : `imane19elhamri@gmail.com`.
- `GET /api/gee/status` : `enabled=true`, `error=null`.
- Vérifications directes : `ee.Initialize(project=...)` réussi et `ee.Number(1).getInfo()` vaut `1`.
- Recherche d’application Sentinel‑2 de petite emprise/période : mode `gee`, 12 images et une scène disponible; aucune analyse raster lourde lancée.

## Baseline historique

Les modules historiques restent présents séparément de `backend/app/ai/` : GEE/Sentinel, NDVI, NDWI, NDBI, BSI, SAVI, Change Detection, classifications supervisées et non supervisées, AOI, exports historiques, et mode de repli offline/mock. Le frontend cartographique historique reste présent. Aucun refactor ni changement de ces traitements n’a été effectué.

## Résultats des suites et builds

- Backend : **227 passed / 0 failed** lors du test complet final.
- Frontend : `npm test` réussi (UI bilingue, AOI import, contrat/intégration AI Building).
- Build client : réussi.
- Build SSR : réussi.
- L’avertissement de taille des chunks client (>500 kB) reste une optimisation facultative; il n’a pas bloqué le build.

## Backlog explicitement différé

- Ground Truth : **DEFERRED**.
- Fine-tuning : **NOT STARTED**.
- Building Change Detection : **NOT STARTED**.
- Validation scientifique de l’exactitude : **NOT COMPLETE**.
- Phase 2 d’optimisation large raster : **OPTIONAL**.
- Optimisation des chunks JavaScript frontend : **OPTIONAL**.

ÉTAPE 13H — STABLE RELEASE BASELINE

RELEASE STATUS :
READY

BACKEND :
VALIDATED

FRONTEND :
VALIDATED

GEE :
VALIDATED

SENTINEL-2 :
VALIDATED

MODEL_A :
BACKEND RETAINED

MODEL_C :
DEFAULT

MODEL_C BUILDING :
VALIDATED

LOCAL ORTHOPHOTO :
VALIDATED

STATISTICS :
VALIDATED

MAP DISPLAY :
VALIDATED

EXPORTS :
VALIDATED

BACKEND TESTS :
227 PASSED / 0 FAILED

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS

GEE PROJECT :
gee-satellite-project-123456

GROUND TRUTH :
DEFERRED

FINE TUNING :
NOT STARTED

BUILDING CHANGE DETECTION :
NOT STARTED

SCIENTIFIC ACCURACY :
NOT YET VALIDATED

READY FOR STABLE RELEASE :
YES

NEXT STEP :
FREEZE VERSION
