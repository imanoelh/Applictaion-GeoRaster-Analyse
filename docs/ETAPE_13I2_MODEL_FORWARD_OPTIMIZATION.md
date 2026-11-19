# Étape 13I.2 — Optimisation de l’inférence CPU de MODEL_C

Date : 20 octobre 2026  
Copie : `Georaster-19-10`

## Résultat

ONNX Runtime CPU, batch 4, 8 threads intra-op et 2 threads inter-op est le meilleur moteur mesuré. Le microbenchmark a obtenu 2,7719 s/tuile, soit 1,56× plus rapide que la meilleure configuration PyTorch testée (8/2 threads, batch 6) et 1,86× plus rapide que la baseline PyTorch actuelle (4/4, batch 4). L’essai complet sur le raster de référence a retourné HTTP 200 en 1 560,314 s. La baseline historique était 2 712,716 s : amélioration de 1,739×, soit 42,48 % de temps en moins.

La sortie agrégée est presque équivalente : 2 411 candidats dans les deux résultats; aire totale ONNX 506 005,2517 m² contre 506 005,1354 m² dans la baseline (+0,1162 m², +0,000023 %). La somme des pixels des polygones ONNX est 4 353 557, contre 4 353 556 pixels positifs relevés dans la baseline (+1 pixel). Le masque complet historique et son GeoJSON n’étant pas archivés, aucune comparaison pixel par pixel ni géométrie par géométrie du raster entier n’est possible. Sur les 64 tuiles de benchmark communes, les masques au seuil 0,50 sont identiques (0 pixel de différence); les logits convertis en probabilités diffèrent au maximum de 6,9142×10⁻⁶.

## Benchmark reproductible

L’environnement de mesure était Python 3.12.10, PyTorch 2.8.0+cpu, Torchvision 0.23.0+cpu, Rasterio 1.5.2 et ONNX Runtime 1.22.1 sur CPU. Le raster source a été préparé une fois en 64 tuiles RGB valides de 512×512; tous les essais ont réutilisé les mêmes tableaux d’entrée. Trois lots d’échauffement précédaient les mesures.

| Essai | Threads intra/inter | Batch | secondes/tuile | Mémoire de travail max. | Masque à 0,50 |
|---|---:|---:|---:|---:|---|
| PyTorch baseline actuelle | 4/4 | 4 | 5,1617 | non relevée | référence |
| PyTorch | 4/4 | 1 | 5,6568 | 1,24 Go | identique |
| PyTorch | 4/4 | 2 | 5,8815 | 2,18 Go | identique |
| PyTorch | 4/4 | 4 | 5,4458 | 2,82 Go | identique |
| PyTorch | 4/4 | 6 | 5,3596 | 3,41 Go | identique |
| PyTorch | 4/4 | 8 | 5,6062 | 4,08 Go | identique |
| PyTorch | 2/2 | 6 | 8,3823 | 3,37 Go | identique |
| PyTorch | 4/2 | 6 | 5,3539 | 3,36 Go | identique |
| PyTorch | 6/2 | 6 | 5,0125 | 3,36 Go | identique |
| PyTorch | 8/1 | 6 | 5,1110 | 3,36 Go | identique |
| PyTorch, MKLDNN désactivé | 8/2 | 6 | 5,3084 | 5,02 Go | identique |
| PyTorch, `channels_last` | 8/2 | 6 | 5,1119 | 3,51 Go | identique |
| ONNX Runtime CPU | intra 8, inter 2 | 1 | 2,9397 | 0,91 Go | identique |
| ONNX Runtime CPU | intra 8, inter 2 | 2 | 2,8111 | 1,15 Go | identique |
| **ONNX Runtime CPU** | **intra 8, inter 2** | **4** | **2,7719** | **1,63 Go** | **identique** |
| ONNX Runtime CPU | intra 8, inter 2 | 8 | 2,8372 | 2,53 Go | identique |

MKLDNN doit rester activé : le désactiver ralentit le meilleur essai PyTorch. `channels_last` n’améliore pas le débit. `torch.compile` a échoué, car le compilateur Microsoft `cl` n’est pas disponible; aucune dépendance de compilation n’a été installée. L’export ONNX dynamique (opset 18) a réussi et a passé ONNX checker.

## Exécution raster complète

Raster `ai-ortho-8d42d0c39d12-3882a676ca4a-3e970d60cef4`, 10 292×9 378 pixels, 575 tuiles au total : 513 traitées et 62 ignorées, batch 4. Le seuil 0,50, le recouvrement 0,20, `min_valid_pixel_ratio=0,05`, `min_object_pixels=4`, les options morphologiques désactivées, la connectivité 8 et la simplification 0 ont été conservés.

| Mesure | PyTorch baseline | ONNX Runtime |
|---|---:|---:|
| Temps total API | 2 712,716 s | 1 560,314 s |
| Accélération end-to-end | — | 1,739× |
| Candidats/polygones | 2 411 | 2 411 |
| Aire totale | 506 005,1354 m² | 506 005,2517 m² |
| Pixels positifs | 4 353 556 | 4 353 557 (somme `pixel_count` des polygones) |
| HTTP | 200 historique | 200 |

