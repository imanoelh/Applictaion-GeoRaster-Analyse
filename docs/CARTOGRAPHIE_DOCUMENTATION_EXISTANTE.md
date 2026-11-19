# Cartographie de la documentation existante

Audit effectué le 27 juillet 2026 contre le code du worktree courant. Les dates sont celles des fichiers ou du titre, pas une garantie de validité.

| Document actuel | Emplacement | Sujet | Statut | Problèmes détectés | Action recommandée |
| --- | --- | --- | --- | --- | --- |
| `README.md` | racine | vue et lancement | valide et mis à jour | point d’entrée concis vers le corpus officiel | conserver comme page d’accueil |
| `Readme01.md` | racine | dépannage de ports | obsolète | PID, chemins et processus historiques, encodage | archiver |
| `backend/README.md` | backend | backend/GEE | partiellement valide | chemin historique, périmètre limité, compte personnel | remplacer par lien officiel + commandes génériques |
| `backend/API_CONTRACT.md` | backend | contrat MVP | partiellement valide | exports PNG/GeoTIFF dits placeholders, routes récentes absentes | conserver comme historique, utiliser `06_BACKEND_API.md` |
| `docs/README.md` | docs | index précédent | partiellement valide | pointe uniquement vers l’ancien corpus | remplacer par portail officiel |
| `ARCHITECTURE.md` | docs | architecture courte | partiellement valide | simplifie les projections, API et exports | archiver après redirection |
| `ANALYSES_INDICES.md` | docs | indices | partiellement valide | seuils/options incomplets, NDBI ancien | archiver après redirection |
| `FONCTIONNALITES.md` | docs | écrans | partiellement valide | niveau Settings/export trop général | archiver |
| `WORKFLOWS.md` | docs | flux | partiellement valide | catalogue/cache/CRS/export incomplets | archiver |
| `HISTORY_CACHE_EXPORTS.md` | docs | cache/export | partiellement valide | mesures de performance non reproductibles, détails GeoTIFF absents | archiver |
| `TESTS_VALIDATION.md` | docs | validation | obsolète | commandes/résultats antérieurs (moins de tests) | archiver |
| `VERSION_VALIDEE_2026-07-09.md` | docs | snapshot daté | à archiver | commits et affirmations « validé » antérieurs au code courant | conserver comme historique de version |
| `DOCUMENTATION_GLOBALE_VERSION_ACTUELLE_2026-07-16.md` | docs | snapshot global | contradictoire | route `/api/gee/search` absente, commit ancien, comptes personnels | archiver |
| `SYNTHESE_DERNIERES_MODIFICATIONS_2026-07-24.md` | docs | snapshot de changements | partiellement valide | HEAD et worktree ont évolué, résultat 20 tests périmé | conserver comme changelog historique |
| `DOCUMENTATION_CONTRAT_CANONIQUE.md` | docs | payload | valide | manque les options/nuances de résolution et CRS | garder comme résumé, référence officielle `05/06` |
| `DOCUMENTATION_VERSION_COURANTE.md` | docs | documentation globale | partiellement valide | routes/export/sécurité simplifiés, prétend être courante | archiver |
| `DOCUMENTATION_AMELIORATIONS_GEORASTER.md` | docs | audit + architecture cible | contradictoire | mélange actuel et cible PostgreSQL/PostGIS/endpoints inexistants | conserver uniquement comme proposition/roadmap historique |
| `COMMANDES_EXECUTION_GEORASTER.md` | docs | installation | obsolète | noms de dépôts/chemins multiples, `.venv` erronée, comptes personnels | archiver |
| `GeoRasterPortal_Raster_Analysis_Guide_EN.docx` | docs | guide fonctionnel anglais | partiellement valide, dupliqué | métadonnées Word 2013 artificielles, seuils/options non exhaustifs | garder comme support non normatif |
| `GUIDE_ANALYSES_TELEDETECTION_GEORASTERPORTAL.docx` | docs | guide fonctionnel français | dupliqué | double du guide anglais, détails techniques incomplets | garder comme support non normatif |
| `nOTE EXPLICATIVES des indices.docx` | docs | notes UI/analyses | incomplet | bruit de conversation, claims UI historiques, formulations non normatives | à archiver |

## Informations encore valides

- séparation frontend/backend ;
- stack principale ;
- liste générale des analyses ;
- principes des formules ;
- cache/History ;
- interface bilingue ;
- dépendance GEE et repli mock.

## Contradictions principales

- 7 analyses dans le README contre 13 dans le code ;
- `/api/gee/search` documentée mais absente ;
- GeoTIFF « placeholder » dans l’ancien contrat alors qu’une URL GEE est produite ;
- « simulation 3D » parfois présentée comme fonction, alors qu’elle est seulement configurée ;
- PostgreSQL/PostGIS et nombreuses routes de classification présentés dans une cible, mais absents ;
- résultats de tests 20/24/35 selon la date ;
- chemins de projets `dph-flow-buddy-main`, `GeoRasterPortal-dev_v1`, `GeoRaster` et utilisateurs différents ;
- paramètres de résolution et exports décrits plus fortement que ce que le code garantit.

## Politique d’archivage

Ne pas supprimer automatiquement ces documents. Ils servent à l’historique. Pour une future opération d’archivage :

1. déplacer les snapshots et anciens guides vers `docs/archive/` ;
2. conserver un bandeau « historique, non normatif » ;
3. ne laisser à la racine de `docs/` que la structure officielle ;
4. vérifier les liens avant le déplacement.
