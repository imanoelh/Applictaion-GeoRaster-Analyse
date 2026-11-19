# Règles de modification

## Principes

1. Lire [DOCUMENTATION_VERSION_FINALE.md](../DOCUMENTATION_VERSION_FINALE.md) et les documents du domaine.
2. Inspecter le worktree : ne pas écraser les changements locaux.
3. Vérifier le comportement dans le code et les tests, jamais uniquement dans un ancien document.
4. Limiter la modification au domaine demandé.

## Contrat frontend/backend

- préférer `geometry`, `start_date`, `end_date`, `sensor`, `resolution`, `cloud_max`, `index`, `analysis_type` ;
- conserver la normalisation legacy tant qu’une migration n’est pas planifiée ;
- mettre à jour ensemble modèles Python, type TypeScript, client API et tests ;
- ne pas réutiliser `source` comme vérité métier si `sensor` est présent.

## Analyses

Toute modification de formule, bande, seuil, palette ou classe exige :

- justification scientifique ;
- test de contrat ;
- vérification GEE et mock ;
- synchronisation catalogue backend, catalogue frontend, légendes et traduction ;
- vérification de Change Detection si l’indice est concerné ;
- validation des exports.

## Cache

- incrémenter la version de traitement adaptée dans `main.py` ;
- vérifier que les résultats incompatibles sont purgés ;
- tester cache froid, chaud, `force=true` et History.

## Couches

- garder les clés stables ;
- synchroniser résultat actif, stats, histogramme, classes, palette, tuile et export ;
- tester la régénération d’URL ;
- ne pas confondre palette source et palette utilisateur.

## Projections

- EPSG:4326 pour les géométries d’entrée ;
- EPSG:3857 pour le web ;
- EPSG:9332 ne doit jamais devenir un CRS raster par défaut ;
- documenter les équivalents GEE ;
- tester AOI hors KSA et multi-zone ;
- vérifier surface et grille.

## Exports

Avant de modifier :

- identifier l’image exacte exportée ;
- vérifier AOI, bande, dtype, NoData, échelle, CRS et nom ;
- distinguer fichier local et URL GEE ;
- ouvrir le résultat dans un SIG ;
- préserver la sous-couche active.

## Sécurité et secrets

- ne jamais committer credentials, clés, base, config locale, exports, uploads ou logs ;
- ne pas considérer `X-User-Role` comme authentification ;
- ne pas afficher les erreurs distantes brutes en production.

## Validation obligatoire

```powershell
C:\Users\Imane_C4E\anaconda3\python.exe -m pytest -q backend\tests
npm.cmd --prefix frontend run test:legend-i18n
npm.cmd --prefix frontend run build
git diff --check
```

Ajouter un test ciblé pour toute correction de bug.

## Documentation

- mettre à jour le document détaillé concerné ;
- enregistrer le changement dans `CHANGELOG_DOCUMENTATION.md` ;
- marquer explicitement « feuille de route » toute fonction non implémentée ;
- conserver les chemins et routes vérifiables.
