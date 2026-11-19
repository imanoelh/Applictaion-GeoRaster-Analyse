# ÉTAPE 14A.8 — Building model shootout sur GOLD verrouillé

## 1. Décision

**MODEL_C6 arrive premier parmi les huit moteurs reproductibles testés. L'amélioration est partielle : Object F1=0,3474, rappel=0,2242, 128 objets GT non appariés sur 165, aucun petit bâtiment apparié sur 38 et aucun bâtiment industriel apparié sur 23.**

- BEST_CANDIDATE = MODEL_C6, au classement relatif du cohort testé.
- MODEL_C6_GENERALIZATION = PARTIAL.
- FINAL_DECISION = MODEL_C6_PARTIAL.
- NEXT_STEP = TARGETED_ACTIVE_LEARNING, exclusivement sur données hors GOLD.
- MODEL_C reste production ; aucune promotion, aucun changement de service/API/frontend.

Le choix de ne pas poursuivre immédiatement le staging suit le cas « aucun modèle assez bon » : même le premier conserve des manques importants sur les priorités demandées. Aucun nouveau seuil numérique d'acceptation ou paramètre optimisé sur GOLD n'a été créé. La place de premier ne suffit pas à déclarer le moteur prêt pour une extraction exhaustive. L'option 14A9 d'optimisation/staging demeure une étape ultérieure possible, après traitement des limites sur données de développement indépendantes.

## 2. GOLD et intégrité

Quatre patches inchangés : RESIDENTIAL_02 (40 bâtiments), DENSE_04 (94), INDUSTRIAL_10 (23), DIFFICULT_11 (8), total **165 features humaines**. La source canonique est `14A7_gold_set/gt/14A7_GOLD_SET_GT_FIXED.gpkg`, table buildings_gt, EPSG:32637. Les quatre masques et RGB sont en grille native EPSG:4326, 512×512. Les coordonnées vectorielles sont transformées en UTM pour les IoU/surfaces ; aucune grille RGB/GT n'est modifiée.

Les 13 fichiers GOLD utilisés (RGB, masques, vecteur et manifests/protocole source) ont des hashes identiques avant/après. Les 17 artefacts modèles inventoriés sont aussi inchangés. Les quatre patches restent interdits à TRAIN, fine-tuning, pseudo-label training, calibration et réglage d'hyperparamètres. TRAIN leakage=0 pour les emprises historiques auditées.

**Portée : validation interne spatialement disjointe, sur quatre scènes d'une même acquisition Maxar partagée avec certains anciens crops.** Ce n'est pas une preuve d'indépendance par acquisition ni de généralisation externe. La scène industrielle est une strate visuelle, pas une certification foncière. Le GOLD est une référence humaine fixe ; sa validité technique ne garantit pas une exhaustivité sémantique parfaite.

## 3. Audit des candidats : 13 examinés, 8 exécutés

| Modèle | Architecture | État |
| --- | --- | --- |
| MODEL_A | U-Net / ResNet34 | NOT_REPRODUCIBLE — segmentation_models_pytorch absent in available stable CPU environment |
| MODEL_C | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_C3 | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_C6 | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_D | U-Net++ / EfficientNetB4 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_F | SegFormer B0 / MiT-B0 | NOT_REPRODUCIBLE — ML_env: transformers missing; existing13q1 env: torchvision::nms import failure; no environment modified |
| MODEL_H | U-Net / ResNet34 3-channel instance head | NOT_REPRODUCIBLE — segmentation_models_pytorch absent in available stable CPU environment |
| MODEL_G | DINOv3-S/16 + UPerNet | NOT_REPRODUCIBLE — BUILDING_CHANNEL_UNRESOLVED_3_LOGITS; NOT_REPRODUCIBLE_PREDICTION_PIPELINE |
| MODEL_F2 | SegFormer B0 / MiT-B0 | NOT_REPRODUCIBLE — ML_env: transformers missing; existing13q1 env: torchvision::nms import failure; no environment modified |
| MODEL_C2 | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_C4 | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_C5 | DeepLabV3 / ResNet50 | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |
| MODEL_E | Historical C+D binary union | BENCHMARKED — LOAD_FORWARD_AND_NORMAL_EXIT_PASS |

Les poids F/F2 sont présents. Le runtime stable `.venv_model_training` ne contient pas transformers ; l'environnement historique `.venv_13q1` échoue à l'import SegFormer avec `operator torchvision::nms does not exist`. Aucun shim, installation ou changement d'environnement n'a été appliqué pour les forcer. A/H nécessitent SMP absent. Le graphe G se charge réellement, mais l'interprétation bâtiment de ses trois logits n'est pas reproductible à partir de la documentation gelée : aucun canal n'a été deviné.

