# Gestion des erreurs

## Backend

### Validation

Pydantic contrôle :

- valeurs capteur/index/résolution ;
- nuages 0–100 ;
- présence des dates et de l’AOI après normalisation ;
- formats d’export.

Des validations manuelles ajoutent noms de classes, géométries, périodes, formats de couleur et taille/type du logo.

### Codes

| Code | Cas |
| --- | --- |
| 307 | redirection normale vers URL GEE |
| 400 | corps/logo absent |
| 403 | rôle non admin |
| 404 | analyse, run, job, cache, cluster ou export absent |
| 413 | logo > 2 Mo |
| 422 | paramètre métier, données insuffisantes, export impossible |
| 502 | calcul GEE : quota, timeout ou erreur distante |

### GEE

`run_analysis` reformule :

- quota → réessayer/réduire AOI ;
- timeout → réduire AOI/élargir période ;
- autre → message d’erreur de l’analyse.

Le catalogue asynchrone stocke l’erreur dans le job. L’absence de GEE déclenche le mock lorsque possible.

### Exports

Les exceptions deviennent 422 pour les exports standard. Les routes PDF/PNG dédiées ne normalisent pas toutes les exceptions : une erreur interne peut devenir 500.

## Frontend

`georaster-api.ts::request` lève une erreur incluant statut, chemin et corps. Les pages affichent des toasts.

`map.tsx` valide :

- AOI ;
- ordre des dates ;
- compatibilité capteur/analyse ;
- périodes Change Detection ;
- présence d’un résultat/run avant export.

Les erreurs de tuiles déclenchent une tentative de rafraîchissement. Les captures PNG/PDF ont des fallbacks.

Le shell `__root.tsx` et `server.ts` gèrent les erreurs de rendu/SSR ; `error-capture.ts` et `error-page.ts` fournissent les helpers.

## Observabilité

Il n’existe pas de journalisation structurée, tracing, métriques ou identifiant de corrélation. Plusieurs erreurs sont seulement envoyées à `console.error`. Les nombreux logs locaux sont des artefacts, pas un système d’observabilité.

## Améliorations recommandées

- schéma d’erreur JSON uniforme ;
- handlers FastAPI globaux ;
- timeouts explicites pour les téléchargements de tuiles ;
- logs structurés sans données sensibles ;
- métriques des jobs/runs/exports ;
- distinction claire entre mock, fallback visuel et résultat réel ;
- test de toutes les erreurs 4xx/5xx exposées à l’UI.
