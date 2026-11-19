# ÉTAPE 13J.1 — Controlled Building Boundary Refinement

Date : 20 octobre 2026  
Raster source : `ai-ortho-8a2cfdde5ede-001127b57045-ff17132850b4` (2048×2048, 0,35 m/pixel)  
Zones diagnostiques : les 16 fenêtres de l’étape 13J, recalculées sur les probabilités sauvegardées et non sur de nouvelles sorties du modèle.

## Baseline figée

MODEL_C `spacenet2_deeplab`, ONNX Runtime CPU, seuil 0,50, RGB global min-max, tuiles 512×512 et recouvrement 0,20 sont restés identiques. Les cartes de probabilité, masques au seuil 0,50 et polygones de référence sont conservés dans [`test-data/diagnostics/13J`](../test-data/diagnostics/13J/). Les copies de baseline par fenêtre sont également sous `test-data/diagnostics/13J1/zone_*/`.

Aucun code de production, checkpoint, artefact ONNX, seuil de production ou moteur n’a été changé. Les variantes ci-dessous sont produites uniquement dans le dossier de diagnostic 13J.1. Il n’y a pas de vérité terrain annotée ; précision, rappel et F1 ne sont donc pas calculés.

## Variantes et métriques

Les seuils 0,40, 0,45, 0,50, 0,55 et 0,60 ont été testés sur les 16 fenêtres. Pour comparer les contours, chaque variante conserve le nettoyage minimal de production (suppression de composantes de moins de 4 pixels, connectivité 8). Les opérations morphologiques ont été testées séparément avec un carré 3×3 et une itération. Le lissage est une convolution gaussienne séparable 5×5, sigma 0,5 pixel, suivie du seuil 0,50. Les fragments du tableau sont définis comme composantes connexes de moins de 25 pixels (3,0625 m²).

| Variante | Aire vs baseline | Composantes | Fragments <25 px | Périmètre vs baseline | Toitures témoins conservées* |
|---|---:|---:|---:|---:|---:|
| Seuil 0,40 | +11,96 % | +4 | 0 | +12,32 % | 16/16 |
| Seuil 0,45 | +6,01 % | +2 | −1 | +7,05 % | 16/16 |
| Seuil 0,50 (baseline) | 0 % | 0 | 0 | 0 % | 16/16 |
| Seuil 0,55 | −4,03 % | −2 | +2 | −2,87 % | 14/16 |
| Seuil 0,60 | −8,10 % | 0 | +5 | −5,40 % | 13/16 |
| Érosion 3×3 | −14,24 % | −1 | +3 | −5,37 % | 14/16 |
| Dilatation 3×3 | +14,06 % | 0 | −2 | +4,33 % | 16/16 |
| Ouverture 3×3 | −0,40 % | −1 | −1 | −3,14 % | 16/16 |
| Fermeture 3×3 | −0,94 % | 0 | 0 | +2,22 % | 16/16 |
| Gaussien sigma 0,5, seuil 0,50 | −0,10 % | −1 | −1 | −0,45 % | 16/16 |

\* « Conservées » signifie que le polygone témoin garde au moins 50 % de recouvrement avec une composante de la variante. Ce test protège les 16 toitures sélectionnées ; ce n’est pas un rappel sur l’ensemble des bâtiments de l’image.

Les changements les plus forts sont l’érosion et la dilatation : chacune déplace le contour d’environ un pixel sur la plupart des zones, mais change l’aire agrégée d’environ 14 %, ce qui dépasse le critère de stabilité. Les seuils 0,45 et 0,40 grossissent certains contours et ajoutent des composantes ; 0,55 et 0,60 perdent des toitures témoins et/ou augmentent les petits fragments. Aucun seuil alternatif n’est acceptable ici.

L’ouverture est le résultat morphologique le plus équilibré dans ces fenêtres : aire −0,40 %, une composante et un fragment de moins, et les 16 objets témoins demeurent. Toutefois, la contact sheet ne montre pas d’amélioration visuelle constante des bords, et la réduction est d’un seul petit fragment sur le jeu complet. La fermeture conserve le compte mais accroît le périmètre de 2,22 %, cohérent avec des petites jonctions/contours supplémentaires plutôt qu’un lissage démontré. Érosion et dilatation ne sont pas sûres pour l’aire ; aucune combinaison de deux opérations n’a été tentée puisqu’aucune opération individuelle n’a amélioré clairement les contours.

