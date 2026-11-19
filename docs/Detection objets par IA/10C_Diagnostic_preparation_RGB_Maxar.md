# Étape 10C — Diagnostic et préparation RGB des orthophotos Maxar

Date d'exécution : 14 octobre 2026  
Portée : diagnostic radiométrique, dérivés techniques et réponse du modèle Building existant.  
Hors portée respectée : aucune modification de l'architecture IA, du frontend, du checkpoint `unet_best.pt`, des analyses historiques ou des exports ; aucun entraînement, fine-tuning ou Building Change Detection.

## 1. Résumé exécutif

Les deux COG Maxar sont des produits géospatiaux valides, pansharpened et corrigés ACOMP, mais ils ne satisfont pas directement le contrat `LocalRasterSource` : huit bandes `uint16`, 1,32 à 1,46 Go et environ 97 à 104 millions de pixels. Le mapping RGB prouvé par les métadonnées Maxar est R=5, G=3, B=2 en index Rasterio 1-based.

Six sous-zones RGB `uint8`, strictement alignées, ont été produites sans écraser les originaux. Les trois stratégies testées sont `0–16383`, `p2–p98` et `p1–p99`. Tous les dérivés passent réellement par l'API `POST /api/ai/raster/local`, `ImageValidator`, `RGBOrthophotoProfile` et `TilingService`.

`p2–p98` est le meilleur rendu humain et fournit le plus de signal au modèle à seuil constant. Il ne résout toutefois pas la détection clairsemée : à 0,50, seuls 0,124 % des pixels 2024 et 0,171 % des pixels 2025 sont positifs. Le filtre `min_object_pixels=4` ne supprime que trois pixels sur 5 217 dans le cas diagnostiqué. Le facteur limitant principal est donc vraisemblablement un écart de domaine du modèle, avec des effets secondaires du stretch et du seuil. Sans vérité terrain, cette conclusion reste un diagnostic technique et non une mesure d'exactitude.

## 2. Audit des COG originaux

| Propriété | 2024-10-07 | 2025-07-28 |
|---|---:|---:|
| Dimensions | 10 662 × 9 715 | 10 292 × 9 378 |
| Pixels | 103 581 330 | 96 518 376 |
| Bandes / type | 8 × uint16 | 8 × uint16 |
| Taille | 1 456 282 838 octets | 1 323 007 113 octets |
| CRS | EPSG:4326 | EPSG:4326 |
| Résolution raster | 3,072320997e-6° | 3,182876995e-6° × 3,182877002e-6° |
| GSD déclaré SkyWatch | 0,34 m | 0,35 m |
| NoData | 0 | 0 |
| Bounds | 39,779133937 ; 21,395880013 ; 39,811891023 ; 21,425727611 | 39,779133395 ; 21,395878478 ; 39,811891565 ; 21,425727498 |
| ColorInterp | gray, puis 7 × undefined | gray, puis 7 × undefined |
| Descriptions internes | absentes | absentes |
| Tuilage / compression | blocs 512², DEFLATE, interleave BAND, COG | blocs 512², DEFLATE, interleave BAND, COG |
| Overviews | 2, 4, 8, 16, 32, 64, 127 | 2, 4, 8, 16, 32, 64, 127 |

Transform 2024 : `(3.072320997e-6, 0, 39.7791339367, 0, -3.072320997e-6, 21.4257276112)`.  
Transform 2025 : `(3.182876995e-6, 0, 39.7791333950, 0, -3.182877002e-6, 21.4257274981)`.

Les tags raster sont `AREA_OR_POINT=Area`; les tags `IMAGE_STRUCTURE` confirment `LAYOUT=COG`, `COMPRESSION=DEFLATE`, `INTERLEAVE=BAND`. Les tags par bande de l'auxiliaire XML contiennent des statistiques GDAL approximatives. Le manifeste complet conserve tous les tags, les blocs et les overviews.

## 3. Bandes Maxar et mapping RGB

