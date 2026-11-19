# GeoRaster Building Dataset v1 (SpaceNet seed)

Ce pipeline est expérimental et indépendant de l’application de production.
Il prépare des couples imagery/masque pour un futur entraînement MODEL_C9.
Il ne modifie pas MODEL_C8, le registre, les routes API, GEE, les indices, les
classifications, les exports ou le mode offline.

## Commande

```powershell
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py `
  --imagery <dossier-imagery-Spacenet> `
  --labels <dossier-labels-Spacenet> `
  --output backend/data/fine_tuning/buildings/datasets/georaster_building_v1 `
  --tile-size 512 --seed 42
```

Découverte sans écriture : ajouter `--dry-run --limit 5`.
Les fichiers vectoriels GeoJSON sont supportés directement. Shapefile/GPKG
nécessitent Fiona dans l’environnement utilisé.

## Convention

`train/`, `val/` et `test/` contiennent `images/*.tif` et `masks/*_mask.tif`.
Les rasters sont lus par fenêtres, sans chargement complet nécessaire. Chaque
tuile mesure 512×512, sans resize déformant. Les masques sont strictement :
0 = background et 255 = building.

Le split est effectué au niveau du raster source avant la génération des tuiles
(seed fixe), afin d’éviter le leakage spatial entre zones voisines. Les tuiles
vides sont conservées jusqu’à `--max-empty-tile-ratio` (0.35 par défaut).

## Métadonnées et QA

- `metadata/dataset_manifest.json` : identifiants, chemins, split, hashes,
  ratios de pixels, CRS et emprise.
- `metadata/dataset_statistics.json` : volumes train/val/test, positives,
  négatives, pixels building et rejets.
- `metadata/rejected_tiles.json` : chaque rejet et sa cause explicite.
- `metadata/source_metadata.json` : provenance et géométrie des sources.
- `generate_dataset_preview.py` produit jusqu’à 20 overlays PNG.

Le pipeline rejette les rasters incompatibles, les fenêtres trop NoData et les
erreurs de rasterisation; il ne les ignore jamais silencieusement.

## État initial dans ce dépôt

Aucun dataset SpaceNet source n’est inclus dans la copie actuelle. Le premier
`--dry-run` doit donc recevoir les chemins externes réels et afficher les
paires image/labels détectées avant toute génération.

## Prochaine étape

Après QA du manifest et des previews, un entraînement MODEL_C9 pourra être
préparé dans un workspace séparé. Cette étape ne lance aucun entraînement.
