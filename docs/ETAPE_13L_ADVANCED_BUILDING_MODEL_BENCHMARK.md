# ÉTAPE 13L — Advanced Building Footprint Model Benchmark

## Résultat exécutif

Le benchmark a traité les **16 mêmes patches Maxar 512×512**, sans réécrire ni transformer les images sources. MODEL_C reste la baseline. Deux candidats ont des poids reproductibles et ont été chargés strictement : WHU U-Net++ / EfficientNet-B4 et HOTOSM U-Net / ResNet-34. Les trois modèles ont généré une carte de probabilité, un masque binaire seuillé à 0,50 et des polygones issus du même polygoniseur Rasterio.

Les annotations du jeu `maxar_v1` sont toutes `NOT_ANNOTATED` (0/16 validées). Les différences de contour ci-dessous sont donc une **lecture visuelle exploratoire** ; aucun score de précision, rappel ou F1 n’est calculé et aucun nouveau modèle ne peut être choisi comme supérieur de façon mesurée. La décision de cette étape est **D — NEED_GROUND_TRUTH_BEFORE_DECISION**.

## Modèles et reproductibilité

| MODEL_ID | Architecture / backbone | Données d’entraînement publiées | Entrée / preprocessing utilisé | Licence annoncée | Poids / taille / chargement strict | ONNX et faisabilité CPU |
|---|---|---|---|---|---|---|
| `spacenet2_deeplab` (MODEL_C) | Torchvision DeepLabV3 / ResNet-50, sortie binaire | SpaceNet 2 | RGB 512×512, RGB global min-max vers float32 [0,1], logits 1 canal → sigmoid | Déclaration du dépôt : MIT | `best_deeplab.pth`, 168,357,171 octets; SHA256 `170C49E1…B84DC555` | ONNX existant, exécuté par ONNX Runtime CPU. Baseline stable. |
| `whu_unetplusplus_efficientnetb4` | U-Net++ / EfficientNet-B4, SMP, 2 logits | WHU Building Dataset, RGB aérien 0,3 m, patches 512² | RGB 512², float32 RGB [0,1], softmax classe bâtiment. La fiche publie RGB/taille mais ne spécifie pas mean/std ; aucune normalisation mean/std n’a été inventée. Le dataset loader GeoAI documente le passage en [0,1]. [Model card](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4), [loader GeoAI](https://opengeoai.org/timm_segment/) | Apache-2.0 | `model.pth`, 84,027,346 octets; SHA256 `922AF7C9…BCC30DC6`; strict `load_state_dict` réussi contre U-Net++ EfficientNet-B4 | Export ONNX techniquement plausible pour cette architecture PyTorch, mais **non essayé** ici. CPU viable sur ce jeu : 1,970 s/patch en moyenne. La fiche annonce ~20,8 M paramètres et un entraînement GPU RTX 6000 Ada; temps/consommation GPU ne sont pas requis pour l’inférence CPU. |
| `hotosm_unet_resnet34` | U-Net / ResNet-34, 3 têtes : masque, frontière, distance signée | `hotosm/vhr-building-segmentation`, imagerie OpenAerialMap + étiquettes OSM | RGB [0,1], 256×256 natif; les 512² inchangés ont été évalués en 4 fenêtres sans recouvrement. Carte bâtiment = sigmoid du canal 0. [Model card](https://huggingface.co/nilsho01/unet-resnet34-vhr-buildings) | AGPL-3.0 selon la fiche : revue de compatibilité requise avant intégration ou distribution | `unet_bldg_instance.pth`, 97,924,507 octets; SHA256 `99AA91E1…EF25DB7E1D`; strict `load_state_dict` réussi contre SMP U-Net ResNet-34 à 3 canaux | Export ONNX plausible, **non essayé**. Le plus rapide ici : 0,931 s/patch CPU, quatre fenêtres natives. Environ 24,4 M paramètres annoncés. Son code de watershed n’a pas été repris ; cette comparaison utilise la même polygonisation simple que les autres. |

Les deux candidats représentent des familles employées spécifiquement pour la segmentation de bâtiments aériens, avec fichiers de poids réellement présents et chargés. La fiche WHU publie un IoU de test WHU de 0,9054 ; la fiche HOTOSM décrit les données, la configuration et plusieurs résultats sur ses propres données. Ces mesures publiées ne sont pas comparables entre elles ni transférables aux orthophotos Maxar de GeoRaster. [WHU](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4), [HOTOSM](https://huggingface.co/nilsho01/unet-resnet34-vhr-buildings).

### Candidats examinés puis écartés du run

- **DINOv3 / UPerNet (HOTOSM)** : poids ONNX référencés, mais l’artefact dépend aussi de DINOv3 et de sa licence Meta dédiée. Non téléchargé ni exécuté ; CPU plus coûteux et conditions d’utilisation/distribution à traiter avant intégration. [Licence DINOv3](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md).
- **Inria / U-Net ResNet-34** : poids identifiés dans la documentation mais aucun artefact de release reproductible n’a été disponible au moment de la sélection.
- **DeepLabV3+, HRNet, D-LinkNet, Mask2Former et Swin** : pas de checkpoint bâtiment haute résolution à la fois reproductible, clairement licencié et directement chargeable dans l’environnement courant retenu pour ce benchmark. Ils ne sont pas déclarés évalués.

Le choix de deux candidats respecte le filtre demandé (2 à 4) sans présenter un modèle seulement parce que son nom est populaire. Aucun candidat expérimental n’a été ajouté au registre GeoRaster ni branché au backend.

## Méthode du benchmark

- Sources : `backend/data/fine_tuning/buildings/maxar_v1/images/` et leurs métadonnées. 16 fichiers TIFF, 512×512, 3 bandes RGB, résolution indiquée 0,35 m; chaque `patch_id` apparaît avec `annotation_status=NOT_ANNOTATED`.
- Environnement : `backend/.venv`, Python associé au backend, PyTorch 2.8.0+cpu, Torchvision 0.23.0+cpu, Rasterio 1.5.2, ONNX Runtime 1.22.1, segmentation-models-pytorch 0.5.0. Aucun GPU n’est utilisé.
- Images sources identiques pour chaque prédiction. MODEL_C est appelé par son adaptateur existant et sa normalisation actuelle; les autres modèles reçoivent le RGB dérivé de ces mêmes pixels avec leur taille/preprocessing documentés. Les quatre fenêtres HOTOSM sont une découpe en mémoire; les TIFF sources restent inchangés.
- Seuil commun de comparaison : 0,50. WHU : softmax classe 1; MODEL_C : sigmoid; HOTOSM : sigmoid du canal masque 0.
- Chaque sortie probabilité et binaire conserve la géotransformation/CRS source. Les polygones sont extraits avec `rasterio.features.shapes`, connectivité 8, puis invalidités de pixels en diagonale réparées avec `shapely.make_valid`. C’est une vectorisation identique minimale pour comparer les masques, **pas** le service de post-traitement/polygonisation de production GeoRaster.
- Les temps ci-dessous couvrent l’inférence du modèle (16 patches; HOTOSM = quatre inférences 256² par patch), pas la lecture TIFF, le polygoniseur, l’export ou le navigateur. Le temps de chargement modèle inclut construction + poids pour les modèles PyTorch; pour MODEL_C il mesure l’ouverture de la session ONNX.
- Pic mémoire : pic de working set du processus Windows contenant Python et les trois modèles chargés. Ce chiffre n’isole pas chaque modèle et ne doit pas être lu comme RAM minimale par modèle.
- Les chargements stricts ont été vérifiés avant la génération. Aucun seuil ni hyperparamètre n’a été calibré sur une vérité terrain locale.

## Temps et volume prédit

| Modèle | Moteur | Chargement | Moyenne / patch | Médiane / patch | Plage / patch | Fenêtres par patch | Moyenne pixels positifs / 512² | Moyenne composantes polygonales |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| MODEL_C | ONNX Runtime CPU | 1,330 s | 3,239 s | 3,170 s | 2,555–4,171 s | 1×512² | 15,666 (6,0 %) | 11,1 |
| WHU U-Net++ | PyTorch CPU | 0,531 s | 2,578 s | 2,484 s | 1,951–4,057 s | 1×512² | 24,668 (9,4 %) | 28,4 |
| HOTOSM U-Net ResNet-34 | PyTorch CPU | 1,058 s | 1,237 s | 1,178 s | 0,825–2,162 s | 4×256² | 48,721 (18,6 %) | 21,7 |

Pic du working set observé pour le processus combiné : **2,082,426,880 octets (≈1,94 GiB)**. Cette valeur inclut Python, bibliothèques et les trois réseaux chargés ; ce n’est pas une mesure mémoire isolée pour MODEL_C ou un candidat.

Les aires prédites ne sont **pas** des métriques de qualité : l’augmentation marquée de pixels positifs de HOTOSM peut refléter une meilleure récupération de petits toits, des faux positifs, un seuil mal calibré pour cette région, ou un mélange de ces effets.

## Lecture visuelle et limites

La planche de contact (RGB, probabilités, masques binaires et overlays polygonisés pour les 16 patches) se trouve à [`contact_sheet_13L.png`](../backend/data/models/building/experimental/benchmark_13L/outputs/contact_sheet_13L.png). Les mêmes sorties sont également enregistrées séparément pour chaque patch et chaque modèle dans `backend/data/models/building/experimental/benchmark_13L/outputs/`.

- Sur les scènes urbaines denses, **WHU U-Net++** paraît suivre plus régulièrement les groupes de toits que MODEL_C, avec davantage de composantes et une couverture plus élevée. C’est la meilleure impression visuelle provisoire sur les contours dans cette planche ; elle n’est pas confirmée pixel par pixel contre annotation.
- **HOTOSM U-Net** marque une surface de toits nettement plus large et semble conserver davantage de petites structures dans certaines scènes. Il produit aussi davantage de surface positive et montre des erreurs/artefacts visuels possibles, notamment sur les zones non urbaines et aux séparations entre fenêtres. « Meilleure détection des petits bâtiments » reste donc une hypothèse visuelle, pas un classement d’exactitude.
- **MODEL_C** demeure le modèle de référence le plus prudent dans ces sorties. Sa couverture plus faible ne signifie pas qu’il omet nécessairement des bâtiments sans vérité terrain indépendante.
- Les masques n’ont pas été lissés ni raffinés; aucune modification de `PostProcessingService`, polygonisation, statistiques, export, registre ou frontend n’a été faite. Le polygone reflète directement le masque seuillé.

**Contrôle des artefacts** : 48 paires de rasters binaire/probabilité vérifiées (16 patches × 3 modèles), dimensions 512×512, valeurs binaires `{0,1}`, probabilités finies dans `[0,1]`, géotransformations et CRS identiques aux sources. Les 48 GeoJSON contiennent 978 entités au total ; après réparation topologique, toutes sont valides et contenues dans les bounds de leurs patches.

**Conclusion qualité** : aucune valeur officielle de Precision/Recall/F1, aucun vainqueur qualité statistiquement justifié, et aucune validation des frontières réelles. Revoir et valider un sous-ensemble représentatif de vérité terrain est le prochain prérequis.

## Compatibilité avec GeoRaster

Chaque candidat est une segmentation RGB qui renvoie des logits convertibles en carte de probabilité, donc son contrat conceptuel peut être encapsulé derrière un `ModelAdapter`. La compatibilité ONNX demeure à vérifier par export, comparaison logits PyTorch/ONNX, gestion des dimensions/fenêtres et test de bout en bout. La tête 3-canaux HOTOSM apporte frontière et distance, mais ce benchmark n’a pas activé son watershed afin de préserver une comparaison aval identique.

MODEL_C, son défaut de production, son checkpoint/ONNX, l’adaptateur, le tiling, le post-traitement, la polygonisation, les statistiques, les exports et l’interface n’ont pas été modifiés. Contrôle après benchmark : le SHA256 de MODEL_A correspond à la valeur attendue (`6CD2467E…D415987`) et MODEL_C à son SHA256 attendu (`170C49E1…B84DC555`). Les candidats et les résultats sont limités au sous-dossier expérimental `benchmark_13L`; le script de benchmark est autonome. L’environnement émet un avertissement PROJ lié à la base `proj.db` de PostgreSQL; les rasters de sortie ont été écrits avec les transformations source. Cette configuration système n’a pas été changée.

## Artéfacts reproductibles

- Script : [`scripts/benchmark_building_models_13L.py`](../scripts/benchmark_building_models_13L.py)
- Résultats patch par patch : `backend/data/models/building/experimental/benchmark_13L/outputs/benchmark_results_13L.csv`
- Résumé performances et charges : `backend/data/models/building/experimental/benchmark_13L/outputs/benchmark_summary_13L.json`
- Planche : `backend/data/models/building/experimental/benchmark_13L/outputs/contact_sheet_13L.png`
- Modèles candidats : `backend/data/models/building/experimental/benchmark_13L/{whu_unetplusplus,hotosm_unet_instance}/`
- Pour chaque modèle et patch : `probability/*.tif`, `binary/*.tif`, `polygons/*.geojson`, `overlay/*.png`.

## Décision

**D. NEED_GROUND_TRUTH_BEFORE_DECISION**. Garder MODEL_C comme baseline stable. WHU U-Net++ est le meilleur candidat exploratoire pour les contours visuels, HOTOSM U-Net ResNet-34 est le plus rapide et celui qui marque le plus de petits toits apparents, mais le second est sous AGPL-3.0 et requiert une validation de licence avant intégration. Avant de promouvoir ou remplacer un modèle : valider des masques Maxar représentatifs, mesurer IoU/F1/precision/recall par patch après calibrage tenu à part, comparer frontières et petites constructions, vérifier les coutures HOTOSM, puis tester l’export ONNX et l’adaptateur.

---

CURRENT BASELINE :
DeepLabV3 / ResNet-50

CANDIDATES TESTED :
WHU U-Net++ EfficientNet-B4; HOTOSM U-Net ResNet-34 instance; MODEL_C baseline

BEST VISUAL BOUNDARIES :
WHU U-Net++ EfficientNet-B4 (provisional visual assessment only)

BEST SMALL BUILDING DETECTION :
HOTOSM U-Net ResNet-34 (most small-roof coverage visually; unverified)

BEST SPEED :
HOTOSM U-Net ResNet-34 — 1.237 s/512² patch (4 × 256² windows)

BEST OVERALL MODEL :
NOT DETERMINED — ground truth required

MODEL_C STATUS :
KEEP

FINE TUNING RECOMMENDED :
YES — only after Maxar review masks are validated

NEXT STEP :
FINE_TUNE BEST MODEL (after ground-truth validation)
