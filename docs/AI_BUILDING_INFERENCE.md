# Inférence bâtiment — étape 3

Cette étape ajoute le moteur d’inférence générique et son premier adaptateur de
segmentation. Elle ne produit ni polygone, ni GeoJSON, ni comptage de bâtiments.

Sur une machine CPU, installer le wheel dédié sans CUDA avec :

```powershell
python -m pip install torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu
```

## Architecture

```text
PreparedTile
  → InferenceService
  → ModelRegistry["building"]
  → BuildingModelAdapter
  → Tensor PyTorch [1, 3, 640, 640], float32
  → probability_map [640, 640], float32
  → threshold
  → binary_mask [640, 640], uint8
  → TilePrediction
```

`BaseModelAdapter` isole GeoRaster du runtime. Un futur adaptateur arbre,
véhicule, ONNX ou TensorRT pourra remplacer l’implémentation sans modifier le
pipeline raster ou l’API.

## Configuration du modèle réel

Le checkpoint n’est jamais téléchargé automatiquement. Les variables sont :

- `AI_BUILDING_MODEL_PATH` : chemin explicite vers un module TorchScript ;
- `AI_BUILDING_MODEL_NAME` : nom, défaut `building-segmentation` ;
- `AI_BUILDING_MODEL_VERSION` : version, défaut `v1` ;
- `AI_BUILDING_OUTPUT_KIND` : `logits` ou `probabilities` ;
- `AI_BUILDING_PROBABILITY_THRESHOLD` : défaut `0.50` ;
- `AI_ALLOW_CUDA` : CUDA seulement si cette valeur est vraie et si CUDA existe.

Sans chemin configuré, une tuile valide provoque l’erreur métier
`MODEL_NOT_CONFIGURED`. Un chemin absent provoque `MODEL_FILE_NOT_FOUND`. Un
fichier incompatible provoque `MODEL_LOAD_FAILED`. Aucune prédiction fictive
n’est produite par la route de production.

Le contrat de checkpoint réel retenu est TorchScript afin que l’architecture du
réseau reste encapsulée dans le fichier. La sortie acceptée est un Tensor, le
premier élément d’un tuple/liste, ou une clé `out`, `logits` ou `mask`. Après
retrait des dimensions batch/canal unitaires, sa forme doit être 640 × 640.

## Provenance et licence

Aucun checkpoint externe n’est inclus dans le projet et aucun téléchargement
de poids n’a été effectué. Par conséquent :

```text
REAL_BUILDING_CHECKPOINT = NOT_CONFIGURED
PROVENANCE               = NOT_APPLICABLE
WEIGHTS_LICENSE           = NOT_APPLICABLE
MODEL_MODE                = TEST_ONLY pour les tests automatisés uniquement
```

Avant toute intégration future, la source, l’URL, l’architecture, le dataset,
les licences du code et des poids, la résolution, les canaux et la normalisation
devront être documentés et validés.

## Inférence et masque

L’entrée interne est CHW `float32` dans `[0, 1]`; l’adaptateur ajoute la dimension
batch NCHW. Le modèle est placé en `eval()` et exécuté sous
`torch.inference_mode()`. Si la sortie contient des logits, `sigmoid` est appliqué
dans l’adaptateur.

Après inférence, probability map et masque binaire sont forcés à zéro sur NoData
et padding. Le seuil de 0,50 est technique et non calibré scientifiquement.
Le ratio positif ne représente ni une précision, ni une confiance globale, ni
un nombre de bâtiments.

## Chargement et streaming

Le registre conserve une instance par type. Le checkpoint est chargé une seule
fois, à la première tuile valide. `reload("building")` ferme l’instance courante
et en recrée une uniquement lorsqu’un rechargement contrôlé est demandé.

`InferenceService.iter_predictions` consomme le générateur de tuiles et produit
un générateur de prédictions. Une tuile marquée `skip_inference` ne déclenche pas
le modèle. Les grandes matrices ne figurent jamais dans la réponse API.

## API

`POST /api/ai/inference/building` réutilise `AIRasterService`, `TilingService` et
`InferenceService`. La réponse contient uniquement le modèle, les comptes de
tuiles, les agrégats techniques et les temps. Elle porte toujours
`quality_mode=integration_test` pour Sentinel-2 à 10 m.