Les fichiers JSON Maxar/SkyWatch identifient, dans l'ordre :

1. Coastal Blue ;
2. Blue ;
3. Green ;
4. Yellow ;
5. Red ;
6. Red Edge ;
7. NIR/NIR1 ;
8. NIR2.

Mapping retenu : `red_band_index=5`, `green_band_index=3`, `blue_band_index=2`.

Les métadonnées déclarent `pansharpening_applied=true`, `atmospheric_correction=ACOMP` et `mosaic_normalization_applied=false`. Les PNG visual sont RGB, mais leurs dimensions diffèrent des COG (2024 : 10 309 × 10 089 ; 2025 : 9 951 × 9 739), sans géoréférencement ni recette d'affichage. Ils ne permettent donc ni une correspondance pixel-à-pixel ni la reproduction fiable d'un « visual-style stretch ». Ils n'ont pas été utilisés par le modèle.

## 4. Statistiques radiométriques

Méthode : échantillonnage déterministe nearest-neighbour ramenant le plus grand côté à 2 048 pixels, exclusion du NoData, puis percentiles sur environ 3,17 millions de valeurs valides par bande. Ces percentiles sont des estimations documentées, pas un histogramme exhaustif des 100 millions de pixels. Le taux NoData échantillonné est 16,989 % en 2024 et 16,998 % en 2025.

### 2024

| # | Bande | Min | Max | Moy. | p1 | p2 | p5 | p50 | p95 | p98 | p99 | Saturés 16383 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Coastal Blue | 1 | 9 508 | 2 063,905 | 957 | 1 026 | 1 131 | 1 867 | 3 818 | 4 730 | 5 220,98 | 0 |
| 2 | Blue | 145 | 11 054 | 2 429,390 | 1 050 | 1 135 | 1 250 | 2 206 | 4 635 | 5 638 | 6 182 | 0 |
| 3 | Green | 451 | 12 228 | 3 150,539 | 1 452 | 1 519 | 1 625 | 2 910 | 5 923 | 6 829 | 7 288 | 0 |
| 4 | Yellow | 682 | 15 747 | 3 616,053 | 1 623 | 1 712 | 1 859 | 3 377 | 6 715 | 7 495 | 7 984 | 0 |
| 5 | Red | 529 | 16 383 | 3 850,831 | 1 653 | 1 778 | 1 956 | 3 612 | 7 129 | 7 881 | 8 407 | 13 |
| 6 | Red Edge | 850 | 15 089 | 3 935,922 | 1 756 | 1 845 | 2 021 | 3 706 | 7 212 | 7 926 | 8 445 | 0 |
| 7 | NIR1 | 937 | 15 813 | 4 045,458 | 1 806 | 1 911 | 2 116 | 3 864 | 7 188 | 7 886 | 8 390 | 0 |
| 8 | NIR2 | 918 | 15 955 | 4 270,037 | 1 895 | 2 015 | 2 243 | 4 103 | 7 429 | 8 154 | 8 671 | 0 |

### 2025

| # | Bande | Min | Max | Moy. | p1 | p2 | p5 | p50 | p95 | p98 | p99 | Saturés 16383 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Coastal Blue | 181 | 9 393 | 1 907,919 | 1 014 | 1 071 | 1 151 | 1 746 | 3 401 | 4 192 | 4 728 | 0 |
| 2 | Blue | 370 | 11 712 | 2 674,821 | 1 487 | 1 551 | 1 645 | 2 484 | 4 660 | 5 609 | 6 225 | 0 |
| 3 | Green | 686 | 14 337 | 3 802,202 | 2 199 | 2 273 | 2 391 | 3 603 | 6 394 | 7 361 | 7 958 | 0 |
| 4 | Yellow | 852 | 16 383 | 4 180,585 | 2 339 | 2 439 | 2 580 | 4 012 | 6 961 | 7 759 | 8 260 | 7 |
| 5 | Red | 865 | 16 383 | 4 327,373 | 2 360 | 2 476 | 2 630 | 4 163 | 7 210 | 7 936 | 8 425 | 10 |
| 6 | Red Edge | 501 | 16 383 | 4 111,221 | 2 286 | 2 368 | 2 503 | 3 966 | 6 764 | 7 414 | 7 869 | 17 |
| 7 | NIR1 | 808 | 16 383 | 4 492,456 | 2 512 | 2 601 | 2 755 | 4 364 | 7 232 | 7 897 | 8 376 | 223 |
| 8 | NIR2 | 980 | 16 383 | 4 559,561 | 2 553 | 2 646 | 2 807 | 4 454 | 7 193 | 7 842 | 8 309 | 369 |

