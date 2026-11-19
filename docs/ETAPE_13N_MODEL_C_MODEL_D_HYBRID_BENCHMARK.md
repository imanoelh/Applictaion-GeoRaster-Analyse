# ÉTAPE 13N — MODEL_C + MODEL_D Hybrid Building Detection Benchmark

## Portée et garde-fous

Benchmark exploratoire effectué sur les six patches TEST verrouillés de 13M. Les seuls prédicteurs utilisés sont les probability maps, masques et GeoJSON archivés sous `backend/data/models/building/experimental/benchmark_13M1B/outputs/`. Aucune inférence fraîche, aucun changement de poids et aucun fine-tuning n’ont été effectués. Les sorties C/D archivées, le GeoPackage humain original, la configuration de production et les traitements GeoRaster n’ont pas été modifiés.

Avant la fusion, les six SHA-256 des images correspondent à la fois au manifeste TEST et aux images archivées du benchmark précédent. Les rasters source, les cartes de probabilité, les masques C/D et les masques de Ground Truth ont tous la même grille : 512 × 512, EPSG:32637, transform affine et bounds identiques. Les probabilités sont dans [0,1]. Le binaire archivé de chaque moteur est exactement reproduit par `probability >= 0.5`; MODEL_D utilise la bande 2 (classe bâtiment) de ses cartes à deux bandes. Les contrôles détaillés sont dans `backend/data/models/building/experimental/benchmark_13N/outputs/grid_validation.json`.

La Ground Truth évaluée est la copie réparée/clippée de 68 features, 80 composantes polygonales, utilisée lors de 13M.1B. Elle reste approximative et ne permet pas d’affirmer une performance scientifique. Le fichier humain original n’a pas été utilisé comme cible modifiable.

## Méthode

Seuil binaire : 0,50. Les métriques pixel sont micro-agrégées sur les six images. Le matching entre composantes C et D est glouton, un-à-un et trié par IoU décroissant; une paire est retenue si IoU > 0,10. Une composante D appariée est `SUPPORTED_BY_C`; sinon elle est `D_ONLY`. Les candidats D-only sont conservés. Pour évaluer les bâtiments, chaque feature Ground Truth est comparée aux composantes prédites à 8 connexions avec matching glouton IoU ≥ 0,50.

La fusion pondérée combine les probabilités brutes; elles peuvent être calibrées différemment entre moteurs. Les poids n’ont pas été optimisés. `HYBRID_D_OBJECT_COVERAGE` conserve tous les composants D et sert à documenter les classes de candidats; son masque est donc identique à D. Pour `HYBRID_C_BOUNDARY_D_COVERAGE`, le footprint C remplace celui de D pour les paires C/D appariées; les objets D sans paire conservent le footprint D. Les composants C non appariés n’y sont pas ajoutés.

## Résultats agrégés

| Variante | IoU | Dice / F1 | Précision | Rappel | Boundary F1 (1 px) | Distance bord moyenne (px) | GT détectés / 68 | GT manqués | Composantes supplémentaires |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MODEL_C_ONLY | 0.303 | 0.465 | **0.585** | 0.386 | 0.233 | 33.94 | 11 | 57 | **80** |
| MODEL_D_ONLY | 0.368 | 0.538 | 0.523 | 0.554 | 0.179 | 16.21 | **18** | 50 | 183 |
| HYBRID_UNION | **0.428** | **0.599** | 0.527 | **0.696** | **0.271** | 19.44 | 16 | 52 | 160 |
| HYBRID_INTERSECTION | 0.211 | 0.349 | **0.613** | 0.244 | 0.137 | 29.42 | 8 | 60 | 107 |
| FUSION_50_50 | 0.342 | 0.510 | 0.585 | 0.452 | 0.185 | 15.78 | 15 | 53 | 187 |
| FUSION_C25_D75 | 0.369 | 0.539 | 0.530 | 0.548 | 0.184 | **14.71** | **18** | 50 | 160 |
| FUSION_C75_D25 | 0.308 | 0.471 | 0.589 | 0.392 | 0.234 | 33.30 | 11 | 57 | 88 |
| HYBRID_D_OBJECT_COVERAGE | 0.368 | 0.538 | 0.523 | 0.554 | 0.179 | 16.21 | 18 | 50 | 183 |
| HYBRID_C_BOUNDARY_D_COVERAGE | 0.386 | 0.557 | 0.543 | 0.572 | 0.214 | 15.51 | 16 | 52 | 153 |

Le meilleur candidat selon le critère d’ingénierie préétabli est `HYBRID_UNION`. Comparé à MODEL_D, il augmente l’IoU de 0,368 à 0,428 et le rappel de 0,554 à 0,696; la précision augmente légèrement de 0,523 à 0,527 et les composantes supplémentaires passent de 183 à 160. Il détecte toutefois 16 features Ground Truth contre 18 pour D seul : le gain pixel ne se traduit donc pas par le meilleur décompte objet. L’intersection est très précise mais perd fortement en rappel. La fusion 25/75 conserve les 18 détections de D et réduit les composantes supplémentaires à 160, mais son gain d’IoU face à D est négligeable (+0,0008).

