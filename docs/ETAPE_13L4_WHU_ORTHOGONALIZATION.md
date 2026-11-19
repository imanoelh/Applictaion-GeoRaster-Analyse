# ÉTAPE 13L.4 — WHU Orthogonalization

## Résultat

L’orthogonalisation GeoAI produit des géométries valides et alignées sur les huit AOI, mais elle n’améliore pas les contours de façon assez régulière pour remplacer les polygones WHU bruts. Le comptage augmente de 171 à 174 éléments, surtout dans les scènes denses et complexes, et les déplacements de contour comprennent des valeurs extrêmes. La décision est donc de conserver les polygones bruts et de valider les contours contre une vérité terrain avant d’envisager un raffinement conditionnel.

Aucune inférence n’a été relancée. Les masques, GeoJSON bruts, RGB, CRS et transforms sont ceux de 13L.3. Les huit copies GeoJSON brutes de cette étape ont été vérifiées identiques octet pour octet aux sources 13L.3. Aucun raster complet n’a été traité.

## Méthode et appel GeoAI

La version expérimentale embarquée est GeoAI **0.43.1**. La signature vérifiée est :

```text
geoai.orthogonalize(input_path, output_path=None, epsilon=0.2,
                    min_area=10, min_segments=4,
                    area_tolerance=0.7, detect_triangles=True)
```

La fonction officielle attend un masque raster, qu’elle vectorise elle-même. Elle a été appelée une fois sur chacun des huit `binary_mask.tif` déjà produits en 13L.3, avec les paramètres par défaut explicités ci-dessus. Le raster contient la prédiction binaire existante ; il n’y a eu ni nouveau seuillage ni nouvelle inférence.

- `epsilon=0.2` : tolérance Douglas–Peucker dans les unités du CRS, soit environ 0,57 pixel à 0,35 m/pixel. La fonction réduit cette valeur à 0,15 m pour les objets qu’elle identifie comme rectangulaires.
- `min_area=10` : les polygones sous 10 m² sont laissés inchangés.
- `min_segments=4` : nombre minimal de sommets de segment visé lors de la simplification.
- `area_tolerance=0.7` : la fonction rejette sa géométrie corrigée si le rapport de surface sort de `[0,7 ; 1/0,7]`, et conserve alors la forme d’origine.
- `detect_triangles=True` : les formes triangulaires détectées sont laissées inchangées.

La fonction source polygonise avec `rasterio.features.shapes()` sans paramètre de connectivité explicite (connectivité par défaut à 4). Cela donne trois objets supplémentaires par rapport au GeoJSON de production WHU : un dans AOI_03 et deux dans AOI_07. Ces fragments ont des surfaces de 0,368 m², 0,245 m² et 0,123 m² (0,735 m² au total). Les surfaces des GeoJSON RAW correspondent aux pixels actifs des masques à la précision flottante, donc cet écart provient de la vectorisation/composantes connexes de l’appel GeoAI, et non d’une nouvelle prédiction.

Les métriques de déplacement utilisent la distance de Hausdorff symétrique entre les limites des polygones appariés par recouvrement maximal. Les 171 éléments RAW sont appariés ; les trois composants supplémentaires n’ont pas de paire RAW indépendante et sont exclus de cette mesure. La valeur maximale est sensible à une pointe locale : l’objet concerné dans AOI_02 garde un IoU de 98,85 %, mais atteint 40,50 pixels de déplacement de Hausdorff. Aucune métrique de précision, rappel ou F1 n’est annoncée, car aucune vérité terrain complète n’est disponible.

## Environnement

Les paquets additionnels ont été installés dans `backend/data/models/building/experimental/benchmark_13L1/orthogonalization_env`, un environnement expérimental distinct de celui utilisé par le backend. Le package GeoAI existant a été importé depuis `benchmark_13L1/geoai_package`. Aucune dépendance n’a été installée ou mise à jour dans l’environnement de production.

Versions utilisées : Python 3.12, GeoAI 0.43.1, GeoPandas 1.2.0, rioxarray 0.23.0, Shapely 2.2.0, pyproj 3.8.0, Rasterio 1.5.2, OpenCV Headless 5.0.0.93, leafmap 0.63.1, NumPy 2.5.4 et pandas 3.0.6. Le processus a pointé temporairement `PROJ_LIB`/`PROJ_DATA` vers la base PROJ de cet environnement pour éviter la base PROJ ancienne de l’installation PostgreSQL présente sur Windows. Ce réglage n’a pas été persisté.

## Résultats agrégés

| Mesure | WHU RAW | GeoAI orthogonalized | Variation |
|---|---:|---:|---:|
| Polygones | 171 | 174 | +3 (+1,75 %) |
| Surface totale | 15 199,31 m² | 15 325,02 m² | +0,83 % |
| Périmètre total | 7 277,20 m | 6 962,03 m | −4,33 % |
| Sommets | 10 850 | 10 207 | −5,93 % |
| Déplacement moyen de limite | — | 1,56 px / 0,55 m | — |
| Déplacement maximum de limite | — | 40,50 px / 14,17 m | — |

