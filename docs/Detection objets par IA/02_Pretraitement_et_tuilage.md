# Étape 2 — Prétraitement et tuilage géoréférencé

## Objectif

Transformer un GeoTIFF validé en un flux de tuiles prêtes pour l’inférence, tout en conservant la correspondance exacte entre pixel, tuile et coordonnées cartographiques.

## Prétraitement

Pour Sentinel-2, les valeurs `uint16` sont normalisées par une règle fixe et reproductible :

```text
float32(clip(DN, 0, 10000)) × 0.0001
```

Le tableau destiné au modèle est au format CHW `float32`. Le NoData et les masques internes Rasterio sont combinés dans un `valid_mask`. Les pixels invalides sont mis à zéro sans être confondus avec de vrais pixels noirs.

## Tuilage

Configuration de référence :

- taille : `640 × 640` pixels ;
- overlap : `20 %`, soit 128 pixels ;
- stride : 512 pixels ;
- ratio valide minimal : `0.05`.

Les fenêtres sont lues en streaming. Une seule tuile doit être présente en mémoire à la fois. Les tuiles de bord sont complétées à droite ou en bas ; le padding est marqué invalide et n’influence pas le modèle.

Chaque `PreparedTile` conserve ses offsets, sa taille réellement lue, son transform et ses bounds. La relation avec le raster global reste déterministe :

```text
col_raster = col_offset + x_tile
row_raster = row_offset + y_tile
```

## API et garanties

`POST /api/ai/raster/tile` renvoie la configuration, les comptes et un échantillon de métadonnées. Les matrices image et masque ne sont pas sérialisées dans la réponse. Une tuile presque vide peut être marquée `skip_inference`.

Cette conception évite la perte de géoréférencement, limite la mémoire et prépare correctement la fusion ultérieure des zones de recouvrement.

**Statut : validée techniquement.**

