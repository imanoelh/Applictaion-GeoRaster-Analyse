# Étape 10 réelle — validation des orthophotos 2024 et 2025

Date de validation : 14 octobre 2026.

## 1. Conclusion exécutive

Deux vrais produits Maxar/SkyWatch haute résolution ont été audités. Ce sont des COG géoréférencés de bonne qualité, mais ils ne respectent pas directement le contrat `LocalRasterSource` actuel : **8 bandes UInt16**, plus de 1,2 Gio chacun, contre **3 bandes RGB uint8** et 512 Mio maximum. Les imports originaux ont donc été refusés proprement par l’API (`HTTP 422`) et aucun seuil ni limite n’a été relevé.

Pour tester le reste du pipeline sans modifier son architecture, deux sous-zones techniques alignées ont été dérivées des COG : bandes Maxar `R=5`, `G=3`, `B=2`, conversion fixe 14 bits vers uint8, grille commune EPSG:32637 à 0,35 m/pixel, 2048 × 2048 pixels. Elles ont validé le modèle réel, le post-traitement, la polygonisation, les résultats et les exports.

Cette validation est **technique et partielle**. Elle ne rend pas les COG originaux directement compatibles et ne mesure pas l’exactitude scientifique.

## 2. Inventaire des fichiers

| Date | Fichier | Extension | Taille | Rôle | Utilisable directement par l’IA |
|---|---|---:|---:|---|---|
| 2024-10-07 | `24OCT07075514-S3DS-200009702746_01_P001_COG.tif` | TIF | 1 456 282 838 o | COG multispectral principal | Non : 8 bandes UInt16 et > 512 Mio |
| 2024-10-07 | `...COG.tif.aux.xml` | XML | 55 571 o | Statistiques GDAL auxiliaires | Métadonnées seulement |
| 2024-10-07 | `...SkyWatch_metadata.json` | JSON | 14 792 o | Métadonnées fournisseur | Métadonnées seulement |
| 2024-10-07 | `...visual.png` | PNG | 142 777 460 o | Aperçu visuel | Non |
| 2025-07-28 | `25JUL28115945-S3DS-200009702745_01_P001_COG.tif` | TIF | 1 323 007 113 o | COG multispectral principal | Non : 8 bandes UInt16 et > 512 Mio |
| 2025-07-28 | `...COG.tif.aux.xml` | XML | 52 747 o | Statistiques GDAL auxiliaires | Métadonnées seulement |
| 2025-07-28 | `...COG.tif.enp` | ENP | 514 606 322 o | Sidecar propriétaire | Non |
| 2025-07-28 | `...SkyWatch_metadata.json` | JSON | 14 795 o | Métadonnées fournisseur | Métadonnées seulement |
| 2025-07-28 | `...visual.png` | PNG | 124 202 404 o | Aperçu visuel | Non |
| 2025-07-28 | `...visual.png.enp` | ENP | 47 109 808 o | Sidecar propriétaire de l’aperçu | Non |

Les PNG n’ont jamais été utilisés comme entrée du pipeline.

## 3. Validation Rasterio des COG originaux

| Propriété | 2024-10-07 | 2025-07-28 |
|---|---:|---:|
| Driver | GTiff | GTiff |
| Dimensions | 10 662 × 9 715 | 10 292 × 9 378 |
| Pixels | 103 581 330 | 96 518 376 |
| Bandes | 8 | 8 |
| Dtype | uint16 × 8 | uint16 × 8 |
| CRS | EPSG:4326 | EPSG:4326 |
| Résolution native | 3,072320997e-6° | 3,182876998e-6° |
| GSD calculé au centre | 0,318 × 0,340 m | 0,330 × 0,352 m |
| GSD fournisseur | 0,34 m | 0,35 m |
| NoData | 0 | 0 |
| NoData échantillonné | 16,989 % | 16,998 % |
| Compression | DEFLATE | DEFLATE |
| Tuilé | Oui, blocs 512 × 512 | Oui, blocs 512 × 512 |
| Interleave | BAND | BAND |
| Overviews | 2, 4, 8, 16, 32, 64, 127 | 2, 4, 8, 16, 32, 64, 127 |
| Tag COG | `LAYOUT=COG` | `LAYOUT=COG` |
| ColorInterp | bande 1 gray, autres undefined | bande 1 gray, autres undefined |
| Descriptions internes | absentes | absentes |

