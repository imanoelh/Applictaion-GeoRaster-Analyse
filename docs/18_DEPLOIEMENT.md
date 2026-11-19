# Déploiement

## État supporté

Le seul scénario clairement opérationnel dans le dépôt est le local :

- FastAPI/Uvicorn sur 127.0.0.1:8010 ;
- Vite/TanStack sur 127.0.0.1:5183.

Le frontend contient `wrangler.jsonc` et une configuration Cloudflare issue de TanStack/Lovable, mais aucun déploiement complet du backend, de SQLite, des exports et des credentials GEE n’est défini.

## Build frontend

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run build
```

Artefacts : `frontend/dist/client` et `frontend/dist/server`.

Le script `serve-built.mjs` peut servir le build localement avec `HOST`/`PORT`.

## Backend

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Pour un environnement réel, prévoir :

- secret manager pour GEE ;
- volume persistant pour SQLite/config/exports/uploads, ou services externalisés ;
- proxy TLS ;
- origine CORS explicite ;
- authentification/autorisation ;
- limites de taille et timeouts ;
- workers et stratégie de jobs partagée.

## Incompatibilités à résoudre

- SQLite et fichiers locaux ne sont pas compatibles avec un runtime serverless éphémère sans adaptation.
- Jobs catalogue et cache de tuiles sont en mémoire.
- Les URL GEE sont temporaires.
- Les endpoints de fichiers statiques supposent un disque local.
- CORS ne connaît que les ports locaux.

## Données à ne pas déployer dans l’image

- credentials GEE ;
- `backend/data/` local ;
- exports et uploads existants ;
- logs ;
- `.venv`, `node_modules`, caches ;
- paramètres utilisateurs de développement.

## Contrôle de mise en production

- environnement reproductible avec lock Python ;
- migration de schéma ;
- stockage objet pour exports ;
- base partagée ;
- gestionnaire de jobs ;
- supervision ;
- tests de sécurité ;
- sauvegarde/restauration ;
- conformité des licences des fonds de carte ;
- politique de conservation des données.
