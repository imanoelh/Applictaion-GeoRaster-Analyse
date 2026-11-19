# Étape 1 — Préparation du raster IA

## Objectif

Créer une entrée raster fiable et isolée pour le pipeline IA sans modifier les analyses historiques de GeoRaster. Cette étape transforme une source GEE en GeoTIFF local validé et identifié par un `raster_id`.

## Réalisation

Le service prépare une composition Sentinel-2 RGB dans l’ordre **B4, B3, B2**. Le raster est reprojeté dans la zone UTM adaptée à l’emprise, puis écrit en GeoTIFF avec un CRS, une transformation affine, des bounds et un NoData explicites. Rasterio relit le fichier produit : une création réussie ne suffit pas, le contrat géospatial doit aussi être valide.

L’API principale est :

```http
POST /api/ai/raster/prepare
```

La réponse expose un identifiant logique et des métadonnées, jamais un chemin serveur. Le raster et son sidecar JSON sont placés dans le cache IA isolé `backend/data/cache/ai-raster`. Leur cycle de vie peut être terminé par :

```http
DELETE /api/ai/raster/{raster_id}
```

## Garanties

- ordre RGB explicite ;
- CRS et géoréférencement obligatoires ;
- dimensions, transform, bounds, dtype et NoData contrôlés ;
- identifiant logique séparé du chemin physique ;
- erreurs métier sans stacktrace ni information sensible ;
- aucun impact sur NDVI, NDWI, NDBI, BSI, SAVI, classifications ou Change Detection.

## Limite scientifique

Sentinel-2 à 10 m sert à valider l’intégration du pipeline. Cette résolution ne permet pas une détection individuelle fiable des bâtiments. Les résultats produits avec cette source portent donc le mode qualité `integration_test`.

**Statut : validée techniquement.**