Transform 2024 :

```text
[3.072320997236484e-06, 0, 39.77913393674901,
 0, -3.072320997236484e-06, 21.425727611232002]
```

Transform 2025 :

```text
[3.182876995269734e-06, 0, 39.77913339495801,
 0, -3.1828770016308434e-06, 21.425727498120004]
```

Bounds natifs et WGS84 :

| Date | Ouest | Sud | Est | Nord |
|---|---:|---:|---:|---:|
| 2024 | 39.77913393674901 | 21.39588001274385 | 39.81189102322155 | 21.425727611232002 |
| 2025 | 39.77913339495801 | 21.39587847759871 | 39.811891564993324 | 21.425727498120004 |

## 4. Bandes et statistiques échantillonnées

La métadonnée SkyWatch identifie : 1 Coastal Blue, 2 Blue, 3 Green, 4 Yellow, 5 Red, 6 Red Edge, 7 NIR, 8 NIR2. Le vrai mapping RGB est donc **5/3/2**. `ColorInterp` seul ne permettait pas de le déduire.

Statistiques calculées sur un échantillon 1867 × 2048 par bande :

| Date | Bande | Min | P1 | Médiane | Moyenne | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 1 | 1 | 958 | 1867 | 2063,71 | 5218 | 9508 |
| 2024 | 2 Blue | 136 | 1052 | 2208 | 2429,13 | 6179 | 11087 |
| 2024 | 3 Green | 451 | 1452 | 2910 | 3150,23 | 7286 | 12228 |
| 2024 | 4 | 641 | 1626 | 3377 | 3615,68 | 7982 | 15747 |
| 2024 | 5 Red | 529 | 1655 | 3612 | 3850,42 | 8401 | 16383 |
| 2024 | 6 | 850 | 1756 | 3706 | 3935,52 | 8440 | 15375 |
| 2024 | 7 | 937 | 1806 | 3864 | 4045,07 | 8385 | 16031 |
| 2024 | 8 | 918 | 1895 | 4103 | 4269,65 | 8666 | 16020 |
| 2025 | 1 | 181 | 1014 | 1746 | 1907,64 | 4727 | 9393 |
| 2025 | 2 Blue | 370 | 1488 | 2484 | 2674,45 | 6225 | 11712 |
| 2025 | 3 Green | 686 | 2199 | 3603 | 3801,74 | 7956 | 14377 |
| 2025 | 4 | 852 | 2339 | 4012 | 4180,08 | 8257 | 16383 |
| 2025 | 5 Red | 865 | 2360 | 4163 | 4326,84 | 8421 | 16383 |
| 2025 | 6 | 501 | 2286 | 3966 | 4110,73 | 7863 | 16383 |
| 2025 | 7 | 808 | 2512 | 4364 | 4491,94 | 8373 | 16383 |
| 2025 | 8 | 980 | 2553 | 4454 | 4559,06 | 8305 | 16383 |

## 5. Compatibilité et mémoire

### COG originaux

```text
ORTHOPHOTO_COMPATIBLE_2024 = NO
ORTHOPHOTO_COMPATIBLE_2025 = NO
```

Causes cumulatives :

1. 8 bandes au lieu d’exactement 3 ;
2. dtype UInt16 au lieu de uint8 ;
3. ordre spectral absent de `ColorInterp` et nécessitant la métadonnée ;
4. fichiers supérieurs à `AI_LOCAL_RASTER_MAX_BYTES=536870912` ;
5. 103,58 M et 96,52 M pixels, supérieurs à `AI_POSTPROCESS_MAX_GLOBAL_PIXELS=25 M`.

L’estimation mémoire conservatrice du post-traitement (`pixels × 16`) serait de 1 657 301 280 octets en 2024 et 1 544 294 016 octets en 2025. Les limites n’ont pas été augmentées.

Les imports API originaux ont retourné :

```text
HTTP 422 — LOCAL_RASTER_INVALID
Le GeoTIFF depasse la taille maximale autorisee (536870912 octets).
```

