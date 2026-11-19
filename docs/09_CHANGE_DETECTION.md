# Détection de changement

## Analyses disponibles

`CHANGE_NDVI`, `CHANGE_NDWI`, `CHANGE_NDBI`, `CHANGE_BSI`, `CHANGE_SAVI`.

Capteurs compatibles : Sentinel‑2 et Landsat 8/9. Sources : `gee_client.py::compute_change_detection_index`, `CHANGE_DETECTION_CONFIG`.

## Entrées

```json
{
  "analysis_type": "change_detection_ndvi",
  "index": "CHANGE_NDVI",
  "period_1": {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
  "period_2": {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
}
```

Le frontend utilise les dates de période 2 comme dates principales du payload. Chaque période est transformée en mosaïque médiane distincte.

## Calcul

```text
indice_1 = indice(mosaïque période 1)
indice_2 = indice(mosaïque période 2)
delta = indice_2 - indice_1
```

Les deux images reçoivent la même projection et la même échelle avant soustraction. Un avertissement apparaît si les mois de début diffèrent de plus de deux mois, ou si une période contient moins de deux images.

## Seuils communs

Les cinq analyses utilisent :

- forte diminution : `[-2, -0.25[` ;
- diminution modérée : `[-0.25, -0.08[` ;
- stable : `[-0.08, 0.08[` ;
- augmentation modérée : `[0.08, 0.25[` ;
- forte augmentation : `[0.25, 2[`.

Les libellés et palettes varient selon l’indice.

## Trois couches distinctes

Chaque résultat GEE contient :

1. `<indice>_period_1` — indice de référence, classes/statistiques de l’indice de base ;
2. `<indice>_period_2` — indice comparé, mêmes classes/statistiques ;
3. `<indice>_change` — delta classé, classes perte/stabilité/gain.

Exemple NDVI :

```text
ndvi_period_1 → NDVI - Period 1
ndvi_period_2 → NDVI - Period 2
ndvi_change   → NDVI Change - Period 2 minus Period 1
```

`active_comparison_layer` pointe par défaut vers la couche de changement. Le gestionnaire frontend garantit qu’une seule sous-couche résultat est active et que statistiques, histogramme, légende et export suivent cette sélection.

## Sémantique

| Base | Négatif | Stable | Positif |
| --- | --- | --- | --- |
| NDVI | perte de végétation | faible variation | gain de végétation |
| NDWI | disparition/baisse d’humidité | faible variation | hausse/apparition d’eau |
| NDBI | baisse de réponse bâtie | faible variation | artificialisation/expansion probable |
| BSI | baisse du sol exposé | faible variation | hausse de sol exposé |
| SAVI | perte de couverture | faible variation | gain de couverture |

## API et frontend

- workflow UI : routes standard analyses/run/result ;
- alternative API tout-en-un : `POST /api/analysis/change-detection` ;
- frontend : `map.tsx::buildRasterPayload`, `runAnalysis`, `comparisonLayers` ;
- carte : `MapView.tsx`.

## Exports

- GeoTIFF : la couche classée sélectionnée ; le code standard reconstruit par défaut le delta final ;
- Map PDF : peut reconstruire les trois visuels et leurs interprétations ;
- PNG layout : suit la sous-couche active ;
- CSV : statistiques/classes de la sous-couche active.

## Précautions

- comparer des saisons proches ;
- contrôler le nombre d’images et la couverture ;
- ne pas interpréter un delta spectral comme une preuve directe de changement d’occupation du sol ;
- vérifier l’alignement, l’échelle et le CRS ;
- NDBI reste sensible aux sols nus.
