# Détection d’objets par IA — dossier des étapes 1 à 12

Ce dossier retrace la construction du pipeline **Building** de GeoRaster. Il décrit ce qui est réellement implémenté, ses contrats techniques et ses limites. Le terme **candidat bâtiment** est volontaire : le modèle est réel, mais son exactitude scientifique n’a pas encore été mesurée sur une orthophoto réelle annotée.

## Vue d’ensemble

| Étape | Sujet | État |
|---:|---|---|
| 1 | [Préparation et validation du raster](01_Preparation_raster_IA.md) | Validée techniquement |
| 2 | [Prétraitement et tuilage géoréférencé](02_Pretraitement_et_tuilage.md) | Validée techniquement |
| 3 | [Service d’inférence Building](03_Inference_Building.md) | Validée techniquement |
| 4 | [Sources GEE et orthophoto locale](04_Sources_GEE_et_orthophoto_locale.md) | Validée techniquement |
| 5 | [Modèle réel U-Net / ResNet-34](05_Modele_reel_UNet_ResNet34.md) | Validée techniquement |
| 6 | [Post-traitement et fusion des overlaps](06_Post_traitement_et_fusion.md) | Validée techniquement |
| 7 | [Polygonisation SIG](07_Polygonisation_SIG.md) | Validée techniquement |
| 8 | [Résultats GeoJSON et statistiques](08_Resultats_GeoJSON_et_statistiques.md) | Validée techniquement |
| 9 | [Intégration frontend](09_Integration_frontend.md) | Validée techniquement |
| 10 | [Validation sur orthophoto réelle](10_Validation_orthophoto_reelle.md) | Partiellement validée sur sous-zones réelles dérivées |
| 10C | [Diagnostic préparation RGB Maxar](10C_Diagnostic_preparation_RGB_Maxar.md) | Validée techniquement, exactitude scientifique non validée |
| 10D | [Protocole vérité terrain Building](10D_Protocole_verite_terrain_Building.md) | Bloquée par annotation humaine |
| 10E | [Test réel Building Maxar 2024/2025](10E_Test_reel_Building_Maxar_2024_2025.md) | Validée fonctionnellement, exactitude scientifique non validée |
| 11 | [Finalisation et exports IA](11_Finalisation_et_exports_IA.md) | Validée techniquement |
| 12 | [Clôture technique et protocole terrain](12_Cloture_technique_et_protocole_terrain.md) | Préparée, validation terrain non exécutée |

## Pipeline final

```text
RasterSource
→ GeeRasterSource / LocalRasterSource
→ validation et profil RGB
→ tuilage géoréférencé
→ BuildingModelAdapter REAL
→ U-Net / ResNet-34
→ cartes de probabilités
→ fusion et post-traitement
→ masque global
→ polygonisation
→ BuildingAnalysisResult
→ GeoJSON EPSG:4326 + statistiques
→ couche frontend + exports
```

## État consolidé

- `REAL MODEL = OUI`
- `MODEL_MODE = REAL`
- `REAL ORTHOPHOTO = OUI, COG ORIGINAUX NON DIRECTEMENT COMPATIBLES`
- `SCIENTIFIC ACCURACY = NON VALIDÉE`
- Backend final : **209 tests réussis, 0 échec**
- Frontend final : **tests réussis, build client et SSR réussis**
- Exports disponibles : **GeoJSON, CSV, metadata JSON via API, ZIP**
- Exports non implémentés : **SHP, GeoPackage**

Les documents 1 à 11 décrivent les réalisations. Les compléments 10B et 10C consignent la validation réelle et le diagnostic radiométrique Maxar. Le document 10D prépare l’annotation humaine et l’évaluation objective ; l’exactitude scientifique reste bloquée tant que le ground truth n’est pas annoté.