La dynamique utile RGB se situe très en dessous de 16 383. La conversion fixe comprime donc fortement le contraste. La saturation 14 bits est négligeable dans R/G/B.

## 5. Convertisseur et stratégies

Outil isolé : `backend/scripts/maxar_rgb_debug_converter.py`. Il reprojette les bandes 5/3/2 sur une grille commune EPSG:32637 de 2 048 × 2 048 pixels à 0,35 m, applique le stretch par canal, écrit un GeoTIFF RGB `uint8` tuilé/DEFLATE avec masque interne et overviews, puis génère un quicklook PNG distinct.

Grille commune : bounds `[582091,891478 ; 2367464,037368 ; 582808,691478 ; 2368180,837368]`, surface 716,8 × 716,8 m, 4 194 304 pixels valides, 16 tuiles IA de 640 pixels avec overlap 20 %.

| Stratégie | Bornes RGB 2024 | Bornes RGB 2025 | Conclusion visuelle |
|---|---|---|---|
| minmax | 0–16383 pour chaque canal | 0–16383 pour chaque canal | nettement sous-exposé, contraste faible |
| p2–p98 | R 1778–7881 ; G 1519–6829 ; B 1135–5638 | R 2476–7936 ; G 2273–7361 ; B 1551–5609 | meilleur contraste des toits/ombres, quelques hautes lumières saturées |
| p1–p99 | R 1653–8407 ; G 1452–7288 ; B 1050–6182 | R 2360–8425 ; G 2199–7958 ; B 1487–6225 | rendu naturel, légèrement moins contrasté |
| metadata scale/offset | non applicable | non applicable | Rasterio indique scale=1, offset=0 ; `ABSCALFACTOR` n'est pas un stretch d'affichage |
| visual-style | non reproductible | non reproductible | dimensions différentes et recette absente |

## 6. Fichiers produits

Dans `test-data/validation-results/maxar_rgb_derivatives/` :

- `maxar_2024_rgb_minmax.tif`, `maxar_2024_rgb_p2p98.tif`, `maxar_2024_rgb_p1p99.tif` ;
- `maxar_2025_rgb_minmax.tif`, `maxar_2025_rgb_p2p98.tif`, `maxar_2025_rgb_p1p99.tif` ;
- un PNG quicklook par GeoTIFF ;
- `quicklook_comparison.png` ;
- `manifest.json` avec audit, statistiques, mapping et paramètres ;
- `ai_diagnostics.json` avec les résultats API ;
- overlays et GeoJSON de debug `p2p98` à 0,30 et 0,50.

Les six GeoTIFF font 6,14 à 9,33 Mo. Les originaux n'ont pas été modifiés.

## 7. Compatibilité GeoRaster réelle

Les six fichiers ont été envoyés individuellement par `POST /api/ai/raster/local` avec mapping explicite 1/2/3. Tous sont acceptés comme : 3 bandes `uint8`, EPSG:32637, résolution 0,35 m, ColorInterp red/green/blue, profil `rgb_orthophoto_uint8_v1`, 16 tuiles valides sur 16. Il ne s'agit pas d'un accès direct au chemin disque : chaque test passe bien par l'upload utilisateur et le cache serveur contrôlé.