| AOI | RAW | Orthogonalisés | Surface | Périmètre | Sommets | Déplacement moyen / max | Temps GeoAI |
|---|---:|---:|---:|---:|---:|---:|---:|
| AOI_01_industrial | 2 | 2 | 0,00 % | 0,00 % | 0,00 % | 0,00 / 0,00 px | 3,081 s |
| AOI_02_small_roofs | 47 | 47 | +1,45 % | −5,14 % | −6,88 % | 2,09 / 40,50 px | 1,737 s |
| AOI_03_dense_urban | 22 | 23 | −1,39 % | −4,10 % | −6,79 % | 1,32 / 11,18 px | 0,490 s |
| AOI_04_adjacent_roofs | 7 | 7 | −11,14 % | −10,06 % | −12,39 % | 0,69 / 4,80 px | 0,063 s |
| AOI_05_shadowed_roofs | 55 | 55 | +0,61 % | −4,01 % | −5,49 % | 1,72 / 26,91 px | 2,654 s |
| AOI_06_roads_bare_soil | 0 | 0 | 0,00 % | 0,00 % | 0,00 % | — | 0,012 s |
| AOI_07_complex_shapes | 34 | 36 | +1,65 % | −4,51 % | −5,49 % | 1,19 / 17,80 px | 1,005 s |
| AOI_08_low_building_density | 4 | 4 | 0,00 % | 0,00 % | 0,00 % | 0,00 / 0,00 px | 0,064 s |

Le temps total passé dans `geoai.orthogonalize()` est de **9,106 s**, soit **1,138 s/AOI** et **0,053 s/polygone RAW** en moyenne. Le temps est mesuré sur la fonction, pas sur l’écriture de tous les fichiers.

Les huit transforms correspondent exactement à celles de 13L.3. Les huit masques font 512 × 512, ont un CRS équivalent à EPSG:32637, et les polygones orthogonalisés restent dans les limites raster. Aucun polygone vide, invalide ou auto-intersecté n’a été trouvé. Aucun changement de surface individuel n’a dépassé le contrôle catastrophique défini pour cette validation (rapport de surface hors de `[0,5 ; 1,5]`). Les fichiers GeoJSON et GeoPackage ont été relus et validés en EPSG:32637.

## Évaluation visuelle par catégorie

Les comparatifs utilisent l’orthophoto d’origine ; le RAW est tracé en cyan et le résultat GeoAI en magenta. Les appréciations ci-dessous sont qualitatives, sans vérité terrain.

- **Rectangular large buildings — SIMILAR.** AOI_01 ne contient que deux candidats, et le grand toit sombre attendu n’est pas prédit par WHU. Le toit clair candidat ne montre pas de gain de contour significatif.
- **Small houses — SIMILAR.** Quelques coins sont plus réguliers, mais les petites toitures et détails sont parfois déformés. Le maximum de Hausdorff de 40,50 px provient d’AOI_02.
- **Dense urban — RAW_BETTER.** Le gain visuel n’est pas constant ; AOI_03 gagne un élément lors de la vectorisation et AOI_04 perd 11,14 % de surface totale. Les limites RAW préservent mieux la forme prédite sans gain de contour démontré après orthogonalisation.
- **Complex roofs — RAW_BETTER.** AOI_07 passe de 34 à 36 géométries, avec un maximum de déplacement de 17,80 px ; les détails de formes complexes sont réduits sans preuve qu’ils étaient des erreurs.
- **Irregular buildings — RAW_BETTER.** Le procédé impose des directions orthogonales et peut effacer de vraies irrégularités. Aucun bénéfice généralisable n’est visible.

Les images et données par AOI se trouvent dans [test-data/diagnostics/13L4](../test-data/diagnostics/13L4/). Chaque sous-dossier contient `comparison.png`, `metrics.json`, le masque utilisé, une copie RAW exacte et les sorties GeoJSON/GeoPackage orthogonalisées. Le tableau complet est disponible dans [summary.csv](../test-data/diagnostics/13L4/summary.csv) et [summary.json](../test-data/diagnostics/13L4/summary.json). Le script expérimental reproductible est [run_orthogonalization.py](../test-data/diagnostics/13L4/run_orthogonalization.py).

`RAW_BETTER` signifie ici qu’il vaut mieux conserver la géométrie prédite sans cette orthogonalisation. Cela ne prouve pas que le RAW suit plus fidèlement les toits : la comparaison reste sans annotations de vérité terrain. L’AOI rectangulaire industrielle est en outre peu représentative, car le grand toit sombre visible n’est pas détecté par WHU.

## Portée des changements

Aucun fichier du frontend, du backend métier, du registre de modèles, des modèles, du post-traitement ou des exports de production n’a été modifié. MODEL_C reste inchangé et par défaut ; MODEL_D reste expérimental. Les seuls ajouts sont cet audit, le script et les sorties expérimentales 13L.4, ainsi que l’environnement GeoAI expérimental. La suite de tests complète n’a pas été relancée, car aucun code de production n’a été touché.

## ÉTAPE 13L.4 — WHU ORTHOGONALIZATION

AOIS :
8

WHU RAW POLYGONS :
171

WHU ORTHOGONALIZED POLYGONS :
174

AREA CHANGE :
+0.83 %

PERIMETER CHANGE :
-4.33 %

VERTEX COUNT CHANGE :
-5.93 %

MEAN BOUNDARY DISPLACEMENT :
1.56 px / 0.55 m

MAX BOUNDARY DISPLACEMENT :
40.50 px / 14.17 m

RECTANGULAR BUILDINGS :
SIMILAR

SMALL BUILDINGS :
SIMILAR

DENSE URBAN :
RAW

COMPLEX ROOFS :
RAW

IRREGULAR BUILDINGS :
RAW

GEOMETRY VALIDITY :
VALIDATED

ORTHOGONALIZATION TIME :
9.11 s total; 1.14 s/AOI; 0.053 s/raw polygon

VISUAL RESULT :
MIXED

FINAL DECISION :
ORTHOGONALIZATION_NO_CLEAR_GAIN

MODEL_C :
UNCHANGED

MODEL_D :
UNCHANGED

PRODUCTION :
UNCHANGED

NEXT STEP :
13M GROUND TRUTH VALIDATION
