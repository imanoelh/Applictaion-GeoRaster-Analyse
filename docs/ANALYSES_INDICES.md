# Analyses raster et indices

## Principes generaux

Chaque analyse produit:

- une image raster calculee;
- une carte classifiee;
- une palette;
- une legende;
- des statistiques;
- des classes avec surfaces et pourcentages;
- une URL de tuile GEE pour affichage cartographique.

## NDVI

Objectif: vegetation.

Formule:

```text
NDVI = (NIR - Red) / (NIR + Red)
```

Bandes Sentinel-2:

- NIR: `B8`;
- Red: `B4`.

Palette de base: rouge vers vert.

Etat: conforme.

## NDWI

Objectif: eau et humidite.

Formule:

```text
NDWI = (Green - NIR) / (Green + NIR)
```

Bandes Sentinel-2:

- Green: `B3`;
- NIR: `B8`.

Palette de base: bleus progressifs.

Etat: conforme.

## NDBI

Objectif: bati et artificialisation.

Formule:

```text
NDBI = (SWIR - NIR) / (SWIR + NIR)
```

Bandes Sentinel-2:

- SWIR: `B11`;
- NIR: `B8`.

Classes stabilisees:

- Non-built-up;
- Low artificialization;
- Probable built-up;
- Dense built-up.

Etat: conforme apres ajustement des labels et descriptions en anglais.

## BSI

Objectif: sols nus.

Formule:

```text
BSI = ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
```

Bandes Sentinel-2:

- SWIR: `B11`;
- Red: `B4`;
- NIR: `B8`;
- Blue: `B2`.

Palette de base: tons terre/brun.

Etat: conforme.

## SAVI

Objectif: vegetation en contexte semi-aride avec reduction de l'effet du sol.

Formule:

```text
SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)
```

Facteur utilise:

- `L = 0.5`.

Bandes Sentinel-2:

- NIR: `B8`;
- Red: `B4`.

Etat: conforme.

## Change Detection

Principe:

```text
Delta index = index periode 2 - index periode 1
```

Analyses supportees:

- `CHANGE_NDVI`;
- `CHANGE_NDWI`;
- `CHANGE_NDBI`;
- `CHANGE_BSI`;
- `CHANGE_SAVI`.

Les palettes Change Detection sont adaptees a la signification du changement:

- pertes en rouge/brun;
- stabilite en clair/neutre;
- gains en vert/bleu/brun selon l'indice.

Etat: conforme.

## OSI-SAR

Objectif: detection de suspects de deversement d'huile sur eau avec Sentinel-1 SAR.

Classes:

- Normal water;
- Low oil-spill suspicion;
- Medium oil-spill suspicion;
- High oil-spill suspicion.

Palette:

- bleu;
- jaune;
- orange;
- rouge.

Note scientifique: OSI-SAR detecte des suspects, pas une confirmation terrain. Les resultats doivent etre interpretes avec le vent, le contexte maritime et une validation experte.

Etat: fonctionnel avec GEE reel.

## Classifications

Classifications supportees:

- supervised classification;
- unsupervised classification.

Etat: fonctionnel, avec interpretation et classes cartographiques.

