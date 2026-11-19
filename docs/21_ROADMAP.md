# Roadmap

Cette feuille de route distingue volontairement l’implémenté du futur.

## Priorité 0 — fiabilisation

- définir le contrat GeoTIFF (dtype, NoData, bandes, compression, CRS, grille) ;
- appliquer ou clarifier la résolution choisie ;
- tester les 13 analyses avec GEE réel ;
- ajouter des tests e2e History → Map → Export ;
- rendre explicites tous les modes mock/fallback.

## Priorité 1 — architecture et sécurité

- extraire routeurs/services par domaine ;
- découper `map.tsx` ;
- ajouter authentification et RBAC ;
- remplacer le header admin et la clé déclarative ;
- uniformiser erreurs/logs ;
- migrer FastAPI startup vers lifespan.

## Priorité 2 — exploitation

- queue persistante pour catalogue et runs ;
- base partagée avec migrations ;
- stockage objet des exports ;
- régénération/archivage des résultats GEE ;
- monitoring, quotas, retry et annulation.

## Priorité 3 — science et données

- calibration/validation des seuils ;
- provenance complète des images ;
- tests de cohérence surfaces/raster ;
- séries temporelles et statistiques zonales dédiées si demandées ;
- workflow de validation OSI‑SAR ;
- versionnement des jeux d’échantillons.

## Priorité 4 — classification professionnelle

- CRUD complet classes/échantillons ;
- import GeoJSON ;
- datasets train/validation versionnés ;
- catalogue de modèles ;
- audit des métriques ;
- comparaison et sélection de modèles ;
- PostGIS uniquement si l’usage multi-projet le justifie.

## Priorité 5 — 3D

Ne commencer qu’après définition du besoin :

- modèle d’altitude et référence verticale ;
- moteur 3D ;
- transformations géodésiques ;
- API et formats ;
- tests de précision.

## Hors périmètre actuel

PostgreSQL/PostGIS, endpoints avancés de classification, séries temporelles, Excel et simulation 3D sont des pistes, pas des fonctionnalités actuelles.
