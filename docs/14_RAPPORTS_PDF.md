# Rapports PDF

## Deux mécanismes

### `report_pdf` standard

`POST /api/runs/{id}/export` avec `report_pdf` appelle `_report_pdf_bytes`. C’est un rapport simple, stocké avec les exports du run.

### Map PDF professionnel

Le bouton UI appelle en priorité :

```text
GET /api/runs/{run_id}/export/map-pdf?layer_key=...
```

Le backend reconstruit `MapPdfExportRequest` depuis le run, les tuiles, l’AOI et la sous-couche. La route POST `/api/export/map-pdf` est un fallback si aucun run n’est disponible.

## Contenu

Pages produites par `_professional_map_pdf_pages` :

- couverture ;
- zone d’étude, image de référence et résultat ;
- page spécifique de comparaison pour Change Detection ;
- résultats, légende et classes ;
- statistiques et graphiques ;
- interprétation, qualité et métadonnées.

Format : 1 240 × 1 754 pixels par page, converti en PDF par Pillow. Version de rapport déclarée : `0.2.0`.

## Sources visuelles

Priorité :

- mosaïque depuis modèle de tuiles GEE ;
- URL thumbnail GEE ;
- screenshot du frontend ;
- fallback textuel/mock si aucune source fiable n’est récupérable.

Le code détecte les images uniformes et tente une reconstruction. Pour Change Detection, les trois sous-couches peuvent être rendues séparément.

## Paramètres transmis

- identifiant run/analyse ;
- type d’analyse ;
- bounds et surface AOI ;
- capteur, dates, résolution, nuages, méthode ;
- capture carte et locator optionnel ;
- légende, statistiques, histogramme, classes ;
- qualité, interprétation, utilisateur ;
- métadonnées et référence spatiale.

## Fichiers

- `backend/exports/reports/*.pdf` ;
- URL statique `/exports/reports/{filename}` ou réponse directe avec `Content-Disposition`.

## Risques

- dépendance réseau aux tuiles/URLs GEE ;
- rapport pouvant contenir un fallback si les sources sont inaccessibles ;
- police et rendu dépendants de Pillow ;
- captures web non géoréférencées ;
- pas de signature ni d’archivage probant.

## Tests présents

`test_map_pdf_adaptive_layout.py` couvre :

- conversion hectares/km² ;
- croissance des panneaux selon la surface ;
- conservation de la taille de page ;
- zoom détaillé mais borné pour petite AOI.

Il manque un test de contenu PDF complet pour chaque analyse et un contrôle visuel automatisé.
