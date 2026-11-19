# Étape 11 — Finalisation et exports IA

## Objectif

Rendre le workflow Building utilisable et démontrable sans prétendre à une validation scientifique : consultation, nettoyage, relance et export du résultat courant.

## Architecture d’export

Le frontend envoie le `BuildingAnalysisResult` courant à :

```http
POST /api/ai/results/building/export
```

Le backend revalide le résultat avec Pydantic puis sérialise l’export en mémoire. Il ne relance ni l’inférence, ni le post-traitement, ni la polygonisation. Aucun cache et aucune base de données supplémentaires ne sont nécessaires.

Formats disponibles :

- **GeoJSON** EPSG:4326, avec uniquement les propriétés publiques utiles ;
- **CSV** UTF-8 BOM, une ligne de statistiques globales et cellules vides pour les valeurs nulles ;
- **metadata JSON** via l’API et dans le ZIP, avec source, modèle, configurations, versions et statut qualité ;
- **ZIP** contenant exactement `building_candidates.geojson`, `building_statistics.csv` et `building_metadata.json`.

Les clés et valeurs sensibles liées aux chemins, checkpoints, secrets, tokens ou credentials sont filtrées. SHP et GeoPackage ne sont pas proposés : aucune dépendance lourde n’a été ajoutée uniquement pour ces formats.

## Frontend et qualité

Le bouton Exporter n’apparaît qu’après un résultat. Les choix exposés sont GeoJSON, CSV et ZIP. L’interface gère chargement, succès et erreur sans bloquer toute l’application. Les avertissements scientifiques restent visibles et la terminologie « candidats bâtiments » est conservée.

## Vérification finale

- backend : **202 passed, 0 failed** ;
- tests frontend : réussis ;
- build frontend client : réussi ;
- build SSR : réussi ;
- compilation Python : réussie ;
- fixture 2 500 entités : validée ;
- exports historiques : non modifiés.

**Statut : validée techniquement ; prête pour un test sur orthophoto réelle.**

