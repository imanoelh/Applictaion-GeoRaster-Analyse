# ÉTAPE 13L.3 — Comparaison A/B sur orthophoto réelle

## Portée et méthode

Comparaison visuelle/engineering de MODEL_C `spacenet2_deeplab` et MODEL_D `whu_unetplusplus_effb4` sur la même orthophoto Maxar RGB 2024 que celle utilisée à l’étape 13L.2 :

- Source : `test-data/validation-results/maxar_rgb_derivatives/maxar_2024_rgb_p2p98.tif`
- Dimensions : 2 048 × 2 048 pixels; CRS EPSG:32637; résolution 0,35 m; transform inchangé.
- SHA-256 : `f1749c2e0816b97e94fd3be73c56c3ee824f80d222f2a6823159c34759c0b6bb`.
- Huit AOI de 512 × 512 pixels, fenêtres fixes reprises à l’identique pour les deux modèles. AOI_03 et AOI_04 se chevauchent de 256 pixels pour échantillonner deux parties de la même zone urbaine dense.
- Entrée RGB identique par AOI. Chaque adapter conserve son preprocessing documenté : MODEL_C calcule son min/max RGB sur chaque raster AOI; MODEL_D utilise RGB float32 / 255 dans [0,1], sans moyenne/écart-type ImageNet.
- Seuil commun inchangé : 0,50. Post-traitement commun inchangé : minimum 4 pixels, pas de remplissage de trous ni morphologie. Tuiles de 512 pour les deux; les AOI tenant chacune dans une tuile, l’overlap configuré n’a pas d’effet sur ces résultats.
- Aucun fine-tuning, changement de poids, modification de seuil ni exécution sur le raster complet 10 292 × 9 378 pixels.
- Les annotations ground truth n’ont pas été utilisées dans cette étape. Il n’y a aucun Precision, Recall, F1 ou IoU officiel.

La planche de sélection montre les fenêtres et leur contexte : [aoi_selection.png](../test-data/diagnostics/13L3/aoi_selection.png). Les mêmes sources et limites sont décrites dans [aois.json](../test-data/diagnostics/13L3/aois.json).

## AOI inspectées

| AOI | Fenêtre pixel (x, y) | Cas représenté | Classement visuel | Observations |
|---|---:|---|---|---|
| AOI_01_industrial | (1280, 1024) | Industriel/commercial | UNCLEAR | Le grand toit industriel sombre n’est pas correctement détecté par les deux; les deux repèrent surtout le petit toit clair. WHU ajoute un petit fragment près du bord. |
| AOI_02_small_roofs | (0, 512) | Petites maisons, ombres, maisons rapprochées | MODEL_D_BETTER | WHU couvre davantage de toits et suit plusieurs formes de toit de plus près; certaines sorties WHU restent fragmentées ou ajoutent des petits objets incertains. |
| AOI_03_dense_urban | (1024, 0) | Zone urbaine dense | MODEL_D_BETTER | DeepLab est très parcimonieux; WHU retrouve plus de portions de toits visibles, avec davantage de fragments et des séparations parfois incertaines. |
| AOI_04_adjacent_roofs | (1024, 256) | Bâtiments très proches | UNCLEAR | Les deux manquent beaucoup de toits; les quelques candidats WHU supplémentaires ne démontrent pas une meilleure séparation. |
| AOI_05_shadowed_roofs | (0, 0) | Toits et ombres | MODEL_D_BETTER | WHU conserve plus de toits partiellement ombragés. Ses contours sont aussi plus fragmentés; l’inspection ne permet pas de juger chaque objet comme bâtiment réel. |
| AOI_06_roads_bare_soil | (1536, 512) | Routes, sol nu, végétation | MODEL_D_BETTER | Les deux masques sont presque vides; DeepLab produit deux petits candidats isolés, WHU aucun. C’est un indice visuel de meilleure suppression du bruit dans cette seule fenêtre. |
| AOI_07_complex_shapes | (0, 1024) | Formes complexes, rues et blocs commerciaux | MODEL_C_BETTER | DeepLab suit plus proprement la longue forme claire; WHU fournit plus de zones et de fragments autour des bâtiments, avec quelques extensions apparentes. |
| AOI_08_low_building_density | (1536, 1536) | Très faible densité | SIMILAR | Les deux restent largement silencieux et repèrent le bâtiment clair au bord de l’image; pas d’avantage général net. |

