# ÉTAPE 14A.7B-LITE FINAL — QA, masques et verrou GOLD

## Résultat

**GOLD validé : 4/4 patches, 165 bâtiments humains, 4/4 masques alignés.** Aucun entraînement, aucune inférence modèle et aucun benchmark n'ont été exécutés. MODEL_C et la production restent inchangés. Le runtime PASS est celui du smoke déjà réalisé à l'étape précédente ; il n'a pas été relancé.

La QA a nécessité une copie corrigée. La GT originale, ses attributs, géométries et WAL sont conservés exactement. Le projet QGIS et les manifests pointent désormais vers la copie finale figée, et non vers la source originale présentant les erreurs.

## 1. Persistance et identité

Le projet `qgis/14A7_GOLD_SET_MANUAL_4.qgz` a été inspecté pour identifier ses sources réelles. Source humaine initiale :

`gt/14A7_GOLD_manual_gt.gpkg`, table buildings_gt, EPSG:32637.

SQLite et OGR confirment **165 features persistées**, y compris celles du journal WAL. Les quatre IDs sont ceux du manifest verrouillé, sans remplacement ni nouveau patch :

| Patch | FEATURES | INVALID final | EMPTY | DUPLICATE | OOB final | ATTRIBUTE_ERROR |
|---|---:|---:|---:|---:|---:|---:|
| 14A7_VAL_2025_RESIDENTIAL_02 | 40 | 0 | 0 | 0 | 0 | 0 |
| 14A7_VAL_2025_DENSE_04 | 94 | 0 | 0 | 0 | 0 | 0 |
| 14A7_VAL_2025_INDUSTRIAL_10 | 23 | 0 | 0 | 0 | 0 | 0 |
| 14A7_VAL_2025_DIFFICULT_11 | 8 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **165** | **0** | **0** | **0** | **0** | **0** |

Les quatre rasters natifs 512×512, trois bandes, ont des SHA256 conformes au manifest de sélection. Aucun RGB n'a été modifié.

## 2. QA initiale et corrections contrôlées

La première lecture de la GT originale a détecté :

- 4 géométries invalides, toutes par auto-intersection : FID 124, 125, 129 et 151.
- 22 géométries légèrement hors emprise : 7 sur RESIDENTIAL et 15 sur DENSE.
- 0 géométrie nulle, vide ou de surface nulle.
- 0 doublon géométrique exact, 0 erreur d'attribut, 0 mauvaise affectation de patch, 0 géométrie traversant deux patches.

Les preuves initiales sont conservées dans `qa/14A7B_gold/original_gt_qa.json`, `original_features_qa.csv` et `repair_feasibility.json`.

Seule la copie suivante a été corrigée :

`gt/14A7_GOLD_SET_GT_FIXED.gpkg`

La copie initiale est une sauvegarde SQLite transactionnelle en lecture seule de la source, **incluant les 165 features du WAL**. Une simple copie du fichier principal aurait été insuffisante : son SHA256 était resté identique à celui du fichier vide alors que les annotations étaient dans le WAL.

Corrections :

| Opération | Nombre | Politique |
|---|---:|---|
| Clip strict | 22 | Intersection avec l'emprise réelle du RGB, projetée en UTM avec bords densifiés ; aucun déplacement ou lissage |
| MakeValid | 4 | Réparation des seuls polygones auto-intersectés ; toutes les parties polygonales conservées sous le même building_id |
| Ajout de bâtiment | 0 | Interdit et non effectué |
| Suppression de bâtiment | 0 | Aucun objet supprimé |
| Suppression de doublon | 0 | Aucun doublon trouvé |

Le dépassement maximal est de 0,3905 m ; la perte de surface maximale après clip est de 1,5823 %. Les quatre MakeValid changent la surface de moins de 0,5 %. Les petites lobes issues des intersections sont conservées, même sous le pixel : aucune suppression ambiguë automatique.

Le résultat comprend **161 Polygon et 4 MultiPolygon valides**. Chaque MultiPolygon demeure une seule feature avec le building_id humain d'origine ; il ne doit pas être compté comme plusieurs bâtiments au futur benchmark. Le schéma GeoPackage autorise ces géométries polygonales mixtes, sans convertir les 139 géométries non ciblées.