D est exécuté via son export ONNX existant et documenté, sans besoin d'installer SMP. E est l'union historique C+D déjà présente dans le catalogue, sans nouveau poids appris. Les huit workers ont chargé leurs artefacts, passé le warm-up et les quatre forwards, puis quitté avec **code 0**. Pour C6/C5, load_state_dict strict=True ; pour ONNX, chargement de session et contrat des tenseurs vérifiés. Une nouvelle équivalence PyTorch/ONNX n'est pas revendiquée.

Fichiers de preuve : `14A8_model_availability.csv`, `14A8_excluded_runtime_evidence.json`, `14A8_worker_exits.json`, `logs/` et `models/*_runtime.json`.

## 4. Protocole gelé avant inférence

`14A8_frozen_protocol.json` et son SHA256 ont été écrits **avant** les runs GOLD. Tous les paramètres proviennent des scripts/configurations locaux historiques, référencés dans ce fichier.

| Moteur | Normalisation | Runtime | Seuil | Min pixels | Connexité |
| --- | --- | --- | --- | --- | --- |
| MODEL_C | rgb_global_patch_minmax | ONNX_RUNTIME_CPU | 0.5 | 4 | 8 |
| MODEL_C3 | rgb_global_patch_minmax | ONNX_RUNTIME_CPU | 0.3 | 479 | 4 |
| MODEL_C6 | rgb_global_patch_minmax | PYTORCH_CPU | 0.3 | 479 | 4 |
| MODEL_D | rgb_div255 | ONNX_RUNTIME_CPU | 0.5 | 4 | 8 |
| MODEL_C2 | rgb_global_patch_minmax | ONNX_RUNTIME_CPU | 0.5 | 1 | 4 |
| MODEL_C4 | rgb_global_patch_minmax | ONNX_RUNTIME_CPU | 0.3 | 1 | 4 |
| MODEL_C5 | rgb_global_patch_minmax | PYTORCH_CPU | 0.5 | 1 | 4 |
| MODEL_E | C_global_minmax;D_rgb_div255 | ONNX_RUNTIME_CPU_COMPOSITE | 0.5 | 4 | 8 |

Tous : une tuile native 512×512, NCHW float32, pas de resize, padding, overlap, fusion de tuiles ou TTA. Les RGB sont identiques. C/C2/C3/C4/C5/C6 utilisent le min-max RGB global du raster de benchmark, donc du patch entier. D utilise RGB/255, sans moyenne/std ImageNet. E utilise séparément ces deux prétraitements. Sortie sigmoid du canal principal pour la famille C ; softmax canal bâtiment1 pour D ; max des probabilités C/D pour E. L'union binaire E a été vérifiée égale à C OR D sur les quatre patches.

C3/C6 reprennent exactement threshold0.30, minimum479 pixels, connexité4 et aucune morphologie de 14A.6C. C2/C4/C5 conservent leurs réglages historiques propres. Pour C/D/E, le filtre standard documenté min4/connexité8, non calibré sur GOLD, est déclaré explicitement. Aucune nouvelle régularisation de contour ou optimisation n'est appliquée.

Cette comparaison porte sur **moteurs et configurations historiques**, sans isoler l'architecture de tous les effets de seuil/post-traitement. C6 versus C3 partage les mêmes règles 0.30/479 ; C production utilise son seuil0.50. Aucun passage de C à0.30 pour améliorer son résultat sur GOLD.

Le C3 ONNX chargé est exactement celui du benchmark14A.6C (SHA256 `2354a456b33512f6a7d20aaf9b72ee12d3d8f91a5c301e507b85ba939c47f468`). Le D ONNX correspond au hash documenté par l'adapter (`62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6`). Les chemins effectivement chargés et tous les hashes sont en annexe.

## 5. Matching objet commun

Le GT conserve ses **165 building_id/features**, dont quatre MultiPolygon comptant chacun pour un bâtiment. Il n'est pas remplacé par les composantes du masque GT, qui fusionneraient certains bâtiments adjacents.

Chaque prédiction est une composante finale après le filtre historique du moteur. Polygonisation sur la grille exacte, reprojection EPSG:32637. Les éventuelles invalidités de polygonisation numérique sont réparées sans morphologie et comptées dans POLYGONIZATION_REPAIRS ; le masque n'est pas modifié par cette réparation vectorielle.

Une matrice complète IoU polygonale GT×prédictions est construite. Matching **Hungarian strict un-à-un**, seuil principal IoU>=0.30 : maximiser d'abord le nombre de paires admissibles, puis la somme des IoU. Des colonnes dummy représentent les non-appariés. Un polygone fusionné ne compte jamais comme plusieurs TP. Les cas de contrôle incluent une matrice où le simple maximum de somme IoU suivi d'un filtre perdrait un TP : le matching gelé conserve les deux paires admissibles.

1320 lignes GT contrôlées = 165×8 moteurs, chaque GT exactement une fois par moteur, aucune réutilisation d'une prédiction comme TP. TP+FN=165 et TP+FP=PRED pour chaque modèle. FP et FN signifient **non-appairés au sens du protocole** : un FN peut être partiellement couvert ou fusionné ; un FP peut être une forme de toit mal segmentée. Ils ne signifient pas systématiquement absence totale de pixels ou objet non bâti.