Les classements et les tendances de faux positifs ci-dessus sont des **VISUAL / ENGINEERING ASSESSMENT** uniquement. Les comptes de candidats ne constituent pas une preuve de qualité.

## Artefacts générés

Pour chaque AOI et modèle, `test-data/diagnostics/13L3/AOI_*/model_c/` ou `model_d/` contient :

- `probability.tif` (float32), `binary_mask.tif` et `valid_mask.tif`;
- `raw_polygons.geojson` issu de la polygonisation;
- `final_geojson.geojson` au format d’export GeoJSON GeoRaster;
- `statistics.json` et `metrics.json` avec le temps, le seuil, le preprocessing, les tuiles, les candidats et les surfaces.

Chaque répertoire AOI contient aussi `source_rgb.tif` et `comparison.png`, planche de six vues : orthophoto, masque et polygones C, masque et polygones D, puis contours C/D combinés. La mosaïque de toutes les comparaisons est [all_aois_overview.png](../test-data/diagnostics/13L3/all_aois_overview.png). Les temps et valeurs brutes sont dans [summary.json](../test-data/diagnostics/13L3/summary.json) et [summary.csv](../test-data/diagnostics/13L3/summary.csv).

## Résultats quantitatifs techniques

Le travail traité est de 8 AOI × 512 × 512 = 2,097 millions de pixels-AOI; cette charge comprend le chevauchement entre AOI_03 et AOI_04. Chaque modèle a exécuté huit tuiles CPU de 512 × 512.

| Mesure | MODEL_C — DeepLabV3 / ResNet-50 | MODEL_D — WHU U-Net++ / EfficientNet-B4 |
|---|---:|---:|
| Runtime | ONNX Runtime CPU | PyTorch CPU |
| Temps total des huit AOI (chargement inclus dans le premier AOI) | 29,70 s | 26,29 s |
| Temps d’inférence cumulé | 27,48 s | 24,28 s |
| Temps moyen d’inférence par tuile | 2,80 s | 2,55 s |
| Chargement du modèle | 3 322 ms | 526 ms |
| Temps total / MP-AOI traité | 14,16 s/MP | 12,54 s/MP |
| Candidats retournés, somme des huit AOI | 69 | 171 |
| Surface candidate cumulée sur les fenêtres | 18 977 m² | 15 199 m² |

Les surfaces et nombres sont des sommes sur les fenêtres, qui se chevauchent partiellement. Ils ne représentent pas un décompte unique de la scène. Aucun pic RAM fiable n’a été mesuré. Les 171 candidats WHU ne signifient pas qu’il y a plus de vrais bâtiments; le surplus comprend aussi des fragments et des objets visuellement incertains.

## Synthèse visuelle

Validation des artefacts : 16 jeux modèle-AOI contrôlés; dimensions, CRS, transform, bounds, plages finies des probability maps, valeurs de masques `{0,1}`, validité des géométries des deux GeoJSON et cohérence entre candidate_count et nombre de features validés.

