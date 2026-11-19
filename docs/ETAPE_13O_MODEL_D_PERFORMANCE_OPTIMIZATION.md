# ÉTAPE 13O — MODEL_D Performance Profiling and Safe Acceleration

Date : 2026-10-23

## Conclusion

Le calcul du réseau U-Net++ EfficientNet-B4 est le goulet principal. L’export ONNX Runtime CPU (4 threads intra-op, 1 inter-op, batch 1) réduit le forward d’environ 1,52× et le temps total observé sur 4096² de 549,35 s à 371,75 s, soit 1,48×. Sur le même crop, les deux moteurs produisent les mêmes 685 candidats; les masques binaires diffèrent sur 4 pixels (IoU 0,99999679), et la surface totale diffère de 0,2325 m². Ce sont des sorties très proches, mais pas des masques au pixel près.

Le moteur ONNX est ajouté au registre comme variante expérimentale sélectionnable. MODEL_D PyTorch est préservé, MODEL_C reste le défaut. Le plein raster n’a pas été relancé : le gain bout en bout sur 4096² est mesurable mais juste sous le seuil souhaité de 1,5×.

## Environnement et inputs

- Raster source : cache Maxar 2025 `ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif`, 10 292 × 9 378, SHA-256 `8d42d0c39d12c36ff9581b933ca11c353e70df07cc0e69fd04193706a0aa09cc`.
- Les crops 512², 2048² et 4096² sont les fenêtres en haut à gauche du même raster préparé; leur SHA-256 est conservé dans `test-data/diagnostics/13O/raster_benchmarks.json`.
- Préparation identique au pipeline actuel : RGB dans l’ordre physique 1/2/3 du raster préparé, `uint8 / 255` vers NCHW `float32` dans [0,1], sans moyenne ni écart-type ImageNet; aucune redimension ni statistique globale par raster.
- Tuiles 512², recouvrement 50 %, seuil 0,50, minimum objet 4 pixels, connectivité 8; post-traitement, fusion, géoréférencement et polygonisation réutilisent les services de l’application.
- MODEL_D checkpoint préservé : 84 027 346 octets, SHA-256 `922af7c96c0dc44256ab8b4d1a071f2151e0a921c997af80b55bb766bcc30dc6`.
- ONNX exporté depuis ce checkpoint : 80 031 737 octets, SHA-256 `62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6`.
- Runtime : Python 3.12.10, PyTorch 2.8.0+cpu, ONNX Runtime 1.22.1, SMP 0.5.0.

## Profilage PyTorch et ONNX

Les temps comprennent génération des tuiles et preprocessing, forward, fusion/post-traitement, polygonisation, construction des statistiques et GeoJSON. Le chargement des moteurs est mesuré à part; le temps total de chaque ligne commence juste avant la consommation du flux de tuiles.

| Crop | Moteur | Tuiles | Total (s) | s/MP | s/tuile | Forward (s) | Forward du total | Candidats | Surface totale (m²) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 512² | PyTorch CPU | 1 | 3,42 | 13,06 | 3,42 | 2,97 | 86,6 % | 9 | 204,0760 |
| 512² | ONNX CPU | 1 | 1,85 | 7,05 | 1,85 | 1,71 | 92,6 % | 9 | 204,0760 |
| 2048² | PyTorch CPU | 49 | 115,98 | 27,66 | 2,37 | 113,15 | 97,6 % | 67 | 6 164,9921 |
| 2048² | ONNX CPU | 49 | 80,92 | 19,29 | 1,65 | 78,42 | 96,9 % | 67 | 6 164,8759 |
| 4096² | PyTorch CPU | 225 | 549,35 | 32,74 | 2,44 | 522,32 | 95,1 % | 685 | 144 841,0594 |
| 4096² | ONNX CPU | 225 | 371,75 | 22,16 | 1,65 | 344,61 | 92,7 % | 685 | 144 840,8270 |

Le profil complet historique donnait 606,59 s sur 4096² (225 tuiles); le run contrôlé PyTorch de cette étape est 549,35 s sur le crop et le protocole consignés ici. Les deux valeurs ne sont pas substituées l’une à l’autre. Le profil 13N.3 du raster entier reste 3 658,85 s, 1 440 tuiles, 37,91 s/MP et 2,54 s/tuile.

