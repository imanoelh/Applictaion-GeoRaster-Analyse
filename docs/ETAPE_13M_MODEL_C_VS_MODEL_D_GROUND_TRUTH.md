# ÉTAPE 13M — MODEL_C vs MODEL_D Ground Truth

## État de cette validation

La comparaison de qualité est **en attente**. Le split TEST est bien verrouillé à six patches, mais les six couches d’annotation dédiées à 13M sont encore vides et portent toutes le statut `NOT_ANNOTATED`. Aucun patch n’est donc `VALIDATED`; aucun compte de bâtiments, masque GT ou score comparatif ne peut être déclaré.

Je n’ai pas dessiné ni validé d’empreintes à la place d’un annotateur humain. Je n’ai pas exécuté les modèles sur ces six images dans cette étape, afin de préserver le protocole aveugle avant l’annotation. Le benchmark est reporté jusqu’à la validation humaine des annotations.

## Patches TEST verrouillés

La liste a été vérifiée dans `backend/data/fine_tuning/buildings/maxar_v1/splits/test.txt` et dans l’index du dataset. Les six identifiants n’ont pas été déplacés entre splits.

| Patch | Date | Catégorie proposée | Statut actuel | Features GT | Masque GT |
|---|---:|---|---|---:|---|
| `GT_2024_difficult_02` | 2024 | difficult | NOT_ANNOTATED | 0 | absent |
| `GT_2024_industrial_02` | 2024 | industrial | NOT_ANNOTATED | 0 | absent |
| `GT_2024_residential_02` | 2024 | residential | NOT_ANNOTATED | 0 | absent |
| `GT_2025_difficult_02` | 2025 | difficult | NOT_ANNOTATED | 0 | absent |
| `GT_2025_industrial_02` | 2025 | industrial | NOT_ANNOTATED | 0 | absent |
| `GT_2025_residential_02` | 2025 | residential | NOT_ANNOTATED | 0 | absent |

Les six GeoTIFF RGB préparés sont en 512 × 512, 3 bandes, EPSG:32637 et 0,35 m/pixel. Le manifeste 13M confirme que les copies d’images correspondent octet pour octet aux sources et maintient `training_use_prohibited=true` et `augmentation_training_prohibited=true`.

Les six GeoJSON de `benchmark_13M_test/annotations/` sont des FeatureCollections vides valides. Leur vacuité indique « non annoté », jamais « aucun bâtiment ». Aucun masque 512 × 512 ne peut être produit sans polygones humains validés.

## Contrôle de l’aveugle

Le projet QGIS 13M contient 12 couches : six couches RGB et six couches `HUMAN_GROUND_TRUTH_EMPTY_*`. L’inspection de son fichier projet confirme qu’il ne référence aucune couche de prédiction, de revue ou de préannotation.

Des fichiers distincts existent dans le répertoire `maxar_v1/review/`; leur métadonnée identifie une source `MODEL_C_PREANNOTATION`, un modèle SpaceNet2 DeepLab et le statut `NOT_REVIEWED`. Ils ne constituent pas la vérité terrain, n’ont pas été copiés dans le paquet TEST et ne doivent pas être utilisés comme labels. Les prédictions 13L.3 concernent des AOI différentes et ne sont pas les prédictions des six patches TEST.

## Artefacts disponibles

- Projet QGIS sans prédictions : [`13M_locked_test_ground_truth.qgz`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth.qgz)
- Guide d’annotation : [`qgis/README.md`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/README.md)
- Contact sheet RGB + modèles vierges : [`contact_sheet_test_blank.jpg`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/overlays/contact_sheet_test_blank.jpg)
- Manifeste du split verrouillé : [`manifest.json`](../backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/metadata/manifest.json)

## Conditions pour reprendre le benchmark

1. Annoter les six RGB dans le projet QGIS 13M, sans ajouter de couche de prédiction. Tracer les toitures visibles, y compris les petites et complexes, et enregistrer les propriétés requises.
2. Après la revue humaine complète, renseigner `annotation_status=VALIDATED` pour chaque patch et chaque bâtiment, avec les champs annotateur/réviseur. Un patch réellement sans bâtiment doit faire l’objet d’une revue humaine documentée avant de rester vide.
3. Vérifier les géométries, bounds et CRS; générer un masque uint8 512 × 512 `{0,1}` sur la grille exacte de chaque GeoTIFF.
4. Une fois les annotations validées, exécuter MODEL_C et MODEL_D sur ces mêmes six patches, conserver probability map, masque, GeoJSON, nombre de candidats et temps, puis calculer les métriques pixel, contour et objet définies par le protocole 13M.

Aucun seuil ne sera choisi sur ces patches TEST. Aucun entraînement ou fine-tuning ne sera effectué dans cette étape. MODEL_C reste le modèle de production par défaut; MODEL_D reste expérimental.

## ÉTAPE 13M — MODEL_C vs MODEL_D GROUND TRUTH

TEST PATCHES :
6

VALIDATED PATCHES :
0 / 6

TOTAL GT BUILDINGS :
NOT AVAILABLE — aucune annotation humaine validée; les six fichiers vides ne signifient pas zéro bâtiment

MODEL_C IOU :
NOT COMPUTED — ground truth pending

MODEL_D IOU :
NOT COMPUTED — ground truth pending

MODEL_C DICE :
NOT COMPUTED — ground truth pending

MODEL_D DICE :
NOT COMPUTED — ground truth pending

MODEL_C PRECISION :
NOT COMPUTED — ground truth pending

MODEL_D PRECISION :
NOT COMPUTED — ground truth pending

MODEL_C RECALL :
NOT COMPUTED — ground truth pending

MODEL_D RECALL :
NOT COMPUTED — ground truth pending

MODEL_C BOUNDARY F1 :
NOT COMPUTED — ground truth pending

MODEL_D BOUNDARY F1 :
NOT COMPUTED — ground truth pending

MODEL_C MEAN BOUNDARY ERROR :
NOT COMPUTED — no validated GT

MODEL_D MEAN BOUNDARY ERROR :
NOT COMPUTED — no validated GT

MODEL_C FALSE POSITIVES :
NOT COMPUTED — ground truth pending

MODEL_D FALSE POSITIVES :
NOT COMPUTED — ground truth pending

MODEL_C MISSED BUILDINGS :
NOT COMPUTED — ground truth pending

MODEL_D MISSED BUILDINGS :
NOT COMPUTED — ground truth pending

MODEL_C MERGED BUILDINGS :
NOT COMPUTED — ground truth pending

MODEL_D MERGED BUILDINGS :
NOT COMPUTED — ground truth pending

MODEL_C FRAGMENTED BUILDINGS :
NOT COMPUTED — ground truth pending

MODEL_D FRAGMENTED BUILDINGS :
NOT COMPUTED — ground truth pending

BEST DETECTION :
NOT DETERMINED

BEST BOUNDARIES :
NOT DETERMINED

BEST SMALL BUILDINGS :
NOT DETERMINED

BEST COMPLEX ROOFS :
NOT DETERMINED

BEST SPEED :
NOT MEASURED ON THESE SIX TEST PATCHES

BEST OVERALL :
NOT DETERMINED

FINAL DECISION :
F. NEED_MORE_GROUND_TRUTH

MODEL_C PRODUCTION :
UNCHANGED

MODEL_D :
EXPERIMENTAL

FINE TUNING :
NOT PERFORMED

NEXT STEP :
EXPAND GROUND TRUTH
