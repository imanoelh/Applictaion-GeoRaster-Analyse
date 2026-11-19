# Cartographie et etat d'avancement du projet GeoRaster

## 1. Objet du document

Ce document donne une lecture claire du projet GeoRaster a partir du depot actuel.

Il vise a repondre a 4 questions :

- qu'est-ce que fait le projet ;
- comment le code est organise ;
- quelles documentations existent deja ;
- ou en est reellement le projet aujourd'hui.

Le contenu ci-dessous est base sur la structure du depot, les fichiers frontend/backend presents, les routes UI, les endpoints API et les documents deja disponibles dans le repository.

## 2. Synthese rapide

GeoRaster est un prototype WebGIS avance pour l'analyse raster, avec :

- un frontend React/TanStack Start/Vite ;
- un backend FastAPI ;
- une integration Google Earth Engine ;
- un stockage SQLite local ;
- un mode fallback mock pour continuer a demontrer l'application meme si le backend ou GEE n'est pas pleinement disponible.

En l'etat, le projet est deja demonstrable et relativement bien avance sur le plan technique.
En revanche, il n'est pas encore totalement stabilise comme produit final : certaines documentations sont heterogenes, plusieurs chemins anciens sont encore mentionnes, et la robustesse depend encore fortement de l'environnement local et de Google Earth Engine.

## 3. Carte du projet

### 3.1 Vue d'ensemble

```text
GeoRaster/
  backend/
    app/
      main.py
      gee_client.py
      db.py
      catalog.py
      models.py
      mock_engine.py
    requirements.txt
    README.md
    API_CONTRACT.md

  frontend/
    src/
      routes/
        index.tsx
        map.tsx
        catalog.tsx
        history.tsx
        settings.tsx
      components/
      data/
      lib/
    package.json

  README.md
  Readme01.md
  COMMANDES_EXECUTION_GEORASTER.md
  DOCUMENTATION_AMELIORATIONS_GEORASTER.md
```

### 3.2 Role de chaque bloc

`frontend/`

- porte l'interface utilisateur ;
- affiche le dashboard, la carte, le catalogue, l'historique et les parametres ;
- consomme les endpoints du backend via `frontend/src/lib/georaster-api.ts`.

`backend/`

- expose l'API FastAPI ;
- gere les analyses, les executions, les exports, le cache et les parametres ;
- orchestre l'usage de Google Earth Engine ;
- persiste les donnees dans SQLite.

`SQLite`

- stocke les analyses, runs, exports, cache de traitement, classes de couverture du sol, echantillons et resultats lies a la classification.

`Documentation racine`

- contient les guides de lancement, le resume fonctionnel et les notes d'amelioration ;
- merite encore une harmonisation, car certains fichiers parlent d'anciens repertoires ou d'un ancien nom de projet.

## 4. Cartographie fonctionnelle

### 4.1 Frontend present dans le depot

Les routes confirmees dans `frontend/src/routes/` sont :

- `/` : dashboard ;
- `/map` : carte et analyse raster ;
- `/catalog` : catalogue d'images ;
- `/history` : historique des analyses ;
- `/settings` : parametres de plateforme.

Les briques frontend visibles dans le code montrent que l'application couvre deja :

- la recherche d'images ;
- le lancement d'analyses ;
- la consultation des resultats ;
- la gestion du cache ;
- le telechargement d'exports ;
- la personnalisation du logo de plateforme ;
- la gestion des echantillons de classification.

### 4.2 Backend present dans le depot

Les endpoints visibles dans `backend/app/main.py` montrent un backend deja riche, structure autour de plusieurs domaines :

- sante et statut GEE ;
- dashboard ;
- catalogue ;
- jobs GEE asynchrones ;
- analyses et runs ;
- historique ;
- cache de resultats ;
- exports ;
- parametres plateforme ;
- classes et echantillons de classification.

Exemples d'endpoints confirmes :

- `GET /api/health`
- `GET /api/gee/status`
- `GET /api/dashboard`
- `GET /api/catalog/images`
- `POST /api/catalog/images/search`
- `POST /api/gee/jobs/catalog`
- `GET /api/gee/jobs/{job_id}/status`
- `POST /api/analyses`
- `POST /api/analyses/{analysis_id}/run`
- `GET /api/runs/{run_id}/result`
- `POST /api/result-cache/search`
- `POST /api/runs/{run_id}/export`
- `GET /api/history`
- `GET /api/settings/platform`
- `POST /api/settings/logo`
- `GET /api/classification/classes`
- `POST /api/classification/samples`

