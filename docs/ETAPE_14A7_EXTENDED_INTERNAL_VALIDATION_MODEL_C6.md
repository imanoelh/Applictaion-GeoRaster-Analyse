# ÉTAPE 14A.7 — Extended internal validation MODEL_C3 vs MODEL_C6

Date : 9 novembre 2026. **Décision : VALIDATION_DATASET_INSUFFICIENT.** Le contrôle préalable des données échoue : aucun patch audité ne réunit GT humaine complète approuvée, indépendance du TRAIN direct/hérité et nouveauté vis-à-vis de 14A.6C. La règle STOP de la section 15 s'applique. Aucune inférence, aucun entraînement, aucune promotion n'a été lancé.

## Inventaire exécuté

Les trois racines demandées ont été lues : `backend/data/fine_tuning/buildings/`, `test-data/`, `backend/data/ground_truth/`. Inventaire : **1885 fichiers utiles**, **792 rasters TIFF lisibles / 792**, **110 enregistrements de couches/conteneurs GeoPackage**, **428 GeoJSON**, **74 patches candidats**. Les copies de diagnostics et prédictions ne sont pas de nouvelles GT.

`14A7_file_inventory.csv` donne les chemins et rôles. `14A7_source_inventory.json` donne CRS, dimensions, bandes, transforms, bounds, couches, comptes de features, erreurs et statuts. `14A7_spatial_sources.json` conserve les coordonnées natives et leur conversion en UTM 37N pour comparer les emprises dans un CRS commun. Le PROJ fourni avec Rasterio est utilisé dans le seul processus d'audit, pour éviter le `proj.db` PostGIS système incompatible ; aucune configuration système n'a été changée.

| Groupe | Données réelles | Décision d'éligibilité |
|---|---|---|
| Seed 14A.2B, 5 patches | GT manuelle approuvée, 100 features dans la référence | TRAIN/calibration C3, donc aussi exposition héritée par C6 : exclus |
| Nouveaux 14A5B | 5 patches, 85 annotations source | 4 patches effectivement entraînés par C6 ; le 5e recouvre un patch entraîné : exclus |
| Targeted 14A.3E/3E2 | Annotations de crops et hard negatives ; couverture complète non établie | Déjà utilisées dans le développement ; jamais traiter leurs zones non annotées comme fond certain |
| 13M, résidentiel/difficile | 4 patches humains, versions réparées approximatives | Recouvrent les emprises Seed C3, exposition héritée par C6 : exclus |
| 13M, industriel | 2 images, 1 feature par image, un seul site sur deux dates | Originaux NOT_REVIEWED et hors bounds ; version réparée explicitement approximative, pas de GT haute précision approuvée |
| 13R | 36 patches initiaux ; manifeste QA utilisable de 34 entrées | Labels `MODEL_C_PSEUDO_LABEL_REVIEWED`, pas GT humaine indépendante |
| VAL 14A2 | 4 RGB 512×512, deux sites sur deux années | Aucune GT humaine approuvée disponible |
| 14A_001 / 14A_003 | Référence historique 47 bâtiments | Contrôles 14A.6C uniquement ; exclus de la validation principale |
| Catalogue test-data | Templates GeoJSON d'annotation vides | Pas de GT ; plusieurs métadonnées du catalogue divergent des TIFF réels |
| Zones maxar_2025 | RGB et fichiers d'annotation vides | Pas de GT supplémentaire ; zones 1/3 = contrôle historique, zone 2 recouvre le TRAIN hérité |

## Provenance effective de C6 et fuite spatiale

Le script réel utilise `PATCHES[:-1]` : `14A2_2024_06`, `14A2_2024_10`, `14A2_2025_02`, `14A2_2025_06`, soit 16 crops 256×256. `14A2_2025_10` n'a pas été entraîné directement, mais son emprise est identique à celle de `14A2_2024_10` : il ne constitue pas une validation géographique indépendante.

