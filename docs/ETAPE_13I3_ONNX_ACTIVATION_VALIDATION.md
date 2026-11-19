# ÉTAPE 13I.3 — ONNX default activation et validation

Date : 20 octobre 2026  
Copie : `Georaster-19-10`

## Résultat

Le backend 8011 a été arrêté puis relancé avec `backend/.venv` (Python 3.12.10). Le port 8010 est resté actif et intact. Le backend 8011 répond toujours après les validations.

`SpaceNet2DeepLabAdapter` sélectionne `onnxruntime` par défaut quand `SPACENET2_ENGINE` n’est pas défini. La branche ONNX charge l’artefact puis exécute l’inférence CPU sans fallback silencieux vers PyTorch. Les inférences complètes réussies ci-dessous, le profil du `.venv` et les dépendances ONNX présentes confirment l’activation en pratique.

Artefact ONNX : 158 461 253 octets, SHA-256 `94661DED0BC79BBCA99C03D55D817BCB7369D46EB13D7983EBF6AE711003FD45`. Le checkpoint MODEL_C `.pth` conserve le SHA-256 attendu `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555`. MODEL_A conserve son SHA-256 attendu `6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987`.

## Essais de l’application sur 8011

| Raster préparé | Dimensions | Résultat | Temps mesuré |
|---|---:|---:|---:|
| `ai-ortho-43561b1ae137-001127b57045-3812594d9838` | 512×512 | HTTP 200, 17 candidats | 4,55 s côté requête |
| `ai-ortho-8a2cfdde5ede-001127b57045-ff17132850b4` | 2048×2048 | HTTP 200, 65 candidats | 84,90 s de traitement indiqué par l’API |

Le temps d’API de 84,90 s comprend la préparation, l’inférence et le post-traitement, pas uniquement le calcul du modèle. Les deux réponses identifient `spacenet2_deeplab`, DeepLabV3 ResNet-50, le hash MODEL_C attendu et le profil `full_raster_global_rgb_minmax_v1`. Les statistiques du raster moyen incluent notamment une aire totale de 5 323,36 m² et 65 candidats.

Les previews raster 512×512 et 2048×2048 retournent HTTP 200 avec `image/png`. L’API d’export a répondu HTTP 200 pour GeoJSON, CSV, métadonnées JSON et ZIP. Les réponses ont également passé la sérialisation des FeatureCollections et des statistiques.

Le frontend 5184 répond HTTP 200 sur `/map`. `.env.local` et le bundle client configurent `http://127.0.0.1:8011` comme API. Les tests frontend réussissent et le build Vite a généré les sorties client et serveur SSR. Aucun navigateur n’étant exposé à l’outil UI de cette session, le rendu visuel de la carte et l’alignement observé à l’écran restent non vérifiés.

## GEE

`GET /api/gee/status` répond HTTP 200, mais retourne `enabled=false` et l’erreur « Credentials Earth Engine introuvables ou invalides ». Le projet reste `gee-satellite-project-123456`, le compte `imane19elhamri@gmail.com` et la collection Sentinel-2 `COPERNICUS/S2_SR_HARMONIZED`. Aucun credential ni fichier de configuration n’a été changé. La requête GEE Sentinel-2 n’a donc pas pu être validée dans cette instance redémarrée.

## Vérifications

- Backend : **228 passed, 0 failed**, 19 subtests passed. Exécuté avec les chemins PROJ/GDAL du `.venv` Rasterio.
- Frontend : `npm.cmd test` réussi (i18n, import AOI, contrat et intégration Building).
- Builds frontend : build client et SSR Vite réussis.
- Ports : 8011 et 5184 répondent ; 8010 conserve son listener initial (PID 10408).
- Aucun modèle, indice, traitement Building, export, classification ou fichier de configuration métier n’a été modifié pendant la validation. Le présent rapport est le seul nouveau fichier de documentation.

## Suite

L’activation ONNX et les inférences sur rasters petit et moyen sont acceptées techniquement. La validation d’ensemble avec GEE reste incomplète jusqu’à ce que le backend 8011 puisse lire les credentials Earth Engine. Le rendu visuel de la carte devra également être contrôlé dans un navigateur. Une fois ces contrôles terminés, la suite IA prévue est l’étape 13J, précision des polygones Building.

```text
ÉTAPE 13I.3 — ONNX DEFAULT ACTIVATION

BACKEND 8011 :
RUNNING

MODEL_C :
spacenet2_deeplab

ACTIVE ENGINE :
ONNX_RUNTIME_CPU

ONNX MODEL LOAD :
SUCCESS

SMALL RASTER :
SUCCESS

MEDIUM RASTER :
SUCCESS

MEDIUM RASTER TIME :
84.90 s (API processing metadata; inclusive)

MEDIUM RASTER CANDIDATES :
65

MAP DISPLAY :
NOT_RUN (no browser surface available)

ORTHOPHOTO ALIGNMENT :
NOT_RUN visually; preview API validated

STATISTICS :
VALIDATED

GEOJSON EXPORT :
VALIDATED

CSV EXPORT :
VALIDATED

METADATA EXPORT :
VALIDATED

ZIP EXPORT :
VALIDATED

FRONTEND → 8011 :
VALIDATED (configuration and HTTP)

GEE :
FAILED (credentials unavailable to backend 8011)

BACKEND TESTS :
228 PASSED / 0 FAILED

FRONTEND TESTS :
SUCCESS

MODEL_A :
UNCHANGED

MODEL_C CHECKPOINT :
UNCHANGED

READY_FOR_ONNX_ACCEPTANCE :
YES (ONNX inference acceptance; GEE/UI checks remain separate)

NEXT STEP :
13J BUILDING POLYGON PRECISION
```