### 4.3 Base de donnees locale

Le fichier `backend/app/db.py` confirme la presence des tables suivantes :

- `analyses`
- `runs`
- `exports`
- `processing_cache`
- `landcover_classes`
- `training_samples`
- `classification_models`
- `classification_results`
- `validation_metrics`

Cette structure montre que le projet ne se limite plus a une simple demo d'interface. Il y a une vraie base de persistence pour suivre les analyses et preparer des usages plus complets autour de la classification.

## 5. Cartographie de la documentation existante

### 5.1 Documents trouves a la racine

`README.md`

- resume global du projet ;
- utile pour une vue tres rapide ;
- contient encore des chemins et noms anciens a nettoyer.

`COMMANDES_EXECUTION_GEORASTER.md`

- document le lancement, les commandes et les verifications ;
- utile pour remettre l'environnement en route.

`Readme01.md`

- document additionnel present dans le depot ;
- a verifier et fusionner si son contenu recouvre le README principal.

`DOCUMENTATION_AMELIORATIONS_GEORASTER.md`

- document de synthese detaille sur les ameliorations ;
- utile, mais demandait une reformulation plus claire et plus factuelle.

### 5.2 Documentation backend

`backend/README.md`

- explique le backend local, la sante API et l'activation de GEE ;
- mentionne encore des chemins historiques.

`backend/API_CONTRACT.md`

- decrit le flux API principal ;
- utile pour comprendre le workflow minimal ;
- semble un peu plus "MVP" que l'etat reel du code actuel.

### 5.3 Etat de la documentation

La documentation est globalement presente, mais elle est encore partiellement designee pour un prototype en evolution.

Les principaux constats sont :

- la doc existe bien, donc le projet n'est pas "sans documentation" ;
- plusieurs documents ne sont pas encore completement alignes entre eux ;
- certains chemins ou noms de dossier sont herites d'anciennes versions ;
- certains textes sont ecrits en mode "ameliorations realisees", alors qu'une partie devrait plutot distinguer : present dans le code, teste, stabilise, a consolider.

## 6. Etat d'avancement du projet

### 6.1 Lecture executive

Le projet est a un stade intermediaire a avance.

Il est suffisamment avance pour :

- faire une demonstration ;
- montrer un workflow coherent de traitement raster ;
- illustrer une integration frontend/backend ;
- exposer des bases serieuses pour GEE, le cache, l'historique et l'export.

Il n'est pas encore totalement mature pour :

- une mise en production directe ;
- un usage multi-utilisateur durci ;
- une exploitation totalement independante de l'environnement local ;
- une validation metier robuste des classifications.

### 6.2 Niveau par bloc

| Bloc | Niveau estime | Commentaire |
| --- | --- | --- |
| Architecture generale | Avance | Separation frontend/backend claire et lisible |
| Interface utilisateur | Avance | Routes principales presentes, experience deja riche |
| Dashboard | Avance | Existe et consomme le backend |
| Carte et analyse raster | Avance | Coeur du produit, deja structure autour d'un vrai workflow |
| Catalogue d'images | Avance | Recherche et consultation presentes |
| Historique | Avance | Consultation et suppression presentes |
| Exports | Avance | Flux backend present, formats prevus |
| Cache de resultats | Avance | Table, recherche et suppression confirmees |
| Parametres / branding | Avance | Gestion du logo deja exposee |
| Google Earth Engine | Intermediaire a avance | Bien integre, mais fortement dependant de la configuration locale |
| Classification | Intermediaire | Structures et endpoints presents, maturite fonctionnelle a confirmer |
| Documentation | Intermediaire | Suffisante pour travailler, mais encore incoherente par endroits |
| Preparation production | Intermediaire | Prototype solide, durcissement encore necessaire |

## 7. Ce qui est clairement deja en place

Les elements suivants sont confirmes par le depot actuel :

- architecture `frontend/` et `backend/` bien separee ;
- routes frontend principales deja implementees ;
- client API centralise dans `frontend/src/lib/georaster-api.ts` ;
- backend FastAPI avec endpoints nombreux et coherents ;
- base SQLite initialisee par le code ;
- mode mock prevu quand GEE ou le backend reel ne sont pas disponibles ;
- jobs GEE asynchrones pour la recherche catalogue ;
- gestion des analyses, runs, resultats et exports ;
- cache de traitements ;
- historique des analyses ;
- personnalisation du logo de plateforme ;
- base de travail pour la classification supervisee.