## 8. Réponse IA par dérivé à threshold 0,50

Le nombre de pixels est mesuré sur le masque global fusionné avant suppression des petits objets. Le temps masque et le temps résultat sont deux appels HTTP complets indépendants incluant chacun l'inférence CPU.

| Date | Stretch | Pixels positifs bruts | Ratio positif | Candidats | Surface totale m² | Temps masque s | Temps résultat s |
|---|---|---:|---:|---:|---:|---:|---:|
| 2024 | minmax | 4 100 | 0,0978 % | 10 | 502,25 | 18,39 | 15,92 |
| 2024 | p1–p99 | 4 698 | 0,1120 % | 11 | 575,505 | 16,15 | 16,17 |
| 2024 | p2–p98 | 5 217 | 0,1244 % | 13 | 638,715 | 17,29 | 19,56 |
| 2025 | minmax | 3 326 | 0,0793 % | 13 | 407,0675 | 16,74 | 17,57 |
| 2025 | p1–p99 | 5 128 | 0,1223 % | 17 | 628,18 | 17,09 | 17,19 |
| 2025 | p2–p98 | 7 193 | 0,1715 % | 22 | 880,775 | 15,93 | 17,35 |

`p2–p98` est donc retenu comme meilleure stratégie RGB de debug. Cette sélection combine lisibilité humaine et augmentation du signal, pas une exactitude scientifique.

## 9. Test limité des thresholds sur p2–p98

| Date | Threshold | Pixels positifs bruts | Ratio positif | Candidats | Surface totale m² |
|---|---:|---:|---:|---:|---:|
| 2024 | 0,30 | 10 199 | 0,2432 % | 36 | 1 248,52 |
| 2024 | 0,40 | 7 824 | 0,1865 % | 23 | 958,195 |
| 2024 | 0,50 | 5 217 | 0,1244 % | 13 | 638,715 |
| 2024 | 0,60 | 4 550 | 0,1085 % | 12 | 557,0075 |
| 2025 | 0,30 | 11 189 | 0,2668 % | 38 | 1 370,1625 |
| 2025 | 0,40 | 9 093 | 0,2168 % | 34 | 1 113,8925 |
| 2025 | 0,50 | 7 193 | 0,1715 % | 22 | 880,775 |
| 2025 | 0,60 | 5 921 | 0,1412 % | 18 | 724,955 |

Le seuil 0,30 produit davantage de fragments sur des toitures très contrastées, mais la majorité du bâti dense reste absente et aucune vérité terrain ne permet de qualifier ces ajouts en vrais ou faux positifs. Hypothèse d'inspection : 0,30–0,40 peut servir à une revue visuelle à rappel potentiellement supérieur. Décision de configuration : le défaut reste 0,50.

## 10. Comparaison visuelle 2024/2025

Les deux dates montrent les mêmes tendances : détections ponctuelles sur des parties de grandes toitures claires ou contrastées, nombreux bâtiments manqués, contours souvent petits et fragmentaires. Aucun décalage spatial systématique n'est visible : les polygones présents suivent correctement les éléments de l'orthophoto. Les routes principales et les vastes sols nus ne deviennent pas des masques continus, mais quelques réponses ambiguës apparaissent sur de petits objets très contrastés. La différence de nombre 2024/2025 ne doit pas être interprétée comme un changement bâti : la radiométrie, l'acquisition et la réponse modèle diffèrent.

## 11. Effet du post-processing

Cas isolé : 2024, p2–p98, threshold 0,50.

| Variante | Pixels positifs | Écart vs brut |
|---|---:|---:|
| min_object_pixels=1 (brut utile) | 5 217 | 0 |
| min_object_pixels=4 (défaut) | 5 214 | -3 |
| + hole filling max 64 | 5 214 | -3 |
| + opening 3×3 | 5 184 | -33 |
| + closing 3×3 | 5 218 | +1 |