Le lissage gaussien change peu les résultats : −0,10 % d’aire, une composante et un fragment de moins, −0,45 % de périmètre. Le déplacement moyen des frontières par rapport à la baseline est d’environ 0,33 m (0,94 pixel), au maximum 0,35 m dans les 16 fenêtres. Ce déplacement n’établit pas que le contour se rapproche de la toiture sans référence annotée.

Le coût des opérations a été chronométré sur 25 répétitions des 16 fenêtres, hors inférence, E/S et vectorisation complète. Temps médian seuil/filtre/composantes : 0,402 s ; ouverture 0,402 s (−0,16 %, bruit de mesure) ; gaussien 0,409 s (**+1,63 %**). Ce petit coût est mesuré sur des fenêtres ; aucune extrapolation au raster entier n’a été faite. Aucun candidat ne ressortant clairement, le test du raster moyen complet et l’analyse de temps API ont été omis comme prévu par le protocole.

## Contrôle visuel et artefacts

La contact sheet [`baseline_vs_refinement_16_zones.jpg`](../test-data/diagnostics/13J1/baseline_vs_refinement_16_zones.jpg) met côte à côte, pour chacune des 16 fenêtres, l’orthophoto avec le contour baseline, l’ouverture 3×3 et le gaussien. La vue de toutes les variantes est dans [`all_variants_overlay_16_zones.jpg`](../test-data/diagnostics/13J1/all_variants_overlay_16_zones.jpg).

Chaque fenêtre possède son masque baseline et ses masques/polygones diagnostiques sous `test-data/diagnostics/13J1/zone_*/<variant>/`. Les GeoTIFF de ces fenêtres gardent la même grille, le même CRS et la même transformation que l’orthophoto de leur fenêtre. Le résumé complet, par zone et agrégé, est dans [`refinement_metrics.json`](../test-data/diagnostics/13J1/refinement_metrics.json) et [`refinement_summary.csv`](../test-data/diagnostics/13J1/refinement_summary.csv).

### Décision

**Aucun raffinement léger n’améliore clairement les frontières.** L’ouverture et le filtre gaussien sont presque neutres et éliminent seulement un fragment de moins de 25 pixels parmi les 16 fenêtres ; les autres variantes changent trop l’aire, érodent ou agrandissent des objets, ou perdent des petites toitures. La qualité visuelle est donc **SIMILAR**, pas améliorée de manière démontrable. Il n’y a pas de configuration expérimentale à retenir ni de raison de modifier le traitement de production.

Le prochain travail utile est de préparer des annotations de contours sur des images représentatives, puis d’évaluer le masque avec une mesure de bord. Cela permettra de décider si MODEL_C atteint sa limite et si un fine-tuning est justifié. Aucun fine-tuning n’a été lancé dans cette étape.

```text
ÉTAPE 13J.1 — CONTROLLED BOUNDARY REFINEMENT

BASELINE THRESHOLD :
0.50

THRESHOLDS TESTED :
0.40 / 0.45 / 0.50 / 0.55 / 0.60

MORPHOLOGY TESTED :
EROSION / DILATION / OPENING / CLOSING — 3x3, 1 iteration

SMOOTHING TESTED :
GAUSSIAN sigma=0.5 pixel, 5x5, threshold 0.50

BEST EXPERIMENTAL CONFIG :
NONE — no consistent boundary improvement

BOUNDARY VISUAL QUALITY :
SIMILAR

FRAGMENTATION :
SIMILAR

SMALL BUILDINGS :
MIXED across thresholds; 16/16 preserved by opening and Gaussian variants

AREA CHANGE :
opening −0.40%; Gaussian −0.10%; threshold 0.45 +6.01%; threshold 0.55 −4.03%

COMPONENT COUNT CHANGE :
opening −1; Gaussian −1; threshold 0.45 +2; threshold 0.55 −2 (16 zones)

PERIMETER CHANGE :
opening −3.14%; Gaussian −0.45%; no ground truth to establish a better fit

PROCESSING OVERHEAD :
Gaussian +1.63%; opening −0.16% measured across 16 zones (25 runs; no inference)

PRODUCTION PIPELINE CHANGED :
NO

MODEL_C :
UNCHANGED

ONNX :
UNCHANGED

MODEL_A :
BACKEND RETAINED

GROUND TRUTH :
ABSENT / DEFERRED

FINE TUNING REQUIRED :
MAYBE — annotate and evaluate boundaries first

CONCLUSION :
MODEL_MASK_LIMIT_REACHED

READY_FOR_PRODUCTION_REFINEMENT :
NO

NEXT STEP :
PREPARE FINE TUNING DATA
```
