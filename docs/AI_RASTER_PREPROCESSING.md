# Prétraitement et tiling raster IA — étape 2

Cette étape ne contient aucun modèle ou mécanisme d’inférence. Elle transforme
un GeoTIFF validé par l’étape 1 en un flux de tuiles NumPy géoréférencées prêt
pour un futur consommateur IA.

## Prétraitement déterministe

Les bandes sont lues par fenêtre Rasterio dans l’ordre `B4, B3, B2`, soit
`R, G, B`. Deux représentations sont conservées pendant l’itération :

- `source_rgb`, valeurs `uint16` originales pour contrôle et débogage ;
- `image`, valeurs `float32` destinées au futur modèle.

La normalisation `sentinel2_sr_fixed_reflectance_clip_scale:v1` est :

```text
float32(clip(DN, 0, 10000)) × 0.0001
```

Elle est fixe et identique pour chaque raster et chaque tuile. Aucun minimum,
maximum, percentile ou histogramme propre à une tuile n’est calculé. Les mêmes
valeurs source donnent donc toujours les mêmes sorties dans `[0, 1]`.

Rasterio combine le NoData déclaré (`0` pour le produit actuel) et les masques
internes. Un pixel n’est valide que lorsque les trois bandes sont valides. La
valeur normalisée du NoData et du padding est `0`, mais le `valid_mask` booléen
permet de les distinguer sans ambiguïté.

## Tiling

Configuration par défaut :

- `tile_size = 640` ;
- `overlap_ratio = 0.20` ;
- `overlap_pixels = 128` ;
- `stride = 512` ;
- `min_valid_pixel_ratio = 0.05`.

Les offsets sont générés jusqu’à ce que chaque pixel du raster soit couvert.
Les données sont lues avec `rasterio.windows.Window`, puis produites par un
générateur : une seule tuile est nécessaire en mémoire à la fois. Aucune tuile
n’est écrite sur disque par défaut.

Le ratio valide est calculé sur la partie réelle de la fenêtre, hors padding.
Une tuile sous le seuil est marquée `skip_inference`; aucune inférence n’est
lancée.

## Padding et géoréférencement

Les pixels réels sont ancrés en haut à gauche. Le padding à droite et/ou en bas
complète la matrice jusqu’à 640 × 640. Le masque du padding vaut toujours faux.
`valid_width` et `valid_height` conservent les dimensions réellement lues.

Le transform est calculé avec `rasterio.windows.transform` et les bounds avec
`rasterio.windows.bounds`. Ils décrivent uniquement la fenêtre réelle, jamais
la zone paddée. Les métadonnées permettent :

```text
col_raster = col_offset + x_tile
row_raster = row_offset + y_tile
```

Une coordonnée située dans le padding est rejetée. Les coordonnées cartographiques
sont retournées dans le CRS source à partir du transform affine de la tuile.

## API

`POST /api/ai/raster/tile` reçoit un `raster_id` validé par l’étape 1 et les
paramètres de tiling. La réponse contient la configuration, les comptes et un
nombre limité de métadonnées de tuiles. Elle ne sérialise jamais `source_rgb`,
`image` ou `valid_mask`.

Les résultats de tiling ne sont actuellement pas mis en cache. Le GeoTIFF et le
sidecar de l’étape 1 restent les seules ressources persistantes, dans le cache
IA isolé.