C6 hérite aussi des cinq patches Seed utilisés par C3. Les `GT_2024/2025_residential_02` recouvrent à 100 % les emprises `14A2_2024/2025_13`. Les `GT_2024/2025_difficult_02` recouvrent deux emprises Seed/Targeted à 50 % chacune. Changer la date ou le nom ne supprime pas cette exposition.

Autre limite constatée dans le code C6 : le manifeste enrichi n'est pas consommé ; aucune validation interne, sélection de meilleur checkpoint ou early stopping n'est exécutée. `best_model_c6.pth` contient le dernier epoch, et l'attribut `best_epoch=2` ne prouve pas une sélection sur validation. Le présent audit corrige cette interprétation du rapport précédent sans modifier le checkpoint.

## Qualité des conteneurs et correspondance des sources

Le GeoPackage `14A5B_new_patch_expansion_gt_FIXED.gpkg` contient 85 features étiquetées VALIDATED mais son en-tête binaire est incohérent : flag 1 / enveloppe déclarée absente, alors que 32 octets d'enveloppe XY précèdent le WKB. Le lecteur conforme démarre au byte 8, au lieu du byte 40 réel ; **85/85 blobs échouent**. L'annonce antérieure d'un GeoPackage validé était donc trop large. Ce défaut est documenté dans `14A7_fixed_gt_container_diagnostic.json`, sans réparation ni changement de géométrie. Les masques déjà produits ne constituent pas de nouvelles annotations indépendantes.

Dans le catalogue `test-data/building-ground-truth`, **14/16 emprises déclarées divergent des TIFF réels**. Les emprises TIFF et les hashes de contenu sont consignés séparément ; aucune réparation ou substitution silencieuse n'a été appliquée.

## Pipeline et checkpoints figés

- C3 : `backend/data/models/model_c3_experimental/model_c3.onnx` ; 158459644 bytes ; SHA256 `2354a456b33512f6a7d20aaf9b72ee12d3d8f91a5c301e507b85ba939c47f468`.
- C6 : `backend/data/models/model_c6_experimental/best_model_c6.pth` ; 168349163 bytes ; SHA256 `7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84`.
- Pipeline de référence 14A.6C : RGB natif 512×512, min-max RGB par image, sigmoid, threshold 0.30, composantes 4-connexes, aire minimale objet 479 px, aucune morphologie, matrice IoU complète, Hungarian maximum-somme puis filtrage IoU >= 0.30.
- Le code historique calcule les métriques pixel sur le masque seuillé avant filtrage des composantes, et les métriques objet sur les composantes filtrées. Cette distinction est enregistrée ; aucun paramètre n'a été ajusté.

## Contrôle historique : références conservées, aucun nouveau run

| Référence 14A.6C uniquement | C3 | C6 |
|---|---:|---:|
| Object Recall | 0.2128 | 0.4468 |
| Object F1 | 0.2817 | 0.4773 |
| FP | 14 | 20 |
| Missed | 37 | 26 |

Ces valeurs proviennent des rapports précédents ; elles ne sont pas présentées comme une nouvelle mesure indépendante ou une reproduction exécutée pendant 14A.7. Le gain de généralisation est **non évalué**, pas rejeté. Aucun classement FP/FN visuel n'est inventé en l'absence d'inférence admissible.

## Patches existants nécessitant une annotation manuelle

Voici les huit RGB proposés, tous déjà dans un split VAL, sans GT fabriquée, sans déplacement de split et sans création de dataset. Ils ne recouvrent ni le TRAIN connu ni les deux emprises historiques après mise dans un CRS commun. Aucun fichier de split TRAIN n'est proposé. Les catégories fines (petits bâtiments, ombres, toits adjacents) doivent être confirmées lors de la revue RGB humaine. Les annotations futures doivent être réservées à l'évaluation C3/C6.

