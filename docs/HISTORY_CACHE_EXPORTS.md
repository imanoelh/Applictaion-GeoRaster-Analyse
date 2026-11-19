# History, cache et exports

## History

History liste les runs executes depuis la base backend.

Donnees restaurees:

- run id;
- analysis id;
- index;
- capteur;
- periode;
- AOI;
- statistiques;
- classes;
- histogramme;
- tuiles;
- exports;
- qualite.

## Visualisation rapide

La visualisation depuis History est optimisee pour le besoin client:

- pas de relance GEE;
- pas de recherche catalogue;
- pas de chargement obligatoire du raster source;
- affichage direct de la carte classifiee;
- legende et statistiques immediates.

## Cache

Le cache evite les recalculs inutiles lorsque le meme contexte d'analyse existe deja.

Il stocke:

- payload d'analyse;
- resultats;
- classes;
- statistiques;
- URLs de tuiles;
- metadata de qualite.

## Exports

Exports disponibles:

- `stats_csv`;
- `stats_json`;
- `geotiff`;
- `map_png`;
- `report_pdf`.

Les exports legers comme CSV/JSON sont rapides. Les exports visuels PDF/PNG/GeoTIFF peuvent etre plus longs car ils impliquent des images, tuiles ou generations de fichiers.

## Suppression

La suppression depuis History utilise l'analysis id et nettoie les donnees liees selon la logique backend existante.

## Performance mesuree

Sur un run History existant:

- `/api/history`: environ `0.05 s`;
- `/api/runs/{run_id}/result`: environ `0.007 s`;
- `/api/runs/{run_id}/tiles`: environ `0.010 s`.

Conclusion: la lenteur venait surtout du frontend qui chargeait des elements inutiles. Le workflow History a ete optimise.

