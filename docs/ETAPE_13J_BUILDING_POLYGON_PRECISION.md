# ÉTAPE 13J — BUILDING POLYGON PRECISION

Date : 20 octobre 2026  
Raster de référence : `ai-ortho-8a2cfdde5ede-001127b57045-ff17132850b4`  
Source : `orthophoto_2025-07-28_rgb_uint8_utm37n_2048.tif`

## Périmètre et méthode

Audit effectué sur le raster RGB local 2048×2048, déjà utilisé à l’étape 13I.3, avec MODEL_C `spacenet2_deeplab`, le moteur ONNX Runtime CPU, le seuil production 0,50, des tuiles 512×512 et le preprocessing global RGB min-max. Aucun poids, seuil de production, profil de preprocessing, moteur, service de post-traitement, code de polygonisation ou paramètre métier n’a été modifié.

Seize fenêtres de diagnostic ont été sélectionnées à travers des toits petits, moyens, grands et complexes, y compris des toits proches d’ombres et de routes. Les artefacts sont conservés sous [`test-data/diagnostics/13J`](../test-data/diagnostics/13J/). Le contact sheet de contrôle visuel est [`selected_roofs_contact_sheet.jpg`](../test-data/diagnostics/13J/selected_roofs/selected_roofs_contact_sheet.jpg) ; les contours comparant 0,40 (cyan), 0,50 (jaune) et 0,60 (rouge) sont dans [`threshold_comparison_contact_sheet.jpg`](../test-data/diagnostics/13J/selected_roofs/threshold_comparison_contact_sheet.jpg). Ces fenêtres servent au diagnostic visuel, pas à mesurer une précision scientifique : aucun polygone de vérité terrain indépendant n’est fourni.

Pour chaque fenêtre sont sauvegardés l’orthophoto RGB, la carte de probabilité, les masques bruts aux trois seuils, le masque après post-traitement, la polygonisation brute et le polygone final. Les masques raster de chaque fenêtre ont les mêmes dimensions, le même CRS, la même résolution et la même transformation affine. Les géométries des GeoJSON par fenêtre sont natives EPSG:32637 et coupées à l’emprise de leur fenêtre. Les artefacts pleine emprise comprennent aussi les GeoJSON de polygonisation natifs et les polygones finaux reprojetés en EPSG:4326.

## Géoréférencement

- CRS orthophoto et polygonisation : **EPSG:32637**.
- Taille : **2048×2048** ; résolution : **0,35×0,35 m/pixel**.
- Bounds : x = 582091,891478 à 582808,691478 m ; y = 2367464,037368 à 2368180,837368 m.
- Transformation affine : `[0.35, 0, 582091.8914781093, 0, -0.35, 2368180.8373675323]`.
- Centre du pixel `(col,row)` : `x = 582091.8914781093 + 0.35 × (col + 0.5)` ; `y = 2368180.8373675323 - 0.35 × (row + 0.5)`. L’affine de `rasterio.features.shapes` décrit les coins des pixels ; il n’y a pas d’ajout manuel d’un demi-pixel.
- La polygonisation native a été re-rasterisée sur la grille d’origine : **0 pixel de différence** avec le masque post-traité. La transformation GeoJSON vers EPSG:4326 a produit 65 géométries valides et non vides.

**Conclusion : aucun décalage géométrique détecté.** L’écart X/Y mesuré entre grille du masque et contours polygonisés est de 0 pixel (0 m, 0 m). La conformité aux bords visibles des toitures est évaluée séparément ci-dessous ; elle ne constitue pas un test de précision géodésique.

## Masque et contours de probabilité

À 0,50, le masque brut contient **43 456 pixels positifs**. Visuellement, plusieurs contours suivent les toits, mais restent crénelés à l’échelle du pixel ; quelques petites détections paraissent être des fragments ou des détails de toiture plutôt que des empreintes complètes. La qualité du masque est donc **APPROXIMATE**.

Les probabilités près des frontières sont étalées autour du seuil : sur les pixels de bord interne et la première couronne externe, **76,4 %** des valeurs sont entre 0,40 et 0,60. La médiane est 0,553 à l’intérieur du masque et 0,446 juste à l’extérieur. Cela correspond à des contours **DIFFUSE** : les intérieurs et fonds lointains sont souvent bien séparés, mais la localisation de la frontière dépend sensiblement du seuil. Ombres, routes et sol nu sont présents dans la scène ; les confusions sont visibles sur certains petits fragments. Cette orthophoto n’offre pas un échantillon suffisant de végétation pour conclure sur cette classe.

### Seuils de diagnostic uniquement

| Seuil | Pixels bruts | Composantes après filtre minimum de 4 pixels | Observation visuelle |
|---:|---:|---:|---|
| 0,40 | 52 772 | 75 | Étend les contours et fait apparaître plus de petites composantes ; déborde davantage sur certains fonds/toits voisins. |
| 0,50 | 43 456 | 65 | Référence de production conservée. |
| 0,60 | 38 173 | 61 | Réduit les empreintes et retire des bordures qui semblent appartenir à certaines toitures. |