## 8. Ce qui reste fragile ou a consolider

Les principaux points de vigilance sont :

- la documentation n'est pas encore completement harmonisee ;
- plusieurs references a d'anciens chemins ou noms de projet restent visibles ;
- la disponibilite du mode reel depend d'un environnement local correctement configure ;
- GEE reste une dependance externe critique ;
- la classification semble techniquement preparee, mais pas encore completement validee comme bloc metier stable ;
- il faut encore distinguer plus clairement ce qui est "code present", "teste localement", "pret demo", "pret production".

## 9. Dependances critiques pour le mode reel

Pour un fonctionnement reel, il faut au minimum :

- un backend FastAPI lance localement ;
- un frontend Vite lance localement ;
- les dependances Python installees ;
- les dependances Node installees ;
- une authentification Earth Engine valide ;
- les variables d'environnement GEE correctement renseignees.

Sans cela, l'application peut rester partiellement demonstrable grace au fallback mock, mais pas completement operationnelle sur des analyses reelles.

## 10. Diagnostic global du projet

Si l'on doit resumer l'etat du projet de facon simple :

GeoRaster est aujourd'hui un prototype WebGIS avance, coherent et deja bien structure, avec un vrai socle technique pour l'analyse raster, l'integration Google Earth Engine, l'historique, le cache et les exports. Le projet est cependant encore dans une phase de consolidation : la base est solide pour une demonstration et pour poursuivre le developpement, mais la documentation, la validation fonctionnelle bout en bout et le durcissement du mode reel doivent encore etre renforces.

## 11. Priorites recommandees

Les prochaines actions les plus utiles sont :

1. harmoniser tous les documents racine pour supprimer les anciens chemins et anciens noms de projet ;
2. verifier de bout en bout le flux reel `AOI -> recherche image -> analyse -> cache -> export -> historique` ;
3. documenter clairement le niveau de maturite par fonctionnalite ;
4. consolider le bloc classification avec des jeux d'echantillons et des metriques de validation ;
5. preparer une feuille de route simple : prototype, demo stable, pre-production.

## 12. Conclusion

L'etat d'avancement du projet est bon.

Le depot montre un projet deja serieux sur le plan technique, nettement au-dela d'une simple maquette, avec plusieurs fonctionnalites importantes deja implementees. La suite ne consiste pas a "commencer le projet", mais surtout a le clarifier, le stabiliser et mieux aligner la documentation avec le code reel.

## 13. Conception cible du module de classification supervisee

Cette section decrit une architecture cible pour faire evoluer GeoRaster vers un module de classification supervisee de niveau professionnel.

Important :

- le depot actuel montre deja des bases pour la classification ;
- la cible ci-dessous decrit le workflow recommande pour une version plus mature ;
- cette cible est pensee pour React + Leaflet, FastAPI, Google Earth Engine et PostgreSQL/PostGIS.

## 14. Objectif metier

Le module doit permettre de produire une carte d'occupation du sol fiable, reproductible et documentee, a partir d'une zone d'interet, d'une image satellite et d'un jeu d'echantillons qualifie.

Les usages attendus sont :

- cartographie de l'occupation du sol ;
- suivi de l'evolution des classes ;
- aide a la decision territoriale ;
- generation de livrables professionnels auditables.

Les classes de base recommandees sont :

- eau ;
- vegetation ;
- bati ;
- sol nu ;
- agriculture ;
- foret ;
- zones humides ;
- autres classes projet selon le territoire.

## 15. Workflow metier recommande

Le workflow UX simple recommande est :

`AOI -> Image -> Classes -> Echantillons -> Entrainement -> Validation -> Classification -> Statistiques -> Rapport`

### 15.1 Etape 1 - Definition de l'AOI

L'utilisateur :

- dessine ou importe une zone d'interet ;
- choisit la zone d'etude finale ;
- peut enregistrer cette zone pour reutilisation.

Objectif technique :

- convertir l'AOI en geometrie GeoJSON ;
- la stocker en PostGIS ;
- l'utiliser pour filtrer les images et borner les calculs GEE.

### 15.2 Etape 2 - Selection de l'image

