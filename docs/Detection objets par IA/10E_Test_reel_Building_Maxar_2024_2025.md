# Étape 10E — Test réel Building sur Maxar 2024 et 2025

Date d’exécution : 14 octobre 2026  
Objectif unique : observer le fonctionnement actuel de `AI Object Detection → Building` sur les deux vraies images Maxar disponibles.  
Hors portée : annotation, calibration scientifique, fine-tuning et Building Change Detection.

## 1. Données et dérivés utilisés

Les entrées sont les GeoTIFF RGB géoréférencés préparés à l’étape 10C :

- 2024 : `test-data/validation-results/maxar_rgb_derivatives/maxar_2024_rgb_p2p98.tif` ;
- 2025 : `test-data/validation-results/maxar_rgb_derivatives/maxar_2025_rgb_p2p98.tif`.

Les PNG/JPG preview n’ont pas été utilisés comme entrée. Les COG originaux huit bandes `uint16` n’ont pas été envoyés à `LocalRasterSource`.

Les deux dérivés ont été vérifiés : 3 bandes `uint8`, ColorInterp RGB, EPSG:32637, résolution 0,35 m, transform et bounds identiques, dimensions 2 048 × 2 048, masque interne géré sans NoData numérique.

## 2. Baseline identique

```text
model                  = unet_best.pt
model_mode             = REAL
RGB mapping            = Maxar Rasterio 5 / 3 / 2
stretch                = p2–p98 par canal
probability_threshold  = 0.50
tile_size              = 640
overlap_ratio          = 0.20
stride                 = 512
min_object_pixels      = 4
hole filling           = max_hole_pixels=0
morphology             = opening=false, closing=false, kernel=3, iterations=1
```

Aucun paramètre n’a été changé entre 2024 et 2025.

## 3. Parcours réel exécuté

Pour chaque date, le fichier a été envoyé par HTTP au workflow utilisateur :

```text
LocalRasterSource
→ ImageValidator
→ RGBOrthophotoProfile
→ TilingService
→ PreparedTile
→ BuildingModelAdapter REAL
→ InferenceService
→ PostProcessingService
→ BuildingPolygonizationService
→ BuildingResultsService
```

Les `raster_id` et `analysis_id` sont conservés dans `comparison_summary.json`. Les caches d’upload temporaires ont été supprimés après production des artefacts.

## 4. Vérification des dérivés

| Propriété | 2024 | 2025 |
|---|---:|---:|
| Dimensions | 2 048 × 2 048 | 2 048 × 2 048 |
| Bandes / dtype | 3 × uint8 | 3 × uint8 |
| ColorInterp | red, green, blue | red, green, blue |
| CRS | EPSG:32637 | EPSG:32637 |
| Résolution | 0,35 × 0,35 m | 0,35 × 0,35 m |
| Bounds | 582091,891478 ; 2367464,037368 ; 582808,691478 ; 2368180,837368 | identiques |
| NoData | aucun ; masque interne | aucun ; masque interne |
| Profil | `rgb_orthophoto_uint8_v1` | `rgb_orthophoto_uint8_v1` |
| LocalRasterSource | accepté | accepté |

## 5. Résultats 2024

| Indicateur | Valeur |
|---|---:|
| Raster ID | `ai-ortho-f1749c2e0816-3882a676ca4a-7fcfad8cca77` |
| Analysis ID | `building-analysis-3aa922f7a8e6473cb44b9108fe549d56` |
| Tiles total / traitées / ignorées | 16 / 16 / 0 |
| Inference | 16 584,26 ms |
| Post-processing | 16 775,65 ms |
| Polygonisation | 87,68 ms |
| Results | 14,24 ms |
| Temps upload + tuilage + inférence + results | 34,49 s |
| Positive pixels globaux avant nettoyage | 5 217 |
| Positive pixel ratio | 0,1244 % |
| Candidate count | 13 |
| Surface totale | 638,715 m² |
| Surface moyenne | 49,1319 m² |
| Surface médiane | 39,4450 m² |
| Surface minimale | 0,6125 m² |
| Surface maximale | 195,3875 m² |

## 6. Résultats 2025