Les scores de contours sont indicatifs et contradictoires selon la métrique : l’union obtient le Boundary F1 à 1 pixel le plus élevé (0,271), tandis que la distance moyenne de contour la plus faible parmi les variantes est celle de `FUSION_C25_D75` (14,71 px). Aucun de ces résultats ne constitue une validation géométrique des footprints.

## Matching et performances

Sur les six patches, le matching C↔D a identifié 39 paires de composantes par IoU > 0,10; les 162 autres composants D sont `D_ONLY` et n’ont pas été éliminés. Le détail des propriétés D (surface en pixels, probabilité moyenne/maximale, composante C associée et distance des centroïdes) est enregistré dans `d_component_classification.csv`; le résumé par patch est dans `object_matching_summary.csv`.

La construction des variantes de tableaux de probabilité et des masques booléens a pris 0,0368 s au total, soit 0,0061 s/patch. Ce chronométrage exclut le matching C/D, les lectures/écritures raster, le rendu des overlays et l’inférence. L’estimation indicative de deux passages séquentiels, fondée sur les timers archivés 13M.1B (MODEL_C 19,085 s + pipeline GeoAI MODEL_D 18,785 s + fusion mesurée), est d’environ 37,907 s pour les six patches. Les périmètres des deux timers archivés diffèrent; cette somme est une estimation, mais un ensemble exécutant deux moteurs sera plus lent qu’un moteur seul.

## Sorties produites

Toutes les nouvelles sorties sont isolées dans `backend/data/models/building/experimental/benchmark_13N/outputs/` :

- neuf variantes de masques GeoTIFF par patch, sur la grille source;
- overlay RGB de chaque variante;
- GeoJSON polygonisés pour le meilleur candidat `HYBRID_UNION`, sans remplacer les GeoJSON C/D archivés;
- `comparison/contact_sheet_13N.png` : RGB, Ground Truth approximative, C, D et union;
- `comparison/contact_sheet_13N_overlays.png` : GT rouge, C vert, D bleu et union jaune;
- métriques agrégées et par patch, tableau de matching objet et classification des composants D;
- script reproductible `scripts/benchmark_hybrid_13N.py`.

Les overlays ont été inspectés visuellement. Ils montrent la couverture complémentaire des modèles, ainsi que les fausses détections conservées par l’union. Les variantes sont des produits de benchmark uniquement.

## Décision

`HYBRID_IMPROVES_TRADEOFF` selon le critère d’ingénierie de cette étape, grâce au gain d’IoU/rappel et à la baisse du nombre de composantes supplémentaires face à MODEL_D. Cette décision ne recommande pas l’intégration en production : le test reste limité à six patches et à une Ground Truth approximative. MODEL_C reste le défaut de production, MODEL_D reste expérimental et le modèle hybride reste benchmark-only.

GROUND TRUTH :
APPROXIMATE / ENGINEERING ONLY

MODEL_C IOU :
0.303

MODEL_D IOU :
0.368

MODEL_C RECALL :
0.386

MODEL_D RECALL :
0.554

MODEL_C DETECTED OBJECTS :
11

MODEL_D DETECTED OBJECTS :
18

MODEL_C EXTRA COMPONENTS :
80

MODEL_D EXTRA COMPONENTS :
183

HYBRID VARIANTS TESTED :
UNION, INTERSECTION, FUSION_50_50, FUSION_C25_D75, FUSION_C75_D25, D_OBJECT_COVERAGE, C_BOUNDARY_D_COVERAGE

BEST HYBRID :
HYBRID_UNION

BEST HYBRID IOU :
0.428

BEST HYBRID DICE :
0.599

BEST HYBRID PRECISION :
0.527

BEST HYBRID RECALL :
0.696

BEST HYBRID F1 :
0.599

BEST HYBRID BOUNDARY F1 :
0.271

BEST HYBRID DETECTED OBJECTS :
16

BEST HYBRID MISSED OBJECTS :
52

BEST HYBRID EXTRA COMPONENTS :
160

HYBRID POSTPROCESS TIME :
0.0368 seconds total / 0.0061 seconds per patch (fusion arrays only)

BEST DETECTION :
HYBRID (pixel recall); MODEL_D and FUSION_C25_D75 tie at 18 GT objects

BEST PRECISION :
HYBRID (HYBRID_INTERSECTION, 0.613)

BEST RECALL :
HYBRID (HYBRID_UNION, 0.696)

BEST BOUNDARIES :
HYBRID (HYBRID_UNION Boundary F1 = 0.271; FUSION_C25_D75 best mean distance = 14.71 px)

BEST OVERALL ENGINEERING RESULT :
HYBRID (HYBRID_UNION)

ENGINEERING DECISION :
HYBRID_IMPROVES_TRADEOFF

SCIENTIFIC VALIDATION :
NOT CLAIMED

MODEL_C PRODUCTION :
UNCHANGED

MODEL_D :
EXPERIMENTAL

NEXT STEP :
13N.1 INTEGRATE HYBRID EXPERIMENTAL
