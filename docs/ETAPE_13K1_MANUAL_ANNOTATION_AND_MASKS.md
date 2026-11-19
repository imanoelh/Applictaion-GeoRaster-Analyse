# ÉTAPE 13K.1 — Workflow d’annotation manuelle et génération des masques

## État actuel

Le workflow est installé pour le pilote `backend/data/fine_tuning/buildings/maxar_v1`. Il indexe et contrôle les 16 images, fournit un GeoJSON éditable par patch, suit les statuts d’annotation, valide la géométrie et génère des GeoTIFF binaires uniquement pour les patches déclarés `VALIDATED` par l’annotateur. La première exécution confirme 16 patches `NOT_ANNOTATED`, 0 patch annoté, 0 masque et 0 erreur sur les fichiers encore vides. Le dataset n’est pas prêt pour l’entraînement.

Aucun polygone n’a été ajouté et aucune annotation ou prédiction IA n’a été utilisée. Les mots `dense`, `residential`, `industrial` et `difficult_context` restent des catégories proposées par le catalogue, à confirmer en examinant l’imagerie.

## Fichiers livrés

- `backend/data/fine_tuning/buildings/maxar_v1/metadata/patch_index.csv` : inventaire de chaque raster, dimensions, nombre et type de bandes, CRS, transformation, emprise, split, source, date, résolution et statut.
- `annotations/<patch_id>.geojson` : un FeatureCollection vide en EPSG:32637 par patch, prêt pour les polygones humains ; le fichier vide ne signifie pas « aucun bâtiment ».
- `metadata/<patch_id>.json` : statut, annotateur, nombre de bâtiments et aire annotée en m², en plus des métadonnées de source et d’emprise.
- `masks/<patch_id>.tif` : produit uniquement si le statut de patch est `VALIDATED`. Raster uint8 avec 0 = fond, 1 = bâtiment, utilisant exactement la grille image, sans resampling et `all_touched=False`.
- `metadata/visual_qa_13k1/{train,val,test}_annotation_mask_contact_sheet.jpg` : image, annotations humaines superposées et masque s’il existe ; le statut est imprimé sous chaque patch.
- `scripts/building_annotation_workflow.py` : prépare les templates, valide les patches et annotations, génère les masques validés et les planches QA.
- `metadata/annotation_validation_report.json` : rapport machine de la dernière exécution.

## Ouvrir et annoter dans QGIS

1. Charger le GeoTIFF depuis `images/<patch_id>.tif` comme fond. Dans le panneau Browser/QGIS, ajouter son fichier `annotations/<patch_id>.geojson` correspondant. Pendant l’annotation principale, ne charger ni couche MODEL_A/MODEL_C, ni carte de probabilité, ni polygone issu de l’IA.
2. Créer/dessiner des polygones sur la limite visible de la toiture. Si QGIS ne permet pas d’ajouter une géométrie au FeatureCollection vide, créer une nouvelle couche GeoJSON **Polygon** avec le CRS du raster et les champs `building_ref_id`, `patch_id`, `date`, `source`, `annotation_status`, `annotator`, `notes`, puis enregistrer le FeatureCollection dans `annotations/<patch_id>.geojson`.
3. Inclure les toitures nettement visibles et les structures permanentes clairement identifiables. Exclure routes, parkings, véhicules, végétation, ombres, sols nus, murs isolés et objets ambigus. Suivre le bord visible de la toiture aussi précisément que possible ; cible indicative <1 pixel (0,35 m) quand la limite est nette.
4. Utiliser un identifiant unique par bâtiment, par exemple `GT_2024_dense_01_B001`. Garder `patch_id`, la date et la source exacts. Mettre le patch à `IN_PROGRESS` pendant le dessin, puis `ANNOTATED` une fois la saisie terminée.
5. Réviser les polygones et les exclusions sans superposition IA. Un patch sans bâtiment visible devient `VALIDATED` uniquement après vérification humaine explicite ; renseigner alors `building_count=0`, `annotated_area_m2=0` et un identifiant d’annotateur dans sa métadonnée. Un GeoJSON vide dont le statut est `NOT_ANNOTATED` ou `IN_PROGRESS` ne sera jamais considéré comme fond seul.
6. Après contrôle humain, changer `annotation_status` dans `metadata/<patch_id>.json` à `VALIDATED`, renseigner `annotator`, et ajouter les mêmes propriétés d’identification aux bâtiments dans le GeoJSON. Lancer le workflow ci-dessous. Il ne rasterise que les patches `VALIDATED`; toute géométrie vide (si bâtiments dessinés), non valide, hors emprise ou ID dupliqué bloque le masque pour le patch.

