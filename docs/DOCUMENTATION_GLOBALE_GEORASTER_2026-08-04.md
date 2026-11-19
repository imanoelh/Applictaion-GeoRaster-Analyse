# Documentation globale de GeoRasterPortal

**Date de référence : 4 août 2026**
**Application : GeoRaster / GeoRasterPortal**
**Branche : `dev_v1`**
**Dépôt : `https://github.com/gissolutionsib/RaterPortal.git`**
**Version de code documentée : commit `5d7ef608467003f6535c9323c2cf9df14d6466bf`**
**Nature du produit : prototype WebGIS avancé d’analyse raster**

---

## Sommaire

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Objectifs et utilisateurs](#2-objectifs-et-utilisateurs)
3. [Périmètre réel de la version](#3-périmètre-réel-de-la-version)
4. [Architecture générale](#4-architecture-générale)
5. [Structure du dépôt](#5-structure-du-dépôt)
6. [Technologies](#6-technologies)
7. [Frontend et expérience utilisateur](#7-frontend-et-expérience-utilisateur)
8. [Workflow complet d’une analyse](#8-workflow-complet-dune-analyse)
9. [Données et collections satellitaires](#9-données-et-collections-satellitaires)
10. [Analyses raster disponibles](#10-analyses-raster-disponibles)
11. [Classification supervisée](#11-classification-supervisée)
12. [Classification non supervisée](#12-classification-non-supervisée)
13. [Détection OSI-SAR](#13-détection-osi-sar)
14. [Mosaïques, nuages et qualité](#14-mosaïques-nuages-et-qualité)
15. [Cartographie et gestion des couches](#15-cartographie-et-gestion-des-couches)
16. [Référentiels spatiaux et CRS](#16-référentiels-spatiaux-et-crs)
17. [Google Earth Engine](#17-google-earth-engine)
18. [Contrat de données de l’API](#18-contrat-de-données-de-lapi)
19. [Référence complète des API](#19-référence-complète-des-api)
20. [Persistance, historique, cache et jobs](#20-persistance-historique-cache-et-jobs)
21. [Exports et rapports](#21-exports-et-rapports)
22. [Paramètres et internationalisation](#22-paramètres-et-internationalisation)
23. [Installation et lancement](#23-installation-et-lancement)
24. [Tests et validation](#24-tests-et-validation)
25. [Gestion des erreurs et exploitation](#25-gestion-des-erreurs-et-exploitation)
26. [Sécurité](#26-sécurité)
27. [Limites connues](#27-limites-connues)
28. [Évolutions recommandées](#28-évolutions-recommandées)
29. [Checklist de recette](#29-checklist-de-recette)
30. [Références internes](#30-références-internes)

---

## 1. Résumé exécutif

GeoRasterPortal est une application WebGIS full stack destinée à l’analyse d’images raster satellitaires. Elle permet à un utilisateur de définir une zone d’intérêt, rechercher des images ou construire une mosaïque, lancer une analyse avec Google Earth Engine, visualiser le résultat sur une carte, consulter des statistiques et exporter les produits obtenus.

La version documentée comprend :

- cinq indices spectraux : NDVI, NDWI, NDBI, BSI et SAVI ;
- cinq analyses de changement entre deux périodes ;
- une détection de cibles sombres suspectes sur l’eau avec Sentinel-1, nommée OSI-SAR ;
- une classification supervisée guidée avec échantillons utilisateur ;
- une classification non supervisée par K-Means ;
- un catalogue, un dashboard, un historique, une page de paramètres et une carte analytique ;
- des sorties statistiques, GeoTIFF, PNG cartographique et PDF professionnel ;
- une interface anglais/arabe avec prise en charge RTL ;
- une persistance locale SQLite et un cache de traitements ;
- un mode Google Earth Engine réel et un mode de repli mock.

L’application est un **prototype avancé démontrable et fonctionnel en local**. Elle n’est pas encore une plateforme de production multi-utilisateur : l’authentification applicative, l’autorisation forte, les jobs distribués et une base de données serveur ne sont pas implémentés.

---

## 2. Objectifs et utilisateurs

### 2.1 Objectifs métier

GeoRaster vise à :

- rendre l’analyse raster accessible depuis un navigateur ;
- centraliser la sélection des données, les paramètres et les résultats ;
- exploiter la capacité de calcul de Google Earth Engine sans exposer sa complexité à l’utilisateur ;
- produire des indicateurs reproductibles pour la végétation, l’eau, le bâti et les sols nus ;
- comparer deux périodes afin de localiser des changements ;
- proposer des classifications d’occupation du sol guidées ou automatiques ;
- conserver un historique des analyses et de leurs exports ;
- fournir des livrables réutilisables dans un SIG ou un rapport.

### 2.2 Utilisateurs visés

Le produit s’adresse principalement aux :

- analystes SIG et télédétection ;
- équipes environnementales et territoriales ;
- spécialistes de l’occupation du sol ;
- opérateurs de suivi agricole, hydrologique ou urbain ;
- équipes de surveillance maritime utilisant OSI-SAR comme outil de présélection ;
- décideurs consultant les cartes et rapports produits par un analyste.

Ces profils sont fonctionnels. Le code ne contient actuellement ni gestion de comptes, ni rôles applicatifs persistants.

### 2.3 Cas d’usage principaux

- évaluer la vigueur ou la densité de la végétation ;
- détecter l’eau libre, l’humidité ou leur évolution ;
- cartographier les réponses bâties et imperméables ;
- repérer les sols nus et leur évolution ;
- suivre la végétation en milieu semi-aride ;
- comparer une zone entre deux périodes ;
- produire une carte d’occupation du sol ;
- présélectionner des cibles sombres SAR suspectes sur l’eau ;
- générer un rapport PDF, une carte PNG, un GeoTIFF ou des statistiques CSV.

---

## 3. Périmètre réel de la version

### 3.1 Fonctionnalités opérationnelles

- navigation entre Dashboard, Map & Analysis, Image Catalog, History et Settings ;
- définition d’une AOI rectangulaire sur une carte Leaflet ;
- affichage ou masquage indépendant de l’AOI, de l’image source et du résultat ;
- choix de cinq fonds de carte ;
- recherche asynchrone d’images/mosaïques avec suivi de progression ;
- calcul réel sur GEE lorsque l’authentification est valide ;
- repli mock lorsque GEE est indisponible pour les workflows qui l’autorisent ;
- calcul, cache, restauration depuis l’historique et régénération de tuiles ;
- statistiques zonales, histogrammes, classes, surfaces et pourcentages ;
- sous-couches période 1, période 2 et changement pour les analyses temporelles ;
- workflow guidé de classification supervisée en trois étapes ;
- dessin de points et polygones d’apprentissage ou de validation ;
- personnalisation du nom et de la couleur des clusters non supervisés ;
- exports bilingues anglais/arabe ;
- persistance du profil, du logo, du fond de carte, des unités et des CRS.

### 3.2 Fonctions expérimentales ou partielles

- la référence géographique 3D EPSG:9332 est configurable, mais aucun moteur 3D n’est implémenté ;
- le frontend possède une cible de build Cloudflare, mais le déploiement full stack n’est pas finalisé ;
- les outils « mesure de distance », « mesure de surface » et « import GeoJSON » affichent actuellement des notifications mais ne constituent pas des outils SIG complets ;
- le profil, la clé API et le rôle administrateur visibles dans les paramètres ne forment pas une authentification de production.

---

## 4. Architecture générale

```text
Utilisateur
   |
   v
Frontend React / TanStack Start / Vite
   |-- routes, formulaires, carte Leaflet, i18n anglais/arabe
   |-- client HTTP georaster-api.ts
   |
   v
API FastAPI : backend/app/main.py
   |-- validation Pydantic et normalisation des contrats
   |-- gestion des analyses, runs, cache, historique et exports
   |-- paramètres de plateforme et fichiers statiques
   |
   +--------------------+
   |                    |
   v                    v
SQLite local       Moteur gee_client.py
   |                    |
   |                    +--> Google Earth Engine
   |                    +--> mock_engine.py si repli autorisé
   |
   v
Analyses, résultats, modèles, métriques, exports
```

### 4.1 Principes d’architecture

- le frontend ne calcule pas les indices ; il prépare les paramètres et présente les résultats ;
- FastAPI est l’orchestrateur central ;
- `request_contracts.py` accepte le contrat canonique actuel et maintient la compatibilité avec l’ancien contrat ;
- `gee_client.py` construit les collections, mosaïques, indices, classifications et URL de tuiles ;
- SQLite conserve l’état fonctionnel local ;
- les URL de tuiles GEE étant temporaires, l’API peut les régénérer à partir du run stocké ;
- le cache est versionné par type de traitement afin d’éviter la réutilisation de résultats devenus incompatibles.

---

## 5. Structure du dépôt

```text
GeoRasterPortal-03-08/
|-- backend/
|   |-- app/
|   |   |-- main.py                 API FastAPI, cache, exports, PDF, CRS
|   |   |-- gee_client.py           moteur Google Earth Engine
|   |   |-- mock_engine.py          résultats de démonstration hors GEE
|   |   |-- models.py               modèles Pydantic
|   |   |-- request_contracts.py    contrat canonique et compatibilité
|   |   |-- db.py                   schéma et accès SQLite
|   |   |-- catalog.py              sources, indices et scènes de démonstration
|   |   |-- platform_store.py       paramètres et logo
|   |   |-- report_i18n.py          textes des rapports anglais/arabe
|   |   `-- run_tile_cache.py       cache mémoire des tuiles régénérées
|   |-- tests/                       suite pytest
|   |-- data/                        base et paramètres locaux, ignorés par Git
|   |-- exports/                     fichiers générés
|   |-- uploads/                     logo importé
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- routes/                  pages TanStack
|   |   |-- components/              carte, navigation et composants UI
|   |   |-- lib/                     API, contrat, i18n et recoloration
|   |   |-- data/mock.ts             métadonnées et fallback frontend
|   |   `-- i18n/                    dictionnaires en.json et ar.json
|   |-- scripts/                     contrôle des légendes bilingues
|   |-- package.json
|   |-- vite.config.ts
|   `-- wrangler.jsonc
|-- docs/                             documentation fonctionnelle et technique
|-- README.md
`-- .gitignore
```

---

## 6. Technologies

### 6.1 Backend

| Technologie | Version déclarée | Rôle |
|---|---:|---|
| Python | 3.11 sur le poste validé | langage backend |
| FastAPI | 0.115.6 | API REST et documentation OpenAPI |
| Uvicorn | 0.32.1 | serveur ASGI local |
| Pydantic | 2.12.4 | validation et normalisation des payloads |
| Earth Engine API | >= 1.5.0 | accès aux collections et calculs GEE |
| Pillow | >= 10.0.0 | rapports PDF et cartes PNG |
| HTTPX | 0.28.1 | client HTTP disponible côté backend |
| arabic-reshaper | 3.0.1 | mise en forme arabe dans les images/PDF |
| python-bidi | 0.6.11 | ordre bidirectionnel pour le rendu RTL |
| SQLite | bibliothèque Python | persistance locale |

### 6.2 Frontend

| Technologie | Version déclarée | Rôle |
|---|---:|---|
| React / React DOM | 19.2.0 | interface utilisateur |
| TanStack Start | 1.167.x | application, SSR et routage full stack frontend |
| TanStack Router | 1.168.x | routes typées |
| TanStack Query | 5.83.x | dépendance disponible pour l’état serveur |
| Vite | 7.3.x | développement et build |
| TypeScript | 5.8.x | typage du frontend |
| Leaflet | 1.9.4 | moteur cartographique |
| React Leaflet | 5.0.0 | intégration React de Leaflet |
| Tailwind CSS | 4.2.x | styles utilitaires |
| Radix UI | composants multiples | composants accessibles |
| Recharts | 3.8.x | graphiques et visualisations |
| Lucide React | 0.575.x | iconographie |
| Sonner | 2.0.7 | notifications |
| date-fns | 4.1.0 | manipulation des dates |

### 6.3 Infrastructure actuelle

- développement local sous Windows/PowerShell ;
- backend par défaut sur `127.0.0.1:8010` ;
- frontend par défaut sur `127.0.0.1:5183` ;
- build frontend client et SSR ;
- configuration Cloudflare Worker présente pour le frontend ;
- stockage local, sans service externe de base de données.

---

## 7. Frontend et expérience utilisateur

### 7.1 Routes principales

| Route | Page | Fonctions |
|---|---|---|
| `/` | Dashboard | compteurs, analyses récentes, catalogue des indices |
| `/map` | Map & Analysis | AOI, recherche, paramètres, calcul, couches, résultats, exports |
| `/catalog` | Image Catalog | filtres par capteur, région, nuage et recherche textuelle |
| `/history` | History | runs, statuts, surfaces, consultation, export et suppression |
| `/settings` | Settings | profil, logo, fond, export, unités, backend et CRS |

### 7.2 Carte analytique

La page `/map` regroupe :

- un panneau de paramètres d’analyse ;
- un panneau cartographique Leaflet ;
- des onglets Images, Layers, Basemap et Tools ;
- une zone de résultats avec statistiques, classes, histogrammes et interprétation ;
- les boutons d’export.

La carte affiche :

- le fond de carte sélectionné ;
- les coordonnées du curseur ;
- une échelle ;
- l’AOI ;
- l’image RGB source ;
- le raster de résultat ;
- les points et polygones de classification supervisée ;
- une légende synchronisée avec la couche active.

### 7.3 Fonds de carte

- OpenStreetMap ;
- Google Satellite ;
- Esri World Imagery, nommé Satellite dans l’interface ;
- OpenTopoMap ;
- CARTO Light.

Ces fonds utilisent des services tiers. Leur disponibilité et leurs conditions d’utilisation dépendent de leurs fournisseurs.

### 7.4 Langues

- anglais, langue scientifique canonique des résultats stockés ;
- arabe, avec direction RTL, labels métier et exports localisés.

Les identifiants techniques tels que `NDVI`, `Sentinel-2`, `GeoTIFF` et les codes EPSG restent inchangés.

---

## 8. Workflow complet d’une analyse

1. L’utilisateur ouvre `/map`.
2. Il choisit une analyse et un capteur compatible.
3. Il définit les dates, le seuil de nuages et la résolution demandée.
4. Pour une détection de changement, il définit deux périodes.
5. Il dessine une AOI rectangulaire.
6. Le frontend transforme l’AOI en GeoJSON Polygon en coordonnées longitude/latitude.
7. La recherche démarre par `POST /api/gee/jobs/catalog`.
8. Le frontend interroge `GET /api/gee/jobs/{job_id}/status` jusqu’à la fin.
9. Une scène ou une mosaïque est affichée en RGB.
10. Avant calcul, le frontend cherche un résultat compatible dans `/api/result-cache/search`.
11. Si nécessaire, il crée l’analyse avec `POST /api/analyses`.
12. Il lance le run avec `POST /api/analyses/{analysis_id}/run`.
13. Le backend détermine le CRS effectif et la version de traitement.
14. Il réutilise le cache compatible ou exécute le moteur GEE/mock.
15. Le résultat est stocké dans `runs` et `processing_cache`.
16. Le frontend récupère `/api/runs/{run_id}/result`.
17. La carte, la légende, les classes, les statistiques et les graphiques sont mis à jour.
18. L’utilisateur peut restaurer ce run depuis History ou générer un export.

Le paramètre `force=true` du endpoint de run permet d’ignorer le cache et de recalculer.

---

## 9. Données et collections satellitaires

| Donnée | Identifiant GEE | Usage |
|---|---|---|
| Sentinel-2 SR harmonisé | `COPERNICUS/S2_SR_HARMONIZED` | indices, changements, classifications, RGB |
| Probabilité de nuage S2 | `COPERNICUS/S2_CLOUD_PROBABILITY` | masque nuage Sentinel-2 |
| Landsat 8 L2 | `LANDSAT/LC08/C02/T1_L2` | indices, changements et classifications à 30 m |
| Landsat 9 L2 | `LANDSAT/LC09/C02/T1_L2` | même usage |
| Sentinel-1 GRD | `COPERNICUS/S1_GRD` | OSI-SAR, bandes VV/VH, mode IW |
| Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | probabilités bâti/sol nu pour NDBI |
| ESA WorldCover | `ESA/WorldCover/v200` | référence supervisée et confirmation du bâti |
| GHSL Built Surface 2018 | `JRC/GHSL/P2023A/GHS_BUILT_S_10m/2018` | récupération conservatrice du bâti historique |
| JRC Global Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | masque d’eau OSI-SAR |
| ERA5 / ERA5-Land | collections ECMWF quotidiennes | contexte de vent OSI-SAR |

Résolutions natives utilisées par le moteur :

- Sentinel-2 : 10 m ;
- Landsat 8/9 : 30 m ;
- Sentinel-1 : classification à 10 m, statistiques OSI-SAR à 30 m par défaut.

Dynamic World et ESA WorldCover sont proposés dans certains contrats de capteurs mais servent principalement de données auxiliaires. Les 13 traitements exécutables n’utilisent pas ces deux sources comme capteurs d’entrée autonomes.

---

## 10. Analyses raster disponibles

### 10.1 Vue générale

| Identifiant | Objectif | Capteurs |
|---|---|---|
| `NDVI` | couverture et vigueur de la végétation | Sentinel-2, Landsat 8/9 |
| `NDWI` | eau et humidité | Sentinel-2, Landsat 8/9 |
| `NDBI` | réponse bâtie et détection multi-observation | Sentinel-2, Landsat 8/9 |
| `BSI` | sols nus et surfaces sèches | Sentinel-2, Landsat 8/9 |
| `SAVI` | végétation avec correction de l’effet du sol | Sentinel-2, Landsat 8/9 |
| `CHANGE_NDVI` | perte/stabilité/gain de végétation | Sentinel-2, Landsat 8/9 |
| `CHANGE_NDWI` | diminution/stabilité/augmentation d’eau ou humidité | Sentinel-2, Landsat 8/9 |
| `CHANGE_NDBI` | évolution de l’évidence bâtie | Sentinel-2, Landsat 8/9 |
| `CHANGE_BSI` | évolution du sol nu | Sentinel-2, Landsat 8/9 |
| `CHANGE_SAVI` | évolution de végétation semi-aride | Sentinel-2, Landsat 8/9 |
| `OSI_SAR` | cibles sombres suspectes sur l’eau | Sentinel-1 |
| `SUPERVISED_CLASSIFICATION` | occupation du sol guidée | Sentinel-2, Landsat 8/9 |
| `UNSUPERVISED_CLASSIFICATION` | regroupement spectral automatique | Sentinel-2, Landsat 8/9 |

### 10.2 Formules

| Indice | Formule |
|---|---|
| NDVI | `(NIR - Red) / (NIR + Red)` |
| NDWI | `(Green - NIR) / (Green + NIR)` |
| NDBI | `(SWIR - NIR) / (SWIR + NIR)` |
| BSI | `((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))` |
| SAVI | `((NIR - Red) / (NIR + Red + 0.5)) × 1.5` |

### 10.3 Bandes

| Indice | Sentinel-2 | Landsat 8/9 |
|---|---|---|
| NDVI | B8, B4 | SR_B5, SR_B4 |
| NDWI | B3, B8 | SR_B3, SR_B5 |
| NDBI | B11, B8 | SR_B6, SR_B5 |
| BSI | B11, B4, B8, B2 | SR_B6, SR_B4, SR_B5, SR_B2 |
| SAVI | B8, B4 | SR_B5, SR_B4 |

### 10.4 NDBI Raw et Built-up detection

Le backend conserve deux lectures complémentaires :

- `ndbi_raw` : valeur continue de la formule NDBI ;
- `ndbi_built_detection` : interprétation métier en quatre classes.

La couche Built-up croise NDBI, NDVI, NDWI, BSI et, pour Sentinel-2, Dynamic World, ESA WorldCover et GHSL. L’objectif est de limiter les faux positifs sur sols nus et de récupérer certains toits clairs lorsqu’une preuve auxiliaire converge.

Classes visibles :

1. No built-up evidence ;
2. Potential impervious surface or road ;
3. Built-up area detected ;
4. High-confidence built-up area.

GHSL utilise un seuil conservateur de 50 m² bâtis par cellule de 100 m² et ne doit pas créer seul une classe de haute confiance.

### 10.5 Détection de changement

Pour NDVI, NDWI, BSI et SAVI :

```text
delta = indice période 2 - indice période 1
```

Chaque résultat contient :

- la couche de la période 1 ;
- la couche de la période 2 ;
- la couche de changement ;
- les statistiques et classes associées à la couche active.

Pour `CHANGE_NDBI`, le backend ne compare pas seulement deux valeurs Raw. Il calcule la détection Built-up pour chaque période, puis compare les classes d’évidence bâtie. La classe stable est centrée autour de zéro ; les valeurs négatives indiquent une baisse et les positives une augmentation de l’évidence bâtie.

Une alerte saisonnière peut être produite lorsque les périodes ne sont pas comparables. L’interprétation reste une aide et ne remplace pas une validation terrain.

---

## 11. Classification supervisée

### 11.1 Workflow guidé

Le frontend propose trois étapes :

1. choisir au moins deux classes et l’algorithme ;
2. dessiner des échantillons de training ou validation dans l’AOI ;
3. vérifier la configuration et lancer le calcul.

Les géométries acceptées sont :

- Point ;
- Polygon fermé automatiquement par le backend.

Seuls les échantillons appartenant au projet demandé et intersectant l’AOI courante sont utilisés.

### 11.2 Algorithmes

- Random Forest, 150 arbres par défaut, plage backend 50 à 500 ;
- CART ;
- SVM RBF avec `gamma=0.5` et `cost=10`.

Le frontend peut demander la comparaison des trois algorithmes. Le résultat principal utilise l’algorithme sélectionné.

### 11.3 Variables d’entrée

La pile de classification contient :

- les bandes spectrales du capteur ;
- NDVI ;
- NDWI ;
- NDBI ;
- BSI ;
- SAVI.

### 11.4 Échantillonnage et validation

- split training par défaut : 70 %, borné entre 50 % et 85 % ;
- échantillons par classe : 160 par défaut, bornés entre 40 et 500 ;
- minimum après échantillonnage : 40 pixels de training et 10 pixels de validation ;
- si aucune géométrie de validation n’est fournie, une séparation aléatoire est créée ;
- le mode guidé strict exige un échantillon de training pour chaque classe sélectionnée.

Si le mode strict n’est pas demandé ou si un workflow compatible l’autorise, ESA WorldCover peut servir de référence de repli.

### 11.5 Résultats

- raster classifié avec filtre modal 3 × 3 ;
- surfaces et pourcentages par classe ;
- matrice de confusion ;
- exactitude globale ;
- coefficient Kappa ;
- précision producteur et utilisateur ;
- erreurs d’omission et de commission ;
- comparaison RF/CART/SVM ;
- avertissement si l’exactitude globale est inférieure à 0,65.

---

## 12. Classification non supervisée

### 12.1 Principe

Le moteur utilise `ee.Clusterer.wekaKMeans` sur une pile spectrale. Aucun échantillon d’apprentissage utilisateur n’est nécessaire.

### 12.2 Modes

- Simple : bandes choisies automatiquement ;
- Expert : l’utilisateur choisit les bandes, avec au moins deux variables.

Paramètres :

- 6 clusters par défaut, bornés entre 2 et 12 ;
- 5 000 pixels échantillonnés par défaut, bornés entre 500 et 20 000 ;
- seed par défaut : 91.

### 12.3 Interprétation

Chaque cluster est caractérisé par ses moyennes NDVI, NDWI, NDBI, BSI et SAVI. Le backend lui associe ensuite une interprétation sémantique indicative : eau, végétation dense, cultures/végétation basse, bâti, sol nu, zone humide/mixte ou cluster non interprété.

Les clusters sont réordonnés par signature spectrale afin de stabiliser les codes entre les réponses. Un filtre modal réduit le bruit ponctuel.

### 12.4 Personnalisation

Après calcul, l’utilisateur peut modifier :

- le nom d’un cluster ;
- sa couleur au format `#RRGGBB`.

Les changements sont synchronisés dans le run, le cache et les artefacts de classification. Le frontend peut recolorer localement les pixels de tuile sans recalcul GEE lorsqu’il connaît la palette source et la palette d’affichage.

---

## 13. Détection OSI-SAR

OSI-SAR recherche des cibles sombres potentielles sur l’eau à partir de Sentinel-1 VV/VH. Ce traitement est une **détection de suspects**, pas une preuve de pollution pétrolière.

### 13.1 Méthode

- sélection Sentinel-1 GRD, mode IW, polarisations VV et VH ;
- composite médian ;
- filtre médian pour réduire le speckle ;
- comparaison à un seuil VV sombre ;
- comparaison à un seuil VH sombre ;
- contraste avec la moyenne locale ;
- masque d’eau JRC optionnel ;
- suppression des petites composantes isolées ;
- score de suspicion de 0 à 3.

### 13.2 Paramètres par défaut

- VV sombre : -18 dB ;
- VH sombre : -25 dB ;
- contraste : 2,5 dB ;
- rayon de contraste : 500 m ;
- rayon speckle : 30 m ;
- surface minimale : 0,5 ha ;
- occurrence d’eau : 50 % ;
- orbite : ANY ;
- statistiques : 30 m ;
- validation ERA5 activée ;
- validation visuelle Sentinel-2 désactivée par défaut.

### 13.3 Classes

1. Normal water ;
2. Low oil-spill suspicion ;
3. Medium oil-spill suspicion ;
4. High oil-spill suspicion.

Le vent, les navires, les ports, les courants, les fronts océaniques et l’imagerie optique doivent être pris en compte avant toute conclusion.

---

## 14. Mosaïques, nuages et qualité

### 14.1 Politique Sentinel-2

- filtrage par AOI et dates ;
- filtrage de métadonnée par pourcentage maximal de nuages ;
- jointure avec la collection de probabilité de nuage ;
- masque SCL et probabilité de nuage inférieure à 40 ;
- composite médian imposé par la politique backend ;
- découpage final à l’AOI.

### 14.2 Landsat

- fusion Landsat 8/9 L2 ;
- masque QA ;
- composite médian ;
- calcul à 30 m.

### 14.3 Grandes AOI

- au-delà de 350 km², Sentinel-2 peut être découpé en tuiles d’environ 20 km ;
- maximum : 80 tuiles estimées ;
- au-delà de 5 000 km² : avertissement ;
- au-delà de 15 000 km² : traitement asynchrone recommandé ;
- au-delà de 32 000 km² : blocage du MVP.

### 14.4 Indicateurs de qualité

Le résultat peut contenir :

- nombre d’images ;
- nombre de tuiles ;
- tuiles valides, vides, faibles ou en erreur ;
- couverture en pourcentage ;
- qualité bonne, moyenne ou faible ;
- avertissement ;
- seuil de nuage ;
- rapport détaillé par tuile.

---

## 15. Cartographie et gestion des couches

Le gestionnaire de couches permet de contrôler :

- visibilité et opacité de l’image multispectrale ;
- visibilité indépendante de l’AOI sans supprimer sa géométrie ;
- visibilité et opacité du résultat ;
- sous-couche active d’une détection de changement ;
- affichage des échantillons supervisés ;
- fond de carte.

La suppression de l’AOI efface la sélection et la masque. Un nouveau dessin la rend de nouveau visible.

Lorsque l’URL d’une tuile GEE a expiré, le frontend peut demander `refresh=true` à `/api/runs/{run_id}/tiles`. Le backend reconstruit alors les URL à partir de l’analyse stockée.

---

## 16. Référentiels spatiaux et CRS

### 16.1 Références utilisées

- AOI GeoJSON d’entrée : EPSG:4326 ;
- carte web Leaflet : EPSG:3857 ;
- système national déclaré : SANSRS / KSA-GRF17 ;
- analyse automatique : UTM KSA-GRF17 selon la longitude centrale ;
- référence 3D expérimentale : EPSG:9332.

### 16.2 CRS proposés

| Code | Usage |
|---|---|
| EPSG:9333 | KSA-GRF17 géographique 2D, sélection manuelle |
| EPSG:9356 | KSA-GRF17 / UTM 36N |
| EPSG:9357 | KSA-GRF17 / UTM 37N |
| EPSG:9358 | KSA-GRF17 / UTM 38N |
| EPSG:9359 | KSA-GRF17 / UTM 39N |
| EPSG:9360 | KSA-GRF17 / UTM 40N |
| EPSG:9332 | KSA-GRF17 géographique 3D, expérimental |

En mode automatique, la zone UTM est déterminée par la longitude centrale de l’AOI. Si l’AOI traverse plusieurs zones, une alerte est retournée et la zone centrale est utilisée.

Pour l’exécution GEE, les CRS KSA-GRF17 projetés sont associés à leurs équivalents WGS84 UTM EPSG:32636 à EPSG:32640. EPSG:9332 n’est pas appliqué aux calculs raster, surfaces ou GeoTIFF ; il reste une référence de simulation future sans hauteur disponible.

---

## 17. Google Earth Engine

### 17.1 Initialisation

Le backend tente :

1. `ee.Initialize(project=...)` si `GEE_PROJECT_ID` ou `GOOGLE_CLOUD_PROJECT` existe ;
2. sinon `ee.Initialize()` avec les credentials et le projet par défaut persistés par le CLI Earth Engine.

L’initialisation est effectuée dans un thread avec temporisation et intervalle avant nouvelle tentative. Le endpoint `/api/gee/status` expose l’état, la collection et la dernière erreur.

### 17.2 Authentification persistante recommandée

```powershell
earthengine authenticate --auth_mode=localhost --force
earthengine set_project "VOTRE_ID_PROJET_GCP"
```

Cette méthode ne nécessite ni fichier `.env`, ni variable d’environnement, ni environnement virtuel. Les credentials GEE ne doivent jamais être ajoutés au dépôt.

### 17.3 Mode mock

Lorsque GEE n’est pas disponible :

- le catalogue et plusieurs analyses retournent des données mock cohérentes avec le contrat ;
- les tuiles réelles, téléchargements GEE PNG et GeoTIFF ne sont pas disponibles ;
- la classification supervisée guidée stricte refuse de continuer, car elle exige GEE et les échantillons réels ;
- un résultat mock en cache n’est pas réutilisé lorsque GEE redevient disponible.

---

## 18. Contrat de données de l’API

### 18.1 URL et format

- base locale : `http://127.0.0.1:8010` ;
- JSON pour les requêtes métier ;
- fichiers binaires ou streaming pour les téléchargements ;
- documentation OpenAPI : `http://127.0.0.1:8010/docs`.

### 18.2 Payload canonique

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[46.60, 24.60], [46.85, 24.60], [46.85, 24.80], [46.60, 24.80], [46.60, 24.60]]]
  },
  "start_date": "2026-01-01",
  "end_date": "2026-03-31",
  "sensor": "sentinel-2",
  "resolution": "auto",
  "cloud_max": 25,
  "index": "NDVI",
  "analysis_type": "spectral_index"
}
```

Le backend dérive les anciens champs `aoi`, `date_start`, `date_end`, `source` et `max_cloud_pct`. Les anciens clients restent compatibles.

### 18.3 Détection de changement

```json
{
  "name": "NDVI Change Detection",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[46.60, 24.60], [46.85, 24.60], [46.85, 24.80], [46.60, 24.80], [46.60, 24.60]]]
  },
  "sensor": "sentinel-2",
  "resolution": "auto",
  "cloud_max": 25,
  "analysis_type": "change_detection_ndvi",
  "period_1": { "start_date": "2025-01-01", "end_date": "2025-03-31" },
  "period_2": { "start_date": "2026-01-01", "end_date": "2026-03-31" }
}
```

### 18.4 Structure générale d’un résultat

```json
{
  "run": { "id": "...", "analysis_id": "...", "status": "succeeded" },
  "analysis_type": "spectral_index",
  "stats": {},
  "histogram": [],
  "classes": [],
  "palette": [],
  "tiles": {
    "rgb_tile_url": "...",
    "index_tile_url": "..."
  },
  "quality": {},
  "quality_summary": {},
  "comparison_layers": [],
  "interpretation": "...",
  "mode": "gee",
  "cached": false,
  "spatial_reference": {},
  "exports": []
}
```

Les classifications ajoutent notamment `accuracy`, `algorithm_comparison` ou `cluster_interpretation`.

---

## 19. Référence complète des API

La version expose **43 routes métier**.

### 19.1 Système et paramètres

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/api/health` | santé du backend |
| GET | `/api/gee/status` | état GEE et dernière erreur |
| GET | `/api/settings/platform` | paramètres et métadonnées CRS |
| PUT | `/api/settings/platform` | sauvegarde des paramètres |
| POST | `/api/settings/logo` | upload brut d’un logo, maximum 2 MB |
| POST | `/api/settings/logo/reset` | restauration du logo par défaut |

### 19.2 Dashboard et catalogue

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/api/dashboard` | compteurs, analyses récentes et indices |
| GET | `/api/catalog/sources` | sources déclarées |
| GET | `/api/catalog/indices` | indices, option `enabled_only` |
| GET | `/api/catalog/images` | catalogue local filtrable |
| POST | `/api/catalog/images/search` | recherche synchrone réelle/mock |
| POST | `/api/gee/jobs/catalog` | création d’une recherche asynchrone |
| GET | `/api/gee/jobs/{job_id}/status` | progression et résultat du job |
| GET | `/api/images` | alias du catalogue local |
| POST | `/api/gee/preview` | aperçu et qualité GEE/mock |

Filtres de `/api/catalog/images` : `sensor`, `region`, `max_cloud`, `q`.
Limite de recherche : 1 à 50, 12 utilisée par le frontend.

### 19.3 Classes et échantillons supervisés

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/api/classification/classes` | classes du projet et classes par défaut |
| POST | `/api/classification/classes` | création d’une classe |
| GET | `/api/classification/samples` | échantillons d’un projet |
| POST | `/api/classification/samples` | création Point/Polygon |
| PUT | `/api/classification/samples/{sample_id}` | modification classe/usage |
| DELETE | `/api/classification/samples/{sample_id}` | suppression d’un échantillon |
| DELETE | `/api/classification/classes/{class_id}/samples` | suppression des échantillons d’une classe |

`usage` vaut `training` ou `validation`. Les coordonnées sont contrôlées dans les bornes longitude/latitude.

### 19.4 Analyses et historique

| Méthode | Route | Fonction |
|---|---|---|
| POST | `/api/analyses` | création et enrichissement CRS |
| GET | `/api/analyses` | liste des analyses |
| GET | `/api/history` | historique centré sur les runs |
| GET | `/api/analyses/{analysis_id}` | détail d’une analyse |
| PUT | `/api/analyses/{analysis_id}` | mise à jour |
| DELETE | `/api/analyses/{analysis_id}` | suppression en cascade applicative |
| POST | `/api/analyses/{analysis_id}/run` | calcul, option `force` |
| POST | `/api/analysis/change-detection` | création et exécution directe d’un changement |

La suppression d’une analyse retire ses runs, exports, résultats de classification et entrées de cache associées. Les fichiers d’export liés sont également supprimés lorsqu’ils existent.

### 19.5 Cache et runs

| Méthode | Route | Fonction |
|---|---|---|
| POST | `/api/result-cache/search` | recherche par contexte et clé exacte |
| DELETE | `/api/result-cache/{cache_key}` | invalidation manuelle |
| GET | `/api/runs` | liste des runs |
| GET | `/api/runs/{run_id}` | état d’un run |
| GET | `/api/runs/{run_id}/result` | résultat complet |
| POST | `/api/runs/{run_id}/clusters/{cluster_code}/rename` | nom et/ou couleur d’un cluster |
| GET | `/api/runs/{run_id}/tiles` | tuiles stockées ou régénérées |

Paramètres des tuiles : `refresh` et `include_rgb`.

### 19.6 Exports

| Méthode | Route | Fonction |
|---|---|---|
| POST | `/api/runs/{run_id}/export` | CSV, JSON, PDF, PNG GEE ou GeoTIFF |
| POST | `/api/export/map-pdf` | rapport à partir d’un payload et captures |
| GET | `/api/runs/{run_id}/export/map-pdf` | rapport reconstruit depuis le run |
| POST | `/api/export/map-layout-png` | composition cartographique PNG |
| GET | `/api/exports` | liste des exports |
| GET | `/api/exports/{export_id}/download` | téléchargement ou streaming GEE |

Kinds de `/api/runs/{run_id}/export` :

- `stats_csv` ;
- `stats_json` ;
- `report_pdf` ;
- `map_png` ;
- `geotiff`.

`language` accepte `en` ou `ar`. `layer_key` permet de sélectionner notamment `ndbi_raw` ou `ndbi_built_detection`.

---

## 20. Persistance, historique, cache et jobs

### 20.1 Base SQLite

Fichier : `backend/data/georaster.db`.

| Table | Contenu |
|---|---|
| `analyses` | payload complet et dates |
| `runs` | état et résultat JSON |
| `exports` | métadonnées, bytes et chemin fichier |
| `processing_cache` | paramètres et résultat par clé |
| `landcover_classes` | classes supervisées |
| `training_samples` | géométries et rôle training/validation |
| `classification_models` | algorithme, bandes, hash et métadonnées |
| `classification_results` | run, palette, statistiques et mode |
| `validation_metrics` | matrice, accuracy, Kappa et erreurs |

Le journal SQLite utilise le mode WAL.

### 20.2 Cache

La clé de cache dépend notamment de l’AOI, des dates, du capteur, de l’indice, des options et de la version du traitement. Les versions courantes incluent par exemple :

- `ndbi-raw-plus-built-detection-v14` ;
- `change-ndbi-built-detection-periods-v4` ;
- `supervised-professional-v2` ;
- `unsupervised-clustering-v3` ;
- `osi-sar-v3`.

Au démarrage, les entrées incompatibles sont purgées. Le cache évite un nouveau calcul mais un nouveau run est tout de même enregistré pour l’historique.

### 20.3 Jobs et cache mémoire

- les recherches catalogue asynchrones sont conservées en mémoire dans le processus FastAPI ;
- le cache mémoire des tuiles régénérées a une durée maximale de 30 minutes ;
- ces données sont perdues au redémarrage du backend ;
- il n’existe pas de queue distribuée ou de worker externe.

---

## 21. Exports et rapports

### 21.1 CSV et JSON

- statistiques, classes et métadonnées ;
- contenu localisé en anglais ou arabe ;
- noms scientifiques officiels conservés lorsque nécessaire ;
- encodage UTF-8.

### 21.2 GeoTIFF

- URL de téléchargement générée par GEE ;
- image découpée à l’AOI ;
- échelle native du capteur ;
- CRS effectif lorsque disponible ;
- streaming par le backend, avec redirection de secours vers GEE.

Le code ne fixe pas explicitement NoData, `filePerBand` ou le type numérique final. Ces caractéristiques doivent être contrôlées avant un usage SIG contractuel.

### 21.3 PNG

Deux mécanismes existent :

- `map_png` via URL GEE pour la couche raster ;
- Map PNG professionnel, composition cartographique 1800 × 1280 avec carte, titre, légende, nord, échelle et localisation.

### 21.4 PDF professionnel

Le rapport peut inclure :

- couverture ;
- contexte et objectif ;
- zone d’étude ;
- image satellite de référence ;
- résultat analytique ;
- légende ;
- statistiques et graphiques ;
- interprétation ;
- paramètres et métadonnées ;
- pages spécifiques aux changements avec période 1, période 2 et delta.

Le rendu arabe utilise reshaping et algorithme bidirectionnel. Les captures frontend sont utilisées lorsqu’elles sont disponibles ; le backend peut aussi reconstruire les images depuis le run et les tuiles.

### 21.5 Stockage

- rapports : `backend/exports/reports/` ;
- mises en page PNG : `backend/exports/map-layouts/` ;
- autres exports persistés : `backend/exports/files/` et table `exports`.

Les sorties générées doivent normalement rester hors Git. Deux rapports de référence sont toutefois actuellement suivis dans le dépôt.

---

## 22. Paramètres et internationalisation

### 22.1 Paramètres persistés

Fichier local : `backend/data/platform_settings.json`.

- nom de plateforme, fixé à GeoRaster par le flux actuel ;
- logo ;
- nom et email déclaratifs du profil ;
- fond de carte par défaut ;
- format d’export par défaut ;
- unité : ha, km² ou m² ;
- type de serveur, endpoint et clé API déclarative ;
- mode de projection automatique ou manuel ;
- CRS manuel ;
- activation de la référence 3D expérimentale.

Le frontend conserve aussi une copie des paramètres dans `localStorage` pour accélérer l’affichage du logo et des valeurs.

### 22.2 Logo

- taille maximale : 2 MB ;
- formats reconnus : PNG, JPEG, GIF, WebP, SVG, BMP, AVIF et ICO ;
- fichiers stockés dans `backend/uploads/platform/` ;
- une seule version active ;
- possibilité de restaurer le logo par défaut.

### 22.3 i18n

- dictionnaires principaux : `frontend/src/i18n/en.json` et `ar.json` ;
- traductions métier complémentaires dans `map.tsx` ;
- traduction des légendes par `result-legend-i18n.ts` ;
- textes des rapports par `backend/app/report_i18n.py`.

---

## 23. Installation et lancement

### 23.1 Prérequis

- Git ;
- Python 3.11 recommandé ;
- Node.js 22 recommandé ;
- npm ;
- compte Google ayant accès à Earth Engine ;
- projet Google Cloud enregistré pour Earth Engine.

### 23.2 Clonage

```powershell
git clone -b dev_v1 https://github.com/gissolutionsib/RaterPortal.git
Set-Location -LiteralPath "RaterPortal"
```

### 23.3 Backend sans venv

```powershell
Set-Location -LiteralPath "backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Avec le Python Anaconda du poste de référence :

```powershell
& "C:\Users\Imane_C4E\anaconda3\python.exe" -m pip install -r requirements.txt
& "C:\Users\Imane_C4E\anaconda3\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

### 23.4 Authentification GEE sans `.env` et sans variables d’environnement

```powershell
& "C:\Users\Imane_C4E\anaconda3\Scripts\earthengine.exe" authenticate --auth_mode=localhost --force
& "C:\Users\Imane_C4E\anaconda3\Scripts\earthengine.exe" set_project "VOTRE_ID_PROJET_GCP"
```

Test :

```powershell
& "C:\Users\Imane_C4E\anaconda3\python.exe" -c "import ee; ee.Initialize(); print('GEE OK:', ee.Number(1).getInfo())"
```

### 23.5 Frontend

Dans un deuxième terminal :

```powershell
Set-Location -LiteralPath "frontend"
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5183
```

URLs :

- application : `http://127.0.0.1:5183/map` ;
- API : `http://127.0.0.1:8010` ;
- Swagger : `http://127.0.0.1:8010/docs`.

Le frontend utilise `http://127.0.0.1:8010` par défaut. `VITE_API_BASE_URL` est seulement une surcharge optionnelle.

### 23.6 Build

```powershell
Set-Location -LiteralPath "frontend"
npm.cmd run build
```

Pour servir localement le build SSR avec le script fourni :

```powershell
node serve-built.mjs
```

---

## 24. Tests et validation

### 24.1 Backend

Commande :

```powershell
Set-Location -LiteralPath "backend"
python -m pytest -q
```

La suite contient **59 tests** couvrant notamment :

- contrat canonique et rétrocompatibilité ;
- cycle analyse, run, cache, export, historique et suppression ;
- paramètres et CRS ;
- classes et échantillons supervisés ;
- règles du workflow supervisé guidé ;
- NDBI Built-up et CHANGE_NDBI ;
- palettes et métadonnées des indices ;
- OSI des résultats mock ;
- personnalisation et ordre stable des clusters ;
- rapports PDF adaptatifs ;
- exports anglais/arabe ;
- EPSG:9332 expérimental.

Deux avertissements FastAPI sont connus : `on_event` est déprécié au profit des lifespan handlers.

**Validation exécutée le 4 août 2026 : `59 passed, 2 warnings`.**

### 24.2 Frontend

```powershell
Set-Location -LiteralPath "frontend"
npm.cmd run test:legend-i18n
npm.cmd run build
```

Le build produit un client et un serveur SSR. Un avertissement de taille signale des chunks supérieurs à 500 kB ; il ne bloque pas la compilation.

État vérifié le 4 août 2026 :

- `npm.cmd run build` : **réussi** pour le client et le serveur SSR ;
- `npm.cmd run test:legend-i18n` : **en échec** sur cinq descriptions arabes manquantes pour `CHANGE_NDBI` : baisse de deux classes ou plus, baisse d’une classe, classe stable, hausse d’une classe et hausse de deux classes ou plus.

Cet échec i18n ne bloque pas le build, mais il doit être corrigé avant de considérer la couverture arabe des légendes comme complète.

### 24.3 Ce que les tests ne garantissent pas

- disponibilité réelle de toutes les collections GEE ;
- quotas du projet Google Cloud ;
- validité scientifique sur toutes les zones ;
- vérité terrain ;
- performance sur de très grandes AOI ;
- compatibilité de tous les fournisseurs de fonds de carte ;
- sécurité de production.

---

## 25. Gestion des erreurs et exploitation

### 25.1 Codes usuels

- 400 : payload ou fichier vide/invalide ;
- 403 : garde administrateur du logo ;
- 404 : analyse, run, job, échantillon, cache ou export absent ;
- 409 : classe supervisée dupliquée ;
- 413 : logo supérieur à 2 MB ;
- 415 : type de logo non supporté ;
- 422 : paramètres métier invalides ou données insuffisantes ;
- 502 : erreur GEE pendant un calcul.

### 25.2 Messages GEE

Le backend distingue notamment :

- quota GEE atteint ;
- timeout ;
- aucune image pour l’AOI/période ;
- couverture insuffisante ;
- AOI trop grande ;
- nombre insuffisant d’échantillons ;
- URL de tuile expirée.

### 25.3 Vérifications rapides

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/health"
Invoke-RestMethod "http://127.0.0.1:8010/api/gee/status" | ConvertTo-Json -Depth 5
```

Sans variables d’environnement, le champ `project` du statut peut être `null` alors que `enabled` est `true`, car le statut lit les variables mais `ee.Initialize()` peut utiliser le projet persistant du CLI.

---

## 26. Sécurité

### 26.1 État actuel

- aucune authentification utilisateur applicative ;
- aucune gestion de session ou JWT ;
- aucune autorisation par ressource ;
- CORS configuré avec `allow_origins=["*"]` ;
- garde logo basée sur `X-User-Role`, valeur par défaut `admin` ;
- clé API des Settings stockée mais non appliquée aux routes ;
- SQLite et fichiers accessibles au processus local ;
- credentials GEE gérés en dehors du dépôt par Google.

### 26.2 Conséquence

Le backend doit rester sur une machine ou un réseau maîtrisé. Il ne faut pas l’exposer tel quel sur Internet.

### 26.3 Mesures nécessaires avant production

- authentification OIDC/OAuth2 ;
- rôles et autorisations côté serveur ;
- restrictions CORS ;
- HTTPS ;
- secrets gérés par un coffre ;
- validation renforcée des uploads ;
- limites de requêtes et quotas utilisateurs ;
- journalisation d’audit ;
- isolation des données par projet/utilisateur ;
- suppression du rôle administrateur implicite.

---

## 27. Limites connues

1. `main.py` et `gee_client.py` sont très volumineux et monolithiques.
2. SQLite convient au prototype local, pas à une forte concurrence.
3. Les jobs asynchrones et le cache de tuiles sont en mémoire.
4. Les URL GEE expirent et doivent être régénérées.
5. Les calculs réels dépendent du réseau, des quotas et de l’accès GEE.
6. La résolution choisie dans l’interface est conservée dans le contrat, mais le moteur utilise principalement 10 m pour Sentinel-2 et 30 m pour Landsat.
7. Le GeoTIFF ne spécifie pas encore strictement NoData, dtype et métadonnées embarquées.
8. L’exactitude scientifique doit être validée par données de référence et terrain.
9. OSI-SAR ne peut pas confirmer seul une pollution pétrolière.
10. Les outils mesure/import GeoJSON ne sont pas finalisés.
11. La simulation 3D n’est pas implémentée.
12. Le profil et la clé API de Settings sont déclaratifs.
13. Le déploiement backend de production n’est pas fourni.
14. Le catalogue `/api/catalog/images` est un petit catalogue local mock ; la vraie recherche passe par GEE.
15. Certaines anciennes documentations du dépôt décrivent des états antérieurs et peuvent être contradictoires.
16. Le contrôle i18n signale cinq descriptions de légende `CHANGE_NDBI` encore absentes en arabe.

---

## 28. Évolutions recommandées

### Priorité 1 — Production et sécurité

- ajouter authentification, rôles et isolation multi-projet ;
- remplacer SQLite par PostgreSQL/PostGIS ;
- déployer le backend avec HTTPS ;
- restreindre CORS ;
- externaliser les secrets et les fichiers.

### Priorité 2 — Architecture

- séparer routes, services, dépôts, moteurs et exports ;
- introduire une queue de jobs, par exemple Celery/RQ et Redis ;
- persister les statuts de jobs ;
- ajouter migrations de base de données ;
- versionner formellement l’API.

### Priorité 3 — SIG et science

- spécifier dtype, NoData, compression et métadonnées GeoTIFF ;
- appliquer réellement les résolutions 10/20/30 m demandées ;
- ajouter import GeoJSON et outils de mesure réels ;
- intégrer une validation terrain ;
- ajouter tests GEE sur zones de référence ;
- documenter la sensibilité des seuils OSI-SAR et NDBI.

### Priorité 4 — Frontend

- découper les gros bundles ;
- fractionner `map.tsx` en composants métier ;
- ajouter tests unitaires et end-to-end ;
- améliorer accessibilité clavier et mobile ;
- ajouter annulation et progression des analyses longues.

---

## 29. Checklist de recette

### 29.1 Technique

- [ ] `/api/health` retourne `ok: true`.
- [ ] `/api/gee/status` retourne `enabled: true` pour une recette réelle.
- [ ] les 59 tests backend passent.
- [ ] le contrôle i18n passe.
- [ ] le build frontend client et SSR réussit.
- [ ] `git diff --check` ne signale pas d’erreur.

### 29.2 Workflow raster

- [ ] dessiner et masquer/réafficher l’AOI ;
- [ ] rechercher une mosaïque Sentinel-2 ;
- [ ] lancer NDVI et vérifier carte, classes et statistiques ;
- [ ] lancer NDBI et vérifier Built-up detection ;
- [ ] lancer une détection de changement et tester ses trois couches ;
- [ ] restaurer le résultat depuis History ;
- [ ] forcer la régénération des tuiles.

### 29.3 Classifications

- [ ] créer au moins deux classes supervisées ;
- [ ] dessiner les échantillons dans l’AOI ;
- [ ] vérifier les seuils pixels training/validation ;
- [ ] contrôler la matrice de confusion et l’accuracy ;
- [ ] exécuter une classification non supervisée ;
- [ ] renommer et recolorer un cluster ;
- [ ] vérifier la persistance dans History.

### 29.4 Exports

- [ ] CSV anglais et arabe ;
- [ ] GeoTIFF ouvrable dans un SIG ;
- [ ] PNG cohérent avec la couche active ;
- [ ] PDF avec image source, résultat, légende et statistiques ;
- [ ] PDF de changement avec période 1, période 2 et delta.

---

## 30. Références internes

Le présent document est le référentiel global daté de la version du 4 août 2026. Les documents spécialisés restent utiles pour les détails historiques ou techniques :

- [Index documentaire](00_INDEX_DOCUMENTATION.md)
- [Architecture technique](02_ARCHITECTURE_TECHNIQUE.md)
- [Installation et configuration](04_INSTALLATION_CONFIGURATION.md)
- [Frontend](05_FRONTEND.md)
- [API backend](06_BACKEND_API.md)
- [Google Earth Engine](07_GOOGLE_EARTH_ENGINE.md)
- [Analyses géospatiales](08_ANALYSES_GEOSPATIALES.md)
- [Détection de changement](09_CHANGE_DETECTION.md)
- [Projections](10_PROJECTIONS_CARTOGRAPHIQUES.md)
- [Exports](13_EXPORTS_GEOSPATIAUX.md)
- [Rapports PDF](14_RAPPORTS_PDF.md)
- [Tests](17_TESTS_ET_VALIDATION.md)
- [Problèmes connus](20_PROBLEMES_CONNUS.md)
- [Améliorations des 27 et 28 juillet](22_AMELIORATIONS_27_28_JUILLET_2026.md)

En cas de contradiction entre un ancien document et cette version, le code du commit `5d7ef608467003f6535c9323c2cf9df14d6466bf`, ses tests et le présent document daté prévalent.

---

**Fin de la documentation globale — GeoRasterPortal — 4 août 2026**