Les seuils IoU0.50/0.70 sont des mesures secondaires préenregistrées, pas un threshold sweep de probabilité ni un choix de paramètre après lecture de GOLD.

## 6. Métriques pixel et contours

Les métriques pixel primaires utilisent les masques au seuil historique, **avant le filtre de composantes**, comme dans14A.6C. Les métriques des masques finaux filtrés sont aussi fournies séparément (`FINAL_MASK_*`). Les mêmes masques GT verrouillés servent à tous les modèles. Le classement principal est objet, donc porte sur les composantes finales.

IoU/Dice/précision/rappel globaux sont regroupés depuis les comptes pixel (micro). Les moyennes par patch sont également conservées (`*_MACRO`) ; ne pas confondre ces agrégations.

Boundary F1 @1px reprend la définition correcte déjà utilisée en14A.1E et gelée en14A.7 : bord interne par érosion8, voisinage de tolérance1px par dilatation8 bornée, précision et rappel puis moyenne harmonique, sans wrap aux limites. Toutes les valeurs sont contrôlées dans[0,1]. **La formule erronée de certains anciens scripts14A.3B/14A.6C n'est pas reprise** ; ses anciennes valeurs ne sont donc pas directement comparables à ce F1. Aucun changement de définition après lecture des résultats.

Mean Boundary Distance réutilise la distance chamfer historique14A.1E, voisinage8 avec diagonale sqrt(2), moyenne symétrique sur les pixels de contour des deux directions, en pixels. Ce n'est pas une nouvelle définition Euclidienne exacte ou une distance en mètres improprement appliquée au CRS géographique. Si le contour prédit est vide alors que le GT ne l'est pas, la distance historique est infinie : le CSV porte INF. La QA a corrigé ce cas pour ne pas omettre silencieusement cette scène du cumul ; Object F1, Boundary F1, autres métriques de classement et paramètres n'ont pas changé. Une moyenne conditionnelle des seules scènes finies est conservée dans MEAN_BOUNDARY_DISTANCE_FINITE_ONLY_PX, explicitement distincte du score global. Preuve : `14A8_boundary_distance_QA.json`.

## 7. Comparaison globale et classement

Priorité appliquée : Object F1, Object Recall, bâtiments non appariés, FP/précision, Boundary F1, IoU pixel, CPU. Le meilleur IoU seul ne détermine pas la décision.

| Rang | Modèle | TP | FP | FN | Précision | Rappel | Object F1 | Pixel IoU | Dice | Boundary F1 | CPU s/patch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | MODEL_C6 | 37 | 11 | 128 | 0.7708 | 0.2242 | 0.3474 | 0.3603 | 0.5298 | 0.2829 | 6.096 |
| 2 | MODEL_C3 | 25 | 3 | 140 | 0.8929 | 0.1515 | 0.2591 | 0.2233 | 0.3650 | 0.1835 | 3.534 |
| 3 | MODEL_E | 34 | 75 | 131 | 0.3119 | 0.2061 | 0.2482 | 0.2692 | 0.4243 | 0.2297 | 4.795 |
| 4 | MODEL_C5 | 27 | 39 | 138 | 0.4091 | 0.1636 | 0.2338 | 0.2130 | 0.3511 | 0.1702 | 6.535 |
| 5 | MODEL_C4 | 29 | 56 | 136 | 0.3412 | 0.1758 | 0.2320 | 0.2742 | 0.4303 | 0.2031 | 3.804 |
| 6 | MODEL_D | 28 | 70 | 137 | 0.2857 | 0.1697 | 0.2129 | 0.2121 | 0.3500 | 0.2165 | 1.405 |
| 7 | MODEL_C2 | 22 | 32 | 143 | 0.4074 | 0.1333 | 0.2009 | 0.1638 | 0.2815 | 0.1209 | 3.782 |
| 8 | MODEL_C | 20 | 24 | 145 | 0.4545 | 0.1212 | 0.1914 | 0.1442 | 0.2521 | 0.0988 | 3.416 |

Les 165 GT sont le même dénominateur pour les huit moteurs. C6 obtient le meilleur rappel/F1 objet et les meilleurs contours de ce groupe. C3 conserve la meilleure précision objet et le plus faible nombre de FP. D est le plus rapide. Les défauts de F/H/G ne permettent aucune conclusion sur leur qualité relative : leurs résultats ne sont pas inventés.

### Robustesse aux seuils de matching

| Modèle | F1 IoU0.30 | F1 IoU0.50 | F1 IoU0.70 |
| --- | --- | --- | --- |
| MODEL_C6 | 0.3474 | 0.2160 | 0.1033 |
| MODEL_C3 | 0.2591 | 0.1347 | 0.0933 |
| MODEL_E | 0.2482 | 0.1387 | 0.0803 |
| MODEL_C5 | 0.2338 | 0.1212 | 0.0693 |
| MODEL_C4 | 0.2320 | 0.1280 | 0.0480 |
| MODEL_D | 0.2129 | 0.1141 | 0.0684 |
| MODEL_C2 | 0.2009 | 0.1370 | 0.0548 |
| MODEL_C | 0.1914 | 0.1244 | 0.0478 |