Les fichiers `.upload-*` temporaires ont été nettoyés.

### Tuilage théorique des originaux

Avec 640 pixels, overlap 20 % et stride 512 :

| Date | Colonnes | Lignes | Total théorique |
|---|---:|---:|---:|
| 2024 | 21 | 19 | 399 |
| 2025 | 20 | 19 | 380 |

Le tuilage effectif n’a pas été lancé sur les originaux, car il aurait contourné le rejet contractuel précédent.

## 6. Sous-zones techniques contrôlées

Deux dérivées ont été produites depuis les COG, jamais depuis les PNG :

- grille commune EPSG:32637 ;
- 2048 × 2048 pixels ;
- 0,35 m/pixel ;
- emprise native `[582091.8914781093, 2367464.0373675325, 582808.6914781093, 2368180.8373675323]` ;
- emprise WGS84 `[39.792037319766514, 21.4075490486379, 39.798987832555014, 21.414057684218903]` ;
- mapping R/G/B = 5/3/2 ;
- conversion fixe `round(clip(value,0,16383) × 255 / 16383)` ;
- trois bandes uint8, ColorInterp red/green/blue ;
- NoData 0 ;
- taille globale 4 194 304 pixels ;
- mémoire post-traitement estimée 67 108 864 octets (64 Mio).

Chaque import API a réussi avec un `raster_id`, un sidecar isolé et le profil `rgb_orthophoto_uint8_v1`. Chaque date produit 16 tuiles, 16 valides, 0 skipped et un ratio valide moyen de 1,0.

## 7. Résultats du modèle réel

Configuration identique : seuil 0,50, tile 640, overlap 0,20, `min_object_pixels=4`, trous désactivés, opening/closing désactivés, connectivité 8 et simplification 0.

| Mesure | 2024-10-07 | 2025-07-28 |
|---|---:|---:|
| Raster ID | `ai-ortho-2262a10ff5ca-001127b57045-4c03d2ba572b` | `ai-ortho-8a2cfdde5ede-001127b57045-2e5e937acb0b` |
| Analysis ID | `building-analysis-666d6f9614244b8880f9583a8fa7a0de` | `building-analysis-e7d54cb3b4c74dbaafa8d80c0e2228bb` |
| Modèle | Kaštela U-Net / ResNet-34 | identique |
| Mode | REAL / CPU | REAL / CPU |
| Version | `sha256-6cd2467e0636` | identique |
| Pixels positifs bruts | 6 691 | 5 545 |
| Temps inférence total | 16 484,71 ms | 18 938,60 ms |
| Moyenne par tuile | 1 030,29 ms | 1 183,66 ms |
| Candidats après post-traitement | 10 | 13 |
| Surface totale | 502,25 m² | 407,0675 m² |
| Surface moyenne | 50,225 m² | 31,3129 m² |
| Post-traitement incluant l’inférence | 17 832,35 ms | 17 874,40 ms |
| Polygonisation | 575,24 ms | 99,79 ms |
| Construction résultats | 88,41 ms | 19,06 ms |
| Appel end-to-end mesuré | 18,70 s | 18,06 s |

Le champ de temps « post-traitement » actuel englobe la consommation du flux d’inférence ; il ne doit pas être additionné au temps d’inférence d’un appel API séparé comme s’il s’agissait du même run.

## 8. Comparaison multi-date

- candidats : 10 en 2024, 13 en 2025, soit un écart de **+3** ;
- surface totale : 502,25 m² en 2024, 407,0675 m² en 2025 ;
- écart de surface candidate : **−95,1825 m²** ;
- les rasters originaux couvrent pratiquement la même zone, mais leurs résolutions et grilles diffèrent légèrement ;
- les dérivées utilisées pour la comparaison ont exactement la même grille et la même emprise.

Ces valeurs sont uniquement des **écarts de candidats IA**. Elles ne démontrent ni construction ni disparition de bâtiments.

## 9. Inspection visuelle et alignement

Le diagnostic superpose les GeoJSON reprojetés aux sous-zones sources. Aucun décalage systématique, aucune inversion X/Y et aucune erreur longitude/latitude n’ont été observés. Les petits contours produits se placent sur les éléments d’image correspondants.

