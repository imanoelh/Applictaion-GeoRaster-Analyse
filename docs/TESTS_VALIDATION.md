# Tests, validation et etat qualite

## Tests executes

Commandes validees:

```powershell
backend\.venv\Scripts\python.exe -m unittest backend.tests.test_gee_contract backend.tests.test_backend_flow backend.tests.test_request_contracts
npm.cmd run build
backend\.venv\Scripts\python.exe -m py_compile backend\app\gee_client.py backend\app\main.py backend\app\mock_engine.py
```

Resultats:

- tests backend: OK;
- build frontend: OK;
- compilation Python: OK;
- statut GEE: OK;
- export `stats_csv`: OK;
- restauration History: optimisee.

## Validation par composant

| Composant | Etat | Commentaire |
| --- | --- | --- |
| Backend API | OK | Endpoints critiques fonctionnels |
| GEE auth | OK | Projet et compte detectes |
| Map & Analysis | OK | Affichage carte, resultats et legendes |
| History | OK | Restauration rapide via prechargement |
| Cache | OK | Reutilise les resultats existants |
| Exports CSV | OK | Teste avec succes |
| Exports PDF/PNG | A surveiller | Fonctionnels mais plus lourds |
| NDVI | OK | Formule et classes conformes |
| NDWI | OK | Formule et classes conformes |
| NDBI | OK | Classes anglaises clarifiees |
| BSI | OK | Palette base/change harmonisee |
| SAVI | OK | Formule et Change Detection conformes |
| OSI-SAR | OK | Resultat suspect, validation terrain necessaire |

## Limites connues

- Les resultats scientifiques dependent de la qualite des images, des nuages, de la saison et de l'AOI.
- OSI-SAR ne confirme pas une pollution; il detecte des suspects.
- Les exports lourds peuvent prendre plus de temps.
- Certaines options Settings restent partiellement UI/prototype.

## Recommandations de suite

- Ajouter des tests unitaires supplementaires pour chaque palette et chaque seuil.
- Ajouter un test e2e History -> Map -> Export.
- Documenter explicitement les options Settings non branchees.
- Continuer le decoupage progressif de `backend/app/main.py` par domaines.

