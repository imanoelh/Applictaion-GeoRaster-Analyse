# Étape 10K — Statistiques Building et affichage de l’orthophoto locale

## Diagnostic des surfaces

La chaîne backend conserve les valeurs dans `BuildingFeature` puis `BuildingResultsService`. Le problème venait du cas Maxar en CRS géographique : `area_map_units` était exprimée en degrés et `area_m2` restait `null`. Le frontend affichait alors la valeur en degrés avec seulement deux décimales, ce qui donnait visuellement `0`.

La correction calcule maintenant `area_m2` et `perimeter_m` dans une zone UTM locale déterminée par le centroïde. La géométrie native, le CRS source, le transform et les coordonnées GeoJSON EPSG:4326 ne sont pas remplacés. Les statistiques backend utilisent `BuildingFeature.area_m2`, puis sont sérialisées sans fallback artificiel vers zéro.

## Orthophoto locale

Un endpoint dédié a été ajouté :

`GET /api/ai/raster/{raster_id}/preview.png`

Il lit le GeoTIFF préparé avec Rasterio, produit un aperçu RGB RGBA limité à 2048 pixels sur le plus grand côté, conserve la transparence NoData et ne charge jamais le COG complet dans le navigateur. Les bounds WGS84 sont ajoutées aux métadonnées de préparation.

Le frontend affiche cet aperçu par `ImageOverlay` sous la couche `AI Building Candidates`, avec l’opacité existante et le contrôle `showRaster`. Le raster scientifique utilisé par l’inférence n’est pas reprojeté ni modifié.

## Validation réalisée

- Endpoint preview testé sur un raster local préparé : HTTP 200, PNG RGBA `2048 × 1866`.
- Métriques projetées et métriques géographiques testées.
- Backend complet : `216 passed, 0 failed`.
- Frontend tests : succès.
- Client build : succès.
- SSR build : succès.
- Backend relancé sur `127.0.0.1:8010`; frontend conservé sur `127.0.0.1:5183`.

Le résultat Maxar 2025 à 729 candidats n’est pas conservé dans le workspace courant avec son `analysis_id`; les valeurs numériques exactes de cette session doivent donc être relues depuis la réponse API réelle. La correction est prête pour cette réponse et ne remplace aucun `null` par `0`.

## Statut

ÉTAPE 10K — STATUT :
PARTIELLEMENT VALIDÉE

STATISTICS ROOT CAUSE :
CRS géographique conservé pour les métriques; `area_m2` absent puis surface en degrés arrondie à 0 par le frontend.

BUILDING AREA METRICS :
VALIDÉES

TOTAL AREA :
Disponible depuis `statistics.total_area_m2` pour un raster géographique; valeur Maxar 729 non rejouée dans ce workspace.

MEAN AREA :
Disponible depuis `statistics.mean_area_m2`.

MEDIAN AREA :
Disponible depuis `statistics.median_area_m2`.

MIN AREA :
Disponible depuis `statistics.min_area_m2`.

MAX AREA :
Disponible depuis `statistics.max_area_m2`.

CSV STATISTICS :
VALIDÉES par réutilisation de `BuildingAnalysisResult.statistics`.

ZIP STATISTICS :
VALIDÉES par réutilisation de `BuildingAnalysisResult.statistics`.

LOCAL ORTHOPHOTO MAP LAYER :
VALIDÉE

ORTHOPHOTO + BUILDING OVERLAY :
VALIDÉ

SPATIAL ALIGNMENT :
VALIDÉ

STANDARD MODEL :
INCHANGÉ

BLOCKWISE PROCESSING :
INCHANGÉ

BACKEND REGRESSION :
AUCUNE

FRONTEND BUILD :
SUCCESS
