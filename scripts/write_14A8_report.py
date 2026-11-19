"""Render the completed frozen benchmark into a reproducible Markdown report."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def rows(name):return list(csv.DictReader((OUT/name).open(encoding='utf-8-sig')))
def j(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def table(headers,data):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in data])
def f(v,n=4):return f'{float(v):.{n}f}'
def main():
 s=j('14A8_summary.json');rank=s['ranking'];by={r['MODEL']:r for r in rank};p=j('14A8_frozen_protocol.json');availability=rows('14A8_model_availability.csv');patch=rows('14A8_patch_metrics.csv');area=j('14A8_area_summary.json');err=j('14A8_error_analysis_summary.json');decision=j('14A8_FINAL_DECISION.json')
 global_table=table(['Rang','Modèle','TP','FP','FN','Précision','Rappel','Object F1','Pixel IoU','Dice','Boundary F1','CPU s/patch'],[[r['RANK'],r['MODEL'],r['TP'],r['FP'],r['FN'],f(r['OBJECT_PRECISION']),f(r['OBJECT_RECALL']),f(r['OBJECT_F1']),f(r['PIXEL_IOU']),f(r['DICE']),f(r['BOUNDARY_F1']),f(r['CPU_TIME_MEAN'],3)] for r in rank])
 candidate_table=table(['Modèle','Architecture','État'],[[r['MODEL'],r['ARCHITECTURE'],r['BENCHMARK_STATUS']+' — '+r['REASON']] for r in availability])
 configs=table(['Moteur','Normalisation','Runtime','Seuil','Min pixels','Connexité'],[[r['model'],r['preprocessing'],r['engine'],r['threshold'],r['min_component_pixels'],r['connectivity']] for r in p['models']])
 scene_sections=[]
 for scene in ['RESIDENTIAL','DENSE','INDUSTRIAL','DIFFICULT']:
  rr=sorted([r for r in patch if r['SCENE']==scene],key=lambda r:-float(r['OBJECT_F1']))
  scene_sections.append('### '+scene+'\n\n'+table(['Modèle','TP','FP','FN','Précision','Rappel','F1','IoU','Boundary F1','CPU s'],[[r['MODEL'],r['TP'],r['FP'],r['FN'],f(r['OBJECT_PRECISION']),f(r['OBJECT_RECALL']),f(r['OBJECT_F1']),f(r['PIXEL_IOU']),f(r['BOUNDARY_F1']),f(r['CPU_TIME_TOTAL'],3)] for r in rr]))
 performance=table(['Modèle','Load s','Warm-up s','Inférence s/patch','Pipeline s/patch','Total 4 patches s','Load+warm+4 patches s','Pic worker MiB'],[[r['MODEL'],f(r['MODEL_LOAD_SECONDS'],3),f(r['WARMUP_SECONDS'],3),f(r['CPU_INFERENCE_MEAN'],3),f(r['CPU_TIME_MEAN'],3),f(r['CPU_TIME_TOTAL'],3),f(r['CPU_COLD_TOTAL'],3),f(r['PEAK_WORKER_MB'],1)] for r in rank])
 small=table(['Modèle','Small TP /38','Small Recall','Small avec pixels positifs bruts','Small perdant toute couverture au filtre'],[[r['MODEL'],str(r['SMALL_TP'])+' /38',f(r['SMALL_RECALL']),err['filter_effects'][r['MODEL']]['small_with_raw_positive_pixels'],err['filter_effects'][r['MODEL']]['small_with_all_raw_coverage_removed']] for r in rank])
 merge=table(['Modèle','Prédictions fusionnées','Bâtiments GT concernés','GT fragmentés'],[[r['MODEL'],r['MERGED_PREDICTED_OBJECTS'],r['GT_BUILDINGS_INVOLVED_IN_MERGES'],r['FRAGMENTED_GT_OBJECTS']] for r in rows('14A8_merge_fragment_summary.csv')])
 sens=rows('14A8_global_object_iou_sensitivity.csv');sensitivity=table(['Modèle','F1 IoU0.30','F1 IoU0.50','F1 IoU0.70'],[[r['MODEL']]+[f(next(a['F1'] for a in sens if a['MODEL']==r['MODEL'] and a['IOU_THRESHOLD']==t)) for t in ['0.3','0.5','0.7']] for r in rank])
 inputs=table(['Type','Fichier','SHA256'],[[r['KIND'],Path(r['PATH']).name,'`'+r['SHA256']+'`'] for r in rows('14A8_gold_input_hashes.csv')])
 weights=table(['Modèle exécuté','Artefact effectivement chargé','SHA256'],[[r['model'],'`'+r['path']+'`','`'+r['sha256']+'`'] for r in p['models']])
 text=f'''# ÉTAPE 14A.8 — Building model shootout sur GOLD verrouillé

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

{candidate_table}

Les poids F/F2 sont présents. Le runtime stable `.venv_model_training` ne contient pas transformers ; l'environnement historique `.venv_13q1` échoue à l'import SegFormer avec `operator torchvision::nms does not exist`. Aucun shim, installation ou changement d'environnement n'a été appliqué pour les forcer. A/H nécessitent SMP absent. Le graphe G se charge réellement, mais l'interprétation bâtiment de ses trois logits n'est pas reproductible à partir de la documentation gelée : aucun canal n'a été deviné.

D est exécuté via son export ONNX existant et documenté, sans besoin d'installer SMP. E est l'union historique C+D déjà présente dans le catalogue, sans nouveau poids appris. Les huit workers ont chargé leurs artefacts, passé le warm-up et les quatre forwards, puis quitté avec **code 0**. Pour C6/C5, load_state_dict strict=True ; pour ONNX, chargement de session et contrat des tenseurs vérifiés. Une nouvelle équivalence PyTorch/ONNX n'est pas revendiquée.

Fichiers de preuve : `14A8_model_availability.csv`, `14A8_excluded_runtime_evidence.json`, `14A8_worker_exits.json`, `logs/` et `models/*_runtime.json`.

## 4. Protocole gelé avant inférence

`14A8_frozen_protocol.json` et son SHA256 ont été écrits **avant** les runs GOLD. Tous les paramètres proviennent des scripts/configurations locaux historiques, référencés dans ce fichier.

{configs}

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

{global_table}

Les 165 GT sont le même dénominateur pour les huit moteurs. C6 obtient le meilleur rappel/F1 objet et les meilleurs contours de ce groupe. C3 conserve la meilleure précision objet et le plus faible nombre de FP. D est le plus rapide. Les défauts de F/H/G ne permettent aucune conclusion sur leur qualité relative : leurs résultats ne sont pas inventés.

### Robustesse aux seuils de matching

{sensitivity}

C6 reste premier à0.30/0.50/0.70. Ces scores restent faibles dans l'absolu ; le maintien du rang ne suffit pas à garantir la qualité de contours d'un produit final.

## 8. Résultats par scène

{chr(10).join(scene_sections)}

C6 est premier en F1 pour RESIDENTIAL, DENSE et DIFFICULT. Sur INDUSTRIAL, D et E sont ex æquo àF1=0.08, avec seulement1TP/23 ; C6 a0TP/23. Il n'y a pas de victoire industrielle exploitable démontrée.

## 9. Petits bâtiments

Le seuil SMALL<=50m² vient du protocole14A.7 figé avant annotation/résultats ; aucun seuil medium/large n'est inventé. Distribution des165 surfaces : minimum {f(area['min_m2'],2)}m² ; Q1 {f(area['q25_m2'],2)} ; médiane {f(area['median_m2'],2)} ; Q3 {f(area['q75_m2'],2)} ; maximum {f(area['max_m2'],2)}m². **38 bâtiments** satisfont cette classe.

{small}

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

{merge}

C6 présente14 groupes fusionnés impliquant37 GT, contre6 groupes/14GT pour C3 et1 groupe/4GT pour C. Il conserve donc davantage de fusions. Son absence de fragmentation selon cette règle ne compense pas les omissions/fusions.

## 12. CPU et mémoire

Même machine et même environnement `.venv_model_training` pour les huit workers : PyTorch2.8.0 CPU, Torchvision0.23.0, ONNX Runtime1.31.1, NumPy2.5.4. Quatre threads intra-op, un inter-op ; exécution séquentielle des moteurs. Un warm-up512 zéro est effectué et exclu du temps moyen. Aucun warm-up ne sert au choix de paramètres.

{performance}

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

{inputs}

## Annexe B — Artefacts réellement exécutés

{weights}

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
'''
 (ROOT/'docs/ETAPE_14A8_BUILDING_MODEL_SHOOTOUT.md').write_text(text,encoding='utf-8')
 print('Report written; frozen run completed; no promotion or training')
if __name__=='__main__':main()