C6 reste premier à0.30/0.50/0.70. Ces scores restent faibles dans l'absolu ; le maintien du rang ne suffit pas à garantir la qualité de contours d'un produit final.

## 8. Résultats par scène

### RESIDENTIAL

| Modèle | TP | FP | FN | Précision | Rappel | F1 | IoU | Boundary F1 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MODEL_C6 | 16 | 3 | 24 | 0.8421 | 0.4000 | 0.5424 | 0.4899 | 0.3649 | 5.645 |
| MODEL_C5 | 13 | 7 | 27 | 0.6500 | 0.3250 | 0.4333 | 0.3326 | 0.2478 | 5.581 |
| MODEL_C3 | 11 | 1 | 29 | 0.9167 | 0.2750 | 0.4231 | 0.3445 | 0.2564 | 3.645 |
| MODEL_C4 | 13 | 11 | 27 | 0.5417 | 0.3250 | 0.4062 | 0.4079 | 0.2676 | 3.544 |
| MODEL_E | 15 | 24 | 25 | 0.3846 | 0.3750 | 0.3797 | 0.3510 | 0.3326 | 4.767 |
| MODEL_D | 13 | 19 | 27 | 0.4062 | 0.3250 | 0.3611 | 0.2331 | 0.3131 | 1.303 |
| MODEL_C2 | 9 | 12 | 31 | 0.4286 | 0.2250 | 0.2951 | 0.2583 | 0.1971 | 3.547 |
| MODEL_C | 8 | 12 | 32 | 0.4000 | 0.2000 | 0.2667 | 0.2257 | 0.1591 | 3.440 |
### DENSE

| Modèle | TP | FP | FN | Précision | Rappel | F1 | IoU | Boundary F1 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MODEL_C6 | 19 | 5 | 75 | 0.7917 | 0.2021 | 0.3220 | 0.3571 | 0.2786 | 7.752 |
| MODEL_C3 | 13 | 2 | 81 | 0.8667 | 0.1383 | 0.2385 | 0.2029 | 0.1683 | 3.422 |
| MODEL_E | 16 | 34 | 78 | 0.3200 | 0.1702 | 0.2222 | 0.2410 | 0.2069 | 4.743 |
| MODEL_C4 | 15 | 35 | 79 | 0.3000 | 0.1596 | 0.2083 | 0.2527 | 0.1933 | 3.462 |
| MODEL_C5 | 13 | 23 | 81 | 0.3611 | 0.1383 | 0.2000 | 0.1923 | 0.1530 | 5.682 |
| MODEL_C2 | 12 | 17 | 82 | 0.4138 | 0.1277 | 0.1951 | 0.1464 | 0.1027 | 3.475 |
| MODEL_C | 11 | 11 | 83 | 0.5000 | 0.1170 | 0.1897 | 0.1292 | 0.0859 | 3.367 |
| MODEL_D | 12 | 35 | 82 | 0.2553 | 0.1277 | 0.1702 | 0.1978 | 0.1973 | 1.448 |
### INDUSTRIAL

| Modèle | TP | FP | FN | Précision | Rappel | F1 | IoU | Boundary F1 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MODEL_D | 1 | 1 | 22 | 0.5000 | 0.0435 | 0.0800 | 0.3616 | 0.0917 | 1.441 |
| MODEL_E | 1 | 1 | 22 | 0.5000 | 0.0435 | 0.0800 | 0.3616 | 0.0917 | 4.787 |
| MODEL_C | 0 | 0 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 3.518 |
| MODEL_C3 | 0 | 0 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0048 | 0.0073 | 3.555 |
| MODEL_C6 | 0 | 0 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 5.539 |
| MODEL_C2 | 0 | 0 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4.159 |
| MODEL_C4 | 0 | 1 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0239 | 0.0245 | 4.023 |
| MODEL_C5 | 0 | 1 | 23 | 0.0000 | 0.0000 | 0.0000 | 0.0033 | 0.0064 | 7.654 |
### DIFFICULT

| Modèle | TP | FP | FN | Précision | Rappel | F1 | IoU | Boundary F1 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MODEL_C6 | 2 | 3 | 6 | 0.4000 | 0.2500 | 0.3077 | 0.2335 | 0.2023 | 5.448 |
| MODEL_C3 | 1 | 0 | 7 | 1.0000 | 0.1250 | 0.2222 | 0.1084 | 0.1740 | 3.513 |
| MODEL_C | 1 | 1 | 7 | 0.5000 | 0.1250 | 0.2000 | 0.0710 | 0.0416 | 3.340 |
| MODEL_C2 | 1 | 3 | 7 | 0.2500 | 0.1250 | 0.1667 | 0.0760 | 0.0607 | 3.945 |
| MODEL_D | 2 | 15 | 6 | 0.1176 | 0.2500 | 0.1600 | 0.1421 | 0.1274 | 1.426 |
| MODEL_E | 2 | 16 | 6 | 0.1111 | 0.2500 | 0.1538 | 0.1425 | 0.1311 | 4.884 |
| MODEL_C5 | 1 | 8 | 7 | 0.1111 | 0.1250 | 0.1176 | 0.0970 | 0.1429 | 7.223 |
| MODEL_C4 | 1 | 9 | 7 | 0.1000 | 0.1250 | 0.1111 | 0.1508 | 0.1852 | 4.189 |

