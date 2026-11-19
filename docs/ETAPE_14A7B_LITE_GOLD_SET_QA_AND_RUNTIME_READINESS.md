# ÉTAPE 14A.7B-LITE — QA GOLD et disponibilité runtime

## Conclusion réelle

**Étape partiellement accomplie : runtime corrigé et contrôlé ; GOLD non validable faute d'annotations persistées.** Le GeoPackage réellement référencé par le projet QGIS contient 0 feature, confirmé par SQLite et OGR, dans les quatre patches. Il n'est pas possible de déclarer ces scènes bâties correctement annotées, de générer des masques GT vides ou d'ouvrir le shootout.

Une demande a été envoyée pour enregistrer les modifications des couches QGIS, ou préciser le chemin si les annotations ont été sauvegardées ailleurs. Aucun fichier source n'a été modifié pour contourner cette absence.

## 1. Identité des quatre patches

Le manifest `14A7_gold_set/manifest/14A7_GOLD_SET_manifest.csv` et `GOLD_SET_LOCK.json` ont été lus. Sélection conservée sans ajout ni remplacement :

| patch_id | Bâtiments persistés | État |
|---|---:|---|
| 14A7_VAL_2025_RESIDENTIAL_02 | 0 | ANNOTATIONS_NOT_PERSISTED |
| 14A7_VAL_2025_DENSE_04 | 0 | ANNOTATIONS_NOT_PERSISTED |
| 14A7_VAL_2025_INDUSTRIAL_10 | 0 | ANNOTATIONS_NOT_PERSISTED |
| 14A7_VAL_2025_DIFFICULT_11 | 0 | ANNOTATIONS_NOT_PERSISTED |

GOLD_SET_LOCKED=YES pour la sélection et les exclusions d'usage déjà définies. Nouvelle vérification des hashes RGB et des emprises face aux 136 zones historiques protégées, avec marge de 20 m : TRAIN leakage 0. Cette indépendance est spatiale interne ; la même grande orthophoto/acquisition reste partagée avec certains anciens crops. Aucune nouvelle indépendance externe n'est revendiquée.

## 2. Source GT effectivement utilisée

