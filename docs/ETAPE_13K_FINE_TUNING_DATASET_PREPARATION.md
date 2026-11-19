# ÉTAPE 13K — Préparation du dataset de fine-tuning Building

## Résultat

Le pilote d’annotation a été assemblé sous `backend/data/fine_tuning/buildings/maxar_v1/`. Il contient 16 patches RGB correctement extraits et géoréférencés, leurs métadonnées, 16 templates GeoJSON vides et des listes de splits candidates. Ce n’est pas encore un dataset d’entraînement : aucune annotation humaine et aucun masque binaire n’étaient fournis dans la copie du projet. Aucun masque de zéros n’a été créé, car cela classerait faussement tous les bâtiments comme arrière-plan.

Les templates GeoJSON présents dans `test-data/building-ground-truth/` confirment eux-mêmes `MANUAL_ANNOTATION_REQUIRED`, `EMPTY_TEMPLATES_ONLY` et `NOT_ANNOTATED`. Les fichiers GeoJSON d’export et les contours de diagnostic du modèle ne sont pas des vérités terrain et n’ont pas servi à produire de labels.

## Images et extraction

- Source : orthophotos Maxar RGB `p2p98` 2024 et 2025 sous `test-data/validation-results/maxar_rgb_derivatives/`.
- Canaux : Maxar 5 → rouge, 3 → vert, 2 → bleu. Les dérivés source sont déjà en RGB, 8 bits.
- Résolution : 0,35 m/pixel ; taille : 512 × 512 ; CRS : EPSG:32637.
- Une emprise 512 × 512 couvre 179,2 m par côté. Les patches ont été extraits en suivant les fenêtres du catalogue sans redimensionner l’image.
- Les contextes `urban_dense`, `residential`, `industrial` et `difficult_context` sont des propositions du catalogue et restent à confirmer visuellement. L’un des patches proposés « industrial » montre surtout du terrain ouvert ; la catégorie doit être revue par l’annotateur.
- Toutes les images retenues proviennent du même secteur de Riyad. Les deux dates apportent une variation temporelle, mais pas une diversité géographique indépendante suffisante pour un fine-tuning robuste.

## Contrôle du catalogue et extraction

Les 16 anciens fichiers `test-data/building-ground-truth/{2024,2025}/patches/*.tif` existaient, mais l’inspection raster a révélé la même emprise géographique dans chacun, alors que le catalogue déclarait des fenêtres différentes. Pour éviter cette incohérence, le pilote a été réextrait directement depuis chaque GeoTIFF source au moyen des offsets de fenêtre consignés au catalogue. Les images de `maxar_v1/images/` ont ensuite été vérifiées : 512 × 512, 3 canaux RGB, EPSG:32637, transformation et emprise propres à chaque fenêtre.

Le validateur `scripts/validate_building_finetuning_dataset.py` vérifie les dimensions/canaux/CRS/emprises, l’alignement image-masque si un masque existe, les valeurs binaires {0,1}, le CRS et la validité des géométries d’annotation quand elles sont présentes, ainsi que le chevauchement d’emprises entre splits. En l’absence de labels, son résultat est : 16 images contrôlées, 0 masques, 0 patches annotés, chevauchement spatial validé, préparation au fine-tuning = false. Le rapport machine est dans `backend/data/fine_tuning/buildings/maxar_v1/metadata/validation_report.json`.

## Structure livrée

```text
backend/data/fine_tuning/buildings/maxar_v1/
  images/       16 GeoTIFF RGB, patches géoréférencés
  masks/        vide, en attente des masques humains
  geojson/      16 templates vides, EPSG:32637
  metadata/     16 JSON par patch + validation_report.json
  metadata/visual_qa/
    images_contact_sheet.jpg
    overlay_contact_sheet.jpg
    contours_contact_sheet.jpg
  splits/
    train.txt   6 candidats
    val.txt     4 candidats
    test.txt    6 candidats
```

Les contact sheets recensent les 16 patches. Les vues « overlay » et « contours » portent explicitement la mention qu’aucune annotation ni aucun contour humain n’est encore disponible : elles ne constituent pas une validation de précision d’annotation. Un annotateur doit inspecter et annoter les images, puis une revue humaine doit confirmer la catégorie, chaque toit, les exclusions et les contours.