C6 est premier en F1 pour RESIDENTIAL, DENSE et DIFFICULT. Sur INDUSTRIAL, D et E sont ex æquo àF1=0.08, avec seulement1TP/23 ; C6 a0TP/23. Il n'y a pas de victoire industrielle exploitable démontrée.

## 9. Petits bâtiments

Le seuil SMALL<=50m² vient du protocole14A.7 figé avant annotation/résultats ; aucun seuil medium/large n'est inventé. Distribution des165 surfaces : minimum 5.20m² ; Q1 58.26 ; médiane 98.80 ; Q3 154.04 ; maximum 1361.57m². **38 bâtiments** satisfont cette classe.

| Modèle | Small TP /38 | Small Recall | Small avec pixels positifs bruts | Small perdant toute couverture au filtre |
| --- | --- | --- | --- | --- |
| MODEL_C6 | 0 /38 | 0.0000 | 9 | 3 |
| MODEL_C3 | 1 /38 | 0.0263 | 7 | 4 |
| MODEL_E | 3 /38 | 0.0789 | 12 | 0 |
| MODEL_C5 | 3 /38 | 0.0789 | 7 | 0 |
| MODEL_C4 | 1 /38 | 0.0263 | 10 | 0 |
| MODEL_D | 3 /38 | 0.0789 | 8 | 0 |
| MODEL_C2 | 1 /38 | 0.0263 | 5 | 0 |
| MODEL_C | 0 /38 | 0.0000 | 4 | 0 |

C6 ne détecte pas davantage de petits bâtiments :0/38, contre1 pour C3 et3 pour D/C5/E. Le filtre479px correspond ici à environ55–56m² ; il peut pénaliser les objets de cette classe. L'analyse des sorties déjà existantes précise l'effet : C6 possède des pixels binaires positifs sur9 petits GT, dont3 perdent toute couverture à cause du filtre gelé. Les29 autres petits GT n'ont déjà aucun pixel positif au seuil historique0.30. Le filtre n'explique donc pas à lui seul ce déficit. Les six ayant encore quelques pixels après filtrage ne satisfont pas le matching objet0.30.

Cette analyse n'essaie aucun seuil/filtre alternatif et ne modifie aucun classement. Elle distingue un effet mécanique observé d'hypothèses de confiance, domaine ou résolution. Toute révision de filtre doit se faire sur développement hors GOLD.

## 10. Faux positifs et FN

Les CSV recensent **310 événements FP** et **1098 événements FN**, cumulés sur les huit moteurs, pas autant de bâtiments distincts. Les64 exemples FN et48 FP principaux ont été inspectés dans les planches, avec statuts de revue explicites. Les autres restent UNREVIEWED/OTHER ou classés seulement par des règles géométriques ; aucune catégorie sémantique certaine n'est inventée pour chaque cas.

Parmi les48 FP examinés :44 ROOF_LIKE_OBJECT,2 BARE_SOIL,1 ROAD,1 OTHER ambigu. Ces comptes décrivent **l'échantillon de revue**, pas la distribution complète. Beaucoup sont des sous-segmentations/fusions de toits avec IoU insuffisant, plutôt que des détections de terrain. L'exemple FP259 de C6 sur DIFFICULT couvre visiblement la voirie/passages piétons. Les exemples FP33/FP85 portent sur du sol nu. Les objets gris ambigus ne sont pas forcés en classe végétation ou toiture.

Les FN portent les tags déterministes SMALL, PATCH_EDGE, DENSE_CLUSTER et ADJACENT_BUILDINGS (distance GT<=1m), complétés dans l'échantillon revu par du contexte d'ombre. Les raisons LOW_CONTRAST/SHADOW/COMPLEX_ROOF demeurent des hypothèses visuelles lorsque non démontrées. Le seuil de matching peut transformer une fusion ou un contour trop petit en FP+FN simultanés ; l'échec n'est pas automatiquement une absence totale de détection.

Pour C6 :11FP contre24 pour C et3 pour C3 ; son coût FP est donc mieux contrôlé que la production et l'union E, mais supérieur àC3. Ses128FN incluent75 bâtiments DENSE,24 RESIDENTIAL,23 INDUSTRIAL et6 DIFFICULT. Ces effectifs délimitent clairement les priorités métier restantes.