Les artefacts montrent le compromis entre extension, fragmentation et retrait de bordures, mais sans vérité terrain le meilleur ajustement ne peut pas être choisi de manière objective : **BEST_DIAGNOSTIC_THRESHOLD = UNCLEAR**. Le seuil production reste 0,50.

## Post-traitement et polygonisation

Au seuil 0,50, le masque brut et le masque final post-traité ont chacun 43 456 pixels : **aucun pixel modifié** et 65 composantes des deux côtés. Les opérations d’ouverture/fermeture et le remplissage des trous sont désactivés. Le filtre de petites composantes est réglé à 4 pixels, mais n’en a supprimé aucune dans ce résultat. L’impact observé du post-traitement est **LOW**.

La polygonisation utilise `rasterio.features.shapes` avec l’affine de la grille, connectivité 8 et tolérance de simplification de production égale à 0. La re-rasterisation conserve exactement les 43 456 pixels du masque ; le nombre et l’emprise des 65 polygones correspondent. Les contours héritent des angles en escalier du masque mais ne sont pas déplacés, agrandis ni lissés par la polygonisation. La qualité de conversion masque-vers-polygone est **GOOD** ; la précision visuelle des polygones reste limitée par le masque.

La simplification est désactivée en production : impact production **NONE**. Les essais géométriques diagnostiques ont conservé 65 polygones :

- tolérance 0,35 m (1 pixel) : Hausdorff max 0,35 m, moyen 0,319 m, aire totale +0,056 % ;
- tolérance 0,70 m (2 pixels) : Hausdorff max 0,764 m, moyen 0,566 m, aire totale −1,115 %.

Ces essais confirment qu’une simplification non nulle peut déplacer des frontières ; aucune tolérance de ce type n’a été appliquée au résultat de production.

## Estimation de l’erreur visuelle

Sur les toits clairs examinés, l’écart apparent typique entre le contour et la bordure visible est estimé à **1–3 pixels**, soit **0,35–1,05 m**. Les petits fragments et zones de contraste faible présentent localement des écarts supérieurs. Il s’agit d’une estimation visuelle sur 16 zones, pas d’une métrique annotée ni d’une mesure validée sur un jeu de vérité terrain.

## Cause et suite

Le géoréférencement est correct, le post-traitement ne modifie pas le masque et la polygonisation restitue exactement ce masque ; la simplification production est nulle. La cause principale des contours imprécis est donc **MODEL_MASK** : les frontières de probabilité sont diffuses et le résultat binaire dépend du seuil. Le seuil et les poids peuvent contribuer ensemble, mais cet audit sans références annotées ne permet pas d’isoler leur part respective.

Un fine-tuning n’est **pas encore** justifié. L’étape suivante recommandée est un raffinement contrôlé des frontières sur les mêmes zones, avec polygones de référence annotés et mesures de précision/rappel aux bords. Si ces mesures confirment ensuite que le masque reste imprécis après réglage diagnostique, un fine-tuning pourra être évalué. Aucun changement de production n’a été fait ici.

Les artefacts et métriques numériques sont indexés dans [`audit_metrics.json`](../test-data/diagnostics/13J/audit_metrics.json) et la liste des fenêtres dans [`selected_roofs.csv`](../test-data/diagnostics/13J/selected_roofs/selected_roofs.csv). Aucun code métier n’a changé ; les tests backend et frontend n’ont donc pas été relancés.

```text
ÉTAPE 13J — BUILDING POLYGON PRECISION

MODEL :
spacenet2_deeplab

ENGINE :
ONNX_RUNTIME_CPU

CURRENT THRESHOLD :
0.50

GEOMETRIC OFFSET :
NO

OFFSET PIXELS :
0 px (raster-to-polygon XOR)

OFFSET METERS :
0 m (raster-to-polygon XOR)

MASK QUALITY :
APPROXIMATE

PROBABILITY BOUNDARIES :
DIFFUSE

POSTPROCESSING IMPACT :
LOW

POLYGONIZATION QUALITY :
GOOD

SIMPLIFICATION IMPACT :
NONE

BEST DIAGNOSTIC THRESHOLD :
UNCLEAR

TYPICAL BOUNDARY ERROR :
~1–3 pixels (visual estimate)
~0.35–1.05 meters

MAIN CAUSE :
MODEL_MASK

FINE TUNING REQUIRED :
NOT_YET

MODEL_C :
UNCHANGED

MODEL_A :
BACKEND RETAINED

ONNX ENGINE :
UNCHANGED

READY_FOR_BOUNDARY_IMPROVEMENT :
YES

NEXT STEP :
13J.1 CONTROLLED BOUNDARY REFINEMENT
```
