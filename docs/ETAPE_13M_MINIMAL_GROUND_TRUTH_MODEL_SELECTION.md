# ÉTAPE 13M — Minimal Ground Truth Model Selection

## État et décision actuelle

Le paquet d'évaluation indépendante est préparé à partir du split TEST déjà défini dans `maxar_v1/splits/test.txt` et `metadata/patch_index.csv`. Il contient exactement les six patches de test. Les six annotations restent vides et `NOT_ANNOTATED` : **aucune vérité terrain humaine n'a été créée ou validée dans cette étape**. Le compte de bâtiments et les métriques restent donc inconnus.

La sélection objective des modèles est **en attente**. Décision actuelle : **E. NEED_MORE_GROUND_TRUTH**. Les sorties de 13L ont été produites à part et ne sont pas copiées dans le paquet d'annotation. Ne pas interpréter un GeoJSON vide comme un patch sans bâtiment. Aucun modèle n'a été promu, aucun poids n'a été modifié et aucun fine-tuning n'a été lancé.

## Patches test verrouillés

| Patch | Date | Catégorie proposée dans l'index | Annotation actuelle |
|---|---:|---|---|
| `GT_2024_difficult_02` | 2024 | difficult | NOT_ANNOTATED |
| `GT_2024_industrial_02` | 2024 | industrial | NOT_ANNOTATED |
| `GT_2024_residential_02` | 2024 | residential | NOT_ANNOTATED |
| `GT_2025_difficult_02` | 2025 | difficult | NOT_ANNOTATED |
| `GT_2025_industrial_02` | 2025 | industrial | NOT_ANNOTATED |
| `GT_2025_residential_02` | 2025 | residential | NOT_ANNOTATED |

Les catégories ci-dessus sont des propositions de catalogue, pas des vérités sur le contenu des images. Les images source sont en 512×512, RGB, EPSG:32637, résolution annoncée 0,35 m/pixel. Le script a copié les six fichiers TIFF à l'identique octet par octet. Chaque source et copie a le même SHA256 dans le manifeste.

Le paquet séparé `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/` marque chaque image `TEST_LOCKED`, `evaluation_only=true`, `training_use_prohibited=true`, `augmentation_training_prohibited=true`. Ces patches doivent rester exclus de tout training, fine-tuning et augmentation training ultérieurs.

## Fichiers préparés

- `images/<patch_id>.tif` : copie identique de l'image source.
- `annotations/<patch_id>.geojson` : FeatureCollection vide en EPSG:32637. Vide signifie **pas encore annoté**.
- `metadata/<patch_id>.json` : split verrouillé, statut, date/source, SHA256, largeur/hauteur, CRS, transform, bounds et chemin vers le template.
- `overlays/<patch_id>_blank.png` : image originale portant seulement l'étiquette explicite `BLANK HUMAN GROUND TRUTH TEMPLATE | NO MODEL PREDICTIONS`.
- `overlays/contact_sheet_test_blank.jpg` : RGB et template vierge côte à côte, six patches.
- `qgis/13M_locked_test_ground_truth.qgz` : projet QGIS avec six groupes, chaque groupe contient seulement RGB et couche d'annotation vide, avec un signet par patch.
- `qgis/README.md` : instructions de saisie, propriétés et validation.
- `metadata/manifest.json` : liste blanche des six ID et empreintes d'images, plus interdiction d'entraînement.

QGIS a rouvert le projet enregistré avec succès : 6/6 groupes, 6 rasters RGB, 6 couches de vérité terrain vides, 6 signets, 0 couche de prédiction. Le GeoJSON vide ne peut pas déclarer les propriétés d'entités sans inclure une entité ; ajouter les champs texte dans QGIS avant la première entité, selon le guide.

Pour ouvrir le projet : exécuter `scripts/open_13M_qgis_annotation.bat` ou ouvrir directement `qgis/13M_locked_test_ground_truth.qgz`. Ne pas ouvrir le projet 13K.1C assisté pour l'annotation du test : il expose des propositions de modèle. Le projet 13M n'inclut aucune prédiction.

## Protocole d'annotation requis

1. Tracer manuellement le contour visible de chaque toiture, y compris petites, grandes, complexes et proches. Exclure routes, véhicules, végétation, ombres, sol nu et objets ambigus.
2. Ne copier aucune géométrie provenant de MODEL_C, WHU ou HOTOSM. Les couches de prédiction restent séparées du jeu d'annotations.
3. Créer un ID unique, par exemple `<patch_id>_B001`; renseigner patch, date, source, annotateur et statut. Marquer les entités `ANNOTATED` pendant la saisie.
4. Vérifier indépendamment tout le patch et les contours; après contrôle complet, définir patch et entités `VALIDATED` et renseigner annotateur/réviseur. Si aucun bâtiment n'est visible, documenter explicitement cette revue humaine; un fichier vide non revu n'est jamais un négatif validé.
5. Produire ensuite un masque uint8 512×512 `{0,1}` depuis les polygones validés. Exiger le même CRS, transform, bounds et grille pixel que le RGB, sans rééchantillonnage.

Cette annotation est une action humaine à effectuer dans QGIS. Aucun nombre de bâtiments ou statut `VALIDATED` n'est imputé automatiquement.