Fichiers : `14A8_false_positive_analysis.csv`, `14A8_missed_buildings_analysis.csv`, `14A8_small_building_analysis.csv`, `14A8_error_analysis_summary.json`, `diagnostics/FP_REVIEW_*.png`, `FN_REVIEW_*.png`.

## 11. Fusions et fragmentations

Règles diagnostiques gelées : une prédiction est fusionnée si elle couvre au moins30% de la surface de chacun d'au moins deux GT ; un GT est fragmenté si au moins deux prédictions ont chacune au moins30% de leur propre surface dans ce GT. Ces mesures d'overlap sont séparées des TP Hungarian ; elles n'ajoutent jamais de TP. La colonne globale MERGED compte les objets prédits fusionnés, pas le nombre de GT impliqués.

| Modèle | Prédictions fusionnées | Bâtiments GT concernés | GT fragmentés |
| --- | --- | --- | --- |
| MODEL_C | 1 | 4 | 5 |
| MODEL_C3 | 6 | 14 | 0 |
| MODEL_C6 | 14 | 37 | 0 |
| MODEL_D | 8 | 20 | 7 |
| MODEL_C2 | 3 | 8 | 6 |
| MODEL_C4 | 10 | 23 | 6 |
| MODEL_C5 | 5 | 12 | 6 |
| MODEL_E | 8 | 21 | 8 |

C6 présente14 groupes fusionnés impliquant37 GT, contre6 groupes/14GT pour C3 et1 groupe/4GT pour C. Il conserve donc davantage de fusions. Son absence de fragmentation selon cette règle ne compense pas les omissions/fusions.

## 12. CPU et mémoire

Même machine et même environnement `.venv_model_training` pour les huit workers : PyTorch2.8.0 CPU, Torchvision0.23.0, ONNX Runtime1.31.1, NumPy2.5.4. Quatre threads intra-op, un inter-op ; exécution séquentielle des moteurs. Un warm-up512 zéro est effectué et exclu du temps moyen. Aucun warm-up ne sert au choix de paramètres.

| Modèle | Load s | Warm-up s | Inférence s/patch | Pipeline s/patch | Total 4 patches s | Load+warm+4 patches s | Pic worker MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MODEL_C6 | 25.955 | 7.067 | 6.060 | 6.096 | 24.385 | 57.407 | 656.4 |
| MODEL_C3 | 0.804 | 3.420 | 3.503 | 3.534 | 14.136 | 18.360 | 436.3 |
| MODEL_E | 1.321 | 4.504 | 4.743 | 4.795 | 19.180 | 25.005 | 867.8 |
| MODEL_C5 | 6.526 | 5.801 | 6.497 | 6.535 | 26.140 | 38.467 | 655.5 |
| MODEL_C4 | 0.756 | 3.120 | 3.765 | 3.804 | 15.218 | 19.093 | 456.1 |
| MODEL_D | 0.749 | 1.235 | 1.354 | 1.405 | 5.618 | 7.602 | 500.8 |
| MODEL_C2 | 0.923 | 3.520 | 3.749 | 3.782 | 15.126 | 19.569 | 436.2 |
| MODEL_C | 1.620 | 5.051 | 3.373 | 3.416 | 13.665 | 20.336 | 436.8 |

CPU_TIME_TOTAL cumule les quatre préparations+forwards+post-traitements/polygonisations ; CPU_TIME_MEAN est ce cumul/4. Le cold total ajoute chargement et warm-up. Les temps de sortie NPZ et d'évaluation sont séparés dans `14A8_runtime_metrics.csv`. Le rendu de planches, calcul de toutes les métriques et I/O GeoTIFF ne sont pas prétendus être le coût de détection en production. Les logs workers conservent également leur temps mural global.

D ONNX est le plus rapide, environ1.405s/patch. C6 PyTorch nécessite6.096s, contre3.416s pour C et3.534s pour C3. Sa mémoire peak worker est656.4MiB. Le chargement C6 inclut l'import runtime et la lecture du checkpoint dans un processus neuf ; l'effet de cache système/ordre de passage n'est pas neutralisé. Un seul passage mesuré sur quatre patches ne constitue pas un intervalle de performance garanti. Aucun coût de grand raster, API, export ou frontend n'est mesuré ici.

Le coût C6 est compatible avec un traitement CPU différé, mais n'est pas une preuve d'acceptabilité interactive ou sur grande orthophoto. Aucun export ONNX ou optimisation de C6 n'est réalisé pendant ce benchmark.

## 13. Comparaison explicite C6

| Comparaison | TP | FP | FN | Object F1 | Autres constats |
|---|---:|---:|---:|---:|---|
| C6 |37|11|128|0.3474|Small0/38 ; merged14 ; Boundary0.2829 |
| C production |20|24|145|0.1914|17TP de moins ; small0/38 ; merged1 |
| C3 |25|3|140|0.2591|12TP de moins ; 8FP de moins ; small1/38 ; merged6 |
| E, meilleur autre candidat au classement |34|75|131|0.2482|3TP de moins ; 64FP de plus ; small3/38 |