**139/139 géométries non ciblées conservent leur WKB exact. Les 165 FID, building_id et tous les attributs sont inchangés.** La source originale conserve son hash logique des features, son hash du fichier principal et celui de son WAL.

Trace détaillée : `qa/14A7B_gold/controlled_copy_repairs.json` et `.csv`, avec FID, building_id, action, surfaces et WKB avant/après. Les changements sont mécaniques et autorisés ; ils ne prétendent pas améliorer sémantiquement le dessin des toits.

## 3. QA finale complète

Sur la copie corrigée :

| Contrôle | Compte |
|---|---:|
| Features | 165 |
| Invalid geometry | 0 |
| Null geometry | 0 |
| Empty geometry | 0 |
| Zero area | 0 |
| Self-intersection | 0 |
| Exact duplicate geometry | 0 |
| Multipart incohérent / type non polygonal | 0 |
| OOB | 0 |
| Wrong patch assignment | 0 |
| Cross-patch geometry | 0 |
| Erreurs attributaires | 0 |

Les building_id sont non vides et globalement uniques. Les patch_id et scene_type correspondent aux quatre patches verrouillés. source=MANUAL sur les 165 features ; aucune source AI_PREANNOTATION n'est acceptée. Le champ review_status initial UNREVIEWED est conservé pour ne pas réécrire les attributs humains ; le résultat de la présente QA et le statut VALIDATED sont portés explicitement dans le manifest et le verrou final.

L'emprise de contrôle est le footprint réel du RGB, pas simplement sa bounding box rectangulaire en UTM. Tolérance numérique de couverture : 1 micromètre en coordonnées UTM. La validité technique et les attributs ne constituent pas à eux seuls une preuve indépendante de l'auteur humain ; l'origine MANUAL est cohérente avec les données et le workflow, aucune prédiction n'a été injectée par cette étape.

Résultats : `qa/14A7B_gold/gold_gt_qa.json`, `features_qa.csv`, `14A7B_FINAL_PER_PATCH_QA.csv`.

## 4. Quatre masques GT exacts

Dossier demandé : `14A7_gold_set/gt_masks/`.

Un GeoTIFF binaire par patch, noms identiques aux patch_id. Aucun rééchantillonnage des RGB. La GT UTM est transformée vers le CRS natif du raster avant rasterisation, avec la grille source exacte et la règle de centre de pixel (ALL_TOUCHED=FALSE).

| Patch | Dimensions | CRS égal RGB | Transform égal RGB | Extent/résolution égaux | Valeurs | Building pixels | Alignement |
|---|---|---|---|---|---|---:|---|
| RESIDENTIAL_02 | 512×512 | PASS | PASS | PASS | {0,1} | 54 110 | PASS |
| DENSE_04 | 512×512 | PASS | PASS | PASS | {0,1} | 98 663 | PASS |
| INDUSTRIAL_10 | 512×512 | PASS | PASS | PASS | {0,1} | 12 807 | PASS |
| DIFFICULT_11 | 512×512 | PASS | PASS | PASS | {0,1} | 14 450 | PASS |

RGB et masques sont nativement en EPSG:4326 ; la GT et le projet restent EPSG:32637. Cette différence entre le vecteur et l'image est traitée par transformation des polygones, sans déplacer la grille image. Tous les masques ont été rouverts, contrôlés et hashés.

Table détaillée : `qa/14A7B_gold/alignment_qa.csv`. Les SHA256 RGB, GT et masques sont enregistrés dans le manifest final.

## 5. QA visuelle humaine

Planche créée et inspectée :

`qa/14A7B_gold/14A7B_HUMAN_GT_CONTACT_SHEET.png`

Chaque ligne montre RGB, contours GT humains et masque GT correspondant. Les contours et masques sont visuellement superposés aux mêmes bâtiments, sans décalage global visible. Aucune prédiction modèle n'y figure. Ce contrôle ne prétend pas certifier une précision de toit subpixel ou une exhaustivité humaine parfaite.

