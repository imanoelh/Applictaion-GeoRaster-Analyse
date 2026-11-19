# Analyses géospatiales

Source principale : `backend/app/gee_client.py`. Catalogue UI : `frontend/src/data/mock.ts`. Route commune : création via `POST /api/analyses`, exécution via `POST /api/analyses/{id}/run`, lecture via `GET /api/runs/{run_id}/result`.

Identifiants canoniques du contrat : `NDVI`, `NDWI`, `NDBI`, `BSI`, `SAVI`,
`OSI_SAR`, `CHANGE_NDVI`, `CHANGE_NDWI`, `CHANGE_NDBI`, `CHANGE_BSI`,
`CHANGE_SAVI`, `SUPERVISED_CLASSIFICATION` et `UNSUPERVISED_CLASSIFICATION`.

## Paramètres communs

- `geometry` : polygone GeoJSON en EPSG:4326 ;
- `start_date`, `end_date` ;
- `sensor` : Sentinel‑2 ou Landsat 8/9 pour les analyses optiques ;
- `resolution` : `auto|10m|20m|30m` ; le moteur utilise toutefois 10 m ou 30 m selon le capteur ;
- `cloud_max` : 0–100 ;
- `index`, `analysis_type`.

Préparation commune : filtre AOI/dates/nuages, masque de nuages, composite médian, découpage AOI, calcul GEE, statistiques, histogramme, classes et tuiles.

## Indices spectraux

### NDVI

- Objectif : couverture et vigueur de la végétation.
- Formule : `(NIR - Red) / (NIR + Red)`.
- Bandes : S2 B8/B4 ; Landsat SR_B5/SR_B4.
- Affichage : image classée.
- Classes :
  - `[-1, 0.2[` aucune ou très faible couverture ;
  - `[0.2, 0.4[` faible ;
  - `[0.4, 0.6[` modérée ;
  - `[0.6, 0.8[` dense ;
  - `[0.8, 1]` très dense.
- Palette : rouge → vert.
- Sorties : min/max/moyenne/écart-type, pixels, surface, histogramme, surfaces/pourcentages par classe, RGB et tuile classée.
- Sources : `INDEX_CONFIG["NDVI"]`, `_compute_index_image`, `compute_sentinel2_index`.

### NDWI

- Objectif : eau de surface et humidité.
- Formule : `(Green - NIR) / (Green + NIR)`.
- Bandes : S2 B3/B8 ; Landsat SR_B3/SR_B5.
- Classes : `[-1,-0.35[`, `[-0.35,-0.15[`, `[-0.15,0.05[`, `[0.05,0.25[`, `[0.25,1]`.
- Sémantique : sec/non-eau, faible humidité/végétation, végétation humide/sol humide, eau peu profonde/mixte, eau libre.
- Particularité : la tuile affichée est l’indice continu avec palette, tandis que les classes alimentent la légende/statistique.

### NDBI

- Objectif : réponse SWIR/NIR associée aux surfaces bâties ou minérales.
- Formule : `(SWIR - NIR) / (SWIR + NIR)`.
- Bandes : S2 B11/B8 ; Landsat SR_B6/SR_B5.
- Classes de l’indice brut :
  - `[-1,0[` réponse négative ;
  - `[0,0.04[` proche de zéro ;
  - `[0.04,0.14[` positive ;
  - `[0.14,1]` fortement positive.
- Important : ces classes ne sont pas à elles seules des classes d’occupation du sol.
- Sous-couches :
  - `ndbi_raw` : NDBI continu ;
  - `ndbi_built_detection` : interprétation multi-observation utilisant aussi NDVI, NDWI, BSI, probabilités temporelles Dynamic World et références WorldCover/GHSL.
- Règle de sûreté `v12` : WorldCover est uniquement une preuve de confirmation. Sa classe bâtie ne peut pas créer une détection à elle seule ; elle doit confirmer une évidence spectrale ou temporelle existante.
- Règle de récupération `v14`, limitée à Sentinel‑2 : GHSL 2018 (`built_surface`) intervient en dernier. Un pixel encore classé « aucune évidence » n’est promu vers « bâti détecté » que si GHSL indique au moins 50 m² bâtis dans la cellule de 100 m² et si NDVI < 0,42 et NDWI < 0,12. GHSL ne peut jamais produire la classe « haute confiance ».
- Limite : GHSL est une référence historique 2018, pas une vérité terrain actuelle. Elle aide à récupérer des toits clairs existants en 2018 mais ne confirme pas les constructions plus récentes.
- Présentation : le backend conserve les deux sous-couches pour le calcul, l’audit et les exports, tandis que l’interface affiche `ndbi_built_detection` comme résultat NDBI utilisateur.
- Classes built detection : aucun indice bâti, imperméable/route potentiel, bâti détecté, bâti haute confiance.
- Sources : `NDBI_BUILT_DETECTION_CONFIG`, `_ndbi_*`, `_analysis_ndbi_built_detection_image`.