L'utilisateur choisit :

- capteur : Sentinel-2 ou Landsat ;
- periode ;
- seuil de nuages ;
- methode de selection : scene unique, mosaïque mediane, least cloudy.

Bonnes pratiques :

- Sentinel-2 pour detail spatial fin ;
- Landsat pour analyses temporelles longues ;
- possibilite de generer une mosaïque nettoyee avant la classification.

### 15.3 Etape 3 - Definition des classes

L'utilisateur cree ou reutilise un schema de classes d'occupation du sol.

Pour chaque classe, il faut definir :

- un code ;
- un nom ;
- une description ;
- une couleur standard ;
- un ordre d'affichage ;
- un statut actif/inactif.

Recommandation :

- gerer des nomenclatures versionnees ;
- permettre des bibliotheques de classes par projet ou territoire.

### 15.4 Etape 4 - Creation des echantillons

L'utilisateur doit pouvoir creer des echantillons de trois manieres :

- points ;
- polygones ;
- import GeoJSON.

Fonctions UX recommandees :

- dessiner directement sur la carte ;
- associer chaque geometrie a une classe ;
- afficher la couleur de la classe pendant la saisie ;
- modifier, supprimer, dupliquer un echantillon ;
- filtrer les echantillons par classe ;
- afficher le nombre d'echantillons par classe ;
- importer un fichier GeoJSON ou un lot de points GPS.

Bonnes pratiques metier :

- exiger une repartition minimale par classe ;
- eviter les echantillons trop proches entre eux ;
- signaler les classes sous-representees ;
- separer echantillons d'entrainement et echantillons de validation.

### 15.5 Etape 5 - Construction des jeux train/validation

Le systeme doit permettre :

- une affectation manuelle `training` ou `validation` ;
- ou une repartition automatique, par exemple 70/30 ou 80/20 ;
- ou une stratification par classe.

Regles conseillees :

- conserver un minimum d'echantillons de validation par classe ;
- interdire l'entrainement si une classe critique n'a pas assez d'exemples ;
- tracer la version du jeu d'echantillons utilise.

### 15.6 Etape 6 - Entrainement des modeles

Algorithmes recommandes :

- `Random Forest` comme algorithme principal ;
- `CART` pour un modele simple et interpretable ;
- `SVM` pour comparaison.

Pourquoi Random Forest en principal :

- robuste au bruit ;
- performant sur donnees multispectrales ;
- stable avec plusieurs bandes et indices ;
- bien adapte a un workflow GEE professionnel.

Parametres utiles a exposer :

- nombre d'arbres ;
- nombre de variables par split ;
- seed aleatoire ;
- profondeur max si necessaire ;
- bandes d'entree ;
- indices ajoutes au modele.

Variables d'entree recommandees :

- bandes spectrales de base ;
- NDVI ;
- NDWI ;
- NDBI ;
- BSI ;
- SAVI ;
- eventuellement texture, pente ou couches auxiliaires si le projet le justifie.

### 15.7 Etape 7 - Validation

Le systeme doit calculer automatiquement :

- matrice de confusion ;
- precision globale ;
- coefficient Kappa ;
- precision utilisateur ;
- precision producteur.

Interpretation attendue :

- precision globale elevee : bon niveau global ;
- precision utilisateur : fiabilite de la classe cartographiee ;
- precision producteur : capacite a retrouver la classe de reference ;
- Kappa : accord global corrige du hasard.

Seuils pratiques a afficher comme aide :

- `> 85 %` : tres bon ;
- `70-85 %` : acceptable selon contexte ;
- `< 70 %` : a ameliorer.

Ces seuils restent indicatifs et doivent etre interpretes selon le territoire, le capteur et la complexite du paysage.

### 15.8 Etape 8 - Classification finale

Une fois le modele valide :

- appliquer le classifieur sur l'image ou la mosaïque dans GEE ;
- produire une couche raster classifiee ;
- generer une palette standard ;
- afficher une legende dynamique dans l'interface ;
- permettre le telechargement ou la visualisation comme couche Leaflet.

### 15.9 Etape 9 - Statistiques finales

Le systeme calcule pour chaque classe :

- surface ;
- pourcentage ;
- nombre de pixels ;
- couleur ;
- libelle ;
- part relative dans l'AOI.

Ces statistiques doivent etre visibles dans :

