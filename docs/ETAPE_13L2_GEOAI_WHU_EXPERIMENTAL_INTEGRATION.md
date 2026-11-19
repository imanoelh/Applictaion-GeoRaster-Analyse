# ÉTAPE 13L.2 — Intégration expérimentale du modèle WHU

## Résumé

MODEL_D `whu_unetplusplus_effb4` est raccordé au registry Building et au pipeline de résultats GeoRaster comme modèle expérimental sélectionnable. MODEL_C (`spacenet2_deeplab`) reste le modèle par défaut. MODEL_A, MODEL_C, le tiling partagé, la fusion, le post-traitement, la polygonisation, les statistiques, les exports et les indices n’ont pas été changés.

L’intégration utilise directement le checkpoint WHU déjà disponible. Elle n’ajoute pas GeoAI ou un autre paquet expérimental aux dépendances runtime du backend. Les prédictions utilisent les mêmes `BuildingAnalysisResult`, statistiques, GeoJSON, CSV, metadata JSON et ZIP que les autres modèles.

## Modèle et poids

| Champ | Valeur vérifiée |
|---|---|
| ID | `whu_unetplusplus_effb4` |
| Statut | `EXPERIMENTAL` |
| Architecture | SMP U-Net++ / EfficientNet-B4 |
| Source du modèle | [giswqs/whu-building-unetplusplus-efficientnet-b4](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4) |
| Jeu de données annoncé | WHU Building Dataset |
| Licence annoncée | Apache-2.0 |
| Checkpoint local | `backend/data/models/building/experimental/whu_unetplusplus_effb4/model.pth` |
| Taille | 84 027 346 octets |
| SHA-256 | `922AF7C96C0DC44256AB8B4D1A071F2151E0A921C997AF80B55BB766BCC30DC6` |
| Entraînement supplémentaire requis pour l’inférence | Non |

Le fichier local est une réutilisation liée du checkpoint déjà présent à l’étape 13L.1; aucun téléchargement ni copie lourde n’a été effectué. Le loader construit `smp.UnetPlusPlus(encoder_name="efficientnet-b4", in_channels=3, classes=2)` et charge le state dict avec `strict=True`. L’output est deux logits par pixel; l’adapter produit la probabilité de la classe bâtiment avec `softmax` sur les deux classes.

## Entrée et tiling

- Entrée RGB, tenseur `float32` NCHW, 512 × 512.
- Valeurs normalisées sur `[0,1]` par division des RGB uint8 par 255; aucune moyenne/écart-type ImageNet n’est appliqué dans l’adapter.
- Les tuiles proviennent du `TilingService` partagé et restent lues fenêtre par fenêtre.
- Paramètres WHU imposés par l’adapter : tile 512, overlap 50 % (stride 256), batch 1 sur CPU.
- Le frontend garde MODEL_C comme valeur initiale. Le choix WHU fixe 512/50 % et est identifié « experimental ».

Le preprocessing RGB local correspond à cette entrée. Les rasters Sentinel-2 passent aussi par l’API commune, mais la distribution des données est différente du domaine d’entraînement WHU; aucune équivalence scientifique ou calibration n’est revendiquée. Une comparaison quantitative des contours nécessite une vérité terrain adaptée à la scène.

## Intégration et géoréférence

Le registry expose MODEL_D avec `default: false` et `status: experimental`; MODEL_C reste `default: true`. Le contrôle de la sélection et de l’overlap est appliqué aux endpoints d’inférence et de post-traitement. Les étages suivants restent communs et inchangés : fusion des overlaps, post-traitement, polygonisation, génération des propriétés/statistiques et exports.

Le parcours vérifié utilise `EPSG:32637` et l’orthophoto Maxar RGB du jeu de validation. Les bounds native gauche et haute retournées correspondent exactement aux bounds du raster source. Les statistiques `candidate_count` et le nombre de features GeoJSON concordent.

## Validation fonctionnelle

| Entrée | Résultat | Temps observé | Contrôles |
|---|---|---:|---|
| 512 × 512 (fenêtre découpée du Maxar RGB 2024) | Succès, 55 candidats | 8,31 s, préparation comprise | MODEL_D/EXPERIMENTAL, CRS et bounds, nombre et statistiques, GeoJSON, CSV, metadata JSON, ZIP |
| 2 048 × 2 048 (Maxar RGB 2024) | Succès, 291 candidats | 149,1 s, préparation comprise | mêmes contrôles, parcours complet avec tiles, fusion, polygonisation et exports |
| Plus grand que 2 048 × 2 048 | Non exécuté | — | Pas de source orthophoto validée plus grande disponible dans ce workspace; 2 048² a déjà pris 149 s en CPU |

Les comptes de candidats sont des sorties techniques de ce modèle sur ces entrées, pas des comptes de bâtiments exacts ni des mesures de précision. Aucun ground truth complet n’a été utilisé pour calculer précision, rappel ou F1. Le contrôle strict-load et le smoke test d’une tuile synthétique sont aussi couverts par les tests backend ajoutés.

