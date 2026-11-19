# GeoRaster — Présentation client haut niveau

## Positionnement
GeoRaster est une plateforme WebGIS de télédétection qui transforme une zone d’intérêt et une période d’analyse en couches cartographiques, indicateurs et exports exploitables. Elle combine des sources satellitaires via Google Earth Engine avec un traitement local d’orthophotos et un moteur IA dédié à la détection des bâtiments.

## Structure proposée du support

1. **Couverture** — GeoRaster, plateforme WebGIS de télédétection et d’analyse raster.
2. **GeoRaster en un coup d’œil** — Carte, catalogue, analyses, historique et exports dans un même parcours.
3. **Problème métier** — Données dispersées, traitements difficiles à reproduire, délais de production et résultats peu traçables.
4. **Proposition de valeur** — Un parcours unique AOI → source → analyse → résultat → export.
5. **Utilisateurs et cas d’usage** — Analystes SIG, environnement, agriculture, urbanisme et surveillance.
6. **Périmètre fonctionnel actuel** — GEE/Sentinel, indices, changement, classifications, IA bâtiments, mode local et exports.
7. **Accès aux images satellitaires** — Recherche par AOI, période, capteur et couverture nuageuse, avec fallback local ou mock documenté.
8. **AOI et préparation** — Dessin de l’AOI, choix de la période, préparation du raster et visualisation Leaflet.
9. **Indices spectraux** — NDVI, NDWI, NDBI, BSI et SAVI, avec statistiques et visualisation.
10. **Détection du changement** — Comparaison temporelle, couches de différence et synthèse des zones évolutives.
11. **Classification supervisée** — Workflow prévu dans le produit et contrats de données présents, validation GEE à renforcer.
12. **Classification non supervisée** — Exploration de classes et contrôle visuel, avec validation scientifique à compléter selon le jeu de données.
13. **Détection IA des bâtiments** — Raster source → préparation RGB → tuilage → inférence → fusion → polygones → statistiques → GeoJSON.
14. **MODEL_C, standard actuel** — DeepLabV3/ResNet-50, ONNX Runtime CPU par défaut, production et stable techniquement.
15. **Benchmarks IA** — C en production, D/D_ONNX/E en expérimentation et benchmark. Les performances historiques restent attribuées à leurs rapports.
16. **Mode local et offline** — Traitement d’orthophotos locales, cache, diagnostics et workflow ArcPy documenté pour les contextes contraints.
17. **Historique et catalogue** — Restauration d’un run sans recalcul, filtres, visualisation, export et suivi des paramètres.
18. **Exports et interopérabilité** — CSV, JSON, GeoTIFF, PNG/PDF selon le cas et GeoJSON/ZIP pour le bâtiment.
19. **Architecture fonctionnelle** — Frontend cartographique, API FastAPI, services d’analyse, catalogue, historique, exports et IA.
20. **Architecture technique** — React/TanStack Start/Leaflet côté client, FastAPI/Python côté serveur, Rasterio/NumPy/PyTorch/ONNX et GEE.
21. **Infrastructure actuelle** — Démonstration locale et préproduction ; modèle de production CPU ; authentification et multi-utilisateur restent à industrialiser.
22. **Faisabilité** — Réutilisation de composants ouverts, séparation des modes en ligne et local, montée en charge progressive.
23. **Économie de solution** — Coûts concentrés sur stockage raster, calcul et exploitation ; la queue, le stockage objet et le monitoring sont des étapes d’industrialisation.
24. **Feuille de route** — Fiabiliser les contrats raster et les tests réels, sécuriser l’architecture, puis industrialiser données, modèles et 3D.
25. **Capacités futures** — séries temporelles, validation scientifique, catalogue de modèles, 3D et automatisation des rapports.
26. **LLM géospatial et pilote client** — Assistant pour interroger les couches et expliquer les résultats, après gouvernance des données ; pilote avec objectifs et KPI mesurables.
27. **Conclusion** — Une base technique fonctionnelle, un standard IA identifié et une trajectoire claire vers l’exploitation.

## Faits et limites à afficher

- MODEL_C (`spacenet2_deeplab`) est le seul modèle Building présenté comme production et défaut logiciel.
- MODEL_D, MODEL_D_ONNX et MODEL_E restent expérimentaux ou benchmark-only.
- La simulation 3D, l’authentification, la production multi-utilisateur, PostgreSQL/PostGIS et les fonctions avancées de classification restent dans la feuille de route ou hors périmètre actuel.
- Les métriques de performance des anciens rapports sont des repères d’ingénierie, pas des scores scientifiques généraux.
- Les visuels du support proviennent des résultats de validation du projet : orthophotos, masques, overlays et comparaisons de bâtiments.

## Sources projet

- `docs/FONCTIONNALITES.md`
- `docs/01_VUE_GLOBALE_PROJET.md`
- `docs/08_ANALYSES_GEOSPATIALES.md`
- `docs/09_CHANGE_DETECTION.md`
- `docs/13_EXPORTS_GEOSPATIAUX.md`
- `docs/18_DEPLOIEMENT.md`
- `docs/21_ROADMAP.md`
- `docs/BUILDING_AI_MODEL_STATUS.md`
- `docs/BUILDING_AI_PRODUCTION_BASELINE_13P.md`
- `docs/ETAPE_13T_BUILDING_DETECTION_USER_ACCEPTANCE_TEST.md`

## Visuels utilisés

- `test-data/validation-results/real-building-test/building_detection_comparison_2024_2025.png`
- `test-data/validation-results/overlay_comparison_2024_2025.png`
- `test-data/validation-results/maxar_rgb_derivatives/quicklook_comparison.png`
- `test-data/diagnostics/13O1/orthophoto_preview.png`
- `test-data/diagnostics/13N3/13N3_model_d_contact_sheet.png`
- `test-data/diagnostics/13L4/AOI_03_dense_urban/comparison.png`
