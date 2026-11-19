# Étape 8 — Résultats GeoJSON et statistiques

## Objectif

Construire un contrat stable entre le backend et le frontend à partir du `BuildingVectorResult`, sans relancer l’inférence ni perdre les mesures natives.

## Contrat de résultat

`BuildingResultsService` produit un `BuildingAnalysisResult` versionné (`result_schema_version = "1.0"`) contenant :

- l’identifiant et le type d’analyse ;
- les métadonnées logiques de la source et du modèle ;
- les configurations publiques ;
- les statistiques des candidats ;
- les bounds natifs et WGS84 ;
- les temps de traitement ;
- une `FeatureCollection` GeoJSON EPSG:4326.

Les géométries natives restent dans le CRS source pour l’aire et le périmètre. Une copie est reprojetée en EPSG:4326 pour l’affichage web, avec l’ordre longitude/latitude. Les métriques en mètres ne sont exposées que si elles sont légitimes.

Un résultat vide est un succès : `candidate_count = 0`, totaux à zéro, statistiques non calculables à `null` et FeatureCollection vide.

## API et sécurité

```http
POST /api/ai/results/building
```

La réponse n’expose ni tenseur, ni tableau NumPy, ni objet Shapely, ni chemin de cache/checkpoint, ni credential. Les sources Sentinel portent `integration_test`; les orthophotos locales portent `real_model_unvalidated` tant qu’aucune validation scientifique n’existe.

Le mot `candidate_count` est contractuel : il empêche de présenter une segmentation non validée comme un inventaire certifié.

**Statut : validée techniquement ; `SCIENTIFIC_ACCURACY = NOT_VALIDATED`.**