Les quatre formats d’export ont été exercés sur les deux tailles. Le ZIP contient `building_candidates.geojson`, `building_statistics.csv` et `building_metadata.json`.

## Non-régression

- Environnement : Python 3.12.10, PyTorch 2.8 CPU, Torchvision 0.23 CPU, SMP 0.5.0, Rasterio 1.5.2.
- Tests ciblés WHU : 2 passés.
- Suite backend `pytest tests -q --basetemp=.pytest-runtime-13l2` : **230 passed**, 19 subtests, 0 failed. Le répertoire temporaire a été forcé dans le workspace car le répertoire temporaire Windows par défaut refusait l’accès.
- Une première exécution globale `pytest -q` a aussi collecté les tests des paquets GeoAI vendus dans `backend/data` et échoué pendant leur collecte à cause de dépendances de test absentes; elle n’est pas le résultat de la suite du projet. La suite explicite `backend/tests` a ensuite passé.
- Frontend `npm test` : succès (checks légendes bilingues, import AOI, contrat AI Building).
- `npm run build` : client et SSR construits avec succès. Vite affiche son avertissement préexistant de chunk client >500 kB.
- Vérification des modèles : MODEL_A fait 97 919 546 octets avec le SHA-256 attendu; MODEL_C fait 168 357 171 octets avec le SHA-256 attendu; checkpoint WHU conforme au hash ci-dessus.
- Aucun fine-tuning ni annotation manuelle n’est requis pour exécuter l’inférence. Une vérité terrain reste requise pour une comparaison scientifique. Le fine-tuning WHU est optionnel et hors de cette intégration.

## Fichiers de code ajoutés ou adaptés

- `backend/app/ai/models/whu_building_adapter.py` : adapter expérimental, hash strict, architecture, entrée/sortie et métadonnées du modèle.
- `backend/app/ai/registry/model_registry.py` : enregistrement WHU non-default; MODEL_C reste le default.
- `backend/app/ai/api/ai_inference_routes.py` et `backend/app/ai/api/ai_postprocessing_routes.py` : respect de l’overlap privilégié WHU seulement.
- `backend/tests/test_whu_building_adapter.py` : hash/strict load/contrat probabilités et statut du registry.
- `frontend/src/features/ai-building/model.ts` et `BuildingDetectionPanel.tsx` : type de modèle, sélecteur MODEL_C/WHU et contraintes 512/50 %.

## Conclusion et suite

MODEL_D est prêt pour un test utilisateur sur une orthophoto RGB réelle. La compatibilité technique du pipeline est validée pour 512 et 2 048 pixels carrés. La qualité comparée des contours, la détection des petits bâtiments et les faux positifs ne sont pas validés faute de comparaison ground truth sur la scène choisie. Garder MODEL_C par défaut jusqu’à une telle comparaison.

CURRENT BASELINE :
DeepLabV3 / ResNet-50

CANDIDATES TESTED :
WHU U-Net++ / EfficientNet-B4 (MODEL_D), integration 512 × 512 and 2048 × 2048

BEST VISUAL BOUNDARIES :
NOT ASSESSED — no ground-truth comparison in this integration

BEST SMALL BUILDING DETECTION :
NOT ASSESSED — no ground-truth comparison in this integration

BEST SPEED :
MODEL_C — comparative timing was not run in this integration

BEST OVERALL MODEL :
NOT DETERMINED — ground-truth comparison required

MODEL_C STATUS :
KEEP

FINE TUNING RECOMMENDED :
NO — not before ground-truth comparison

NEXT STEP :
TEST WHU ON REAL ORTHOPHOTO /
TEST ORTHOGONALIZATION /
GROUND TRUTH COMPARISON /
FINE TUNE WHU

## État final

MODEL_D :
whu_unetplusplus_effb4

ARCHITECTURE :
U-Net++ / EfficientNet-B4

PRETRAINED :
YES

TRAINING REQUIRED FOR INFERENCE :
NO

MANUAL ANNOTATION REQUIRED FOR INFERENCE :
NO

GROUND TRUTH REQUIRED FOR SCIENTIFIC COMPARISON :
YES

FINE TUNING REQUIRED :
NO / OPTIONAL

SMALL RASTER :
SUCCESS

MEDIUM RASTER :
SUCCESS

LARGE RASTER :
NOT_RUN

GEOREFERENCE :
VALIDATED

POLYGONIZATION :
VALIDATED

STATISTICS :
VALIDATED

EXPORTS :
VALIDATED

MODEL_C :
UNCHANGED

MODEL_A :
UNCHANGED

DEFAULT MODEL :
MODEL_C

WHU STATUS :
EXPERIMENTAL

PRODUCTION PIPELINE :
UNCHANGED

READY_FOR_WHU_USER_TEST :
YES

NEXT STEP :
TEST WHU ON REAL ORTHOPHOTO /
TEST ORTHOGONALIZATION /
GROUND TRUTH COMPARISON /
FINE TUNE WHU