## 6. Scellement et référence canonique

**GT canonique :** `gt/14A7_GOLD_SET_GT_FIXED.gpkg`, table buildings_gt.

SHA256 final : `a0acdb604e6a89cf517845ab9d19f33dd712e38c6949d7fec14ceac2360e6724`.

La copie finale est autonome, sans dépendance à un WAL actif, protégée en lecture seule. Le projet QGIS existant est conservé et ses cinq vues GT pointent vers cette copie avec l'option GDAL IMMUTABLE=YES et le mode lecture seule des couches. Les quatre RGB et les groupes sont conservés.

Le projet a été relu avec **PyQGIS 3.40.14** : 9 couches valides, 0 source cassée, vues GT 40/94/23/8 et table canonique 165 ; les cinq couches GT sont en lecture seule. Le hash du GPKG reste identique après réouverture. Aucun nouveau test Desktop interactif n'est revendiqué à cette étape.

Lors du premier scellement, les providers QGIS ont mis à jour des métadonnées internes du conteneur. Le checksum a donc été calculé définitivement après fermeture/normalisation du conteneur et protection en lecture seule ; aucun changement de géométrie ou d'attribut n'en résulte. Le manifest ne retient pas le checksum intermédiaire.

Manifest CSV mis à jour : `manifest/14A7_GOLD_SET_manifest.csv`.

Verrous : `manifest/GOLD_SET_LOCK.json` et `GOLD_VALIDATED_ANNOTATION_LOCK.json`.

Pour les quatre patches :

- GOLD_SET_LOCKED=YES ; manual_gt_status=VALIDATED ; qa_status=PASS.
- FORBIDDEN_FOR_TRAINING=YES.
- FORBIDDEN_FOR_FINE_TUNING=YES.
- FORBIDDEN_FOR_THRESHOLD_CALIBRATION=YES.
- FORBIDDEN_FOR_PSEUDO_LABEL_TRAINING=YES.
- FORBIDDEN_FOR_HYPERPARAMETER_TUNING=YES.
- Seuls usages permis : BENCHMARK, VALIDATION, MODEL COMPARISON.

Le garde-fou de provenance et d'emprise existant reste applicable aux futurs consommateurs. Ce contrat et la protection de la copie ne remplacent pas l'obligation pour les futurs scripts de respecter le verrou.

## 7. Runtime, fuite et arrêt

Le smoke runtime précédent est lu, non réexécuté : `qa/14A7B_runtime/fixed_runtime_smoke.json`, passed=true, processus normal code 0. La correction de cycle de vie précédente reste en place ; aucun import/inférence ML supplémentaire dans cette étape.

Les quatre patches restent spatialement disjoints des crops historiques protégés et exclus du TRAIN. Même acquisition Maxar partagée : il s'agit d'un GOLD interne fixe, pas d'une validation externe par acquisition. Aucun résultat de modèle n'a guidé la réparation géométrique, la sélection ou le verrouillage.

État exploitable : `qa/14A7B_READINESS.json` et `qa/14A7B_gold/FINAL_READINESS.json`.

**STOP avant 14A8 : aucun shootout, aucune inférence et aucun entraînement n'ont été lancés.** Réouvrir le projet existant pour consulter la copie finale en lecture seule. Toute future correction du GOLD devra faire l'objet d'une nouvelle version explicite et d'une nouvelle QA, jamais d'une modification silencieuse de cette référence.

GOLD PATCHES :
4

GT BUILDINGS :
165

INVALID :
0

OOB :
0

DUPLICATES :
0

ATTRIBUTE ERRORS :
0

VALID PATCHES :
4 / 4

MASKS READY :
4 / 4

RGB MASK ALIGNMENT :
PASS

TRAIN LEAKAGE :
0

GOLD SET LOCKED :
YES

RUNTIME ML :
PASS

GOLD SET READY :
YES

MODEL SHOOTOUT READY :
YES

NEXT STEP :
14A8_BUILDING_MODEL_SHOOTOUT
