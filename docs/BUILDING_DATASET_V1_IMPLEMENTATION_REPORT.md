# Rapport — pipeline SpaceNet Building Dataset v1

## Audit initial

Avant implémentation, les conventions existantes ont été inspectées :
`backend/data/fine_tuning/buildings/`, les scripts de préparation Maxar,
`TilingService`, les profils Rasterio et les adaptateurs Building. Les datasets
existants sont des artefacts Maxar/benchmark. Aucun répertoire imagery SpaceNet
ou labels SpaceNet n’était présent dans cette copie.

## Fichiers créés

- `backend/scripts/building_dataset/prepare_spacenet_building_dataset.py`
- `backend/scripts/building_dataset/generate_dataset_preview.py`
- `backend/tests/test_spacenet_dataset_pipeline.py`
- `docs/BUILDING_DATASET_V1.md`
- ce rapport

Le workspace de sortie attendu est :
`backend/data/fine_tuning/buildings/datasets/georaster_building_v1/`.
Il ne sera rempli qu’après fourniture de chemins SpaceNet réels.

## Fonctionnement

- association imagery/labels par clé de nom normalisée, avec diagnostics des
  fichiers sans correspondance;
- lecture Rasterio par fenêtres, tile par tile;
- reprojection des géométries vers le CRS raster;
- réparation sûre `buffer(0)` uniquement lorsque la géométrie obtenue reste
  valide;
- clipping au raster puis rasterisation directe dans la fenêtre;
- images et masques GeoTIFF 512×512 alignés;
- masque strict `0 background / 255 building`;
- tuiles vides conservées et plafonnées par configuration;
- split au niveau source raster, seed 42 par défaut;
- manifest, statistiques, source metadata et rejected tiles explicites;
- `--dry-run` et `--limit` pour validation progressive;
- previews RGB + masque sans QGIS.

## Commande dry-run exécutée

```text
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py --imagery backend/data/spacenet/imagery --labels backend/data/spacenet/labels --output backend/data/fine_tuning/buildings/datasets/georaster_building_v1 --dry-run --limit 5
```

Résultat réel dans cette copie : 0 imagery, 0 labels, 0 paire. Ce résultat est
normal car SpaceNet n’est pas inclus dans le dépôt; aucune donnée distante n’a
été téléchargée automatiquement.

## Tests

Les trois tests ciblés du pipeline passent (`3 passed`). Ils couvrent :
masque rasterisé et aligné 512×512, dry-run déterministe et rejet NoData.
La compilation Python des deux scripts passe également.

## Non-régression

Fichiers de production non touchés : MODEL_C8, autres adaptateurs, model
registry, GEE, NDVI, NDWI, NDBI, BSI, SAVI, Change Detection, classifications,
exports, frontend, routes API, cache, stockage de production et mode offline.

MODEL_C9 n’a pas été créé et aucun entraînement n’a été lancé.

## Limites connues

Le nombre de tuiles, la répartition train/val/test, la consommation RAM/disque
et les statistiques finales ne peuvent être calculés qu’après fourniture des
images et footprints SpaceNet. Le pipeline est prêt à les produire de façon
reproductible.
