# GeoRaster - execution complete de l'application

Ce projet est maintenant organise en deux dossiers principaux :

```text
dph-flow-buddy-main/
  backend/    API FastAPI, Google Earth Engine, cache, exports
  frontend/   Application React/TanStack/Vite
```

## 1. Prerequis

- Python Anaconda installe
- Node.js et npm installes
- Compte Google Earth Engine authentifie
- Projet Google Cloud / GEE :

```powershell
gee-satellite-project-123456
```

Compte utilise :

```powershell
imane19elhamri@gmail.com
```

## 2. Installation backend

Ouvrir un terminal PowerShell :

```powershell
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\backend"

C:\Users\Imane_C4E\anaconda3\python.exe -m pip install -r requirements.txt
```

## 3. Authentification Google Earth Engine

Toujours dans le dossier `backend` :

```powershell
C:\Users\Imane_C4E\anaconda3\python.exe -m ee authenticate
```

Alternative si la commande precedente ne s'ouvre pas correctement :

```powershell
C:\Users\Imane_C4E\anaconda3\Scripts\earthengine.exe authenticate
```

Puis connecter le projet GEE dans le terminal backend :

```powershell
Set-Item Env:GEE_PROJECT_ID "gee-satellite-project-123456"
Set-Item Env:GEE_ACCOUNT_EMAIL "imane19elhamri@gmail.com"
```

## 4. Lancer le backend

Dans un terminal PowerShell :

```powershell
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\backend"

Set-Item Env:GEE_PROJECT_ID "gee-satellite-project-123456"
Set-Item Env:GEE_ACCOUNT_EMAIL "imane19elhamri@gmail.com"

C:\Users\Imane_C4E\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Backend attendu :

```text
http://127.0.0.1:8010
```

## 5. Verifier backend et GEE

Ouvrir un deuxieme terminal PowerShell :

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/gee/status
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/catalog/indices?enabled_only=true
```

La connexion GEE est correcte si `/api/gee/status` retourne :

```json
{
  "enabled": true,
  "project": "gee-satellite-project-123456",
  "account": "imane19elhamri@gmail.com"
}
```

## 6. Installation frontend

Important : les dependances frontend ne sont pas dans `requirements.txt`.
Elles sont dans `frontend/package.json`.

Ouvrir un nouveau terminal PowerShell :

```powershell
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\frontend"

npm install
```

## 7. Lancer le frontend

Dans le dossier `frontend` :

```powershell
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\frontend"

npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force
```

Frontend attendu :

```text
http://127.0.0.1:5183/map
```

Ouvrir la plateforme :

```powershell
Start-Process http://127.0.0.1:5183/map
```

## 8. Si le frontend Vite refuse de demarrer

Dans ce projet, `vite dev` peut parfois bloquer sur la configuration Lovable/TanStack dans certains environnements Windows. Si cela arrive, utilise le build deja valide et le serveur de secours :

```powershell
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\frontend"

npm run build
C:\Program Files\nodejs\node.exe serve-built.mjs
```

Le frontend sera alors accessible sur :

```text
http://127.0.0.1:5183/map
```

## 9. Verifier frontend

Dans un autre terminal :

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5183/map
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5183/node_modules/.vite/deps/react.js
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5183/@id/virtual:tanstack-start-client-entry
```

Chaque commande doit retourner `StatusCode 200`.

## 9. Workflow utilisateur dans l'application

1. Ouvrir `http://127.0.0.1:5183/map`.
2. Dessiner la zone d'interet sur la carte.
3. Choisir :
   - date debut ;
   - date fin ;
   - capteur ;
   - resolution ;
   - nuages max.
4. Cliquer sur `Search GEE images`.
5. Selectionner une image ou une mosaique.
6. Choisir une analyse :
   - NDVI ;
   - NDWI ;
   - NDBI ;
   - BSI ;
   - SAVI ;
   - Supervised Classification ;
   - Unsupervised Classification.
7. Cliquer sur `Run raster analysis`.
8. Le resultat s'affiche dans le groupe `Analysis result`.
9. Les sous-couches deja calculees peuvent etre rechargees sans recalcul GEE.

## 10. Cache et couches resultats

Le backend evite les recalculs si les parametres sont identiques :

- meme AOI ;
- meme periode ;
- meme capteur ;
- meme resolution ;
- meme seuil nuages ;
- meme analyse.

Les resultats sont disponibles comme sous-couches :

```text
Analysis result
  NDVI classified
  NDWI classified
  NDBI classified
  BSI classified
  SAVI classified
  Supervised Classification
  Unsupervised Classification
```

Boutons disponibles :

- `Recalculate` : force un nouveau calcul GEE.
- `Delete result` : supprime la sous-couche active du cache.

## 11. Exports

Les exports sont disponibles depuis le panneau resultats :

- GeoTIFF ;
- PNG ;
- Map PDF ;
- CSV stats ;
- JSON stats via API.

## 12. Commandes de diagnostic

Verifier les ports :

```powershell
netstat -ano | Select-String ":8010"
netstat -ano | Select-String ":5183"
```

Verifier les processus :

```powershell
Get-Process python -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue
Get-Process npm -ErrorAction SilentlyContinue
```

Verifier la compilation backend :

```powershell
cd "C:\Users\hp\Desktop\TASKS\Protoype WebGIS Raster Analyse\dph-flow-buddy-main_01\dph-flow-buddy-main"
python -m compileall backend\app
```

Verifier le build frontend :

```powershell
cd "C:\Users\hp\Desktop\TASKS\Protoype WebGIS Raster Analyse\dph-flow-buddy-main_01\dph-flow-buddy-main\frontend"
npm run build
```

## 13. Correction erreur Vite 504 Outdated Optimize Dep

Si la console navigateur affiche :

```text
504 Outdated Optimize Dep
Failed to fetch dynamically imported module
```

Arreter le frontend, supprimer le cache Vite, puis relancer :

```powershell
cd "C:\Users\hp\Desktop\TASKS\Protoype WebGIS Raster Analyse\dph-flow-buddy-main_01\dph-flow-buddy-main\frontend"

Remove-Item -LiteralPath ".\node_modules\.vite" -Recurse -Force

npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force
```

## 14. Structure finale attendue

```text
dph-flow-buddy-main/
  backend/
    app/
    data/
    requirements.txt
    API_CONTRACT.md

  frontend/
    src/
    node_modules/
    dist/
    package.json
    package-lock.json
    vite.config.ts
    tsconfig.json
    components.json

  COMMANDES_EXECUTION_GEORASTER.md
  README.md
```






-------------------------------------------
commande avec venv:
Depuis backend, utilisez seulement le .venv du projet.
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\backend"

.\.venv\Scripts\Activate.ps1

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\earthengine.exe authenticate --force

$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload




Ensuite frontend:
cd "C:\Users\Imane_C4E\OneDrive\Desktop\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\GeoRasterPortal-dev_v1\GeoRasterPortal-dev_v1\frontend"

npm install
npm run dev -- --host 127.0.0.1 --port 5183 --strictPort --force
