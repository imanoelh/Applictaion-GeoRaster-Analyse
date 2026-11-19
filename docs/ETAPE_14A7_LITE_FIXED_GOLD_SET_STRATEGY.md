# ÉTAPE 14A.7-LITE — Fixed Gold Set + validation assistée

## Décision et périmètre

L'annotation complète des 14 patches n'est plus demandée. Quatre patches fixes constituent le GOLD final ; les dix autres deviennent une réserve de correction assistée. MODEL_C reste production. Aucun entraînement, fine-tuning, benchmark GOLD ou modification API/frontend/export/GEE/indices/classification/cache/offline.

Livrables : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set/` avec `manifest/`, `qgis/`, `gt/`, `qa/` et un sous-dossier séparé `ai_assisted/`.

## 1. Sélection fixe avant toute annotation

| Strate | Patch GOLD | Justification |
|---|---|---|
| Résidentiel / petits bâtiments | 14A7_VAL_2025_RESIDENTIAL_02 | Petits bâtiments, formes variées, voirie et parcelles ouvertes |
| Urbain dense | 14A7_VAL_2025_DENSE_04 | Petits toits adjacents, tissu irrégulier, ombres |
| Industriel | 14A7_VAL_2025_INDUSTRIAL_10 | Toitures complexes, compound/dépôt, stockage et véhicules à exclure ; classe visuelle indicative |
| Difficile | 14A7_VAL_2025_DIFFICULT_11 | Sol nu, faible contraste et bâtiments coupés par le bord |

Sélection automatique déterministe sur les catégories/tags visuels de l'audit 14A.7A : scores par strate, égalités départagées par patch_id. Les poids et le classement complet sont enregistrés dans `qa/selection_ranking.json`. Aucun score de modèle ou résultat GOLD n'a guidé cette sélection. La planche `qa/GOLD_4_RGB.png` permet de voir les quatre scènes.

Manifeste : `manifest/14A7_GOLD_SET_manifest.csv`. Lock : `manifest/GOLD_SET_LOCK.json`, GOLD_SET_LOCKED=YES, hashes RGB et emprises conservés. Les quatre patches étaient déjà exclus de tous les TRAIN historiques audités. Nouvelle vérification contre les 136 emprises protégées avec marge de 20 m : aucun recouvrement. Aucun recouvrement entre patches GOLD ou avec les crops C6 connus.

**Limite d'indépendance :** ces patches partagent la grande orthophoto et l'acquisition Maxar 2025 avec certains crops historiques. C'est un holdout spatial interne, pas une validation externe par acquisition. Quatre patches assurent un contrôle stable et peu coûteux, mais pas une preuve de généralisation universelle. La strate industrielle est une description visuelle, pas un usage foncier certifié.

## 2. Verrouillage et protection contre les fuites

Interdits pour les quatre patches : training, fine-tuning, pseudo-label training, calibration de seuil et réglage d'hyperparamètres. Usage autorisé : benchmark final avec configurations gelées avant lecture des résultats.

`scripts/gold_set_14A7_guard.py` fournit un garde-fou hors production pour les futurs consommateurs : refus des IDs GOLD, des hashes identiques et des emprises recouvrantes, même après renommage. Les entrées sans provenance sont refusées. Vérifications exécutées : les dix autres patches sont acceptés ; GOLD par ID et GOLD renommé par emprise sont refusés.

Ce verrou est un contrat de données accompagné d'un garde-fou réutilisable : il n'intercepte pas automatiquement tous les anciens scripts. Toute future préparation TRAIN/calibration/active-learning doit l'appeler et enregistrer son résultat. La production et les anciens scripts de training n'ont pas été modifiés.

Ne pas transformer les erreurs GOLD en exemples de fine-tuning. Le minage d'erreurs et le réglage des paramètres doivent utiliser les scènes hors GOLD. Conserver un journal des évaluations ; multiplier les choix guidés par ce petit holdout réduirait son indépendance.

## 3. Projet QGIS manuel : quatre patches seulement

Ouvrir directement `qgis/14A7_GOLD_SET_MANUAL_4.qgz`.

- 4 RGB natifs 512×512, 4 vues GT filtrées et 1 table GT canonique : 9 couches.
- `gt/14A7_GOLD_manual_gt.gpkg`, table buildings_gt, Polygon EPSG:32637, **0 feature**.
- Champs patch_id, building_id, scene_type, source et review_status ; valeurs MANUAL/UNREVIEWED, UUID et identifiants de patch préremplis.
- Contours verts transparents, labels patch_id, groupes et 4 signets. Première paire visible au démarrage.
- RGB natifs EPSG:4326 conservés, affichage QGIS en EPSG:32637 ; aucun rééchantillonnage des fichiers.
- Création avec l'API QGIS 3.40.14 et les réglages du projet fonctionnel 14A5A.
- Contrôles providers, édition sans modification, sauvegarde, deux relectures PASS. Test de persistance d'une feature uniquement dans une copie temporaire PASS ; GT réelle vide.
- **Test réel QGIS Desktop 3.40.14-Bratislava : ouverture PASS, sauvegarde PASS, réouverture PASS, édition sans modification PASS, 0 source cassée, 4 RGB.** Cycle de contrôle 17,14 s ; `qa/gold_desktop_qa.json`. Le canvas `qa/gold_desktop_canvas.png` a été inspecté : le RGB résidentiel s'affiche correctement.

Le premier contrôle Desktop a rencontré un estimateur featureCount=-1 sur une vue filtrée non encore comptée. Le contrôle final vérifie également l'itération réelle des features ; après réouverture, les cinq vues/table retournent estimate=0 et actual=0. Aucun bâtiment n'a été ajouté au GOLD.

Les messages GDAL d'agrégation d'emprise sur les tables initialement vides ont été consignés pendant la construction ; les lectures, édition, intégrité SQLite, sauvegarde et réouverture finales sont contrôlées séparément. Aucun blocage d'ouverture final observé.

Le projet historique à 14 patches est conservé avec ses sources et ses couches, mais son titre/rôle devient SCENE_RESERVE_NOT_FULL_MANUAL_QUEUE. Sa notice indique explicitement de n'annoter que les quatre GOLD. Aucun ancien RGB ou Ground Truth n'est supprimé.

Notice utilisateur : `README_MANUAL_GOLD_ONLY.md`. Éditer et sauvegarder une seule vue GT à la fois. Les masques GT GOLD seront générés seulement après annotation, QA géométrique et approbation humaine.

## 4. Dix autres patches : propositions IA séparées

`manifest/AI_ASSISTED_POOL.json` contient exactement les dix patches hors GOLD. Ils ne sont plus une file d'annotation manuelle exhaustive et ne deviennent pas automatiquement TRAIN.

Une passe C6 a produit **91 propositions** sur ces dix patches, sans prédiction sur le GOLD. Strict load PASS ; checkpoint inchangé. Prétraitement identique à 14A.6C : min-max RGB par patch, sigmoid, seuil 0,30, composantes 4-connexes de 479 pixels minimum, sans morphologie. Ce filtre est hérité, sans optimisation sur les nouvelles scènes ; il peut supprimer de petits bâtiments que l'humain devra ajouter.

Fichiers séparés :

- `ai_assisted/AI_PREANNOTATION.geojson` : export brut archivé, aucune prétention de GT.
- `ai_assisted/AI_PREANNOTATION.gpkg`, couche AI_PREANNOTATION : copie de revue éditable, en EPSG:32637, source MODEL_C6_PREDICTION, review_status UNREVIEWED, is_ground_truth=0.
- `ai_assisted/probability/`, `masks/`, `overlays/` : résultats IA seulement, pas des masques GT.
- `ai_assisted/HUMAN_CORRECTION_REVIEW.gpkg` : cible humaine séparée, initialement vide.
- `qgis/14A7_AI_ASSISTED_REVIEW.qgz` : dix groupes, RGB + propositions violettes + cibles humaines vertes ; providers et sauvegarde/réouverture PyQGIS PASS. Pas de validation Desktop revendiquée pour ce second projet.
- `qa/AI_ASSISTED_10_CONTACT_SHEET.png` pour une revue rapide.

QA des dix probability maps et masques : dimensions 512×512, valeurs finies, probabilités dans [0,1], masques binaires {0,1}, CRS/transform/bounds exacts des RGB. Les géométries des propositions ont un contrôle séparé dans `qa/final_delivery_qa.json` ; une proposition ne devient jamais GT par son seul passage en QA technique.

Temps mesuré CPU quatre threads : **7,306 s/patch en moyenne**, chargement 2,096 s, hors polygonisation/écritures. Ce n'est pas une comparaison équitable entre modèles ni une estimation garantie sur une autre machine.

**Anomalie runtime à conserver visible :** les dix forwards et tous les fichiers ont été produits, mais le processus ML termine anormalement à la fermeture. Un probe minimal torch+rasterio+torchvision reproduit une access violation Windows (-1073741819). Les sorties sont contrôlées indépendamment ; le runtime n'est pas déclaré entièrement stable. Aucun correctif global de l'environnement n'a été tenté dans cette étape. Ce défaut doit être résolu avant un shootout reproductible.

Aucune préannotation n'a été copiée dans le GOLD ou déclarée humaine validée. Aucun masque GT n'a été créé.

## 5. Audit local des modèles disponibles

`manifest/14A8_model_candidates.csv` fournit architecture, dataset, spécialisation bâtiment, résolution, CPU, licence déclarée, poids/ONNX et disponibilité des modules. `qa/local_model_artifacts.json` conserve les chemins, tailles et SHA256.

| Modèle | Spécialisation et données | État local pour 14A8 |
|---|---|---|
| MODEL_C | DeepLabV3 ResNet50, SpaceNet2 | Poids + ONNX présents ; production inchangée |
| MODEL_C3 | Même architecture, transfert sur Seed GT local | Poids + ONNX présents ; référence expérimentale |
| MODEL_C6 | Même architecture, C3 + quatre patches 14A5B | Poids présents ; strict load et dix forwards exécutés ; anomalie de fermeture du processus |
| MODEL_D | U-Net++ EfficientNetB4, WHU Building | Poids + ONNX présents ; voie ONNX CPU candidate, à revalider sur protocole gelé |
| MODEL_F | SegFormer B0/MiT-B0, SpaceNet2 Paris | Poids présents ; transformers absent dans .venv_model_training ; chargement actuel non revendiqué |
| MODEL_H | U-Net ResNet34, tête instance 3 canaux, HOTOSM VHR | Poids présents ; SMP absent dans cet environnement ; licence AGPL historique et sémantique des canaux à contrôler |
| MODEL_G | DINOv3-S + UPerNet, HOTOSM | ONNX présent ; absence de PTH sans importance pour cette voie ; canal bâtiment historiquement ambigu, exclure tant que non résolu |
| MODEL_F2 | SegFormer transféré sur 13R1B | Poids présents ; dépendance transformers absente ; considérer séparément du F original |
| MODEL_A, C2, C4, C5 | Références historiques / variantes locales | Artefacts inventoriés ; candidats secondaires, aucun nouveau test de qualité |

Les déclarations MIT (C/F), Apache-2.0 (D), AGPL-3.0 (H) proviennent du code/documentation locale ; aucune nouvelle validation juridique ni reconsultation amont n'est revendiquée. Les licences inconnues restent UNKNOWN/NOT_RECONFIRMED. La disponibilité d'un fichier ou module ne vaut pas un strict load réussi. Aucun poids n'a été téléchargé, exporté, modifié ou réentraîné.

Les vitesses non mesurées restent NOT_MEASURED. Le CSV distingue le temps C6 mesuré ici du temps C3 historique de 4,310 s/512 ; ces chiffres ne servent pas à classer les moteurs.

## 6. Protocole 14A8 préparé, benchmark non lancé

`manifest/14A8_SHOOTOUT_PROTOCOL.json` définit les contrôles et métriques avant annotation :

- Object Precision/Recall/F1, FP, Missed Buildings, IoU pixel, Dice, Boundary F1, Small Building Recall et CPU time.
- GT objets issue des features humaines, pas d'une fusion des bâtiments adjacents par composantes de masque.
- Matrice complète d'IoU polygonale, matching strict un-à-un, maximisation du nombre de correspondances admissibles puis de l'IoU ; seuils 0,30/0,50/0,70. Aucun polygone fusionné compté plusieurs fois comme TP.
- Petits bâtiments : surface GT visible <=50 m² en EPSG:32637, règle prédéclarée avec effectifs publiés.
- Boundary F1 : précision et rappel de contour puis moyenne harmonique, dilatation bornée sans wrap aux bords, assertions [0,1]. Ne pas réimporter aveuglément les anciennes fonctions de métriques : certaines formules archivées nécessitent cette revalidation.
- Configurations/checkpoints/prétraitements/post-traitements hashés avant le run ; aucun sweep sur GOLD. Même RGB pour tous les moteurs ; respect du prétraitement spécifique de chaque modèle.
- Temps de chargement, warm-up, forward/512, pipeline complet et mémoire séparés, nombre de threads/engine/versions enregistré.
- Décision multi-critères : rappel et bâtiments manqués, FP, F1 objet, contours, petits bâtiments et CPU. Pas de remplacement fondé sur IoU seul.

La priorité A→F demandée est retenue : annoter/QA les quatre GOLD une seule fois ; benchmark des moteurs reproductibles ; choix explicite ; analyse d'erreurs sur données hors GOLD ; correction assistée ciblée ; fine-tuning utile seulement ; re-test final GOLD avec configuration gelée. Le GOLD n'est jamais un pool de correction pour l'entraînement.

## 7. Pipeline assisté futur et Active Learning

Contrat préparé : RGB + provenance → garde-fou GOLD → prédiction du moteur choisi → polygones AI_PREANNOTATION → copie de revue QGIS → DELETE/EDIT/ADD humains → QA géométrique/alignement → approbation humaine → promotion vers GT validée → split géographique indépendant → éventuel entraînement. La promotion automatique en GT ou le fine-tuning ne sont pas implémentés/exécutés ici.

Prioriser les candidats hors GOLD selon incertitude calibrée sur données de développement, désaccord entre moteurs, petits objets manqués après revue humaine, FP importants, fusions/fragmentations, routes/sol nu et ombres. Une incertitude ou un désaccord n'est pas une mesure de vérité. Dédupliquer les emprises, limiter la quantité par catégorie et consigner le coût humain ; aucune sélection aléatoire exhaustive des quatorze patches.

## 8. État final et limites

GOLD manuel encore vide : le shootout n'est pas exécutable aujourd'hui. Restent à faire : quatre annotations humaines, QA et validation, puis runtime ML reproductible et gates des candidats. Aucune nouvelle métrique de qualité C3/C6 n'est annoncée sur ces patches. Les résultats 14A.6C restent des références historiques, non recalculées dans cette étape.

Les hashes RGB et des artefacts modèles inventoriés sont vérifiés dans `qa/final_delivery_qa.json`. Les fichiers de production restent inchangés. Le projet à quatorze patches est conservé ; seuls son titre/rôle et sa notice sont mis à jour.

TOTAL ORIGINAL VALIDATION PATCHES :
14

GOLD SET PATCHES :
4

PATCHES REQUIRING FULL MANUAL ANNOTATION :
4

PATCHES REMOVED FROM FULL MANUAL ANNOTATION :
10

TRAIN LEAKAGE :
0

GOLD SET LOCKED :
YES

AI ASSISTED ANNOTATION PLANNED :
YES

MODEL SHOOTOUT READY :
NO

NEXT STEP :
MANUAL_ANNOTATE_4_GOLD_PATCHES

puis

14A8_BUILDING_MODEL_SHOOTOUT
