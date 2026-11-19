# Étape 7 — Polygonisation SIG

## Objectif

Transformer le masque binaire global nettoyé en candidats vectoriels géoréférencés. La polygonisation porte sur le raster global, jamais tuile par tuile.

## Méthode

`BuildingPolygonizationService` utilise `rasterio.features.shapes` avec le masque valide et le transform affine source. Seule la valeur 1 est vectorisée. Les géométries sont converties en `Polygon` ou `MultiPolygon` Shapely.

Les géométries invalides sont réparées avec `make_valid` uniquement lorsque nécessaire. Les parties polygonales sont conservées, les lignes et points parasites sont éliminés. Les trous intérieurs significatifs sont préservés. La simplification est désactivée par défaut afin de ne pas altérer les contours.

## Déterminisme et mesures

Les candidats sont triés dans l’ordre du raster, puis reçoivent des identifiants stables :

```text
building_000001
building_000002
...
```

L’aire, le périmètre, le centroïde et les bounds sont calculés dans le CRS source. `area_m2` et `perimeter_m` ne sont renseignés que lorsque le CRS est projeté et utilise le mètre. Aucun calcul surfacique n’est fait en longitude/latitude.

## API

`POST /api/ai/vectorize/building` exécute le pipeline existant une fois et renvoie un résumé. Le GeoJSON peut être inclus pour débogage avec `include_geojson=true`. Le `feature_count` est un nombre de candidats vectoriels, pas un nombre de bâtiments scientifiquement confirmé.

**Statut : validée techniquement.**

