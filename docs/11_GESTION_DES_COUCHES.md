# Gestion des couches

## Couches cartographiques

`MapView.tsx` superpose :

1. fond de carte ;
2. image source/mosaïque (`zIndex 300`) ;
3. résultat raster (`zIndex 450`) ;
4. échantillons de classification ;
5. AOI ;
6. légende et contrôles.

Le frontend gère visibilité et opacité de l’image source et du résultat.

## Fonds

- OpenStreetMap ;
- Esri World Imagery ;
- Google Satellite ;
- OpenTopoMap ;
- CARTO Light.

Ce sont des services tiers ; leurs licences, quotas et disponibilité doivent être vérifiés avant production.

## Résultats simples

Le backend renvoie `tiles.rgb_tile_url` et `tiles.index_tile_url`. Sans URL réelle, `ResultOverlay` affiche un faux raster en bandes horizontales : c’est un fallback visuel mock, pas un résultat scientifique.

## NDBI

`comparison_layers` contient :

- `ndbi_raw` ;
- `ndbi_built_detection`.

La statistique, la légende et l’export suivent la couche active.

## Change Detection

Trois sous-couches par analyse : période 1, période 2 et delta. `activeComparisonLayerKey` garantit l’exclusivité visuelle.

## Cache et tuiles expirées

- une couche cachée est convertie en résultat frontend par `layerToRunResult` ;
- `GET /api/runs/{run_id}/tiles?refresh=true` régénère les URL GEE ;
- les tuiles de comparaison sont fusionnées par clé ;
- la restauration History charge le résultat sauvegardé avant toute régénération.

## Classification non supervisée

La modification de couleur :

- met à jour classes, interprétation, palette, run, cache et table de classification ;
- conserve `tile_source_palette` ;
- recolore localement les pixels dans un `L.GridLayer` canvas ;
- ne recalcule pas les groupes.

Si CORS bloque la lecture des pixels, la tuile originale est conservée.

## Légende

Priorité :

1. classes du résultat backend ;
2. légende statique de `frontend/src/data/mock.ts`.

La traduction applique `result-legend-i18n.ts`. La légende indique libellé, sens et couleur.

## Règles de modification

- garder un identifiant stable de sous-couche ;
- synchroniser tuile, classe, palette, histogramme, statistique et export ;
- tester cache, History et URL régénérée ;
- ne jamais utiliser le fallback `ResultOverlay` comme preuve d’un calcul réussi.
