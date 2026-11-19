# Fonctionnalites applicatives

## Dashboard

Le Dashboard donne une vision generale de l'application et sert de point d'entree visuel.

Etat: fonctionnel.

## Map & Analysis

La page Map & Analysis permet de:

- dessiner une AOI;
- choisir une periode;
- choisir un capteur;
- rechercher des images GEE;
- afficher le raster source;
- choisir une analyse;
- executer le calcul;
- afficher le resultat classe;
- consulter statistiques, histogrammes et classes;
- exporter les resultats.

Etat: fonctionnel.

## Image Catalog

Le catalogue permet de rechercher et selectionner des images satellitaires disponibles selon la zone, la periode, le capteur et la couverture nuageuse.

Etat: fonctionnel avec GEE; fallback possible si GEE indisponible.

## History

History liste les analyses executees et permet:

- recherche;
- filtre par statut;
- visualisation;
- export;
- suppression.

Amelioration recente: le clic sur l'icone oeil precharge le run et restaure directement la carte classee, l'AOI, la legende et les statistiques sans relancer de calcul ni de catalogue.

Etat: stabilise pour la visualisation rapide.

## Settings

Settings contient des parametres UI et certains elements de branding.

Etat: partiellement branche. Les options non connectees doivent rester considerees comme prototype.

## Exports

Exports supportes selon les cas:

- CSV statistiques;
- JSON statistiques;
- GeoTIFF;
- PNG layout;
- PDF rapport.

Etat: fonctionnel globalement. Les exports lourds PDF/PNG peuvent prendre plus de temps car ils recuperent ou reconstruisent des visuels.

