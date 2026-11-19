# ÉTAPE 13M.1B — FAST MODEL_C VS MODEL_D COMPARATIVE BENCHMARK

## Portée et niveau de confiance

Comparaison des six patches TEST verrouillés avec les géométries humaines transformées pour l’évaluation uniquement. Toutes les métriques sont **APPROXIMATE / ENGINEERING BENCHMARK ONLY**. Les réparations `make_valid` et le clipping peuvent changer le nombre de composantes, et cette Ground Truth n’est pas une référence scientifique.

Le GeoPackage humain original `benchmark_13M_test/annotations/ground_truth_layers.gpkg` n’a pas été modifié. MODEL_C, MODEL_D et le fine-tuning n’ont pas été exécutés dans cette instance restaurée. Les outputs d’inférence déjà calculés dans les benchmarks 13L/13L1 ont été réutilisés et copiés, car chacun des six TIFF TEST a le même SHA-256 octet pour octet que l’image traitée auparavant. Cette provenance est enregistrée dans `backend/data/models/building/experimental/benchmark_13M1B/outputs/benchmark_provenance.json`. Les temps sont les timings archivés des mêmes fichiers; ce rapport ne les présente pas comme une nouvelle mesure murale.

- MODEL_C : sortie de `scripts/benchmark_building_models_13L.py`, ONNX Runtime CPU, DeepLabV3 / ResNet-50, checkpoint hash validé par le script 13L.
- MODEL_D : sortie GeoAI 0.43.1 CPU, WHU U-Net++ / EfficientNet-B4, via `scripts/benchmark_geoai_13L1.py`. Le rapport de validation 13L1 a établi que les masques GeoAI sont identiques aux masques WHU du benchmark 13L.
- Seuil binaire : 0,50 pour les deux moteurs. Les prédictions utilisent les rasters inchangés de `benchmark_13M_test/images/`.

L’environnement Python actuellement disponible ne contient pas PyTorch, Rasterio, ONNX Runtime ou GeoAI; il n’a donc pas permis de relancer l’inférence. Les cartes comparées proviennent néanmoins d’une exécution antérieure réussie sur des TIFF dont les hashes sont identiques aux six patches verrouillés.

## Copie Ground Truth réparée