- la fiche resultat ;
- l'historique ;
- le rapport PDF ;
- les exports CSV/JSON.

### 15.10 Etape 10 - Rapport professionnel

Le rapport PDF doit contenir :

- metadata du projet ;
- AOI ;
- image source ;
- date ;
- capteur ;
- bandes et indices utilises ;
- classes utilisees ;
- nombre d'echantillons par classe ;
- proportion train/validation ;
- algorithme utilise ;
- parametres du modele ;
- matrice de confusion ;
- precision globale ;
- Kappa ;
- precision utilisateur par classe ;
- precision producteur par classe ;
- surfaces et pourcentages par classe ;
- carte finale ;
- interpretation automatique.

Exemple d'interpretation automatique :

- classes bien detectees ;
- classes confondues entre elles ;
- classes sous-echantillonnees ;
- recommandation de reprise d'echantillons si la precision est insuffisante.

## 16. Workflow technique avec Google Earth Engine

### 16.1 Preparation de l'image

Pipeline recommande dans GEE :

1. charger la collection ;
2. filtrer sur l'AOI ;
3. filtrer sur la periode ;
4. filtrer sur les nuages ;
5. appliquer un masque nuages ;
6. construire la mosaïque ou choisir la meilleure scene ;
7. calculer les indices ;
8. composer l'image finale servant a la classification.

### 16.2 Preparation des echantillons

Les echantillons saisis dans React sont envoyes au backend puis convertis en `ee.FeatureCollection`.

Chaque feature doit contenir :

- geometrie ;
- `class_code` ;
- `class_name` ;
- `sample_role` : `training` ou `validation` ;
- `project_id` ;
- `dataset_version`.

### 16.3 Entrainement dans GEE

Schema cible :

1. echantillonner l'image sur les geometries ;
2. construire deux collections : train et validation ;
3. entrainer plusieurs classifieurs ;
4. comparer leurs resultats ;
5. retenir le meilleur modele ou celui choisi par l'utilisateur.

Exemple logique :

- `ee.Classifier.smileRandomForest(...)`
- `ee.Classifier.smileCart()`
- `ee.Classifier.libsvm(...)`

Le backend doit orchestrer ces etapes et stocker :

- les parametres du modele ;
- les bandes utilisees ;
- le hash des echantillons ;
- les metriques ;
- les identifiants GEE ou artefacts resultants.

### 16.4 Validation dans GEE

Apres prediction sur le jeu de validation :

- calcul de la matrice de confusion ;
- derivee des precisions par classe ;
- retour de metriques normalisees au backend.

Le backend peut ensuite :

- sauvegarder les metriques en base ;
- les transformer en JSON lisible ;
- les transmettre au frontend pour les tableaux et graphiques.

### 16.5 Production du raster classe

Une fois le modele retenu :

- classifier l'image cible ;
- calculer les surfaces par classe ;
- generer une couche tuilable ;
- produire une URL de tuiles ou un export GEE.

Sorties recommandees :

- couche tuilable pour la carte ;
- GeoTIFF pour SIG ;
- PNG pour rapport ;
- JSON/CSV pour statistiques.

## 17. Architecture applicative cible

### 17.1 Frontend React + Leaflet

Le frontend doit fournir les modules suivants :

- panneau de definition AOI ;
- panneau de recherche d'image ;
- gestionnaire de classes ;
- editeur d'echantillons ;
- tableau de repartition train/validation ;
- panneau d'entrainement des algorithmes ;
- vue de metriques ;
- vue de resultat classe ;
- export et rapport.

Composants recommandés :

- `ClassificationClassManager`
- `TrainingSampleEditor`
- `SampleImportDialog`
- `ModelTrainingPanel`
- `ValidationMetricsPanel`
- `ClassificationLegend`
- `ClassificationStatsPanel`
- `ClassificationReportPanel`

### 17.2 Backend FastAPI

Le backend doit porter la logique metier et exposer des endpoints pour :

- classes ;
- echantillons ;
- jeux train/validation ;
- entrainement ;
- validation ;
- resultat classe ;
- rapport ;
- cache modele ;
- historique.

Exemples d'endpoints cibles :

