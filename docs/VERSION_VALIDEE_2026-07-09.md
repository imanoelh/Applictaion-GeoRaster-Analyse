# Version validee - 2026-07-09

Ce document resume l'etat final valide de GeoRasterPortal apres les derniers travaux de stabilisation des analyses, palettes, historique, traduction et exports.

Objectif: fournir une reference courte pour expliquer au client ce qui est disponible, ce qui a ete valide et ce qui a ete corrige sans modifier les calculs scientifiques ni les endpoints sensibles.

## Etat global

La version actuelle est validee sur la branche `dev_v1`.

Dernier commit pousse:

```text
b3e9f5f validation tous les analyses et les exports
```

La version inclut aussi le commit precedent:

```text
e6ff05a Correction export PNG cartographique
```

## Fonctionnalites principales validees

- Recherche d'images satellitaires via Google Earth Engine.
- Dessin d'une zone d'interet sur la carte.
- Affichage du raster source multispectral ou SAR.
- Execution des indices de base.
- Execution des Change Detection.
- Detection OSI-SAR oil spill suspects.
- Affichage de la carte classifiee.
- Legende, classes, statistiques et histogramme.
- Historique des analyses executees.
- Restauration rapide d'un run depuis History.
- Exports CSV, GeoTIFF, PNG cartographique et PDF rapport.
- Interface bilingue anglais / arabe avec RTL.

## Analyses de base validees

### NDVI

Objectif: vegetation.

Formule conservee:

```text
NDVI = (NIR - Red) / (NIR + Red)
```

Etat valide:

- calcul GEE conserve;
- palette rouge vers vert;
- classes, legende et statistiques coherentes;
- export PNG/PDF alimente par le resultat classe.

### NDWI

Objectif: eau et humidite.

Formule conservee:

```text
NDWI = (Green - NIR) / (Green + NIR)
```

Etat valide:

- calcul GEE conserve;
- palette adaptee au rendu demande: eau en bleu, humidite/vegetation en verts/cyans, sols secs en tons clairs;
- palette harmonisee entre carte, legende et statistiques.

### NDBI

Objectif: bati et artificialisation.

Formule conservee:

```text
NDBI = (SWIR - NIR) / (SWIR + NIR)
```

Etat valide:

- bandes Sentinel-2 conformes: SWIR `B11`, NIR `B8`;
- classes en anglais professionnel;
- descriptions de classes visibles dans la legende;
- affichage et statistiques coherents.

### BSI

Objectif: sols nus.

Formule conservee:

```text
BSI = ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
```

Etat valide:

- calcul conserve;
- palette de sols nus harmonisee;
- Change Detection BSI corrige pour eviter les classes non pertinentes comme water, vegetation ou built-up.

### SAVI

Objectif: vegetation en zones semi-arides.

Formule conservee:

```text
SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)
```

Facteur:

```text
L = 0.5
```

Etat valide:

- calcul conserve;
- palette de base appliquee;
- Change Detection SAVI harmonise avec la palette SAVI.

### OSI-SAR

Objectif: detection de suspects de deversement d'huile sur eau.

Etat valide:

- Sentinel-1 SAR conserve;
- classes: Normal water, Low oil-spill suspicion, Medium oil-spill suspicion, High oil-spill suspicion;
- statistiques et legende affichees;
- carte classee affichee lorsque les conditions SAR/eau sont disponibles;
- note scientifique conservee: OSI-SAR est un detecteur de suspects et necessite une validation experte.

## Change Detection valide

Principe conserve:

```text
Delta index = index periode 2 - index periode 1
```

Analyses validees:

- `CHANGE_NDVI`;
- `CHANGE_NDWI`;
- `CHANGE_NDBI`;
- `CHANGE_BSI`;
- `CHANGE_SAVI`.

Ameliorations validees:

- resume automatique de changement;
- surfaces de perte, stabilite et gain;
- interpretation automatique;
- avertissement sur les periodes peu comparables;
- palettes harmonisees avec les indices de base lorsque demande;
- classes et statistiques coherentes avec le raster classe.