Les splits regroupent ensemble les occurrences 2024 et 2025 d’une même emprise spatiale ; aucune emprise de patch ne se recoupe entre splits. Ce contrôle évite le chevauchement direct et le mélange des deux dates d’un même patch. Il ne prouve pas une indépendance géographique complète : les patches sont dans un seul AOI et certains candidats sont voisins. Garder le test intact et ajouter des zones géographiques indépendantes avant d’utiliser les scores comme mesure de généralisation.

## Règles d’annotation à appliquer

Annoter les limites visibles des toitures (cible d’erreur inférieure à un pixel lorsque la limite est nette, soit environ 0,35 m). Inclure les bâtiments permanents clairement identifiables. Exclure routes, parkings, véhicules, végétation, ombres, terrain nu, murs isolés et objets ambigus. Le masque futur sera uint8 binaire : 0 arrière-plan, 1 bâtiment ; il doit avoir la même grille, le même CRS, la même emprise et la même taille que l’image. Enregistrer l’identifiant/annotateur, le statut de revue et le nombre de bâtiments dans la métadonnée.

## Compatibilité modèle

Le preprocessing observé dans l’adapter MODEL_C est `full_image_global_rgb_minmax_to_0_1`, profil `full_raster_global_rgb_minmax_v1`. La préparation conserve les images RGB source sans nouvelle normalisation, redimensionnement ou augmentation ; les transformations et augmentations d’entraînement devront être fixées lors d’une étape ultérieure et rester compatibles avec le comportement d’inférence. Flips, rotations de 90° et variations modérées de luminosité/contraste ne sont que des options futures, non appliquées ici.

MODEL_C, le fichier ONNX, MODEL_A, le registre et le pipeline de production n’ont pas été modifiés. Aucun entraînement ni fine-tuning n’a été lancé.

## Étape de reprise

**Dernier point accompli :** 16 patches candidats extraits depuis les orthophotos source, avec split spatial candidat et contrôle technique de base.

**Prochaine action :** compléter l’annotation manuelle des 16 templates et produire/contrôler les masques alignés ; réviser les catégories proposées ; puis enrichir le dataset avec plusieurs zones urbaines indépendantes et vérifier l’équilibre positif/négatif avant toute étape 13L.

ÉTAPE 13K — FINE-TUNING DATASET PREPARATION

DATASET NAME :
maxar_v1 (annotation-ready pilot)

SOURCE :
Maxar RGB p2p98, 2024 et 2025, un seul AOI de Riyad

PATCH SIZE :
512x512

TOTAL PATCHES :
16 candidats, 0 annoté

TRAIN PATCHES :
6 candidats, 0 annoté

VALIDATION PATCHES :
4 candidats, 0 annoté

TEST PATCHES :
6 candidats, 0 annoté

POSITIVE PATCHES :
0 annoté ; nombre réel positif à déterminer

EMPTY PATCHES :
0 annoté ; nombre réel vide à déterminer

ANNOTATED BUILDINGS :
0

ANNOTATION STATUS :
NOT_ANNOTATED — templates GeoJSON vides ; masques absents

ANNOTATION QUALITY CHECK :
PARTIAL

SPATIAL LEAKAGE CHECK :
VALIDATED — aucun chevauchement d’emprise entre splits et même emprise multi-date conservée dans le même split ; indépendance géographique limitée à un AOI

MASK FORMAT :
BINARY (cible uint8 : 0 background, 1 building ; fichiers non encore créés)

PREPROCESSING :
RGB Maxar bands 5/3/2 ; pas de redimensionnement ; compatibilité observée MODEL_C : full_image_global_rgb_minmax_to_0_1, profil full_raster_global_rgb_minmax_v1

MODEL_C :
UNCHANGED

ONNX :
UNCHANGED

PRODUCTION PIPELINE :
UNCHANGED

READY_FOR_FINE_TUNING :
NO

NEXT STEP :
COMPLETE DATASET FIRST
