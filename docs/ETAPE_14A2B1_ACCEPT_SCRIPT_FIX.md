# ÉTAPE 14A.2B1 — ACCEPT SCRIPT FIX

## Cause

L'ancien script créait une nouvelle `QgsApplication`, appelait `initQgis()`, puis `exitQgis()`. Depuis la console Python de QGIS, cet appel arrêtait l'application hôte. Il utilisait aussi `sys.argv` et `SystemExit`, ce qui provoquait l'erreur liée à `__file__` ou interrompait la console.

Le script corrigé expose uniquement `accept_selected_proposal()`. Il utilise `QgsProject.instance()`, les couches déjà chargées, ne lit aucun autre projet et ne contient aucun appel à `QgsApplication`, `exitQgis`, `sys.exit`, `quit`, `clear` ou terminaison de processus.

## Utilisation dans QGIS

```python
from pathlib import Path
exec(Path(r"D:/.../scripts/accept_14A2B1_seed_proposal.py").read_text(encoding="utf-8"))
accept_selected_proposal()
```

Sélectionner exactement une feature dans une couche `ASSISTED_PROPOSALS`. Le script identifie son `patch_id`, trouve la couche `SEED_GROUND_TRUTH` correspondante, copie la géométrie et renseigne `review_status=ACCEPTED` ainsi que la source assistée. En cas de sélection absente, multiple, couche cible absente ou erreur, aucune copie n'est effectuée et QGIS reste ouvert.

## Test dans l'environnement QGIS 3.40.14

Une sélection unique a été copiée dans la couche cible, les attributs ont été renseignés, puis la feature de test a été retirée afin de laisser le seed dataset vide. Résultat : `RESULT=True`, `COUNT_AFTER=1`, `review_status=ACCEPTED`, `COUNT_FINAL=0`, QGIS toujours vivant.

ROOT CAUSE :
Ancien script appelant QgsApplication.initQgis()/exitQgis() et utilisant SystemExit/sys.argv depuis QGIS.

QGIS CLOSE FIXED :
YES

SINGLE SELECT TEST :
PASS

TARGET GT COPY :
PASS

QGIS REMAINS OPEN :
YES

PROJECT SAVE :
PASS

PROJECT REOPEN :
PASS

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

READY_FOR_SAFE_MANUAL_REVIEW :
YES