## History et performance

Le module History est valide pour la consultation rapide des analyses deja executees.

Workflow attendu:

- l'utilisateur ouvre History;
- il clique sur l'icone de visualisation;
- l'application restaure directement le run sur Map & Analysis;
- la carte classee, la legende et les statistiques sont affichees sans relancer GEE;
- le catalogue et le raster source ne sont pas obligatoires pour cette restauration.

Objectif client atteint:

- moins d'attente;
- pas de recalcul inutile;
- consultation directe du resultat stocke.

## Exports valides

### CSV stats

Etat: valide.

Contenu:

- statistiques principales;
- classes;
- surfaces;
- pourcentages.

### GeoTIFF

Etat: valide.

Principe:

- export du raster via URL ou fichier selon la logique backend existante.

### PNG cartographique

Etat: corrige et valide.

Probleme corrige:

- l'ancien PNG pouvait afficher seulement un fond Leaflet ou un rectangle vide;
- le raster classe n'etait pas toujours injecte dans le cadre.

Correction validee:

- le PNG utilise le resultat classe du run;
- le backend reconstruit l'image depuis les tuiles GEE si necessaire;
- le cadre carte est agrandi;
- le PNG affiche uniquement la carte classee de l'analyse, avec titre, legende, echelle et fleche nord;
- les noms de fichiers sont horodates pour eviter le cache navigateur.

### Map PDF report

Etat: corrige et valide.

Probleme corrige:

- les sections `3. Satellite image of reference` et `4. Result of the analysis` pouvaient afficher un fallback mock;
- le PDF ne retrouvait pas toujours le run ou les bounds AOI lorsque `bbox` etait absent.

Correction validee:

- le frontend envoie un identifiant fiable de run/cache;
- le backend retrouve les resultats depuis `runs` ou `processing_cache`;
- si `bbox` est absent, les bounds sont reconstruits depuis le GeoJSON AOI;
- les sections 3 et 4 peuvent afficher les vraies images GEE.

## Traduction anglais / arabe

Etat: valide.

Fonctionnalites:

- switch English / العربية;
- langue par defaut: anglais;
- sauvegarde dans `localStorage`;
- restauration au rechargement;
- support RTL en arabe;
- sidebar placee correctement en mode arabe;
- pages principales testees: Dashboard, Map & Analysis, Catalog, History, Settings.

## Dashboard

Etat: valide.

Ameliorations realisees:

- suppression de `Recent raster analyses` lorsque demande;
- `Processing overview` prend l'espace horizontal;
- suppression de `Raster workflow` et `Quick access` lorsque demande;
- `Analysis portfolio` prend l'espace horizontal;
- pas de modification backend.

## Contraintes respectees

Les corrections recentes n'ont pas modifie:

- les formules des indices;
- les bandes Sentinel-2 ou Sentinel-1;
- la connexion Google Earth Engine;
- les endpoints backend sensibles;
- le workflow principal de calcul;
- les autres analyses non concernees;
- les exports CSV/GeoTIFF lors des corrections PNG/PDF.

## Points d'attention

- Redemarrer le backend apres toute modification backend avant de tester PDF ou PNG.
- Les exports visuels dependent des tuiles et thumbnails GEE; ils peuvent etre plus longs que CSV/JSON.
- OSI-SAR reste une detection de suspects, pas une preuve terrain.
- Les fichiers generes dans `backend/exports/` sont des artefacts locaux et ne doivent pas etre commits sauf besoin explicite.

## Synthese finale

La version actuelle de GeoRasterPortal est stabilisee pour une demonstration client avancee:

- calculs GEE fonctionnels;
- analyses et Change Detection coherents;
- palettes harmonisees;
- historique rapide;
- exports visuels corriges;
- rapport PDF enrichi;
- interface bilingue anglais/arabe;
- documentation projet centralisee dans `docs/`.