**Bottleneck principal : MODEL_FORWARD.** Il représente 95,1 % du temps PyTorch 4096² et 92,7 % du temps ONNX mesuré. La lecture/préparation raster représente 2,40 s en PyTorch et 2,15 s en ONNX pour 4096²; le coût de fusion/post-traitement est d’environ 20 s et la polygonisation environ 1,6 s. Les statistiques ne sont pas recalculées par tuile. Le pipeline lit par fenêtres et conserve la fusion disk-backed/memmap pour les grandes dimensions.

Une passe séparée, sans inference, a isolé les sous-étapes du tiling 4096² sur cache chaud : lecture raster 0,720 s, normalisation 0,911 s, assemblage/preparation de tuile et metadata 0,427 s (225 tuiles, total 2,058 s). Cette passe instrumente les appels `read` et `normalize` réels des services. Elle est une mesure diagnostic distincte et n’est pas additionnée aux lignes A/B ci-dessus. Chargement à part : PyTorch 0,556 s selon son adapter; ONNX adapter 1,092 s incluant validation SHA, dont 0,442 s pour la création de session.

Les latences individuelles ONNX 4096² : moyenne 1,532 s/tuile, médiane 1,484 s, p95 1,900 s, min 1,312 s, max 2,273 s. PyTorch : moyenne 2,321 s, médiane 2,251 s, p95 2,932 s, min 1,940 s, max 3,573 s.

## Batch et configuration des threads

Un premier essai sur quatre tuiles réelles comparait batch 1/2/4 et threads ONNX 1/2/4. Pour batch 1, la médiane mesurée descend de 2,80 s (1 thread) à 1,57 s (2 threads) et 1,56 s (4 threads). Le meilleur résultat complet ci-dessus est obtenu avec 4 threads. Les batches 2 et 4 n’améliorent pas le débit par tuile; batch 1 est donc retenu. Pas de parallélisme entre instances, de préfetch, de quantification, ni de modification de formule preprocessing.

## Équivalence numérique et spatiale

| Crop | Max abs. probabilité | Moyenne abs. | Différences binaires | IoU masque | Compte candidats PyTorch / ONNX | Delta surface totale |
|---:|---:|---:|---:|---:|---:|---:|
| 512² | 0,0002404 | 0,000000980 | 0 | 1,00000000 | 9 / 9 | 0 m² |
| 2048² | 0,0000973 | 0,000000069 | 1 | 0,99998115 | 67 / 67 | −0,1162 m² |
| 4096² | 0,0000973 | 0,000000072 | 4 | 0,99999679 | 685 / 685 | −0,2325 m² |

Le seuil s’applique à la probabilité telle que produite par chaque runtime. Les écarts binaires sont situés aux pixels dont la probabilité est très proche de 0,50; ce n’est donc pas une égalité stricte des masques. Pour 4096², les grilles ont même shape, CRS, transform et bounds; les 4 pixels représentent environ 0,000024 % de la grille. Le compte de candidats est identique. Le GeoJSON et les cartes probability ont des hashes différents, comme attendu lorsque les probabilités flottantes varient; les artefacts, hashes et statistiques par moteur sont fournis pour contrôle.

## Intégration

- Nouveau moteur : `whu_unetplusplus_effb4_onnx`, explicitement non défaut et marqué expérimental dans le ModelRegistry.
- Artefact sous `backend/data/models/building/experimental/whu_unetplusplus_effb4/onnx/model.onnx`; le chargement valide le hash ONNX et le hash du checkpoint source MODEL_D.
- Format d’entrée/sortie : `image` NCHW `[batch,3,512,512]` float32; `logits` `[batch,2,512,512]`; softmax à deux classes en gardant l’index building 1. Pas de sigmoid et pas de double activation.
- Le moteur PyTorch `whu_unetplusplus_effb4` demeure disponible. MODEL_C `spacenet2_deeplab` demeure le défaut du registre. Aucun changement du frontend ni des exports n’a été fait.
- RAM : aucun OOM. Le pic mémoire privé du processus n’a pas été capturé instrumentellement sur le run 4096²; la mémoire physique disponible, échantillonnée à la fin des runs, a varié de 5 254 à 5 847 MiB. Cette plage n’est pas présentée comme un pic RAM du processus.
- Le raster complet optimisé n’a pas été exécuté. L’estimation linéaire de temps n’est pas utilisée comme résultat de benchmark.