Le temps réel « model forward » n’a pas été instrumenté séparément dans ce run. Le temps API de 1 560,314 s et le champ enveloppant `postprocessing_time_ms=1 503 789,614 ms` sont mesurés; ce dernier inclut l’inférence, la lecture/préparation des fenêtres et le post-traitement et ne doit pas être interprété comme du temps modèle pur. À titre d’estimation seulement, 513 tuiles × 2,7719 s/tuile donnent 1 421,975 s de forwards. Aucun masque ou seuil n’a été modifié pour améliorer l’équivalence.

Le premier essai complet, sur le port de profil 8012, avait fini l’inférence mais n’avait pas produit de réponse : l’environnement chargeait le `proj.db` incompatible de PostgreSQL 17. Le run validé a été relancé sur 8013 après avoir pointé `PROJ_LIB`, `PROJ_DATA` et `GDAL_DATA` vers les données de Rasterio de l’environnement; la transformation EPSG:4326 → EPSG:3857 et la réponse complète ont alors réussi. Les ports 8010 et 8011 n’ont pas été arrêtés ni modifiés.

## Intégration et intégrité

- `SpaceNet2DeepLabAdapter` charge le moteur `onnxruntime` par défaut; `SPACENET2_ENGINE=pytorch` reste disponible pour le moteur original. `SPACENET2_ORT_INTRA_THREADS` et `SPACENET2_ORT_INTER_THREADS` règlent respectivement les threads (défauts 8 et 2).
- L’entrée ONNX est `image` (NCHW float32), la sortie est le logit binaire `out`; l’adapter applique sigmoid, contrôle les dimensions et masque les pixels invalides. Le checkpoint `.pth` reste vérifié avant chargement de l’artefact.
- L’artefact expérimental `backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx` fait 158 461 253 octets, SHA-256 `94661DED0BC79BBCA99C03D55D817BCB7369D46EB13D7983EBF6AE711003FD45`. `onnxruntime==1.22.1` est désormais déclaré dans les dépendances backend; la création/export nécessite `onnx==1.19.0`, installé dans l’environnement d’essai, sans dépendance d’export ajoutée au runtime.
- MODEL_C reste le modèle Building sélectionné par défaut et garde son statut expérimental / non validé scientifiquement. MODEL_A n’a pas été modifié : SHA-256 `6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987`. Le checkpoint MODEL_C `.pth` reste inchangé : SHA-256 `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555`.
- Tiling, fusion des recouvrements, post-traitement, polygonisation, statistiques, exports, indices, classifications, GEE et frontend métier n’ont pas été modifiés.

## Tests et builds

- Backend : **228 passed, 0 failed**, 19 subtests passed. L’essai a utilisé les données PROJ/GDAL du wheel Rasterio et un `--basetemp` sous `backend/.pytest-runtime` parce que le dossier Temp utilisateur n’est pas accessible dans cet environnement.
- Frontend : `npm.cmd test` réussi (tests i18n, import AOI et contrat Building).
- Build client Vite réussi; build SSR Vite réussi. Le build conserve l’avertissement existant sur les chunks client supérieurs à 500 kB.

## Point d’application

Le code et les dépendances déterminent désormais ONNX Runtime comme moteur par défaut au prochain démarrage de l’application. Le service déjà actif sur `8011` a été laissé intact et n’a pas rechargé le nouveau code; son moteur après ce changement n’est donc pas confirmé. Pour activer l’optimisation dans l’interface existante, redémarrer le backend avec les variables PROJ/GDAL pointant vers Rasterio. Le backend `8011` répond encore à l’API modèles. Le contrôle HTTP du frontend `5184/map` a expiré après cinq secondes : les tests et builds frontend passent, mais la page servie n’a pas été validée pendant cette étape. Les instances temporaires 8012 et 8013 de profilage ont été arrêtées.

```text
ÉTAPE 13I.2 — MODEL_C CPU INFERENCE OPTIMIZATION

BEST ENGINE : ONNX_RUNTIME_CPU
BEST SECONDS PER TILE : 2.7719
SPEEDUP VS BEST PYTORCH : 1.562x
SPEEDUP VS CURRENT BASELINE : 1.862x
FULL RASTER TOTAL : 1560.314 s
FULL RASTER SPEEDUP : 1.739x
FULL RASTER MODEL_FORWARD : NOT INSTRUMENTED (estimate 1421.975 s)
FULL RASTER OUTPUT : 2411 candidates; +1 positive pixel; area +0.1162 m²
FULL RASTER HTTP : 200
BACKEND TESTS : 228 PASSED / 0 FAILED
FRONTEND TESTS : SUCCESS
CLIENT BUILD : SUCCESS
SSR BUILD : SUCCESS
MODEL_A : UNCHANGED
MODEL_C CHECKPOINT : UNCHANGED
MODEL_C ENGINE DEFAULT : ONNX_RUNTIME
READY FOR PERFORMANCE ACCEPTANCE : YES, WITH 1-PIXEL AGGREGATE DIFFERENCE
ACTIVE 8011 SERVICE : RESTART REQUIRED TO LOAD THE NEW DEFAULT
```