| Indicateur | Valeur |
|---|---:|
| Raster ID | `ai-ortho-cba9a8be71b6-3882a676ca4a-e4fb2d8967bf` |
| Analysis ID | `building-analysis-954819991c08463ab4a7ccacbb4467a5` |
| Tiles total / traitées / ignorées | 16 / 16 / 0 |
| Inference | 17 129,67 ms |
| Post-processing | 18 581,87 ms |
| Polygonisation | 150,49 ms |
| Results | 25,01 ms |
| Temps upload + tuilage + inférence + results | 36,76 s |
| Positive pixels globaux avant nettoyage | 7 193 |
| Positive pixel ratio | 0,1715 % |
| Candidate count | 22 |
| Surface totale | 880,775 m² |
| Surface moyenne | 40,0352 m² |
| Surface médiane | 20,4575 m² |
| Surface minimale | 0,4900 m² |
| Surface maximale | 108,6575 m² |

Le `positive_pixel_count` publié ici est celui du masque global fusionné avant suppression des petits objets. Le compteur tuile-par-tuile de l’endpoint d’inférence est conservé séparément dans la synthèse, car il compte les pixels recouverts plusieurs fois par les overlaps.

## 7. Comparaison technique 2024/2025

| Indicateur | 2024 | 2025 | Différence 2025−2024 |
|---|---:|---:|---:|
| Candidate count | 13 | 22 | +9 |
| Surface totale m² | 638,715 | 880,775 | +242,060 |
| Surface moyenne m² | 49,1319 | 40,0352 | -9,0967 |
| Surface médiane m² | 39,4450 | 20,4575 | -18,9875 |
| Positive pixels globaux | 5 217 | 7 193 | +1 976 |
| Positive ratio | 0,1244 % | 0,1715 % | +0,0471 point |
| Tiles traitées | 16 | 16 | 0 |
| Temps total | 34,49 s | 36,76 s | +2,26 s |

Ces différences sont uniquement des différences techniques de réponse du pipeline sur deux acquisitions. Elles ne sont pas nommées « nouveaux bâtiments », « démolitions » ou « changement de bâtiment ».

## 8. Exports et visualisations

Le dossier [real-building-test](../../test-data/validation-results/real-building-test/) contient pour chaque date : GeoJSON, CSV, ZIP, résultat JSON et overlay PNG, ainsi qu’une comparaison côte à côte et `comparison_summary.json` à sa racine.

Les GeoJSON restent les sorties SIG de référence ; les PNG sont uniquement des visualisations.

## 9. Inspection visuelle

Les overlays montrent quelques correspondances claires sur des toitures contrastées, mais de nombreux bâtiments évidents non détectés, des empreintes fragmentaires et des grandes toitures parfois seulement partiellement détectées. Les petites toitures sont rarement détectées. Il n’y a pas de masque continu systématique sur les routes principales ou les sols nus, mais quelques réponses ambiguës apparaissent sur des objets très contrastés.

La réponse est fonctionnelle mais faible et non exhaustive.

## 10. Alignement spatial

Alignement spatial validé visuellement : absence de décalage systématique, pas d’inversion X/Y, transform EPSG:32637 conservée, polygonisation WGS84 correctement superposable, même grille et mêmes bounds pour les deux dates.

## 11. Frontend réel

Le navigateur contrôlé n’était pas disponible dans cette exécution. Le test frontend manuel est donc documenté comme `MANUAL_BROWSER_TEST = NOT_AVAILABLE`. Le backend réel et les artefacts visibles ont été testés ; aucun échec frontend n’est inféré de cette indisponibilité.

## 12. Limitations et recommandation

- aucune vérité terrain disponible ;
- aucune Precision/Recall/F1/IoU calculée ;
- résultat limité à la sous-zone commune 2 048² ;
- qualité visuelle faible et nombreux faux négatifs ;
- comparaison 2024/2025 non interprétable comme changement bâti ;
- test navigateur non disponible.

Recommandation suivante : faire annoter les patches préparés à l’étape 10D, puis exécuter le baseline objectif pixel/objet avant toute décision de calibration ou de fine-tuning. Ne pas développer Building Change Detection à ce stade.

TEST RÉEL BUILDING — STATUT :
VALIDÉ

2024 PIPELINE :
VALIDÉ

2025 PIPELINE :
VALIDÉ

REAL MODEL :
OUI

THRESHOLD :
0.50

2024 BUILDING CANDIDATES :
13

2025 BUILDING CANDIDATES :
22

SPATIAL ALIGNMENT :
VALIDÉ

EXPORTS :
VALIDÉS

FRONTEND REAL TEST :
NON DISPONIBLE

GROUND TRUTH :
NON DISPONIBLE

SCIENTIFIC ACCURACY :
NON VALIDÉE

MODEL QUALITY ON MAXAR :
FAIBLE

PRÊT POUR ÉTAPE SUIVANTE :
NON
