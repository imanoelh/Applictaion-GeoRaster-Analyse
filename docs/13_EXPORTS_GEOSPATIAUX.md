# Exports géospatiaux

## Matrice

| Sortie | Déclenchement UI | Route principale | Génération |
| --- | --- | --- | --- |
| GeoTIFF | bouton GeoTIFF | `POST /api/runs/{id}/export` | URL GEE |
| CSV stats | bouton CSV | même route | octets CSV locaux |
| JSON stats | API seulement | même route | JSON local |
| PNG GEE | API standard | même route kind `map_png` | URL thumbnail GEE |
| PNG cartographique | bouton PNG | `POST /api/export/map-layout-png` | Pillow, fichier local |
| PDF simple | API standard | kind `report_pdf` | PDF minimal |
| Map PDF | bouton Map PDF | `GET /api/runs/{id}/export/map-pdf` | Pillow, PDF multi-pages |

## GeoTIFF

Chaîne :

1. `map.tsx::exportFile("geotiff")` transmet le run et la sous-couche.
2. `main.py::create_export` charge le résultat stocké.
3. `gee_client.create_index_geotiff_url` reconstruit l’image GEE finale.
4. `getDownloadURL` reçoit `name`, `region`, `scale`, `crs`, `format=GEO_TIFF`.
5. L’URL est enregistrée en base et dans un fichier local portant l’extension `.tif`.
6. `GET /api/exports/{id}/download` répond par redirection 307 vers GEE.

Le fichier local `.tif` de 162 octets observé est donc un conteneur texte de l’URL, pas le raster binaire. Le vrai GeoTIFF est téléchargé depuis GEE.

### Image exportée

- indices simples : image continue de l’indice ;
- NDBI built : raster entier classé si `layer_key=ndbi_built_detection` ;
- Change Detection : raster entier des classes de delta ;
- OSI‑SAR : classes 0–3 ;
- classifications : raster catégoriel.

### Emprise, CRS, résolution

- emprise : géométrie AOI ;
- CRS : CRS analytique effectif, traduit en WGS84 UTM pour les zones KSA ;
- échelle : 10 m Sentinel‑2/Sentinel‑1 ou 30 m Landsat.

### Éléments non spécifiés

Le code ne fixe pas :

- valeur NoData ;
- `unmask` ;
- dtype explicite pour les indices continus ;
- compression ;
- `filePerBand` ;
- `crsTransform`/alignement de pixel ;
- tags de métadonnées GeoTIFF ;
- noms de bandes contractuels ;
- maximum de taille/téléchargement.

Pour les rasters classés, plusieurs chemins utilisent `toInt`; les indices continus conservent le type GEE. Une validation SIG doit contrôler masque/NoData, dtype, bande, géotransformée et CRS du fichier réellement téléchargé.

## CSV et JSON

CSV inclut les statistiques et classes du résultat ou de la sous-couche. JSON sérialise le résultat exporté. Les fichiers sont stockés dans `backend/exports/files/` et référencés en SQLite.

Il n’existe pas d’export Excel.

## PNG cartographique

Le frontend tente une capture de la couche résultat limitée à l’AOI. En échec, il envoie un pixel neutre et le backend reconstruit depuis les tuiles du run. Pillow compose un format 1 800 × 1 280 avec titre, carte, légende, nord, échelle et informations.

## Téléchargement et erreurs

- 404 run/export absent ;
- 422 GEE indisponible en mode mock, couche invalide ou génération impossible ;
- réseau/CORS/tuiles expirées ;
- quota/taille GEE ;
- redirection temporaire expirée.

## Tests requis

- chaque famille d’analyse et chaque sous-couche ;
- AOI minuscule, grande et multi-zone ;
- CRS automatique et manuel ;
- ouverture du GeoTIFF dans GDAL/QGIS ;
- contrôle statistique entre raster et API ;
- capture PNG avec et sans tuiles disponibles ;
- expiration/régénération des URL ;
- noms uniques et nettoyage.
