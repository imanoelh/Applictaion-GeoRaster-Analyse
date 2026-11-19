# ÉTAPE 13M.0 — QA des 3 premiers patches Ground Truth

Date du contrôle : 2026-10-22  
Périmètre : uniquement les trois patches TEST verrouillés annoncés. Aucun modèle IA n'a été exécuté; aucune prédiction ni opération de fine-tuning n'a été utilisée.

## Résultat de recherche des annotations

Le projet QGIS `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth.qgz` a été modifié le 2026-10-22. Son contenu référence toujours les six sources GeoJSON sous `../annotations/`; les couches affichées dans le projet sont nommées `HUMAN_GROUND_TRUTH_EMPTY_*`.

Les trois sources des patches demandés n'ont pas été modifiées depuis le 2026-10-20 et ne contiennent aucune feature :

| Patch | GeoJSON source | Features persistées | Statut dans GeoJSON | Statut metadata |
|---|---|---:|---|---|
| 01 — `GT_2024_difficult_02` | `benchmark_13M_test/annotations/GT_2024_difficult_02.geojson` | 0 | `NOT_ANNOTATED` | `NOT_ANNOTATED` |
| 02 — `GT_2024_industrial_02` | `benchmark_13M_test/annotations/GT_2024_industrial_02.geojson` | 0 | `NOT_ANNOTATED` | `NOT_ANNOTATED` |
| 03 — `GT_2024_residential_02` | `benchmark_13M_test/annotations/GT_2024_residential_02.geojson` | 0 | `NOT_ANNOTATED` | `NOT_ANNOTATED` |

Aucun GeoJSON d'annotation correspondant n'a donc été trouvé comme modifié ou renseigné. Le projet QGIS a été sauvegardé, mais les entités dessinées ne sont pas présentes dans les sources référencées par le projet. Le nombre réel de bâtiments et leurs surfaces ne peuvent pas être établis à partir de ces fichiers. `0 feature persistée` ne signifie pas `0 bâtiment sur l'image`.

## Vérification des géométries et du raster

Les GeoJSON sont parseables et leurs CRS déclarés sont `EPSG:32637`, mais leurs FeatureCollections sont vides. Il n'existe donc aucune géométrie sur laquelle tester les types Polygon/MultiPolygon, validité, auto-intersection, surface nulle, limites, doublons ou bâtiments au bord. Ces contrôles ne peuvent pas être validés tant que les dessins ne sont pas écrits dans les sources GeoJSON.

Les trois rasters de référence ont été lus avec l'environnement Python du backend. Pour chacun, l'image est RGB `uint8`, de dimensions 512×512 et le CRS raster se résout vers `EPSG:32637`. Le transform et les bounds du raster concordent avec les métadonnées du patch. Cela valide la grille raster de référence, mais ne valide pas un masque absent.

| Patch | Raster dimensions | CRS | Transform/bounds vs metadata |
|---|---:|---|---|
| 01 — `GT_2024_difficult_02` | 512×512, 3 bandes | EPSG:32637 | Identiques |
| 02 — `GT_2024_industrial_02` | 512×512, 3 bandes | EPSG:32637 | Identiques |
| 03 — `GT_2024_residential_02` | 512×512, 3 bandes | EPSG:32637 | Identiques |

## Masques et overlays QA

Aucun masque et aucun overlay humain QA n'a été généré. Comme les annotations source sont vides et marquées `NOT_ANNOTATED`, écrire des masques tout noirs aurait assimilé à tort des données manquantes à une vérité terrain négative; un overlay sans contour humain aurait été trompeur. Les templates vierges préexistants ne sont pas comptés comme overlays QA produits lors de ce contrôle.

Aucune annotation ni metadata n'a été modifiée automatiquement. Aucun patch n'a été passé à `VALIDATED`.

## Action nécessaire pour reprendre

Dans QGIS, enregistrer les éditions des couches humaines vers leurs GeoJSON sources (`benchmark_13M_test/annotations/GT_2024_difficult_02.geojson`, `.../GT_2024_industrial_02.geojson`, `.../GT_2024_residential_02.geojson`) et confirmer que le nombre de features est non nul pour les scènes contenant des bâtiments. Vérifier le chemin de la couche, quitter le mode édition puis enregistrer les modifications de la couche. Ensuite relancer ce QA : géométries, métriques, masks et overlays; mettre à jour le statut uniquement après validation de tous les contrôles.

## Rapport final

PATCH 01 :
NEEDS_CORRECTION
BUILDINGS : 0 feature persistée; nombre réel non mesurable

PATCH 02 :
NEEDS_CORRECTION
BUILDINGS : 0 feature persistée; nombre réel non mesurable

PATCH 03 :
NEEDS_CORRECTION
BUILDINGS : 0 feature persistée; nombre réel non mesurable

GEOMETRY VALIDITY :
FAILED — aucune géométrie exportée à contrôler

RASTER ALIGNMENT :
VALID — grille raster alignée aux métadonnées; alignement du masque non vérifié car masque absent

OUT_OF_BOUNDS FEATURES :
0 persistée; contrôle spatial impossible sans features

DUPLICATE FEATURES :
0 persistée; contrôle des doublons impossible sans features

GT MASKS QA :
FAILED — aucun masque généré, annotations absentes

OVERLAYS QA :
FAILED — aucun overlay humain généré, contours absents

PATCHES READY_FOR_VALIDATION :
0 / 3

NEXT STEP :
CORRECT FIRST 3 PATCHES
