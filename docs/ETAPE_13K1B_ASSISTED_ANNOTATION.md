# ÉTAPE 13K.1B — Annotation assistée MODEL_C

## Résultat de l’exécution

MODEL_C a été exécuté sur chacun des 16 patches 512×512 avec l’adapter existant, ONNX Runtime CPU, et le seuil 0,50. Le script a vérifié le SHA256 du checkpoint avant l’inférence. Temps mur de génération : 62,577 s ; temps calcul MODEL_C cumulé par patch dans le manifeste. Le checkpoint et le modèle ONNX ont été lus seulement.

Le résultat est **177 polygones candidats répartis dans 12 patches**. Quatre patches ont zéro candidat au seuil choisi. Cela peut signaler une zone sans bâtiment visible ou un oubli du modèle ; ce résultat ne classe jamais le patch comme vide. Les propositions et scores servent à guider la review uniquement. Les catégories de confiance sont des repères heuristiques sur les scores de la sortie (moyenne ≥0,80 : HIGH ; ≥0,60 : MEDIUM ; <0,60 : LOW). Ces scores ne sont pas calibrés et ne confirment pas la validité d’un bâtiment.

Checkpoint MODEL_C : SHA256 `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555`. ONNX lu : SHA256 `94661DED0BC79BBCA99C03D55D817BCB7369D46EB13D7983EBF6AE711003FD45`. ID `spacenet2_deeplab`, profil observé `full_raster_global_rgb_minmax_v1`, moteur `ONNX_RUNTIME_CPU`.

## Séparation pré-annotation / vérité terrain

Pour chaque patch, deux fichiers distincts existent :

- `pre_annotations/<patch_id>_model_c.geojson` contient les propositions immuables par rapport au travail humain (recréables par inférence), avec `source=MODEL_C_PREANNOTATION`, l’ID, l’engine, le seuil, les scores et `review_status=NOT_REVIEWED`.
- `review/<patch_id>_review.geojson` est la copie destinée à l’édition humaine. Si elle existe déjà à la prochaine exécution, le générateur la préserve.

`annotations/<patch_id>.geojson` reste la vérité terrain officielle et n’a pas été modifié par la génération IA. Actuellement, les 16 GeoJSON finaux sont vides, les 16 patches restent `annotation_status=NOT_ANNOTATED`, il n’existe aucun patch `VALIDATED` et aucun masque n’a été généré. L’auto-validation est désactivée.

Le script `scripts/promote_validated_model_c_reviews.py` refuse de promouvoir un patch sans `review_status=VALIDATED` et `reviewer` explicite dans `metadata/<patch_id>.json`. Chaque bâtiment doit en plus avoir `review_status=REVIEWED` ou `VALIDATED`, une géométrie valide dans le patch, et un ID unique. Le script refuse d’écraser un GeoJSON final non vide ou déjà traité. Après promotion, lancer `scripts/building_annotation_workflow.py`, qui réutilise le validateur et le rasteriseur existants et crée un masque seulement pour le statut `VALIDATED`.

## Utilisation dans QGIS

Option de chargement par patch : exécuter dans la console Python de QGIS le fichier `scripts/qgis_open_model_c_review.py`, puis choisir un GeoTIFF dans `images/`. Le script ajoute au projet ouvert le patch RGB et son `review/<patch_id>_review.geojson` correspondant ; il ne vide pas le projet, ne l’enregistre pas et ne modifie pas l’installation globale de QGIS. La commande QGIS n’est pas disponible sur le PATH de l’environnement de préparation, donc ce lanceur est fourni mais n’a pas pu être vérifié dans une instance QGIS.

Pendant cette étape d’assistance, comparer le RGB et le calque `review` pour corriger les contours, supprimer les faux positifs, ajouter les bâtiments manquants, scinder les bâtiments fusionnés ou réunir les fragments. Les 177 propositions ne sont pas toutes correctes ; ne supprimer aucun candidat uniquement parce que son score est classé LOW. Les quatre patches à zéro proposition demandent une revue complète comme les autres.

Les statuts de patch figurent dans `metadata/<patch_id>.json` : `NOT_REVIEWED`, `IN_REVIEW`, `REVIEWED`, `VALIDATED`. Les statuts par objet figurent dans les propriétés du GeoJSON review. Un patch ne peut être promu à `VALIDATED` qu’après contrôle humain. Un patch sans candidat peut être validé vide uniquement après inspection explicite de l’image.

## Priorité et mesure du temps

`metadata/review_priority.csv` permet le tri par nombre de candidats, nombre/ratio de scores LOW, fragmentation (candidats par m²), surface prédite, surface moyenne et nombre de sommets. Ordre prioritaire initial :

1. `GT_2024_residential_02` — 36 candidats, dont 15 LOW ;
2. `GT_2025_difficult_02` — 28 candidats, dont 8 LOW ;
3. `GT_2025_dense_02` — 17 candidats, dont 6 LOW.

`metadata/review_time_log.csv` est prêt pour ces trois patches. Les temps `manual_from_scratch_minutes` et `assisted_review_minutes` sont vides car aucune annotation humaine chronométrée n’a encore été réalisée. Le gain de temps ne peut donc pas être mesuré sans inventer des durées. Après saisie d’au moins trois paires, calculer le speedup comme moyenne(manuel) / moyenne(assisté), sur les mêmes patches et le même critère d’arrêt.

## Contact sheets

Des contact sheets distinctes train/val/test se trouvent dans `metadata/visual_qa_13k1b/`. Chaque ligne présente RGB, pré-annotation MODEL_C (rouge), annotation humaine finale (bleu) et masque validé (vert). Les deux dernières colonnes affichent actuellement « not annotated » / « no validated mask » ; aucune couche IA n’a été copiée dans la vérité terrain.

## Commandes

Depuis la racine du projet dans PowerShell :

```powershell
$env:PROJ_LIB = "backend\.venv\Lib\site-packages\rasterio\proj_data"
$env:PROJ_DATA = $env:PROJ_LIB
$env:GDAL_DATA = "backend\.venv\Lib\site-packages\rasterio\gdal_data"
backend\.venv\Scripts\python.exe scripts\generate_model_c_preannotations.py
backend\.venv\Scripts\python.exe scripts\promote_validated_model_c_reviews.py
backend\.venv\Scripts\python.exe scripts\building_annotation_workflow.py
```

Le script d’inférence n’écrit que sous `pre_annotations/`, `review/` et les métadonnées de review. Il ne modifie pas les poids MODEL_A/MODEL_C, ONNX, les services ou la configuration du pipeline production. Aucun fine-tuning ni augmentation n’a été exécuté.

ÉTAPE 13K.1B — ASSISTED ANNOTATION

TOTAL PATCHES :
16

PREANNOTATIONS GENERATED :
16 fichiers ; 177 polygones candidats

REVIEW FILES GENERATED :
16

QGIS WORKFLOW :
PARTIAL — lanceur fourni, non testé dans QGIS

HUMAN VALIDATION REQUIRED :
YES

AUTO-VALIDATION :
DISABLED

MASK GENERATION :
REUSED — aucun masque généré, 0 patch VALIDATED

QA CONTACT SHEETS :
CREATED

ANNOTATION SPEEDUP ESTIMATE :
NOT MEASURED — journal de temps prêt pour 3 patches prioritaires

MODEL_C :
UNCHANGED

ONNX :
UNCHANGED

MODEL_A :
UNCHANGED

PRODUCTION PIPELINE :
UNCHANGED

READY_FOR_ASSISTED_REVIEW :
YES

NEXT STEP :
REVIEW PATCHES IN QGIS
