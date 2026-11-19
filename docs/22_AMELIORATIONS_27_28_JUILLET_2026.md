# 22 — Améliorations des 27 et 28 juillet 2026

## 1. Objet

Ce document présente les dernières améliorations fonctionnelles, scientifiques et techniques de GeoRasterPortal réalisées les 27 et 28 juillet 2026.

Les interventions ont été ciblées afin de préserver :

- les autres analyses raster ;
- les contrats API existants ;
- l’intégration Google Earth Engine ;
- les exports GeoTIFF, CSV, PNG et PDF ;
- le cache, l’historique et la restauration des résultats ;
- la structure générale du frontend et du backend.

## 2. Synthèse

Le cycle a principalement porté sur :

1. la fiabilisation de l’analyse NDBI Built-up ;
2. la cohérence entre les couches visibles et les exports ;
3. la correction de l’image satellite dans le rapport PDF ;
4. la correction de l’export cartographique PNG ;
5. l’alignement de `CHANGE_NDBI` sur la logique NDBI Built-up ;
6. l’amélioration de l’interface arabe ;
7. la consolidation documentaire et la validation du projet.

## 3. Améliorations du 27 juillet 2026

### 3.1. NDBI Raw et Built-up detection

Le backend conserve deux représentations complémentaires :

- `ndbi_raw` : réponse spectrale continue calculée par `(SWIR - NIR) / (SWIR + NIR)` ;
- `ndbi_built_detection` : interprétation multi-observation des surfaces bâties et imperméables.

L’interface présente par défaut `Built-up detection`. Le résultat Raw reste disponible dans le backend pour la traçabilité scientifique et les traitements internes.

### 3.2. Réduction des faux positifs

La logique Built-up a été renforcée afin d’éviter qu’un sol nu clair soit automatiquement interprété comme une zone bâtie.

Les données auxiliaires sont utilisées comme preuves de confirmation :

- Dynamic World ;
- ESA WorldCover ;
- GHSL Built Surface 2018.

WorldCover ne peut plus créer seul une détection bâtie. GHSL intervient en dernier recours avec un seuil conservateur de `50 m²` bâtis par cellule de `100 m²` et ne peut jamais produire seul une classe de haute confiance.

### 3.3. Récupération des toits clairs

Les toits clairs pouvant présenter une valeur NDBI faible ou négative sont récupérés uniquement lorsque plusieurs indices ou références convergent.

Les quatre classes finales sont :

1. No built-up evidence ;
2. Potential impervious surface or road ;
3. Built-up area detected ;
4. High-confidence built-up area.

### 3.4. Validation NDBI réelle

Les contrôles enregistrés le 27 juillet comprennent :

- validation sur plusieurs zones réelles ;
- comparaison avec l’imagerie satellite ;
- `40` tests backend réussis ;
- calcul GEE forcé mesuré à environ `36,5 s` ;
- restauration depuis le cache mesurée à environ `0,10 s` ;
- exports CSV, PNG et GeoTIFF contrôlés.

### 3.5. Interface arabe et identité visuelle

Les améliorations suivantes ont été intégrées :

- logo positionné à droite en mode arabe ;
- titre de la plateforme traduit en arabe dans le menu latéral ;
- titre du header adapté au mode RTL ;
- conservation de la disposition anglaise ;
- absence de modification des menus, analyses ou appels backend.

### 3.6. Consolidation documentaire

Une documentation finale structurée a été ajoutée :

- document de synthèse globale ;
- index officiel ;
- chapitres numérotés `01` à `21` ;
- cartographie des documents historiques ;
- règles de modification et problèmes connus ;
- commandes d’installation, de lancement et d’authentification GEE.

Le commit de référence du 27 juillet est :

```text
5ac968db — Finalize GeoRaster NDBI documentation and Arabic branding
```

## 4. Améliorations du 28 juillet 2026

### 4.1. Diagnostic de la connexion Google Earth Engine

Le diagnostic a confirmé que :

- l’authentification utilisateur GEE fonctionne ;
- le projet utilisé est `gee-satellite-project-123456` ;
- l’initialisation directe retourne `GEE OK: 1` ;
- le backend répond sur `http://127.0.0.1:8010` ;
- l’échec initial de `/api/gee/status` provenait d’un backend arrêté ou d’une ancienne instance, et non de la plateforme frontend.

### 4.2. Renommage des exports

Les libellés ont été rendus plus explicites :

| Ancien libellé | Nouveau libellé anglais | Arabe |
|---|---|---|
| PNG | Map PNG | خريطة PNG |
| Map PDF | PDF Report | تقرير PDF |

Seuls les textes visibles ont été modifiés. Les routes, contenus et formats d’export sont inchangés.

### 4.3. Image satellite manquante dans le rapport PDF

#### Symptôme

La section « Satellite image of reference » affichait un panneau de secours au lieu de l’image Sentinel-2, tandis que le résultat de l’analyse apparaissait correctement.

#### Cause

Lors de la sélection de `ndbi_built_detection`, la valeur :

```json
{
  "rgb_tile_url": null
}
```

écrasait l’URL RGB valide du run principal.

#### Correction

La fusion des métadonnées de couche ignore désormais les URL vides. La couche Built-up remplace uniquement l’URL du résultat analytique et conserve l’image RGB de référence.

#### Validation

