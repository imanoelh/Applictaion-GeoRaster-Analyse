# GeoRaster Analytics

Plateforme WebGIS d’analyse raster fondée sur React, FastAPI, Leaflet et Google Earth Engine.

## Documentation de référence

- [Documentation finale](DOCUMENTATION_VERSION_FINALE.md)
- [Index documentaire](docs/00_INDEX_DOCUMENTATION.md)
- [Installation et configuration](docs/04_INSTALLATION_CONFIGURATION.md)
- [Contrat de l’API](docs/06_BACKEND_API.md)
- [Analyses géospatiales](docs/08_ANALYSES_GEOSPATIALES.md)
- [Problèmes connus](docs/20_PROBLEMES_CONNUS.md)

Les anciens guides sont conservés pour traçabilité. Leur statut est détaillé dans la
[cartographie documentaire](docs/CARTOGRAPHIE_DOCUMENTATION_EXISTANTE.md).

## Capacités principales

La plateforme expose treize traitements : cinq indices spectraux, cinq détections de
changement, la détection OSI SAR, la classification supervisée et la classification
non supervisée.

## Démarrage local

Backend :

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload --port 8010
```

Frontend, dans un second terminal :

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5183
```

Les prérequis, variables d’environnement et procédures de validation sont décrits
dans le [guide d’installation](docs/04_INSTALLATION_CONFIGURATION.md).
