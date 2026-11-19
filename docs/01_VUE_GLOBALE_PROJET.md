# Vue globale du projet

## Finalité

GeoRasterPortal transforme une AOI et une période en résultats raster visualisables et exportables. Il vise la télédétection appliquée à la végétation, l’eau, le bâti, les sols nus, le changement temporel, l’occupation du sol et les anomalies maritimes SAR.

## Utilisateurs visés

- analystes SIG/télédétection ;
- équipes environnement, agriculture, urbanisme et surveillance maritime ;
- démonstrations et prototypes décisionnels.

## Parcours principal

```text
AOI → période/capteur → recherche d’images → analyse → cache/GEE
→ statistiques/classes → couches Leaflet → historique → exports
```

## Écrans

| Route UI | Rôle | Source |
| --- | --- | --- |
| `/` | Dashboard, KPI, portefeuille d’analyses | `frontend/src/routes/index.tsx` |
| `/map` | Workflow complet carte/analyse/export | `frontend/src/routes/map.tsx` |
| `/catalog` | Catalogue mock filtrable | `frontend/src/routes/catalog.tsx` |
| `/history` | Runs, restauration, export, suppression | `frontend/src/routes/history.tsx` |
| `/settings` | Branding, fonds, export, CRS, option 3D | `frontend/src/routes/settings.tsx` |

## Niveau de maturité

| Bloc | État vérifié |
| --- | --- |
| Indices et changement | Implémentés, contrats unitaires couverts |
| Classifications | Implémentées ; validation GEE réelle dépend des données |
| OSI‑SAR | Implémenté ; détecteur de suspects, jamais preuve de pollution |
| Carte/couches | Implémentée, y compris sous-couches et recoloration locale |
| Cache/History | Implémenté et testé en mode mock |
| Exports | Implémentés ; validation réseau GEE non exécutée ici |
| Projections KSA | Implémentées et partiellement testées |
| Simulation 3D | Configuration seulement |
| Authentification | Absente |
| Production multi-utilisateur | Non prête |

## Sources de vérité

- analyses : `backend/app/gee_client.py::INDEX_CONFIG`, `CHANGE_DETECTION_CONFIG` ;
- catalogue fonctionnel : `backend/app/catalog.py::INDICES` ;
- contrat : `backend/app/models.py`, `request_contracts.py` et `frontend/src/lib/georaster-contract.ts` ;
- routes : décorateurs FastAPI de `backend/app/main.py` ;
- interface : `frontend/src/routes/map.tsx` et `frontend/src/data/mock.ts`.