## Règles d'évaluation après validation

La comparaison n'est exécutable qu'une fois que les six patches sont `VALIDATED` et que leurs six masques alignés ont été vérifiés. Utiliser les prédictions 13L sauvegardées et les paramètres identiques, sans recalibrer de seuil sur ces patches test.

- Pixel : calculer TP/FP/FN, Precision, Recall, F1/Dice et IoU pour chaque patch; fournir moyenne macro des six et scores micro agrégés par pixels. Utiliser le masque rasterisé avec la convention centre-pixel `all_touched=False`.
- Contours : extraire le bord des masques binaires; Boundary F1 avec tolérance de 1 pixel (0,35 m); Boundary IoU avec une bande de 1 pixel de chaque côté. Mean Boundary Distance = moyenne symétrique des distances euclidiennes aux bords les plus proches; Hausdorff = maximum symétrique. Rapporter pixels et conversion métrique (1 px = 0,35 m).
- Objets : chaque bâtiment est une entité polygone dans l'annotation et un composant connexe après seuil. Associer une fois chacun avec matching biparti maximisant l'IoU, seuil objet IoU ≥ 0,50. GT non associé = manqué; prédiction non associée = faux positif. Une prédiction avec IoU ≥0,25 sur au moins deux GT = candidat fusionné; un GT avec IoU ≥0,25 sur au moins deux prédictions = candidat fragmenté. Rapporter ces cas séparément des décomptes un-à-un.
- Petits bâtiments : rapporter la détection d'objets annotés de surface ≤100 m² séparément (rappel des objets GT petits, faux positifs candidats, et distributions d'aire). Ne conclure qu'à partir des labels vérifiés.
- Performance : conserver temps/patch et engine 13L. La RAM de 13L est une mesure combinée; elle n'est pas un classement RAM isolé par candidat.
- Licence : le modèle HOTOSM reste `LICENSE_REVIEW_REQUIRED` (AGPL-3.0 déclaré par sa fiche) avant toute intégration ou promotion. La sélection de qualité ne vaut pas autorisation de déploiement.

Le classement priorisera l'exactitude bâtiment et contour, les petits bâtiments et faux positifs, puis la vitesse. En attendant les labels, aucun vainqueur n'est déclaré.

## Artéfacts de préparation

- Génération déterministe du paquet : [`scripts/prepare_13M_test_ground_truth.py`](../scripts/prepare_13M_test_ground_truth.py)
- Projet QGIS : [`13M_locked_test_ground_truth.qgz`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth.qgz)
- Planche vierge : [`contact_sheet_test_blank.jpg`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/overlays/contact_sheet_test_blank.jpg)
- Manifeste : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/metadata/manifest.json`

---

ÉTAPE 13M — MODEL SELECTION WITH GROUND TRUTH

TEST PATCHES :
6

VALIDATED TEST PATCHES :
0 / 6

TOTAL ANNOTATED BUILDINGS :
NOT AVAILABLE — no human annotations yet

MODEL_C IOU :
NOT AVAILABLE — ground truth pending

WHU IOU :
NOT AVAILABLE — ground truth pending

HOTOSM IOU :
NOT AVAILABLE — ground truth pending

MODEL_C DICE :
NOT AVAILABLE — ground truth pending

WHU DICE :
NOT AVAILABLE — ground truth pending

HOTOSM DICE :
NOT AVAILABLE — ground truth pending

MODEL_C BOUNDARY F1 :
NOT AVAILABLE — ground truth pending

WHU BOUNDARY F1 :
NOT AVAILABLE — ground truth pending

HOTOSM BOUNDARY F1 :
NOT AVAILABLE — ground truth pending

MODEL_C MEAN BOUNDARY ERROR :
NOT AVAILABLE — ground truth pending

WHU MEAN BOUNDARY ERROR :
NOT AVAILABLE — ground truth pending

HOTOSM MEAN BOUNDARY ERROR :
NOT AVAILABLE — ground truth pending

MODEL_C MISSED BUILDINGS :
NOT AVAILABLE — ground truth pending

WHU MISSED BUILDINGS :
NOT AVAILABLE — ground truth pending

HOTOSM MISSED BUILDINGS :
NOT AVAILABLE — ground truth pending

MODEL_C FALSE POSITIVES :
NOT AVAILABLE — ground truth pending

WHU FALSE POSITIVES :
NOT AVAILABLE — ground truth pending

HOTOSM FALSE POSITIVES :
NOT AVAILABLE — ground truth pending

BEST BOUNDARIES :
NOT DETERMINED

BEST DETECTION :
NOT DETERMINED

BEST SMALL BUILDINGS :
NOT DETERMINED

BEST SPEED :
HOTOSM — 1.237 s/patch on 13L CPU benchmark; quality is not established

BEST OVERALL :
NOT DETERMINED — need validated test ground truth

HOTOSM LICENSE :
REVIEW_REQUIRED

MODEL_C PRODUCTION :
UNCHANGED

FINE TUNING PERFORMED :
NO

NEXT STEP :
EXPAND GROUND TRUTH — manually annotate and validate all 6 locked TEST patches