### BSI

- Objectif : exposition des sols nus.
- Formule : `((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))`.
- Bandes : S2 B11/B4/B8/B2 ; Landsat SR_B6/SR_B4/SR_B5/SR_B2.
- Classes : très faible `[-1,0[`, faible `[0,0.2[`, modérée `[0.2,0.4[`, forte `[0.4,0.6[`, très forte `[0.6,1]`.
- Palette : beige clair → brun foncé.

### SAVI

- Objectif : végétation avec correction du fond de sol.
- Formule : `((NIR - Red) / (NIR + Red + 0.5)) * 1.5`.
- Bandes : mêmes bandes que NDVI.
- Classes : sol nu/absence `[-1,0[`, très faible `[0,0.15[`, faible semi-aride `[0.15,0.3[`, modérée `[0.3,0.45[`, forte `[0.45,0.65[`, très forte `[0.65,1]`.

## OSI‑SAR

- Objectif : candidats sombres susceptibles de correspondre à une nappe d’hydrocarbure.
- Capteur forcé : Sentinel‑1 GRD IW, VV+VH.
- Processus :
  - médiane des scènes ;
  - filtre médian spatial ;
  - contraste `moyenne locale VV - VV` ;
  - score = test VV sombre + test VH sombre + contraste ;
  - masque eau JRC ;
  - suppression des objets sous la surface minimale ;
  - classes 0–3.
- Valeurs par défaut :
  - VV < −18 dB ; VH < −25 dB ;
  - contraste > 2,5 dB, rayon 500 m ;
  - filtre speckle 30 m ;
  - objet minimal 0,5 ha ;
  - occurrence eau ≥ 50 % ;
  - vent optimal 2–10 m/s ;
  - statistiques 30 m.
- Contexte : ERA5 optionnel par défaut ; vérification optique Sentinel‑2 désactivée par défaut.
- Résultats : surface d’eau, surface suspecte, pourcentage, forte suspicion, moyennes VV/VH/contraste/score/vent, classes, tuiles.
- Limite scientifique : un sombre SAR peut avoir d’autres causes. Une validation experte est obligatoire.

## Classification supervisée

- Entrées : mosaïque optique, six bandes spectrales et NDVI/NDWI/NDBI/BSI/SAVI.
- Algorithmes : Random Forest (défaut), CART, SVM RBF.
- Défauts/limites : 150 arbres, 160 échantillons par classe, split 70/30, seed 37 ; limites backend respectives 50–500, 40–500 et 50–85 %.
- Échantillons :
  - utilise les points/polygones `training_samples` d’un projet s’ils donnent ≥ 40 pixels d’entraînement et ≥ 10 de validation ;
  - sinon repli vers un échantillonnage stratifié ESA WorldCover v200.
- Classes de repli : eau, arbres, cultures/végétation basse, bâti, sol/sable, zone humide, mangrove, neige/glace.
- Post-traitement : `focal_mode` carré rayon 1 pixel.
- Validation : matrice de confusion, overall accuracy, Kappa, producer/user accuracy, erreurs d’omission/commission ; comparaison des trois algorithmes optionnelle.
- Résultats : raster catégoriel, surfaces, histogramme, métriques, interprétation et artefacts SQLite.

## Classification non supervisée

- Entrées : six bandes et cinq indices.
- Méthode : `ee.Clusterer.wekaKMeans`, ordre préservé, seed 91.
- Options :
  - mode simple ou expert ;
  - 2–12 groupes (défaut 6) ;
  - 500–20 000 pixels d’échantillonnage (défaut 5 000) ;
  - sélection de bandes en mode expert, minimum deux.
- Stabilisation : les groupes bruts sont triés selon leur signature spectrale, recodés 1..N puis lissés par `focal_mode`.
- Interprétation : calcul des moyennes NDVI/NDWI/NDBI/BSI/SAVI et attribution d’un nom sémantique probable.
- Personnalisation : le frontend permet de renommer et recolorer sans recalculer l’appartenance des pixels.
- Résultats : surfaces/pourcentages, signatures, groupes, palette et tuiles.

## Analyses absentes

Il n’existe pas de route autonome de statistiques zonales ou de série temporelle. Les statistiques sont zonales sur l’AOI au sein de chaque run ; les seules analyses temporelles sont les cinq détections de changement à deux périodes. Il n’existe pas de projection/visualisation raster 3D.

## Exports

Toutes les analyses GEE peuvent fournir GeoTIFF, PNG GEE et PDF/PNG cartographiques. CSV/JSON utilisent le résultat stocké. Le choix d’une sous-couche est possible pour NDBI et les couches de comparaison via `layer_key`.