Fichier : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/evaluation_ground_truth/ground_truth_benchmark_repaired.gpkg`.

| Patch | Features avant | Features après | Features réparées | Features clippées | Composantes polygonales après |
|---|---:|---:|---:|---:|---:|
| GT_2024_difficult_02 | 16 | 16 | 5 | 3 | 21 |
| GT_2024_industrial_02 | 1 | 1 | 0 | 1 | 1 |
| GT_2024_residential_02 | 20 | 20 | 2 | 5 | 22 |
| GT_2025_difficult_02 | 19 | 19 | 4 | 3 | 23 |
| GT_2025_industrial_02 | 1 | 1 | 0 | 1 | 1 |
| GT_2025_residential_02 | 11 | 11 | 1 | 1 | 12 |
| **Total** | **68** | **68** | **12** | **14** | **80** |

Les 68 features ont été conservées; aucune géométrie vide n’a été supprimée. Après `make_valid` et intersection avec les bounds exacts de chaque raster : 0 géométrie invalide, 0 hors bounds, 0 vide, 0 doublon exact. Chaque feature conserve `original_fid`, `repair_applied`, `clip_applied`, `parts_before`, `parts_after` ainsi que ses attributs humains. Les six masques GT sont 512×512, uint8 binaire {0,1}, sur le CRS, geotransform et bounds identiques au raster d’origine; aucun resampling n’a été effectué.

## Métriques pixel agrégées

Métriques micro calculées sur les 6 × 512 × 512 pixels, à partir des masques binaires existants et des masques GT réparés.

| Métrique | MODEL_C | MODEL_D |
|---|---:|---:|
| IoU | 0.303 | **0.368** |
| Dice | 0.465 | **0.538** |
| Precision | **0.585** | 0.523 |
| Recall | 0.386 | **0.554** |
| F1 | 0.465 | **0.538** |
| Boundary F1, tolérance 1 px | **0.233** | 0.179 |
| Mean boundary distance, symétrique | 33.94 px | **16.21 px** |

Boundary F1 et distances sont de faible confiance à cause de la Ground Truth approximative, de `make_valid` et du clipping. Le Boundary F1 à 1 pixel favorise MODEL_C; la distance moyenne favorise MODEL_D, qui couvre davantage de bordures. Aucun score de contour n’est une mesure scientifique.

## Métriques objet et petites constructions

Règle objet : rasteriser chaque feature Ground Truth réparée séparément; étiqueter les composantes prédites avec connectivité 8; apparier de façon gloutonne, par IoU décroissant, un à un, avec un seuil IoU ≥ 0,50. Une feature Ground Truth appariée est détectée; sinon elle est manquée. Une composante prédite non appariée est supplémentaire. Cette règle ne cherche pas à tirer des conclusions fines sur les fusions ou fragmentations créées par la réparation.

| Mesure | MODEL_C | MODEL_D |
|---|---:|---:|
| Bâtiments GT détectés | 11 / 68 | **18 / 68** |
| Bâtiments GT manqués | 57 | **50** |
| Composantes prédites supplémentaires | **80** | 183 |
| Composantes prédites totales (connectivité 8) | 91 | 201 |

Petits bâtiments : seuil exploratoire de 100 m² après réparation/clipping. Il y en a 7; MODEL_C en détecte 0, MODEL_D en détecte 1 (1/7). L’échantillon est trop faible pour conclure à un avantage robuste.

## Performance et couverture visuelle

Temps issus des exécutions précédentes sur les mêmes fichiers, non re-mesurés pendant cette étape :

- MODEL_C `adapter.predict` : 19.09 s total / 3.181 s par patch / 12.13 s par megapixel; chargement ONNX archivé séparément : 1.33 s.
- MODEL_D GeoAI complet : 18.78 s total / 3.131 s par patch / 11.94 s par megapixel.
- MODEL_D appel direct WHU du benchmark 13L, même poids/sortie validée équivalente : 15.16 s total / 2.527 s par patch / 9.64 s par megapixel, sans I/O GeoAI.

Les timers ne couvrent pas exactement le même périmètre; MODEL_C est chronométré autour de `predict`, tandis que GeoAI couvre aussi son wrapper et ses I/O raster. Les temps ne départagent donc pas solidement les moteurs. La légère avance du timer GeoAI sur les six patches ne suffit pas à désigner un vainqueur end-to-end.

Observation visuelle de la planche : MODEL_D couvre davantage de toitures résidentielles/denses sur ces patches, notamment là où MODEL_C manque des zones (patch 2025 residential); cela vient avec beaucoup plus de composantes supplémentaires. Sur les deux patches industrial, la règle IoU identifie le bâtiment GT avec MODEL_C, mais aucun avec MODEL_D. MODEL_C paraît plus précis sur les contours détectés et génère moins de composantes supplémentaires. Les patches disponibles sont résidentiels, difficiles et industriels; aucun patch étiqueté `dense` n’appartient à cet échantillon TEST.

Planche complète RGB, GT, probabilités, masques et contours : `backend/data/models/building/experimental/benchmark_13M1B/outputs/comparison/contact_sheet_13M1B.png`.
Planche d’overlays RGB/GT/MODEL_C/MODEL_D : `backend/data/models/building/experimental/benchmark_13M1B/outputs/comparison/contact_sheet_13M1B_overlays.png`.
Les masques, probabilités, GeoJSON et overlays individuels des deux modèles sont sous `backend/data/models/building/experimental/benchmark_13M1B/outputs/{model_c,model_d}/`.
Métriques détaillées : `comparison/metrics_summary.json`, `comparison/metrics_per_patch.csv`, `comparison/object_metrics_per_patch.csv`.

## Décision exploratoire

MODEL_D gagne sur l’IoU, le Dice, le rappel pixel, le nombre d’objets détectés et légèrement sur la couverture des bâtiments de moins de 100 m². MODEL_C gagne en précision, boundary F1 à 1 pixel et nombre réduit de composantes supplémentaires. La décision est donc **MODELS_COMPLEMENTARY**, uniquement pour l’ingénierie et sur la Ground Truth réparée approximative. Aucun modèle n’est promu par cette comparaison. MODEL_C reste le défaut production; MODEL_D reste expérimental. La Ground Truth humaine originale et le split TEST restent verrouillés et inchangés.

GROUND TRUTH TYPE :
APPROXIMATE_EVALUATION_GROUND_TRUTH

ORIGINAL GT BUILDINGS :
68

REPAIRED GT GEOMETRIES :
68 features / 80 polygon components

SELF_INTERSECTIONS AFTER REPAIR :
0

OUT_OF_BOUNDS AFTER CLIP :
0

DUPLICATES AFTER :
0

TOTAL GT BUILDINGS AFTER :
68

TEST PATCHES :
6

MODEL_C IOU :
0.303

MODEL_D IOU :
0.368

MODEL_C DICE :
0.465

MODEL_D DICE :
0.538

MODEL_C PRECISION :
0.585

MODEL_D PRECISION :
0.523

MODEL_C RECALL :
0.386

MODEL_D RECALL :
0.554

MODEL_C F1 :
0.465

MODEL_D F1 :
0.538

MODEL_C BOUNDARY F1 :
0.233 (LOW CONFIDENCE)

MODEL_D BOUNDARY F1 :
0.179 (LOW CONFIDENCE)

MODEL_C DETECTED GT OBJECTS :
11 / 68

MODEL_D DETECTED GT OBJECTS :
18 / 68

MODEL_C MISSED GT OBJECTS :
57 / 68

MODEL_D MISSED GT OBJECTS :
50 / 68

MODEL_C EXTRA COMPONENTS :
80

MODEL_D EXTRA COMPONENTS :
183

MODEL_C TIME :
19.09 s total; 3.181 s/patch; 12.13 s/MP (archived timing)

MODEL_D TIME :
18.78 s GeoAI total; 3.131 s/patch; 11.94 s/MP (archived timing; timer scope differs)

BEST DETECTION :
MODEL_D (higher recall/IoU; more extra components)

BEST SMALL BUILDING COVERAGE :
MODEL_D (1/7 vs 0/7; LOW SAMPLE)

BEST VISUAL BOUNDARIES :
MODEL_C by 1px Boundary F1; LOW CONFIDENCE

BEST SPEED :
NO CLEAR WINNER (timing scopes differ)

ENGINEERING DECISION :
MODELS_COMPLEMENTARY

SCIENTIFIC VALIDATION :
NOT CLAIMED

MODEL_C :
PRODUCTION UNCHANGED

MODEL_D :
EXPERIMENTAL

NEXT STEP :
OPTIONAL FUTURE PRECISE GROUND TRUTH