Le filtre minimal ne retire que 0,057 % du signal brut. `hole filling=64` ne change rien dans cet échantillon ; opening/closing ont un effet minime. Le post-processing par défaut n'est pas responsable de l'absence massive de bâtiments. Aucun de ces paramètres n'est modifié dans la configuration produit.

## 12. Diagnostic principal

- Mauvais mapping RGB : écarté par les métadonnées Maxar.
- Mauvaise conversion radiométrique : facteur secondaire réel ; p2–p98 augmente le signal, mais ne restaure pas une segmentation complète.
- Contraste insuffisant : confirmé pour le min/max fixe, amélioré par p2–p98.
- Résolution : 0,34–0,35 m est très détaillée et peut différer de la distribution d'entraînement ; le modèle redimensionne aussi chaque tuile 640 vers sa taille d'entrée effective.
- Threshold trop strict : facteur secondaire ; 0,30 augmente les fragments, sans résoudre les nombreux manques.
- Post-processing trop agressif : écarté pour la configuration actuelle.
- Domaine d'entraînement / généralisation : facteur le plus probable. Le modèle applique en outre un z-score par canal et par tuile ; les changements linéaires de stretch sont en partie neutralisés, sauf clipping et quantification. La réponse demeure faible malgré un RGB visuellement correct.

Conclusion : `MODEL DOMAIN GAP` est le facteur limitant principal le mieux soutenu par les observations, sans prétendre le prouver scientifiquement faute de vérité terrain.

## 13. Limitations

- aucune couche bâtiment de référence ;
- aucune Precision, Recall, F1 ou IoU calculable ;
- percentiles estimés sur échantillon, non exhaustifs ;
- sous-zone de 716,8 m seulement, choisie pour rester sous la limite de 25 millions de pixels ;
- comparaison multi-date non utilisable comme Change Detection ;
- PNG visual non géoréférencés et non reproductibles ;
- appréciations « faux positifs/faux négatifs » uniquement visuelles ;
- CPU et appels répétés : les temps caractérisent ce poste, pas une infrastructure de production.

## 14. Recommandations immédiates

1. Utiliser `p2–p98` comme préparation Maxar de debug explicite, sans l'intégrer encore au pipeline principal.
2. Conserver `threshold=0,50` par défaut ; proposer 0,30–0,40 uniquement comme mode d'inspection non calibré.
3. Acquérir une vérité terrain bâtiment datée et alignée sur plusieurs zones Maxar représentatives.
4. Mesurer pixel/object metrics avant toute décision de seuil ou de fine-tuning.
5. Si les métriques confirment le diagnostic, constituer un jeu d'entraînement/validation Maxar à 0,30–0,40 m avec annotations contrôlées, puis évaluer un fine-tuning séparé.
6. Ne pas démarrer Building Change Detection tant que la détection mono-date n'est pas fiable sur les deux dates.

## 15. Tests et traçabilité

- tests dédiés du convertisseur : 3 passed ;
- backend complet : 205 passed, 0 failed ;
- frontend : non relancé, car aucun fichier frontend ni contrat public n'a été modifié ;
- modèle : checkpoint existant `unet_best.pt`, mode REAL, U-Net/ResNet-34, CPU ;
- fichiers de preuve : `manifest.json`, `ai_diagnostics.json`, quicklooks, overlays et GeoJSON de debug dans le dossier des dérivés.

ÉTAPE 10C — STATUT :
VALIDÉE

MAXAR ORIGINALS :
VALIDES

RGB DERIVATIVES :
VALIDÉS

BEST RGB STRATEGY :
p2–p98 PAR CANAL SUR RGB 5/3/2

MODEL RESPONSE :
FAIBLE

MAIN LIMITING FACTOR :
MODEL DOMAIN GAP

GROUND TRUTH :
NON DISPONIBLE

SCIENTIFIC ACCURACY :
NON VALIDÉE

PRÊT POUR CHANGE DETECTION BUILDING :
NON

PRÊT POUR FINE-TUNING :
NON
