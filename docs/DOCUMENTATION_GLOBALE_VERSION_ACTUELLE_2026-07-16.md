# Documentation globale - GeoRasterPortal dev_v1

Date de mise a jour : 2026-07-16  
Branche projet : `dev_v1`  
Depot GitHub : `https://github.com/gissolutionsib/RaterPortal.git`  
Dernier commit pousse valide : `146e91a Improve bilingual frontend translations`

## 1. Objectif du projet

GeoRasterPortal est une plateforme WebGIS d'analyse raster multispectrale. Elle permet de rechercher des images satellite, de dessiner une zone d'interet, de lancer des analyses geospatiales via Google Earth Engine, d'afficher les resultats sous forme de couches cartographiques, puis d'exporter les resultats.

La version actuelle vise un MVP fonctionnel autour de Sentinel-2, Google Earth Engine, des indices spectraux classiques et des workflows de detection de changement.

## 2. Etat global de la version actuelle

La version `dev_v1` est fonctionnelle avec :

- Backend FastAPI actif sur `http://127.0.0.1:8010`.
- Frontend Vite/TanStack actif sur `http://127.0.0.1:5183`.
- Connexion Google Earth Engine operationnelle quand l'authentification locale est effectuee.
- Recherche d'images Sentinel-2 via GEE.
- Affichage des mosaiques et couches d'analyse sur la carte.
- Calcul des indices : `NDVI`, `NDWI`, `NDBI`, `BSI`, `SAVI`, `OSI-SAR`.
- Detection de changement : `CHANGE_NDVI`, `CHANGE_NDWI`, `CHANGE_NDBI`, `CHANGE_BSI`, `CHANGE_SAVI`.
- Classification supervisee et non supervisee.
- Exports : `GeoTIFF`, `PNG`, `Map PDF`, `CSV stats`.
- Interface bilingue anglais/arabe amelioree sur les menus principaux.

## 3. Architecture generale

### Backend

Chemin principal : `backend/`

Technologies :

- Python.
- FastAPI.
- Uvicorn.
- Google Earth Engine API.
- Pillow pour certains exports/cartographies.
- Stockage local SQLite et fichiers d'exports.

Roles principaux :

- Exposer les endpoints API.
- Authentifier et verifier Google Earth Engine.
- Rechercher les images Sentinel-2.
- Construire les mosaiques GEE.
- Calculer les indices spectraux.
- Calculer les detections de changement.
- Gerer le cache de resultats.
- Gerer les exports et rapports.

Endpoints importants :

- `GET /api/health`
- `GET /api/gee/status`
- `POST /api/gee/search`
- `POST /api/analyses`
- `POST /api/analyses/{analysis_id}/run`
- `GET /api/runs/{run_id}/result`
- `GET /api/runs/{run_id}/tiles`
- `POST /api/runs/{run_id}/export`
- `POST /api/export/map-layout-png`
- `POST /api/export/map-pdf`

### Frontend

Chemin principal : `frontend/`

Technologies :

- Vite.
- React.
- TanStack Router.
- Leaflet pour la cartographie.
- i18n local `en.json` et `ar.json`.

Routes principales :

- `/` : Dashboard.
- `/map` : Map & Analysis.
- `/catalog` : Image Catalog.
- `/history` : History.
- `/settings` : Settings.

## 4. Travaux realises dans cette version

### 4.1 Detection de changement NDVI

Le workflow `NDVI Change Detection` a ete stabilise et enrichi.

Ameliorations :

- Affichage du resultat final `NDVI Change Detection`.
- Ajout des sous-couches de comparaison :
  - `NDVI - Period 1`
  - `NDVI - Period 2`
  - `NDVI Change - Period 2 minus Period 1`
- Une seule sous-couche active a la fois pour eviter la confusion visuelle.
- Statistiques, histogramme, classes et legende synchronises avec la sous-couche selectionnee.
- Conservation du processus de calcul GEE : delta = periode 2 - periode 1.

Validation fonctionnelle :

- Les couches periode 1, periode 2 et delta s'affichent correctement.
- Les classes de vegetation loss/stable/gain restent coherentes.
- Les resultats sont proches de la realite observable selon les tests visuels effectues.

### 4.2 Detection de changement NDWI

Le meme principe que `CHANGE_NDVI` a ete applique a `CHANGE_NDWI`.

Ameliorations :

- Ajout des couches :
  - `NDWI - Period 1`
  - `NDWI - Period 2`
  - `NDWI Change - Period 2 minus Period 1`
- Palette et classes adaptees a l'eau et l'humidite.
- Legende professionnelle :
  - disparition eau/humidite,
  - diminution humidite,
  - zone stable,
  - augmentation humidite,
  - apparition probable d'eau.

Validation fonctionnelle :

