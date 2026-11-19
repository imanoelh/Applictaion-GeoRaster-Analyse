# Étape 9 — Intégration frontend GeoRaster

## Objectif

Exposer le pipeline Building dans le parcours utilisateur réel, depuis le choix de la source jusqu’à l’inspection cartographique des candidats.

## Parcours

```text
GeoRaster
→ Détection d’objets IA
→ Bâtiments
→ Sentinel test ou orthophoto locale
→ paramètres
→ lancement
→ résultats, carte et statistiques
```

Le frontend React/TypeScript s’appuie sur un client API centralisé. Le panneau Building gère les paramètres, le chargement, les erreurs métier, l’état du résultat et la relance. L’import local passe par `LocalRasterSource` et ne contourne pas le backend.

## Affichage cartographique

Une seule couche Leaflet GeoJSON représente les candidats. Elle dispose de styles normal, survolé et sélectionné, d’une légende, d’un popup par objet et d’un zoom limité à des bounds valides. Les statistiques globales proviennent du contrat backend.

La suppression d’un résultat retire ensemble la couche, le popup, la légende, les statistiques et la sélection. Cette centralisation évite les états visuels orphelins.

## Qualité et volume

L’interface affiche explicitement que les résultats sont des **candidats bâtiments générés par IA** et que la précision scientifique n’est pas validée. Pour Sentinel-2, elle rappelle que la résolution de 10 m convient seulement au test d’intégration.

Les tests couvrent notamment 0, 10, 100, 1 000 et 2 500 entités, ainsi que le popup, la visibilité, la suppression et les erreurs. Les builds client et SSR réussissent.

**Statut : validée techniquement et intégrée au frontend.**

