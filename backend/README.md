# GeoRaster Backend (MVP V1)

Backend FastAPI pour le prototype **GeoRaster** selon le CPS V1:
Sentinel-2 Surface Reflectance, NDVI, NDWI, classification par seuils,
statistiques zonales, histogramme, exports et historique.

## Lancer En Local

```powershell
cd "C:\Users\hp\Desktop\TASKS\Protoype WebGIS Raster Analyse\GeoRasterPortal-19-07\GeoRasterPortal-dev_v1\backend"
C:\Users\hp\anaconda3\python.exe -m pip install -r requirements.txt
C:\Users\hp\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

API health:

- `GET http://127.0.0.1:8010/api/health`

Documentation interactive:

- `http://127.0.0.1:8010/docs`

Contrat API MVP:

- [API_CONTRACT.md](./API_CONTRACT.md)

## Activer Google Earth Engine

Le backend fonctionne en mode mock si Earth Engine n'est pas encore authentifie.
Pour charger des images Sentinel-2 reelles et obtenir des tuiles RGB/NDVI/NDWI:

```powershell
cd "C:\Users\hp\Desktop\TASKS\Protoype WebGIS Raster Analyse\GeoRasterPortal-19-07\GeoRasterPortal-dev_v1\backend"
C:\Users\hp\anaconda3\python.exe -m pip install -r requirements.txt
C:\Users\hp\anaconda3\Scripts\earthengine.exe authenticate --force
```

Connectez-vous avec le compte Earth Engine:

```text
imane19elhamri@gmail.com
```

Puis relancez le backend avec le project id GEE:

```powershell
$env:GEE_PROJECT_ID="gee-satellite-project-123456"
$env:GEE_ACCOUNT_EMAIL="imane19elhamri@gmail.com"
C:\Users\hp\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Verification:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/gee/status
```

## Notes

- Stockage MVP: SQLite (`./data/georaster.db`).
- Le moteur d'analyse utilise GEE si l'authentification est active, sinon il conserve un fallback mock.
- `app/gee_client.py` gere la recherche Sentinel-2, les tuiles RGB, NDVI/NDWI, les statistiques, histogrammes et surfaces par classe.
