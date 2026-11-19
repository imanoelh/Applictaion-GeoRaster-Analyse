# Étape 6 — Post-traitement et fusion des overlaps

## Objectif

Recomposer les prédictions par tuile en une carte de probabilités globale puis en un masque binaire propre, sans rupture spatiale aux bordures.

## Fusion

Les `TilePrediction` sont consommées en streaming. Deux accumulateurs globaux `float32`, somme des probabilités et somme des poids, réalisent une moyenne uniforme sur les overlaps :

```text
global_probability = probability_sum / weight_sum
```

Seuls la zone réellement lue et les pixels du `valid_mask` contribuent. Le seuil est appliqué **après** fusion ; les masques binaires des tuiles ne sont jamais simplement concaténés.

## Configuration de référence

- `probability_threshold = 0.50` ;
- `min_object_pixels = 4` ;
- `max_hole_pixels = 0` ;
- opening et closing désactivés ;
- noyau morphologique 3, une itération ;
- connectivité 8.

Les petites composantes sont filtrées. Le remplissage des trous et la morphologie sont disponibles mais désactivés par défaut, car leur effet n’a pas été calibré sur une vérité terrain.

## Géométrie et mémoire

`BuildingMaskResult` conserve le CRS, le transform, les dimensions et les bounds du raster source. L’aire technique d’un pixel vaut `abs(resolution_x × resolution_y)` dans les unités du CRS.

Les accumulateurs restent en mémoire. La limite `AI_POSTPROCESS_MAX_GLOBAL_PIXELS`, fixée par défaut à 25 000 000 pixels, protège contre les rasters trop grands. La route `POST /api/ai/postprocess/building` renvoie un résumé, jamais les matrices globales.

**Statut : validée techniquement ; paramètres non calibrés scientifiquement.**