Constats factuels :

- nombreux bâtiments évidents manqués sur les deux dates ;
- détection très clairsemée ;
- plusieurs contours ne couvrent qu’un fragment de toiture ;
- quelques contours suivent des détails très brillants ou contrastés ;
- plusieurs grandes empreintes sont absentes ;
- aucun cas massif de route entière segmentée comme bâtiment ;
- pas de conclusion fiable sur les petits bâtiments denses ;
- différences fortes d’illumination et de radiométrie entre 2024 et 2025.

Le diagnostic est disponible dans `test-data/validation-results/overlay_comparison_2024_2025.png`.

## 10. Exports

Pour chaque date :

- GeoJSON valide, 10 puis 13 features ;
- CSV UTF-8 valide, une ligne, `candidate_count` cohérent ;
- ZIP valide avec `building_candidates.geojson`, `building_statistics.csv` et `building_metadata.json` ;
- `scientific_accuracy_status=NOT_VALIDATED` ;
- `source_type=orthophoto_local` ;
- aucun chemin interne sensible détecté.

Limite constatée : la date d’acquisition n’est pas un champ du `BuildingAnalysisResult`; elle est donc absente du metadata JSON exporté. Les fichiers de validation conservent la date dans leur nom et dans le manifeste, mais cette provenance n’est pas encore portée par le contrat d’export.

## 11. Frontend et non-régression

- frontend HTTP `/map` : 200 OK ;
- tests frontend : réussis, y compris 2 500 features ;
- build client : réussi ;
- build SSR : réussi ;
- backend : **202 passed, 0 failed** avec répertoire temporaire local ;
- compilation Python des quatre scripts : réussie.

Le test manuel dans le navigateur n’a pas pu être certifié : le service natif de contrôle Windows était indisponible après réinitialisation. Les imports et exports ont été testés par les mêmes endpoints que le frontend, mais les clics, popups, légende et téléchargements UI ne sont pas déclarés validés.

## 12. Vérité terrain, seuils et recommandations

Aucune couche SHP, GPKG ou GeoJSON de bâtiments n’a été trouvée. Le GeoJSON présent dans `test-data` est un AOI et n’a pas été utilisé comme vérité terrain.

```text
GROUND_TRUTH = NOT_AVAILABLE
SCIENTIFIC_ACCURACY = NOT_VALIDATED
```

Les seuils 0,40 et 0,60 n’ont pas été testés : sans vérité terrain et avec une conversion radiométrique dérivée, leur comparaison visuelle ne justifierait pas un nouveau défaut. Le seuil reste 0,50.

Recommandations avant calibration ou change detection Building :

1. définir un profil d’ingestion versionné pour Maxar Multi-8 UInt16, incluant une transformation radiométrique approuvée ;
2. éviter d’augmenter simplement les limites : prévoir crop/AOI ou post-traitement bloc par bloc ;
3. porter la date d’acquisition et le produit source dans `BuildingAnalysisResult` et les exports ;
4. obtenir une vérité terrain bâtiment datée ;
5. valider le parcours frontend manuellement ;
6. seulement ensuite évaluer seuil, taille minimale et change detection.

ÉTAPE 10 RÉELLE — STATUT :
PARTIELLEMENT VALIDÉE

ORTHOPHOTO 2024 :
PROBLÈME

ORTHOPHOTO 2025 :
PROBLÈME

GEORASTER COMPATIBILITY :
PROBLÈME

REAL MODEL :
OUI

END-TO-END 2024 :
VALIDÉ

END-TO-END 2025 :
VALIDÉ

FRONTEND REAL TEST :
NON VALIDÉ

EXPORTS :
VALIDÉS

SPATIAL ALIGNMENT :
VALIDÉ

GROUND TRUTH :
NON DISPONIBLE

SCIENTIFIC METRICS :
NON DISPONIBLES

SCIENTIFIC ACCURACY :
NON VALIDÉE

BACKEND REGRESSION :
AUCUNE

FRONTEND BUILD :
SUCCESS

PRÊT POUR CALIBRATION / CHANGE DETECTION BUILDING :
NON