- **Grands bâtiments** : UNCLEAR. Les deux ratent le grand toit industriel sombre de l’AOI_01.
- **Petits bâtiments** : avantage visuel local à MODEL_D dans les zones résidentielles AOI_02 et AOI_05; davantage de fragments et objets suspects accompagnent ce gain de couverture.
- **Densité urbaine** : avantage de couverture à MODEL_D dans AOI_03; AOI_04 reste un cas d’échec/ambiguïté pour les deux.
- **Séparation des bâtiments proches** : UNCLEAR. WHU segmente davantage d’îlots mais produit aussi plus de fragmentation; sans vérité terrain il est impossible d’établir si les séparations correspondent aux vrais bâtiments.
- **Contours** : avantage local à MODEL_D sur plusieurs toits résidentiels; MODEL_C donne une forme visuellement plus propre dans AOI_07. Aucun vainqueur global.
- **Tendance aux faux positifs apparents** : MODEL_C = MEDIUM; MODEL_D = MEDIUM. Appréciation visuelle : les candidats C hors toit restent présents mais moins nombreux; le masque D couvre souvent des toits plausibles, tout en affichant davantage de petits fragments/objets incertains et quelques extensions dans AOI_07. Ce n’est pas une mesure scientifique.
- **Performance WHU** : acceptable pour le test de sous-zones CPU (2,55 s/tuile en moyenne), légèrement plus rapide sur cette charge. Le raster complet n’a pas été lancé et ne peut pas être déclaré acceptable sur la base de ce profil.
- **Orthogonalisation** : à tester sur un petit échantillon ciblé des sorties résidentielles WHU, car plusieurs masques suivent des toits plausibles mais leurs footprints restent irréguliers. Elle ne résoudra pas les objets manqués ou les candidats faux.

## Conclusion et non-régression

Décision : **MODELS_COMPLEMENTARY**. MODEL_D apporte une couverture visuellement intéressante pour des toits résidentiels petits, rapprochés ou ombragés; ses masques et footprints restent plus fragmentés et affichent une tendance plus élevée aux faux positifs apparents. MODEL_C reste plus parcimonieux et meilleur dans au moins une zone de formes complexes. La comparaison n’établit pas de supériorité scientifique.

Cette étape n’a changé aucun code production, poids, seuil, modèle par défaut, traitement, export ou indice. MODEL_A est inchangé; MODEL_C reste le default/baseline; MODEL_D reste expérimental. Le grand raster 96,5 MP est explicitement reporté. La suite conseillée est un test d’orthogonalisation WHU limité à des cas résidentiels prometteurs, puis une comparaison ground truth avant toute affirmation de précision ou bascule de modèle.

ÉTAPE 13L.3 — REAL ORTHOPHOTO A/B TEST

ORTHOPHOTO :
Maxar 2024 RGB p2-p98, 2048x2048, EPSG:32637, 0.35 m

NUMBER OF AOIS :
8

MODEL_C :
DeepLabV3 / ResNet-50

MODEL_D :
WHU U-Net++ / EfficientNet-B4

MODEL_C TOTAL TIME :
29.70 seconds

MODEL_D TOTAL TIME :
26.29 seconds

MODEL_C SEC/MP :
14.16 seconds/MP-AOI

MODEL_D SEC/MP :
12.54 seconds/MP-AOI

LARGE BUILDINGS :
UNCLEAR

SMALL BUILDINGS :
MODEL_D

DENSE URBAN :
MODEL_D

BUILDING SEPARATION :
UNCLEAR

BOUNDARY ALIGNMENT :
MODEL_D

APPARENT FALSE POSITIVES :
MODEL_C = MEDIUM
MODEL_D = MEDIUM

MODEL_D VISUAL ADVANTAGE :
YES

MODEL_D PERFORMANCE ACCEPTABLE :
YES

ORTHOGONALIZATION WORTH TESTING :
YES

GROUND TRUTH STILL REQUIRED FOR SCIENTIFIC CLAIM :
YES

MODEL_C PRODUCTION :
UNCHANGED

MODEL_D STATUS :
EXPERIMENTAL

FINAL ENGINEERING DECISION :
MODELS_COMPLEMENTARY

NEXT STEP :
13L.4 WHU ORTHOGONALIZATION /
13M GROUND TRUTH VALIDATION /
KEEP MODEL_C