| Patch | Split existant | Scène déclarée | Travail nécessaire |
|---|---|---|---|
| `14A2_2024_03` | val | INDUSTRIAL | GT humaine complète à créer |
| `14A2_2024_07` | val | INDUSTRIAL | GT humaine complète à créer |
| `14A2_2025_03` | val | INDUSTRIAL | GT humaine complète à créer |
| `14A2_2025_07` | val | INDUSTRIAL | GT humaine complète à créer |
| `13R_industrial_005_06656_03072` | val | industrial | GT humaine complète à créer |
| `13R_industrial_011_08192_06656` | val | industrial | GT humaine complète à créer |
| `13R_industrial_017_05120_08192` | val | industrial | GT humaine complète à créer |
| `13R_industrial_023_01024_01536` | val | industrial | GT humaine complète à créer |

Les variantes 2025 des deux VAL 14A2 couvrent les mêmes sites : les huit RGB représentent six emprises distinctes, avec deux réplications temporelles. Toutes les scènes sont déclarées industrielles. Ce plan exploite les VAL existants mais ne suffit pas encore à démontrer la généralisation résidentielle/dense : il faudra préparer des RGB VAL résidentiels/denses réellement nouveaux, hors TRAIN et hors emprises historiques, puis les annoter. Aucun identifiant de nouveau patch n'est inventé dans cette étape. Les deux `GT_2024/2025_industrial_02` peuvent être revus pour une évaluation complémentaire après approbation humaine, mais leur unique bâtiment et site ne suffisent pas à eux seuls. `13R_industrial_008_03584_04096` est exclu des propositions : il recouvre une zone historique et une petite partie du TRAIN après reprojection.

## Livrables et décision

Les cinq sorties minimales demandées sont créées. Les métriques non exécutées sont vides/null avec statut `NOT_RUN_VALIDATION_DATASET_INSUFFICIENT`, jamais zéro simulé. Les overlays RGB/GT/C3/C6 ne sont pas produits : le gate STOP interdit de lancer les prédictions sur des données inadmissibles ; `14A7_overlays_manifest.json` documente cette limite. Le plan d'annotation est dans `14A7_additional_gt_required.csv`. Aucune conclusion CONFIRMED/REJECTED n'est possible sans les annotations indépendantes ; le statut d'insuffisance prévu en section 15 prévaut.

VALIDATION PATCHES :
0 executed (74 candidats audités ; 2 contrôles historiques conservés)

INDEPENDENT PATCHES :
0 avec GT humaine complète approuvée

TRAIN LEAKAGE :
0 (aucun patch exécuté)

C3 CHECKPOINT :
backend/data/models/model_c3_experimental/model_c3.onnx

C6 CHECKPOINT :
backend/data/models/model_c6_experimental/best_model_c6.pth

C3 OBJECT PRECISION :
NOT_RUN

C3 OBJECT RECALL :
NOT_RUN

C3 OBJECT F1 :
NOT_RUN

C3 FP :
NOT_RUN

C3 MISSED :
NOT_RUN

C3 PIXEL IOU :
NOT_RUN

C3 BOUNDARY F1 :
NOT_RUN

C3 CPU TIME :
NOT_RUN

C6 OBJECT PRECISION :
NOT_RUN

C6 OBJECT RECALL :
NOT_RUN

C6 OBJECT F1 :
NOT_RUN

C6 FP :
NOT_RUN

C6 MISSED :
NOT_RUN

C6 PIXEL IOU :
NOT_RUN

C6 BOUNDARY F1 :
NOT_RUN

C6 CPU TIME :
NOT_RUN

GENERALIZATION GAIN :
NOT_EVALUATED — VALIDATION_DATASET_INSUFFICIENT

FINAL DECISION :
VALIDATION_DATASET_INSUFFICIENT

PRODUCTION MODEL :
MODEL_C

NEXT STEP :
PREPARE_ADDITIONAL_VALIDATION_GT
