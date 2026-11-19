# Installation et configuration

## Prérequis

- Python 3.11+ ;
- Node.js/npm ;
- accès et authentification Google Earth Engine pour les données réelles ;
- Windows PowerShell pour les commandes ci-dessous.

## Backend

Depuis la racine :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Authentifier GEE avec l’exécutable fourni par le paquet Earth Engine, puis définir :

```powershell
$env:GEE_PROJECT_ID="<projet-google-cloud-autorise>"
$env:GEE_ACCOUNT_EMAIL="<compte-informatif>"
```

`GOOGLE_CLOUD_PROJECT` peut remplacer `GEE_PROJECT_ID`. Ne pas inscrire d’identifiant personnel ou de credential dans Git.

Lancement :

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Vérification :

```powershell
Invoke-WebRequest http://127.0.0.1:8010/api/health
Invoke-WebRequest http://127.0.0.1:8010/api/gee/status
```

## Frontend

```powershell
Set-Location frontend
npm.cmd install
$env:VITE_API_BASE_URL="http://127.0.0.1:8010"
npm.cmd run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

`VITE_API_BASE_URL` est optionnel : la valeur par défaut est `http://127.0.0.1:8010`.

## Variables d’environnement vérifiées

| Variable | Consommateur | Obligatoire | Rôle |
| --- | --- | --- | --- |
| `GEE_PROJECT_ID` | `gee_client.py` | pour GEE réel | projet Earth Engine |
| `GOOGLE_CLOUD_PROJECT` | `gee_client.py` | alternative | projet GCP |
| `GEE_ACCOUNT_EMAIL` | statut GEE | non | information affichée |
| `VITE_API_BASE_URL` | client frontend | non | base de l’API |
| `PORT`, `HOST` | `serve-built.mjs` | non | serveur du build |
| `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE` | `main.py` | non | correction des chemins CA invalides |

`MAPTILER_KEY` n’est référencée par aucun fichier source. L’avertissement de build provient de la couche de configuration Lovable/Vite, pas de GeoRasterPortal.

## Configuration persistée

`backend/data/platform_settings.json` est généré localement et ignoré par Git. Clés :

- identité, profil, fond, format d’export et unité ;
- connexion backend déclarative ;
- `projection_mode`, `manual_crs` ;
- activation et CRS de référence 3D.

La clé `backend_connection.api_key` n’est pas utilisée pour authentifier les appels.

## CORS et réseau

`main.py` autorise actuellement `http://localhost:5183` et `http://127.0.0.1:5183`. Adapter explicitement cette liste pour un déploiement distant.