- `GET /api/classification/classes`
- `POST /api/classification/classes`
- `PUT /api/classification/classes/{id}`
- `DELETE /api/classification/classes/{id}`
- `GET /api/classification/samples`
- `POST /api/classification/samples`
- `POST /api/classification/samples/import`
- `PUT /api/classification/samples/{id}`
- `DELETE /api/classification/samples/{id}`
- `POST /api/classification/datasets/split`
- `POST /api/classification/train`
- `GET /api/classification/models`
- `GET /api/classification/models/{id}`
- `POST /api/classification/models/{id}/classify`
- `GET /api/classification/results/{id}`
- `GET /api/classification/results/{id}/tiles`
- `GET /api/classification/results/{id}/report`

### 17.3 Google Earth Engine

GEE reste le moteur de calcul pour :

- preparation de l'image ;
- echantillonnage ;
- entrainement ;
- validation ;
- classification raster ;
- statistiques spatiales ;
- export GeoTIFF et images.

### 17.4 PostgreSQL/PostGIS

PostgreSQL/PostGIS devient la couche de persistence principale pour :

- classes ;
- echantillons ;
- jeux de donnees ;
- modeles ;
- resultats ;
- metriques ;
- AOI ;
- historique.

## 18. Structure PostgreSQL/PostGIS recommandee

### 18.1 Table `landcover_classes`

Role :

- stocker les classes d'occupation du sol.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NULL`
- `code INTEGER NOT NULL`
- `name VARCHAR(100) NOT NULL`
- `description TEXT NULL`
- `color VARCHAR(20) NOT NULL`
- `sort_order INTEGER DEFAULT 0`
- `is_active BOOLEAN DEFAULT TRUE`
- `schema_version VARCHAR(50) NOT NULL`
- `created_at TIMESTAMP NOT NULL`
- `updated_at TIMESTAMP NOT NULL`

Contraintes conseillees :

- unicite `(project_id, schema_version, code)`
- unicite `(project_id, schema_version, name)`

### 18.2 Table `training_samples`

Role :

- stocker les echantillons dessines ou importes.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL`
- `class_id UUID NOT NULL`
- `sample_role VARCHAR(20) NOT NULL`
- `sample_source VARCHAR(30) NOT NULL`
- `geometry GEOMETRY(GEOMETRY, 4326) NOT NULL`
- `properties_json JSONB NULL`
- `quality_status VARCHAR(20) DEFAULT 'valid'`
- `annotator_id UUID NULL`
- `dataset_version VARCHAR(50) NOT NULL`
- `created_at TIMESTAMP NOT NULL`
- `updated_at TIMESTAMP NOT NULL`

Valeurs recommandees :

- `sample_role` : `training`, `validation`
- `sample_source` : `draw_point`, `draw_polygon`, `geojson_import`

Index utiles :

- index spatial `GIST(geometry)`
- index sur `(project_id, class_id)`
- index sur `(project_id, sample_role)`

### 18.3 Table `classification_datasets`

Role :

- figer un jeu d'echantillons utilise pour un entrainement.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL`
- `name VARCHAR(150) NOT NULL`
- `schema_version VARCHAR(50) NOT NULL`
- `sampling_strategy VARCHAR(50) NOT NULL`
- `train_ratio NUMERIC(5,2) NOT NULL`
- `validation_ratio NUMERIC(5,2) NOT NULL`
- `samples_hash VARCHAR(128) NOT NULL`
- `filters_json JSONB NULL`
- `created_by UUID NULL`
- `created_at TIMESTAMP NOT NULL`

### 18.4 Table `trained_models`

Role :

- stocker les modeles entraines ou leurs metadonnees.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL`
- `dataset_id UUID NOT NULL`
- `algorithm VARCHAR(30) NOT NULL`
- `model_name VARCHAR(150) NULL`
- `input_bands JSONB NOT NULL`
- `input_indices JSONB NULL`
- `hyperparams_json JSONB NULL`
- `gee_model_asset_id TEXT NULL`
- `samples_hash VARCHAR(128) NOT NULL`
- `aoi_hash VARCHAR(128) NOT NULL`
- `image_fingerprint VARCHAR(128) NOT NULL`
- `status VARCHAR(20) NOT NULL`
- `is_cached BOOLEAN DEFAULT TRUE`
- `created_at TIMESTAMP NOT NULL`
- `updated_at TIMESTAMP NOT NULL`

Index utiles :

- index sur `(project_id, algorithm)`
- index sur `(project_id, samples_hash, aoi_hash, image_fingerprint)`

### 18.5 Table `classification_results`

Role :

- stocker les sorties de classification.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL`
- `model_id UUID NOT NULL`
- `aoi GEOMETRY(MULTIPOLYGON, 4326) NOT NULL`
- `source_sensor VARCHAR(50) NOT NULL`
- `source_image_id TEXT NULL`
- `date_start DATE NULL`
- `date_end DATE NULL`
- `classified_tile_url TEXT NULL`
- `classified_raster_uri TEXT NULL`
- `legend_json JSONB NOT NULL`
- `class_stats_json JSONB NOT NULL`
- `area_total_ha NUMERIC(18,4) NULL`
- `status VARCHAR(20) NOT NULL`
- `created_at TIMESTAMP NOT NULL`