- Les resultats changent correctement selon la periode selectionnee.
- Le rendu respecte la logique hydrique de NDWI.
- Le calcul GEE et l'API backend ne sont pas modifies de maniere destructive.

### 4.3 Detection de changement NDBI

Le workflow `CHANGE_NDBI` a ete corrige et aligne avec les autres detections.

Probleme detecte :

- Une erreur GEE indiquait que le backend cherchait des bandes `B11` alors que l'image calculee disponible contenait deja une bande `NDBI`.
- Message observe : `Band pattern 'B11' did not match any bands. Available bands: [NDBI]`.

Correction :

- Le processus a ete ajuste pour ne pas recalculer NDBI depuis des bandes brutes lorsque l'image d'indice `NDBI` est deja produite.
- Les couches de comparaison ont ete ajoutees :
  - `NDBI - Period 1`
  - `NDBI - Period 2`
  - `NDBI Change - Period 2 minus Period 1`

Validation fonctionnelle :

- Le resultat final affiche les zones stables, les diminutions de reponse built-up et les nouvelles artificialisations.
- Les statistiques et classes sont coherentes.
- Le resultat teste montre une zone majoritairement stable, ce qui est plausible pour une zone peu changeante.

### 4.4 Detection de changement BSI

Le workflow `CHANGE_BSI` a ete applique avec le meme concept.

Ameliorations :

- Couches :
  - `BSI - Period 1`
  - `BSI - Period 2`
  - `BSI Change - Period 2 minus Period 1`
- Rendu adapte a l'exposition de sol nu.
- Classes :
  - forte diminution de sol nu,
  - diminution moderee,
  - zone stable,
  - augmentation moderee,
  - forte augmentation de sol expose.

Validation fonctionnelle :

- Les couches periode 1 et periode 2 sont disponibles.
- Le delta est calcule selon la logique periode 2 - periode 1.
- Les resultats visuels sont coherents avec les zones arides et semi-arides testees.

### 4.5 Detection de changement SAVI

Le workflow `CHANGE_SAVI` a ete finalise.

Ameliorations :

- Couches :
  - `SAVI - Period 1`
  - `SAVI - Period 2`
  - `SAVI Change - Period 2 minus Period 1`
- Conservation de la logique SAVI pour les zones semi-arides avec reduction de l'effet du sol.
- Classes adaptees au changement de couverture vegetale en contexte semi-aride.

Validation fonctionnelle :

- Les resultats sont affichables depuis le cache ou apres recalcul.
- Les statistiques, classes et legendes suivent la sous-couche active.
- Le rendu visuel est coherent pour les zones de vegetation faible ou clairsemee.

## 5. Ameliorations frontend et UX

### 5.1 Layers de comparaison

Les detections de changement affichent maintenant des sous-couches de comparaison pour les indices concernes.

Principe :

- Une analyse de changement peut afficher :
  - la carte de l'indice a la periode 1,
  - la carte de l'indice a la periode 2,
  - la carte de variation finale.
- Une seule couche est active visuellement a la fois.
- Les statistiques et la legende suivent la couche selectionnee.

Ce principe est applique a :

- `CHANGE_NDVI`
- `CHANGE_NDWI`
- `CHANGE_NDBI`
- `CHANGE_BSI`
- `CHANGE_SAVI`

### 5.2 Bouton de recherche images

Le bouton a ete simplifie :

- Ancien libelle : `Search GEE images`
- Nouveau libelle : `Search images`
- Version arabe : `بحث عن الصور`

Objectif :

- Rendre le bouton plus clair pour l'utilisateur final.
- Garder GEE comme moteur technique interne sans l'imposer dans l'interface.

### 5.3 Suppression du badge History

Le badge superieur `Live backend history` a ete retire de la page History.

Important :

- Aucun endpoint backend n'a ete supprime.
- Le tableau History continue de charger les analyses depuis le backend.
- Les actions voir, exporter, supprimer restent conservees.

## 6. Internationalisation anglais/arabe

Une grande partie de l'interface a ete amelioree en arabe professionnel.

Pages traitees :

- Dashboard.
- Map & Analysis.
- Image Catalog.
- History.
- Settings.

Regles appliquees :

- Les noms techniques des indices restent en anglais : `NDVI`, `NDWI`, `NDBI`, `BSI`, `SAVI`, `OSI-SAR`, `CHANGE_NDVI`, etc.
- Les descriptions, statuts, labels, boutons et messages utilisateur sont traduits.
- Les termes metier sont adaptes au contexte SIG/teledetection.
- Les valeurs techniques comme `Sentinel-2`, `GeoTIFF`, `PNG`, `CSV`, `EPSG`, `OpenStreetMap` restent conservees.

Corrections specifiques :