1. **C6 gagne-t-il encore ?** Oui au classement relatif des moteurs testés sur ce GOLD interne, et aux trois seuils de matching. L'amélioration n'atteint pas une détection exhaustive ni la généralisation externe.
2. **Davantage de petits bâtiments ?** Non :0/38.
3. **Trop de FP ?**11, moins que C/D/E, plus que C3 ; plusieurs sont des erreurs de forme/fusion, et une voirie est clairement visible dans l'échantillon.
4. **Davantage de fusions ?** Oui :14 groupes, contre6 pour C3.
5. **Contours meilleurs ?** Boundary F1=0.2829 est le meilleur du cohort. Le MBD global C6 est INF, car il n'existe aucun contour prédit au seuil historique sur INDUSTRIAL ; la valeur conditionnelle13.74px ne concerne que les trois autres scènes et ne constitue pas une amélioration globale de MBD. La qualité absolue reste limitée.
6. **CPU acceptable ?**6.10s par512 et chargement élevé mesurés ; usage batch plausible, staging/ONNX/grands rasters non validés.

## 14. Décision et reprise

**MODEL_C6_PARTIAL** décrit ces résultats plus justement qu'une validation générale. C6 est le meilleur candidat relatif, avec des manques sur les critères prioritaires. Aucune hypothèse de supériorité de F/H n'est tirée de leur indisponibilité.

La prochaine étape recommandée est TARGETED_ACTIVE_LEARNING sur de **nouvelles scènes hors GOLD**, avec garde-fou d'ID/hash/emprise : petits bâtiments et objets de faible contraste, diversité industrielle, séparation des toits adjacents, voirie/sol nu. Les dix scènes de correction assistée restent un pool potentiel soumis à revue et séparation géographique ; leurs propositions IA ne sont pas automatiquement GT.

Sur ces données de développement seulement, vérifier séparément les causes du défaut de rappel et le rôle du filtre479, avant de décider d'un fine-tuning ciblé ou d'un staging optimisé. Aucun réglage, exemple d'entraînement, correction de GT ou pseudo-label ne doit provenir des quatre GOLD. Un prochain modèle doit avoir sa configuration gelée avant son évaluation finale, avec journal des évaluations pour limiter l'adaptation répétée au holdout.

Cette étape s'arrête ici : pas de fine-tuning automatique, pas de changement de seuil sur GOLD, pas de promotion de C6, pas de remplacement de MODEL_C.

## 15. Livrables et inspection