Index utiles :

- index spatial `GIST(aoi)`
- index sur `(project_id, model_id)`

### 18.6 Table `validation_metrics`

Role :

- stocker les performances du modele.

Champs recommandes :

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL`
- `model_id UUID NOT NULL`
- `result_id UUID NULL`
- `confusion_matrix_json JSONB NOT NULL`
- `overall_accuracy NUMERIC(8,4) NOT NULL`
- `kappa NUMERIC(8,4) NULL`
- `user_accuracy_json JSONB NULL`
- `producer_accuracy_json JSONB NULL`
- `class_support_json JSONB NULL`
- `validation_sample_count INTEGER NOT NULL`
- `created_at TIMESTAMP NOT NULL`

## 19. Strategie de cache et reutilisation

Le cache doit fonctionner a deux niveaux :

### 19.1 Cache des echantillons/datasets

Objectif :

- reutiliser un meme jeu d'echantillons versionne ;
- eviter de reconstruire un split train/validation identique.

Cle logique :

- projet ;
- schema de classes ;
- hash des echantillons ;
- strategie de split.

### 19.2 Cache des modeles

Objectif :

- reutiliser un modele deja entraine si le contexte n'a pas change.

Cle logique recommandee :

- `project_id`
- `algorithm`
- `samples_hash`
- `aoi_hash`
- `image_fingerprint`
- `input_bands`
- `input_indices`
- `hyperparams`

Si cette cle est identique :

- proposer `Reuse existing model` ;
- eviter un nouvel entrainement ;
- recharger les metriques et la carte si le resultat existe deja.

## 20. Rapport PDF professionnel

Le rapport doit etre structure en sections claires :

1. Contexte de l'analyse
2. AOI et source image
3. Classes d'occupation du sol
4. Echantillons d'entrainement et de validation
5. Algorithmes testes
6. Resultats de validation
7. Carte classifiee finale
8. Statistiques de surface
9. Interpretation automatique
10. Conclusion et recommandations

L'interpretation automatique doit generer des phrases du type :

- `Le modele Random Forest presente la meilleure precision globale parmi les algorithmes testes.`
- `La classe eau est bien separee, avec une precision utilisateur elevee.`
- `La confusion principale concerne vegetation et agriculture ; un enrichissement des echantillons est recommande.`
- `Le niveau de performance global permet un usage operationnel de la carte dans un contexte de pre-analyse.`

## 21. Recommandations de mise en oeuvre

Priorite 1 :

- finaliser la gestion des classes ;
- enrichir l'edition des echantillons sur la carte ;
- stocker les geometries en PostGIS.

Priorite 2 :

- industrialiser le split train/validation ;
- ajouter Random Forest, CART et SVM dans un meme service backend ;
- sauvegarder les metriques de validation.

Priorite 3 :

- ajouter le cache des modeles ;
- produire la carte classifiee versionnee ;
- generer un PDF professionnel complet.

Priorite 4 :

- ajouter comparaison de modeles ;
- scorecards de qualite ;
- audit trail complet des jeux d'echantillons et des versions de modele.

## 22. Synthese finale

Pour un usage professionnel, le module de classification supervisee de GeoRaster doit evoluer d'une logique "classification lancee depuis une carte" vers une logique complete de chaine de production :

- classes normalisees ;
- echantillons tracables ;
- jeux train/validation versionnes ;
- algorithmes comparables ;
- metriques fiables ;
- carte finale interpretable ;
- statistiques par classe ;
- rapport professionnel ;
- cache et reutilisation des modeles.

Cette architecture est entierement compatible avec une application WebGIS moderne basee sur React, FastAPI, Google Earth Engine et PostgreSQL/PostGIS.