- Le Dashboard en anglais n'affiche plus les descriptions francaises de `NDVI`, `NDWI`, `NDBI`.
- Les menus Map & Analysis, Catalog, History et Settings sont plus complets en arabe.
- Les options de resolution sont traduites en arabe :
  - `Automatic` -> `تلقائي`
  - `10 m` -> `10 م`
  - `20 m` -> `20 م`
  - `30 m` -> `30 م`
- Les fonds de carte sont traduits en arabe quand l'interface est en arabe.

## 7. Etat Google Earth Engine

La connexion GEE fonctionne si :

- Le compte Google est authentifie localement.
- Le fichier de credentials existe.
- Le projet GEE est defini.
- Le backend est relance apres la configuration des variables d'environnement.

Variables utilisees :

```powershell
$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"
```

Endpoint de verification :

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/gee/status
```

Resultat attendu :

```json
{
  "item": {
    "enabled": true,
    "project": "gee-satellite-project-123456",
    "account": "imane19elhamri@gmail.com",
    "collection": "COPERNICUS/S2_SR_HARMONIZED",
    "error": null
  }
}
```

Point important :

- Si le port `8010` est deja utilise, il faut fermer l'ancien backend ou tuer le processus avant de relancer.
- Si `enabled:false`, verifier l'authentification Earth Engine, le projet GEE et la connexion internet.

## 8. Commandes de lancement sur une nouvelle machine

### 8.1 Cloner la branche

```powershell
cd "C:\Users\%USERNAME%\Desktop"
git clone -b dev_v1 https://github.com/gissolutionsib/RaterPortal.git
cd "C:\Users\%USERNAME%\Desktop\RaterPortal"
```

### 8.2 Installer et lancer le backend sans venv

Avec Python global :

```powershell
cd "C:\Users\%USERNAME%\Desktop\RaterPortal\backend"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

earthengine authenticate --force

$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Avec Anaconda :

```powershell
cd "C:\Users\%USERNAME%\Desktop\RaterPortal\backend"

C:\Users\%USERNAME%\anaconda3\python.exe -m pip install -r requirements.txt

C:\Users\%USERNAME%\anaconda3\Scripts\earthengine.exe authenticate --force

$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"

C:\Users\%USERNAME%\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### 8.3 Installer et lancer le frontend

Dans un deuxieme terminal :

```powershell
cd "C:\Users\%USERNAME%\Desktop\RaterPortal\frontend"

npm install
npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force
```

### 8.4 Ouvrir l'application

```text
http://127.0.0.1:5183
```

## 9. Tests rapides de validation

Dans un troisieme terminal :

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/gee/status
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5183/map
```

Validation attendue :

- `/api/health` retourne `ok:true`.
- `/api/gee/status` retourne `enabled:true`.
- `/map` retourne une page HTML frontend.

Test fonctionnel manuel :

1. Ouvrir `/map`.
2. Dessiner une zone d'interet raisonnable.
3. Lancer `Search images`.
4. Selectionner une image Sentinel-2 ou une mosaique.
5. Lancer `NDVI`.
6. Verifier l'affichage de la couche, de la legende, des statistiques et histogrammes.
7. Lancer une detection de changement, par exemple `CHANGE_NDVI`.
8. Tester les sous-couches periode 1, periode 2 et variation.
9. Tester un export `PNG`, `Map PDF` ou `CSV stats`.

## 10. Precautions importantes

Ne pas committer :

- `backend/.venv/`
- les fichiers generes dans `backend/exports/`
- les rapports PDF temporaires,
- les images PNG de test,
- les credentials GEE,
- les caches locaux.

Ne pas casser :

- la logique de calcul GEE,
- les noms techniques des indices,
- les endpoints backend,
- la structure des resultats `comparison_layers`,
- le cache de traitement,
- les exports.

Avant chaque push :

```powershell
npm.cmd --prefix frontend run build
git diff --check
git status --short
```

## 11. Validation effectuee avant documentation

Derniere validation connue :

- Build frontend execute avec succes.
- Push GitHub effectue sur `dev_v1`.
- Commit pousse : `146e91a Improve bilingual frontend translations`.
- Les changements pousses concernaient uniquement les fichiers frontend valides.
- Les fichiers generes, exports, `.venv` et documents non lies n'ont pas ete inclus dans le commit.

## 12. Resume executif

La version actuelle de GeoRasterPortal `dev_v1` est une version avancee et utilisable du MVP WebGIS raster. Elle integre une connexion GEE, des analyses multispectrales, des detections de changement completes pour les principaux indices, des couches comparatives periode 1/periode 2/delta, des exports, un historique backend et une interface bilingue anglais/arabe plus professionnelle.

Le point le plus important de cette version est la stabilisation des workflows de change detection sans casser la logique existante de calcul GEE ni les exports. L'application peut etre lancee sur une nouvelle machine avec les commandes documentees ci-dessus.
