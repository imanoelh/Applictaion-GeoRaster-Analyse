# Frontend

## Stack et démarrage

React 19, TanStack Start/Router/Query, Vite 7, Leaflet, Recharts, Tailwind/Radix. `vite.config.ts` délègue l’essentiel à `@lovable.dev/vite-tanstack-config`.

## Pages

| Page | Responsabilités | API |
| --- | --- | --- |
| `index.tsx` | KPI et portefeuille | `GET /api/dashboard` |
| `catalog.tsx` | filtre du catalogue statique | `GET /api/catalog/images` |
| `history.tsx` | liste, restauration, export, suppression | history, result, download, delete analysis |
| `settings.tsx` | plateforme, logo, fonds, CRS, option 3D | settings/logo |
| `map.tsx` | AOI, recherche, calcul, couches, stats, exports | principal client API |

## Carte

`components/MapView.tsx` :

- fonds OSM, Esri, Google Satellite, OpenTopoMap et CARTO ;
- tuiles source et résultat GEE ;
- AOI rectangulaire ;
- dessin point/polygone pour les échantillons ;
- légende dynamique ;
- opacité et échelle ;
- recoloration locale des tuiles non supervisées si la palette utilisateur diffère de la palette source.

La projection d’affichage Leaflet reste Web Mercator ; les coordonnées AOI sont envoyées en GeoJSON EPSG:4326.

## Contrat canonique

`map.tsx::buildRasterPayload` et `lib/georaster-contract.ts` produisent :

```json
{
  "geometry": {"type": "Polygon", "coordinates": []},
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "sensor": "sentinel-2",
  "resolution": "auto",
  "cloud_max": 20,
  "index": "NDVI",
  "analysis_type": "spectral_index"
}
```

Ajouts conditionnels : `period_1/period_2`, `supervised_options`, `unsupervised_options`, `osi_sar_options`.

## Workflow `map.tsx`

- `loadCatalogImages` : démarre un job GEE et le poll.
- `runAnalysis` : vérifie capteur/périodes, cherche le cache, crée l’analyse, lance le run et charge le résultat.
- `activateCachedLayer` : restaure une couche sans recalcul.
- effet `getRunTiles` : régénère des URL expirables.
- `exportFile` : export run standard.
- `exportMapPdf` : téléchargement PDF par run, avec fallback POST.
- `exportMapLayoutPng` : capture de la carte ou reconstruction backend.

## Gestion de l’état et de l’historique

History précharge le résultat dans `sessionStorage` sous `georaster:history-restore`, puis navigue vers `/map?run_id=...`. Map restaure AOI, dates, capteur, couches et statistiques sans catalogue ni recalcul.

## Internationalisation

- dictionnaires globaux `en.json` et `ar.json` ;
- libellés de résultats dans `result-legend-i18n.ts` ;
- calendrier localisé ;
- contrôle automatisé de 13 analyses/130 termes.

## Écarts à connaître

- `src/data/mock.ts` reste utilisé à la fois comme fallback et catalogue UI officiel des légendes ;
- le catalogue `/catalog` affiche les images statiques, pas le workflow GEE live de `/map` ;
- la résolution choisie est transmise mais le backend calcule aux échelles capteur ;
- `map.tsx` et les captures d’export sont volumineux et fortement couplés.
