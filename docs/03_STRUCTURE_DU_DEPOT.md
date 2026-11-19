# Structure du dépôt

```text
.
├─ README.md
├─ Readme01.md                         # note historique de lancement
├─ DOCUMENTATION_VERSION_FINALE.md     # référence centrale
├─ docs/                               # documentation officielle + historique
├─ backend/
│  ├─ app/                             # API et moteur métier
│  ├─ tests/                           # tests backend
│  ├─ data/                            # SQLite/config locale, ignorées par Git
│  ├─ exports/                         # fichiers générés, ignorés par Git
│  ├─ uploads/                         # logo local, ignoré par Git
│  ├─ API_CONTRACT.md                  # contrat MVP historique
│  ├─ README.md
│  └─ requirements.txt
└─ frontend/
   ├─ src/
   │  ├─ routes/                       # pages TanStack
   │  ├─ components/                   # carte, navigation, UI
   │  ├─ lib/                          # API, contrat, i18n, erreurs
   │  ├─ data/                         # catalogue et légendes UI
   │  └─ i18n/                         # anglais/arabe
   ├─ scripts/                         # contrôle des légendes
   ├─ package.json
   ├─ vite.config.ts
   ├─ wrangler.jsonc
   └─ serve-built.mjs
```

## Dossiers générés ou locaux

Ne pas considérer comme source :

- `.venv/`, `node_modules/`, `.pytest_cache/`, `__pycache__/`, `frontend/dist/` ;
- `backend/data/*.db`, `backend/data/*.json` ;
- `backend/exports/`, `backend/uploads/`, fichiers `*.log` ;
- `frontend/.wrangler/`.

Ils sont couverts par `.gitignore`, même si des artefacts locaux existent dans le workspace.

## Fichiers déterminants

| Sujet | Fichiers |
| --- | --- |
| Contrat de requête | `backend/app/models.py`, `request_contracts.py`, `frontend/src/lib/georaster-contract.ts` |
| Routage API | `backend/app/main.py` |
| Analyses scientifiques | `backend/app/gee_client.py` |
| Rendu/couches | `frontend/src/routes/map.tsx`, `components/MapView.tsx` |
| Catalogue/légendes | `backend/app/catalog.py`, `frontend/src/data/mock.ts` |
| Base | `backend/app/db.py` |
| Exports | `main.py`, `gee_client.py::create_index_*_url` |
| Tests | `backend/tests/`, `frontend/scripts/check-result-legend-i18n.mjs` |
