# Préparation raster IA — étape 1

Cette étape ajoute uniquement la frontière d’entrée raster du futur moteur IA.
Elle ne contient aucun modèle, entraînement, segmentation ou inférence.

## Chaîne implémentée

`AOI GeoRaster → workflow Sentinel-2/GEE existant → B4/B3/B2 → GeoTIFF 10 m → Rasterio → validation`

- `POST /api/ai/raster/prepare` accepte le même contrat AOI, dates, nuages,
  méthode d’image et éventuel `image_id` que les traitements actuels.
- Le client GEE réutilise `_build_analysis_mosaic`; il ne recrée ni recherche
  Sentinel-2, ni masque nuage, ni logique de composite.
- Le raster temporaire contient les valeurs Sentinel-2 brutes en ordre RGB
  `B4, B3, B2`, dans le fuseau UTM de l’AOI, à 10 mètres.
- Rasterio contrôle lecture, bandes, CRS, transform, limites, résolution,
  dimensions, type et NoData. Les limites sont aussi reprojetées en WGS84 et
  comparées à l’AOI demandée.
- La réponse contient seulement l’identifiant et les métadonnées; jamais les
  octets du raster ni son chemin local.

## Fichiers temporaires

Les fichiers sont confinés à `backend/data/cache/ai-raster`, séparément des
exports et des caches des analyses. Leur identifiant contient la source, la
date, le hash AOI et une valeur aléatoire. Un sidecar JSON conserve les
métadonnées. `DELETE /api/ai/raster/{raster_id}` supprime uniquement les fichiers
de cet identifiant; `cleanup_expired` permet une purge limitée au même dossier.
Tout échec supprime les fichiers complets ou partiels de la requête concernée.

## Limite scientifique

La réponse porte `quality_mode=integration_test` et avertit que Sentinel-2 à
10 m ne permet pas de garantir une détection individuelle fiable de petits
bâtiments, arbres ou véhicules. Cet avertissement n’empêche pas la préparation.