## Règles du validateur et masque

Le validateur contrôle les images 512×512, trois bandes RGB, uint8, CRS, transformation/emprise, les statuts autorisés (`NOT_ANNOTATED`, `IN_PROGRESS`, `ANNOTATED`, `VALIDATED`), le CRS GeoJSON, les types Polygon/MultiPolygon, géométries valides/non vides, surface positive, inclusion complète dans l’emprise, ID bâtiment unique et correspondance `patch_id`. Les groupes spatiaux multi-date doivent garder un split commun et les emprises entre train/validation/test ne doivent pas se chevaucher.

Pour chaque annotation `VALIDATED`, le rasteriseur produit une bande uint8 GeoTIFF avec mêmes largeur/hauteur, CRS et transformation que l’image ; le masque utilise 0 comme arrière-plan valide et 1 comme bâtiment, sans nodata ni rééchantillonnage. La règle pixel-edge est `all_touched=False` : un pixel est sélectionné selon le test centre-pixel de Rasterio. Les patches validés sans bâtiment donnent donc un masque entièrement nul, mais uniquement après validation humaine.

Exécution depuis la racine du projet (variables PROJ/GDAL requises par l’environnement rasterio Windows) :

```powershell
$env:PROJ_LIB = "backend\.venv\Lib\site-packages\rasterio\proj_data"
$env:PROJ_DATA = $env:PROJ_LIB
$env:GDAL_DATA = "backend\.venv\Lib\site-packages\rasterio\gdal_data"
backend\.venv\Scripts\python.exe scripts\building_annotation_workflow.py
```

Le script crée des masques uniquement après passage du statut à `VALIDATED`. Il ne charge aucun modèle, ne fait aucune augmentation et n’entraîne rien.

## Vérification actuelle des images et diversité

Index contrôlé : 16 images en 512×512, RGB uint8, EPSG:32637, résolution 0,35 m, sources `p2p98` 2024/2025, dates, transformations et emprises. Les splits restent TRAIN 6, VALIDATION 4, TEST 6 ; aucune emprise entre splits ne se chevauche et les deux dates d’une même fenêtre sont groupées.

Inspection visuelle des contact sheets de patches (ce n’est pas un comptage de bâtiments annotés) : plusieurs patches montrent des grappes de toitures et des rues ; quelques patches sont majoritairement sol nu/parcelles ouvertes ou ont peu de toits ; des ombres de bâtiments et des croisements routiers sont visibles ; la végétation est peu représentée ; les toits sont surtout plats et leur variété complexe est limitée. Les patches `industrial` proposés comprennent aussi des zones qui paraissent surtout ouvertes. Confirmer chaque catégorie et distinguer bâtiment/sol nu/routes au moment de l’annotation.

**Diversité : LIMITED.** Il s’agit toujours d’un seul AOI de Riyad, avec deux dates et seulement 16 patches. Le jeu ne couvre pas suffisamment de villes, de contextes, de bâtiments positifs/négatifs validés, ni de types de végétation ou d’architecture pour mesurer une généralisation. Ajouter des zones géographiques indépendantes après cette première annotation ; conserver le test séparé.

## Point de reprise

Les images et le workflow sont prêts ; la tâche suivante est l’annotation/revue humaine des patches. Ne passer au fine-tuning qu’après que chaque patch du jeu retenu est `VALIDATED`, tous ses masques alignés sont présents, les validations sont sans erreur et la diversité/séparation des zones est jugée suffisante.

ÉTAPE 13K.1 — ANNOTATION + MASK GENERATION

TOTAL PATCHES :
16

TRAIN :
6

VALIDATION :
4

TEST :
6

ANNOTATED PATCHES :
0

VALIDATED PATCHES :
0

VALIDATED EMPTY PATCHES :
0

TOTAL BUILDINGS :
0 annoté ; nombre réel à établir manuellement

TOTAL MASKS :
0

MASK ALIGNMENT :
VALIDATED — aucune divergence détectée ; aucun masque car aucun patch n’est VALIDATED

GEOJSON VALIDATION :
VALIDATED — templates vides et CRS cohérents ; annotations humaines pas encore soumises

CONTACT SHEETS :
CREATED

SPATIAL LEAKAGE :
NO

DATASET DIVERSITY :
LIMITED

MODEL_C :
UNCHANGED

MODEL_A :
UNCHANGED

ONNX :
UNCHANGED

PRODUCTION PIPELINE :
UNCHANGED

READY_FOR_FINE_TUNING :
NO

NEXT STEP :
COMPLETE ANNOTATION FIRST