Le rapport réel a été régénéré et inspecté :

- section 3 : image satellite RGB présente ;
- section 4 : résultat Built-up présent ;
- autres pages et statistiques conservées.

### 4.4. Export Map PNG incohérent

#### Symptôme

Le raster exporté utilisait les couleurs du NDBI Raw, mais la légende utilisait les classes Built-up.

#### Cause

La clé de la couche active n’était pas transmise au reconstructeur backend. Celui-ci appelait donc le générateur PNG sans `ndbi_built_detection`.

#### Correction

La clé de couche active est maintenant transmise du frontend au backend et utilisée :

- pour le thumbnail GEE ;
- pour les tuiles de secours ;
- pour la reconstruction cartographique ;
- pour maintenir la cohérence entre raster, classes, statistiques et légende.

#### Validation

Sur un run réel de `2,96 km²` :

- les quatre couleurs Built-up sont présentes ;
- aucun pixel de la palette bleue Raw n’est présent dans la zone cartographique exportée ;
- les surfaces de la légende correspondent aux classes affichées.

### 4.5. Alignement de CHANGE_NDBI avec le NDBI de base

#### Ancien fonctionnement

```text
NDBI Raw période 1
NDBI Raw période 2
Delta des valeurs NDBI Raw
```

#### Nouveau fonctionnement

```text
Built-up detection période 1
Built-up detection période 2
Delta des classes d’évidence urbaine
```

Chaque période utilise exactement le même contexte que le NDBI Built-up de base :

- NDBI ;
- NDVI ;
- NDWI ;
- BSI ;
- Dynamic World ;
- WorldCover ;
- GHSL.

La différence entre les périodes est interprétée ainsi :

| Différence de classe | Interprétation |
|---:|---|
| `-3` ou `-2` | diminution importante de l’évidence bâtie |
| `-1` | faible diminution |
| `0` | classe stable |
| `+1` | nouvelle artificialisation probable |
| `+2` ou `+3` | forte augmentation de l’évidence bâtie |

Cette modification concerne uniquement `CHANGE_NDBI`. Les traitements `CHANGE_NDVI`, `CHANGE_NDWI`, `CHANGE_BSI` et `CHANGE_SAVI` conservent leur logique.

### 4.6. Invalidation du cache CHANGE_NDBI

La version de traitement est devenue :

```text
change-ndbi-built-detection-periods-v4
```

Les anciens résultats basés sur le Raw ne sont donc plus réutilisés. Après redémarrage du backend, le premier lancement de `CHANGE_NDBI` force un nouveau calcul.

### 4.7. Tests et build

Validation finale du 28 juillet :

```powershell
cd backend
C:\Users\Imane_C4E\anaconda3\python.exe -m pytest -q

cd ..\frontend
npm.cmd run build
```

Résultats :

- backend : `44 passed` ;
- frontend : build client et SSR réussi ;
- compilation Python réussie ;
- contrôle `git diff --check` réussi ;
- aucun fichier de credentials, export de diagnostic ou `node_modules` ajouté au commit.

Le processus GEE temporaire isolé n’a pas pu réutiliser les credentials conservés en mémoire par l’instance déjà ouverte sur le port `8010`. La validation GEE finale de la nouvelle version `CHANGE_NDBI v4` doit donc être exécutée après redémarrage du backend authentifié.

## 5. Vérification fonctionnelle recommandée

Après redémarrage du backend :

1. ouvrir Map & Analysis ;
2. sélectionner une petite zone connue ;
3. lancer NDBI et vérifier la couche Built-up ;
4. lancer `NDBI Change Detection` sur deux saisons comparables ;
5. ouvrir « NDBI - Period 1 » puis « NDBI - Period 2 » ;
6. vérifier que les légendes utilisent les quatre classes Built-up ;
7. ouvrir la couche de changement ;
8. exporter Map PNG, GeoTIFF, CSV et PDF Report ;
9. vérifier la cohérence entre carte, légende, statistiques et historique.

Les périodes ne doivent plus afficher :

- Negative NDBI response ;
- Near-zero NDBI response ;
- Positive NDBI response ;
- Strong positive NDBI response.

Elles doivent afficher les classes Built-up listées dans la section 3.3.

## 6. Livraison Git

La version consolidée a été poussée sur :

```text
Dépôt  : https://github.com/gissolutionsib/RaterPortal.git
Branche: dev_v1
Commit : 933cebbed935a4aac0319bf99ee58fb95f621333
Message: Fix NDBI change detection and map exports
```

Le commit contient :

- les corrections du rapport PDF ;
- la cohérence de l’export Map PNG ;
- les nouveaux libellés d’export ;
- la logique `CHANGE_NDBI v4` ;
- les tests de non-régression associés ;
- les descriptions fonctionnelles mises à jour.

## 7. Conclusion

Le cycle des 27 et 28 juillet améliore principalement la fiabilité du NDBI dans les environnements arides, la cohérence des résultats entre l’écran et les exports, ainsi que la traçabilité scientifique de la détection de changement.

Le NDBI Raw reste conservé comme donnée scientifique interne. Les utilisateurs voient et exportent la couche Built-up interprétée, et `CHANGE_NDBI` compare désormais deux interprétations Built-up cohérentes plutôt que deux réponses Raw présentées comme des classes urbaines.