## Tests et régressions

- Tests ciblés des adaptateurs MODEL_D PyTorch et ONNX : **4 passed**.
- Suite backend : **236 passed, 0 failed**, 19 subtests; 3 022 avertissements. La première tentative sans `--basetemp` dans le workspace était bloquée par une permission sur le répertoire temporaire Windows; la suite finale a été passée avec `backend/.pytest-runtime/13O-full-qa-20261023`, les chemins PROJ/GDAL provenant du venv.
- Tests frontend : **SUCCESS** (tests légendes/i18n, import AOI, contrat Building).
- Build client et build SSR via `npm.cmd run build` : **SUCCESS**. Avertissement de bundle JavaScript >500 kB, sans échec.
- Aucun changement au modèle/registre MODEL_C par défaut, au checkpoint PyTorch MODEL_D, à MODEL_E, au preprocessing, aux services raster, post-traitement, polygonisation, statistiques, exports, frontend, GEE, indices, classifications ou Change Detection.

## Fichiers de preuve

- Résultats détaillés/timings/hashes : [raster_benchmarks.json](../test-data/diagnostics/13O/raster_benchmarks.json).
- Comparaison runtime, batches et écarts de probabilité : [engine_comparison.json](../test-data/diagnostics/13O/engine_comparison.json).
- Sous-étapes de lecture, normalisation, préparation tuile et chargement ONNX : [tiling_phase_profile.json](../test-data/diagnostics/13O/tiling_phase_profile.json), [onnx_model_load.json](../test-data/diagnostics/13O/onnx_model_load.json).
- Script reproduisant le benchmark multi-tailles : [full_benchmark_model_d.py](../test-data/diagnostics/13O/full_benchmark_model_d.py).
- Scripts export/benchmark : [benchmark_model_d_onnx.py](../test-data/diagnostics/13O/benchmark_model_d_onnx.py).
- Masques, cartes de probabilité, crops et GeoJSON PyTorch/ONNX : fichiers préfixés par `pytorch_` et `onnxruntime_cpu_` dans `test-data/diagnostics/13O/`.
- Suite backend : [backend_full_tests.log](../test-data/diagnostics/13O/backend_full_tests.log).

BASELINE FULL RASTER TIME :
3658.85 s

BASELINE FULL RASTER MINUTES :
60.98

PRIMARY BOTTLENECK :
MODEL_FORWARD

MODEL_FORWARD PERCENT :
95.08 % PyTorch / 92.70 % ONNX sur 4096²

BEST ENGINE :
ONNX_RUNTIME_CPU

BEST BATCH :
1

BASELINE 4096 TIME :
606.59 s historique; 549.35 s dans le run contrôlé

OPTIMIZED 4096 TIME :
371.75 s

4096 SPEEDUP :
1.48 x bout en bout; 1.52 x sur le forward

BASELINE SECONDS/MP :
36.16 historique 4096; 32.74 run PyTorch contrôlé

OPTIMIZED SECONDS/MP :
22.16

MASK EQUIVALENCE :
VALIDATED — quasi équivalente, 4 pixels différents / IoU 0.99999679; identité stricte FAILED

CANDIDATE EQUIVALENCE :
VALIDATED — mêmes candidats (685), delta surface −0.2325 m²

FULL RASTER OPTIMIZED TEST :
NOT_RUN

OPTIMIZED FULL TIME :
NOT_MEASURED

OPTIMIZED FULL MINUTES :
NOT_MEASURED

FULL RASTER SPEEDUP :
NOT_MEASURED

RAM PEAK :
PROCESS PEAK NOT MEASURED; SYSTEM AVAILABLE RAM LOWEST SAMPLED 5254 MiB

MODEL_D ORIGINAL :
PRESERVED

MODEL_C :
DEFAULT UNCHANGED

MODEL_E :
UNCHANGED

BACKEND TESTS :
236 PASSED / 0 FAILED

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS

FINAL DECISION :
MODEL_D_OPTIMIZATION_SUCCESS

NEXT STEP :
KEEP MODEL_D EXPERIMENTAL