Dossier : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout/`.

Sept CSV demandés présents : availability, patch_metrics, global_model_comparison, false_positive_analysis, missed_buildings_analysis, runtime_metrics, gold_input_hashes. Compléments : matching GT détaillé, sensibilité IoU, analyses adjacence/petits objets, distribution d'aire, gagnants par scène, protocole/hash, runtime des workers et décision JSON.

- `14A8_GLOBAL_CONTACT_SHEET.png` : RGB, GT puis huit modèles sur les quatre scènes.
- `overlays/*_comparison.png` : une comparaison par scène.
- `overlays/MODEL_*__*.png` : contours512×512, **vert=GT, magenta=prédictions**.
- `models/MODEL_*/` : probability map, masque au seuil, masque final et polygones géoréférencés.
- `diagnostics/` : principaux FP et exemples FN avec IDs correspondant aux CSV.
- `14A8_METRICS_DASHBOARD.png` : synthèse statique, inspectée visuellement.
- `14A8_matching_and_identity_QA.json` : intégrité matching, union E et identités historiques.
- `14A8_FINAL_DECISION.json` : décision et contrôles d'immuabilité.

Les overlays résidentiels/denses, la comparaison industrielle et les sept planches d'erreurs ont été inspectés. Le rendu ne sert pas à modifier le GOLD ou sélectionner un seuil.

## Annexe A — SHA256 des entrées GOLD

Chemins complets et tailles dans `14A8_gold_input_hashes.csv`. Toutes les valeurs ci-dessous sont identiques après exécution.

| Type | Fichier | SHA256 |
| --- | --- | --- |
| GOLD_METADATA | 14A7_GOLD_SET_manifest.csv | `73370347965003b68cddd03202b27ba82d0809522cb73ce5a4bc6372dea867b8` |
| GOLD_METADATA | GOLD_SET_LOCK.json | `ee87d54be05c10c53b28a2831b9ed8ffce485bc80eab8b27baed747088b6cfeb` |
| GOLD_METADATA | GOLD_VALIDATED_ANNOTATION_LOCK.json | `7e58328517809cf05d28c6a8ef49c2632e75f975973f8fd0f956b378432b09d8` |
| GOLD_METADATA | 14A8_SHOOTOUT_PROTOCOL.json | `6d771952a330611c19f187adb49ab073485e643e0f79de716f65487cb5bd4e7d` |
| HUMAN_GT_VECTOR | 14A7_GOLD_SET_GT_FIXED.gpkg | `a0acdb604e6a89cf517845ab9d19f33dd712e38c6949d7fec14ceac2360e6724` |
| RGB | 14A7_VAL_2025_RESIDENTIAL_02.tif | `684b7c29e85cecfb465d78fb2ca534e412b9f31af4ea58380a7ac883a5d22404` |
| HUMAN_GT_MASK | 14A7_VAL_2025_RESIDENTIAL_02.tif | `2ad0d8f96b6329802baa0f42ecf5f584470d9bee734e59e9ecdc41425501215d` |
| RGB | 14A7_VAL_2025_DENSE_04.tif | `907b215a922223850b9477784ba3f42b030c22bdf627c171108aa804c43f4e86` |
| HUMAN_GT_MASK | 14A7_VAL_2025_DENSE_04.tif | `bdc765cade025ed4c1ca744778faf37c6439ab086da0b3f1ef37ddaf9085a2f4` |
| RGB | 14A7_VAL_2025_INDUSTRIAL_10.tif | `66133eb973eb8c451c929d925145193a958c2857e9644f5d547fdc2adae13ee9` |
| HUMAN_GT_MASK | 14A7_VAL_2025_INDUSTRIAL_10.tif | `5a54b0106fe970699e1f64748d3a0ebaf725e926dbd081c7fef2ec340247917a` |
| RGB | 14A7_VAL_2025_DIFFICULT_11.tif | `3b96984beb9a6cace5b6cbe0ded96303d8179e68802a833b603b8f78bdc4e915` |
| HUMAN_GT_MASK | 14A7_VAL_2025_DIFFICULT_11.tif | `fe786ab772cc334d766befcb6137942a7f187b2eacd5fca9575febfb9546a9ae` |

## Annexe B — Artefacts réellement exécutés

| Modèle exécuté | Artefact effectivement chargé | SHA256 |
| --- | --- | --- |
| MODEL_C | `backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx` | `94661ded0bc79bbca99c03d55d817bcb7369d46eb13d7983ebf6ae711003fd45` |
| MODEL_C3 | `backend/data/models/model_c3_experimental/model_c3.onnx` | `2354a456b33512f6a7d20aaf9b72ee12d3d8f91a5c301e507b85ba939c47f468` |
| MODEL_C6 | `backend/data/models/model_c6_experimental/best_model_c6.pth` | `7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84` |
| MODEL_D | `backend/data/models/building/experimental/whu_unetplusplus_effb4/onnx/model.onnx` | `62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6` |
| MODEL_C2 | `backend/data/models/model_c2_experimental/model_c2.onnx` | `2f3b5a6f1dd4e10690b9e321930b9f4593e6abe9e4af89e160936c37fc7d7d91` |
| MODEL_C4 | `backend/data/models/model_c4_experimental/model_c4.onnx` | `9183b2d0d4ad7576a6f7b831a7698f2e709014d2b524daaa371d60a169449dbf` |
| MODEL_C5 | `backend/data/models/model_c5_experimental/final_model_c5.pth` | `1667891bd6e3a02746d2e6ccfc58b68f5179363a4b6e8027930a0592914136a3` |
| MODEL_E | `backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx;backend/data/models/building/experimental/whu_unetplusplus_effb4/onnx/model.onnx` | `94661ded0bc79bbca99c03d55d817bcb7369d46eb13d7983ebf6ae711003fd45;62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6` |

Les hashes des autres poids audités et des sources PTH sont dans `14A8_model_weight_hashes.json` ;17/17 inchangés. Le diff des fichiers backend/app et frontend est vide. Les éventuelles modifications antérieures de scripts runtime hors production sont distinctes ; aucun nouveau changement de ces services n'est effectué ici.

GOLD PATCHES :
4

GOLD BUILDINGS :
165

GOLD TRAIN LEAKAGE :
0

MODELS AUDITED :
13

MODELS BENCHMARKED :
8 — MODEL_C, MODEL_C3, MODEL_C6, MODEL_D, MODEL_C2, MODEL_C4, MODEL_C5, MODEL_E

MODEL_C OBJECT F1 :
0.1914

MODEL_C3 OBJECT F1 :
0.2591

MODEL_C6 OBJECT F1 :
0.3474

BEST OBJECT RECALL :
MODEL_C6 — 0.2242

BEST OBJECT F1 :
MODEL_C6 — 0.3474

LOWEST MISSED BUILDINGS :
MODEL_C6 — 128

LOWEST FP :
MODEL_C3 — 3

BEST BOUNDARY F1 :
MODEL_C6 — 0.2829

FASTEST CPU MODEL :
MODEL_D ONNX — 1.405 s/patch

BEST OVERALL MODEL :
MODEL_C6 — classement relatif des moteurs testés

MODEL_C6 GENERALIZATION :
PARTIAL

FINAL DECISION :
MODEL_C6_PARTIAL

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
TARGETED_ACTIVE_LEARNING