Le `.qgz` a été ouvert comme archive et son XML de couches lu : les quatre vues filtrées et la table canonique pointent toutes vers :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set/gt/14A7_GOLD_manual_gt.gpkg`

Table `buildings_gt`, Polygon, EPSG:32637. Les filtres patch_id correspondent aux quatre IDs attendus.

- SQLite integrity_check : ok.
- Feature count SQLite : 0.
- Feature count OGR : 0.
- Dernier changement stocké dans gpkg_contents : 2026-11-09T10:05:39.268Z. Cette valeur de métadonnée n'est pas une preuve d'annotation humaine.
- SHA256 avant/après QA : `82bc3e6edc105e9c15654a79862e3f4baf633263f5fbb70db723523f80c4436e`, inchangé.
- WAL de ce fichier observé vide au contrôle initial ; aucune annotation n'a été récupérée en interprétant un fichier vide comme vérité terrain.

La GT alternative du projet à quatorze patches n'est pas substituée à cette source. Les anciens jeux TRAIN ne sont pas réutilisés. Un projet QGIS sauvegardé n'implique pas que ses modifications de couche ont été enregistrées ; la présence éventuelle de dessins en mémoire dans une fenêtre QGIS n'a pas été assimilée à des features persistées.

## 3. QA géométrique, spatiale et attributaire

Les contrôles exécutables sont dans `scripts/qa_14A7B_gold_set.py`. Ils lisent la source sans la modifier, vérifient l'emprise réelle du raster avec bords densifiés transformés en UTM, les géométries et leurs attributs.

| Contrôle | Compte observé |
|---|---:|
| Features | 0 |
| Géométries invalides | 0 |
| Null geometry | 0 |
| Empty geometry | 0 |
| Zero area | 0 |
| Self-intersection | 0 |
| Doublons géométriques exacts normalisés | 0 |
| Multipart/type incohérent | 0 |
| OOB | 0 |
| Wrong patch assignment | 0 |
| Cross-patch geometry | 0 |
| Erreurs attributaires | 0 |

**Ces zéros concernent un ensemble vide : ils ne constituent pas une validation des annotations.** Les champs patch_id/building_id/scene_type/source/review_status sont présents, mais aucune feature ne permet d'en confirmer les valeurs ou l'unicité. source=MANUAL ne peut donc pas être confirmé pour des bâtiments inexistants dans le fichier.

Aucune géométrie IA n'a été injectée. Aucune géométrie n'a été ajoutée, réparée, supprimée ou déplacée. Aucun fichier FIXED n'est créé : l'absence d'annotations n'est pas un défaut de géométrie réparable automatiquement. L'origine manuelle ne serait de toute façon pas prouvée par la seule valeur d'un attribut.

Preuves :

- `14A7_gold_set/qa/14A7B_gold/gold_gt_qa.json`.
- `features_qa.csv` : en-tête et 0 ligne feature.
- `patches_qa.csv` : les quatre patches explicitement en attente.
- `alignment_qa.csv` : en-tête seul, aucun faux PASS.

## 4. Masques, alignement et planche

Les quatre RGB ont été ouverts : 512×512, trois bandes, hashes conformes. Les RGB natifs sont EPSG:4326 et la GT est EPSG:32637 ; la future rasterisation transformera les polygones dans le CRS natif et reprendra exactement transform, dimensions, résolution et bounds de chaque RGB, sans rééchantillonnage de l'image.

Mais le gate QA complet échoue aujourd'hui sur l'absence de bâtiments. Par conséquent :

- Masques GT générés : **0/4**.
- Alignement RGB/masque : **NOT_RUN**, pas de PASS revendiqué.
- Aucun masque de prédiction C6 n'a servi de substitution.
- `qa/14A7B_gold/14A7B_HUMAN_GT_CONTACT_SHEET.png` est une **planche de diagnostic**, avec RGB, panneau GT vide et mention MASK NOT GENERATED. Elle n'est pas une référence humaine validée et n'affiche aucune prédiction de modèle.

## 5. Verrouillage

Le verrou de sélection reste YES : les mêmes quatre IDs demeurent interdits à l'entraînement, fine-tuning, pseudo-label training, calibration et réglage d'hyperparamètres. Le garde-fou spatial existant est conservé.

Le verrou définitif des **annotations validées et masques hashés** n'est pas créé. `GOLD_VALIDATED_ANNOTATION_LOCK.json` ne doit apparaître qu'après QA PASS sur les annotations réellement persistées. Les anciens manifests ne sont pas marqués VALIDATED. GOLD SET READY=NO.

## 6. Audit runtime en lecture seule

Environnement : `.venv_model_training/Scripts/python.exe`, Python 3.12, PyTorch CPU 2.8.0, Torchvision CPU 0.23.0 et ONNX Runtime local. Les probes n'ont chargé aucun checkpoint et n'ont lu aucune image GOLD.

| Probe | Exit code | Stade |
|---|---:|---|
| torch seul | 0 | NORMAL_EXIT |
| rasterio seul | 0 | NORMAL_EXIT |
| onnxruntime seul | 0 | NORMAL_EXIT |
| torch puis rasterio | 0 | NORMAL_EXIT |
| torchvision normal | 0 | NORMAL_EXIT |
| torch + rasterio + registration manuelle globale nms/qnms | 3221225477 / 0xC0000005 | SHUTDOWN |
| Même registration dans une fonction | 3221225477 / 0xC0000005 | SHUTDOWN |
| Torch + ONNX Runtime, informations des thread pools | 0 | NORMAL_EXIT |

Les deux probes défaillants atteignent **BODY_COMPLETED** avant le crash. L'échec se produit donc lors de la terminaison native, pas pendant un forward ou l'écriture d'un fichier.

**RUNTIME_FAILURE_STAGE :** Python/native shutdown après le corps du programme.

**EXIT_CODE :** 3221225477, représentation signée -1073741819, Windows access violation 0xC0000005.

**MODEL CONCERNED :** aucun poids intrinsèquement identifié comme défectueux. Le code de compatibilité utilisé par le runner C6 et certaines anciennes utilités C3/C6 est le déclencheur isolé ; les imports ONNX seuls n'échouent pas.

**REPRODUCIBLE :** YES, deux variantes minimales avec registration manuelle échouent ; les variantes normales quittent avec 0.

**ROOT_CAUSE confirmée au niveau du déclencheur :** création inutile d'un `torch.library.Library('torchvision','DEF')` et définition manuelle de nms/qnms dans cet environnement qui dispose déjà de ses opérateurs natifs. Le retrait de cette couche de compatibilité supprime le crash. La destruction/désinscription native de cette Library à la fermeture est l'explication probable du mécanisme ; aucun stack trace natif symbolisé ne permet de prétendre avoir identifié la ligne C++ exacte.

Les probes normaux torch/rasterio, ONNX et informations OpenMP/MKL ne montrent pas le défaut. Aucun multiprocessing n'est utilisé dans le smoke. Les handles raster sont fermés par contexte, les sessions/modèles sont libérés explicitement, le fichier de sortie est rouvert et vérifié. Il n'est pas justifié de réinstaller PyTorch/GDAL, de changer les thread pools globalement ou de modifier la production.

Preuves : `qa/14A7B_runtime/import_shutdown_probes.json`.

## 7. Correction minimale et non-régression

Seul le code d'enregistrement manuel des opérateurs a été retiré dans :

- `scripts/prepare_14A7_lite_gold_set.py`.
- `scripts/train_model_c6_14A6.py`.
- `scripts/benchmark_14A6B_c3_vs_c6.py`.

Ces scripts utilisent désormais l'import normal de Torchvision et la durée de vie des opérateurs gérée par le module. Aucun script d'entraînement ou de benchmark n'a été exécuté pour cette vérification. Les deux fichiers historiques ont uniquement changé en tête de module ; les fonctions d'architecture, preprocessing, seuils, postprocessing et métriques ont des AST hashés identiques avant/après : `math_functions_unchanged.json`.

Les poids n'ont pas été modifiés. Aucun changement d'architecture, seuil, normalisation, post-traitement, métrique ou modèle production. Aucun changement backend/API/frontend/GEE/export/registry.

## 8. Smoke test hors GOLD après correction

- Trois nouveaux processus d'import normal Torch/Torchvision/rasterio : **3/3 exit code 0**.
- Fixture non-GOLD : `14A7_VAL_2025_RESIDENTIAL_01`, hash vérifié et image inchangée.
- Opérateur natif Torchvision nms sur tenseurs vides : PASS.
- Instanciation/libération d'un DeepLab sans poids préentraînés : PASS, sans forward C3/C6.
- Fixture PyTorch Conv2d déterministe sur ce RGB, sortie comparée à la moyenne des trois canaux : PASS.
- Une session ONNX MODEL_C sur le même patch non-GOLD : PASS ; sortie finie, poids inchangés ; aucune métrique de qualité calculée.
- Modèles/sessions supprimés, fichiers raster fermés, sortie NPZ relue : PASS.
- Processus terminé normalement, code **0**, stderr vide, aucun processus enfant lancé par le worker, processus worker attendu et terminé : PASS.
- Durée du worker complet : 24,62 s ; pas une mesure de performance comparative.
- Inférence C3 : NOT_RUN. Inférence C6 : NOT_RUN. Inférence GOLD : NOT_RUN. Training : NOT_RUN. Shootout : NOT_RUN.

Preuves : `qa/14A7B_runtime/fixed_runtime_smoke.json`, `smoke_fixture_outputs.npz`. Le défaut de fermeture identifié est **RESOLVED dans l'environnement local audité** ; ce résultat n'est pas une garantie pour un autre environnement ni un strict-load de tous les candidats F/D/H.

## 9. Reprise exacte

Enregistrer les **modifications des couches**, et pas uniquement le projet QGIS. Si les annotations sont dans un autre GeoPackage, fournir son chemin pour vérifier la provenance sans substituer arbitrairement la source. Rejouer ensuite la QA sur les mêmes quatre IDs, traiter d'éventuelles anomalies uniquement dans une copie, générer les quatre masques puis leurs hashes et le verrou final.

Le prochain benchmark prévu reste 14A8, mais il est bloqué tant que le GOLD n'est pas validé. Il ne faut ni réannoter les dix autres patches, ni réentraîner, ni lancer le shootout maintenant.

GOLD PATCHES :
4

GT BUILDINGS :
0 persisté

INVALID :
0 sur 0 géométrie — annotations absentes

OOB :
0 sur 0 géométrie — annotations absentes

DUPLICATES :
0

ATTRIBUTE ERRORS :
0 sur 0 feature — non validable

MASKS :
0 / 4

RGB MASK ALIGNMENT :
FAIL — NOT_RUN, masques non générés

TRAIN LEAKAGE :
0

GOLD SET LOCKED :
YES — sélection ; verrou des annotations validées en attente

RUNTIME ML ISSUE :
RESOLVED

RUNTIME SMOKE TEST :
PASS

GOLD SET READY :
NO

MODEL SHOOTOUT READY :
NO

NEXT STEP :
14A8_BUILDING_MODEL_SHOOTOUT — BLOQUÉ : enregistrer les annotations puis terminer 14A.7B-LITE
