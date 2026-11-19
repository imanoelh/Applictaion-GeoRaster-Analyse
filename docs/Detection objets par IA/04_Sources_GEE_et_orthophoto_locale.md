# Étape 4 — Sources GEE et orthophoto locale

## Objectif

Unifier deux sources sous le même contrat `RasterSource` : Sentinel-2 via GEE pour l’intégration et GeoTIFF local pour la future exploitation haute résolution.

## Profils supportés

| Source | Profil | Entrée | Normalisation |
|---|---|---|---|
| `sentinel2_gee` | `sentinel2_sr_v1` | B4/B3/B2 `uint16` | réflectance fixe `[0,1]` |
| `orthophoto_local` | `rgb_orthophoto_uint8_v1` | R/G/B `uint8` | `pixel / 255.0` |

Une orthophoto officielle doit être un **GeoTIFF RGB, trois bandes, uint8, avec CRS et géoréférencement**. Un fichier `uint16` est refusé : aucune règle arbitraire de conversion n’est appliquée.

## Import utilisateur

```http
POST /api/ai/raster/local?filename=ortho.tif
Content-Type: image/tiff
```

Le corps du fichier est diffusé vers un temporaire serveur. Aucun chemin disque client n’est accepté. La limite par défaut est 512 Mio, configurable par `AI_LOCAL_RASTER_MAX_BYTES`.

L’ordre RGB est déterminé par `ColorInterp`, puis par les descriptions de bandes. S’il reste ambigu, l’utilisateur doit fournir `red_band`, `green_band` et `blue_band`. Le sidecar conserve le profil, le mapping, le hash du contenu, le CRS, la résolution, les bounds et le NoData.

## Validation obtenue

Un GeoTIFF synthétique 1500 × 1300, EPSG:32638, 0,25 m/pixel a validé l’import, les neuf tuiles, les bords, le padding, la normalisation et le géoréférencement.

Ce test prouve le contrat logiciel, pas la qualité sur une acquisition réelle.

**Statut : validée techniquement ; vraie orthophoto non disponible.**

