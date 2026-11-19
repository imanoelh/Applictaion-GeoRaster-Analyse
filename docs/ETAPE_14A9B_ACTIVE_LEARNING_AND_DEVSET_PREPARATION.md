# 14A.9B — Active Learning ciblé et DEV non-GOLD

## Livraison

Deux jeux **distincts**, sans entraînement ni calibration : **10 patches ACTIVE_LEARNING_TRAIN**, **4 patches DEV_CALIBRATION**. Les 14 RGB sont des fenêtres nouvelles 512×512 de l'orthophoto locale, copiées sans resampling et sans modifier la source. Aucun ancien TRAIN/VAL/TEST n'a changé d'affectation.

Projets directement ouvrables :

- `14A9B_active_learning/qgis/14A9B_ACTIVE_LEARNING_CORRECTION.qgz` : 30 couches (10 RGB, 10 références IA, 10 copies éditables), 10 bookmarks.
- `14A9B_dev_set/qgis/14A9B_DEV_CALIBRATION_CORRECTION.qgz` : 12 couches, 4 bookmarks.

Références IA violettes en lecture seule ; copies éditables vertes préremplies. Une seule paire de travail visible au départ. Les couches s'appellent explicitement NOT_GT / GT_PENDING. **Aucune GT humaine n'est déjà validée**. Le DEV n'est donc **pas prêt à calibrer**.

## Inventaire et séparation

163 petits RGB GeoTIFF (3 bandes minimum, jusqu'à 1024 pixels) inventoriés récursivement dans les jeux Building et test-data : tous lisibles ; 42 doublons stricts de pixels identifiés, non sélectionnés comme nouvelles données. 45 sources TRAIN non dupliquées sont seulement admissibles à une re-revue historique. Les sources à statut ambigu, GOLD, VAL et TEST restent exclues. Les PNG de visualisation, masques mono-bande, probabilités et grandes orthophotos parentes ne sont pas assimilés à des patches RGB d'annotation. L'inventaire historique complet et ses emprises sont conservés dans qa/.

208 fenêtres nouvelles éligibles spatialement examinées sur cinq planches RGB ; elles constituent des **candidats**, pas 208 nouveaux fichiers matérialisés ni 208 fenêtres mutuellement disjointes. Quatre sont réservées au DEV, donc 204 restent potentiellement TRAIN avant toute sélection additionnelle. Le CSV demandé comprend les 163 sources historiques et ces 208 fenêtres, avec origine, statut, exclusion, contexte et sélection. Les contextes non examinés restent UNREVIEWED.

Les 14 fenêtres retenues sont toutes distantes de **plus de 20 m** entre elles et des emprises historiques protégées, incluant les 4 GOLD, le pool 14A.7 réservé à validation et les références déclarées de tests anciens. Empreintes de pixels uniques, différentes des anciens RGB. Garde GOLD vérifié sur ID, hash et emprise. **TRAIN/DEV overlap=0 ; GOLD overlap=0**. La même acquisition Maxar parente reste partagée : développement interne spatialement séparé, aucune prétention d'indépendance entre acquisitions.

## Répartition exclusive du batch TRAIN

| Groupe principal de revue | Nombre | Patches AL |
|---|---:|---|
| Petits bâtiments / diversité de toits | 4 | 01,02,03,04 |
| Dense / adjacent | 2 | 05,06 |
| Ombres / faible contraste | 2 | 07,08 |
| Contexte FP route / sol nu | 2 | 09,10 |

Les catégories décrivent la priorité visuelle du patch, pas une GT de taille ou de matériau. La présence et la surface exactes des petits bâtiments seront confirmées par l'humain ; plusieurs contextes se recoupent. Les 4 DEV couvrent dense, résidentiel, ombres et scènes mixtes séparément.

## C6 utilisé exclusivement pour proposer

Même checkpoint SHA256 `7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84`, strict load réussi, CPU PyTorch, RGB min-max global, sigmoid, seuil historique **0,30**, connexité **4**, filtre historique **479 pixels**, aucune morphologie. **Aucun sweep**. Le protocole et le split sont enregistrés avant correction humaine.

**124 propositions TRAIN**, **49 propositions DEV**, soit **173** au total, toutes étiquetées MODEL_C6_PREDICTION_NOT_GT, NOT_REVIEWED, NOT_VALIDATED et is_ground_truth=0. Les copies vertes reprennent ces géométries ; elles ne deviennent pas humaines par simple copie.

La table `14A9B_C6_priority_indicators.csv` décrit composantes brutes/petites, fraction proche de 0,30 et couverture. La bande descriptive [0,25;0,35] ne change aucun masque et ne sélectionne aucun nouveau seuil. Par exemple AL04 comporte 25 petites composantes sur 40 ; AL05 montre 41 composantes brutes et des toits voisins fusionnés dans les overlays. Les planches finales ont été inspectées. Les deux scènes route/sol nu n'ont aucune composante finale : **contextes négatifs à examiner**, pas un nombre de FP humains confirmé. Le manifeste d'erreurs reste PENDING_HUMAN_REVIEW : aucun FN/FP corrigé fictif.

## Revue à réaliser

KEEP, DELETE, EDIT, SPLIT, ADD dans la copie verte. Utiliser les huit catégories demandées pour les erreurs et renseigner annotator. Voir `MANUAL_REVIEW.md` dans chaque dataset. Les UUID, proposal_id, correction_action et statuts permettent le rapprochement avec la référence figée ; les suppressions devront être reprises dans le manifeste d'erreurs lors de la QA post-correction. Aucun script utilisateur ou console Python requis pour ouvrir les projets et modifier les couches.

Les propositions réduisent le dessin initial, mais **les zones sans prédiction doivent aussi être revues**. Ajouter les bâtiments manqués. Ne pas utiliser les copies comme labels finaux avant cette revue, notamment sur petits objets. Les masques présents sont des masques **IA** rangés sous AI_PREANNOTATION_C6 ; le dossier DEV/masks ne contient volontairement aucun faux masque GT humain. Les masques humains binaires seront produits après correction et validation.

## Contrôles réellement exécutés

- 14 RGB strictement identiques aux fenêtres parentes ; dimensions/grilles natives conservées. Projet/vectoriels EPSG:32637, RGB natifs EPSG:4326 affichés par transformation QGIS ; aucune reprojection des RGB.
- 173 propositions valides, non vides, surfaces positives ; hors bounds=0, doublons de géométries par patch=0, attributs complets avec statuts explicites.
- Ré-rastérisation des vecteurs de travail sur chaque grille RGB : **égalité pixel par pixel** avec les masques IA correspondants ; dimensions, CRS et transform identiques.
- SQLite integrity_check=ok sur les quatre GeoPackages. Édition et persistance d'une feature test validées **dans une copie temporaire seulement**.
- Les deux projets s'ouvrent et se rouvrent via PyQGIS 3.40.14 ; 30/12 couches valides et 10/4 bookmarks. Le constructeur a émis des avertissements SQLite lors du nettoyage de connexions ; les contrôles indépendants des quatre fichiers ont ensuite confirmé intégrité et lecture complètes. Ne pas attribuer ces avertissements à une corruption sans preuve.
- Contrôle Desktop dédié : `{"train": "PASS", "dev": "PASS"}`. Résultats détaillés dans `qa/QGIS_DESKTOP_QA.json` lorsqu'exécutés complètement. Un simple lancement sans résultat n'est pas un PASS.
- **78 fichiers GOLD** comparés par SHA256 avant/après : aucun changement. 163 RGB historiques inchangés, orthophoto parente et poids C/C6 inchangés. Production backend/frontend non modifiée. Aucun modèle promu, aucune calibration, aucun entraînement.

## Décision

**Prêt pour correction humaine assistée. Pas prêt pour calibration DEV.** Après correction : QA géométrique et sémantique, finalisation des sources/statuts humains, masques alignés, registre des erreurs et vérification de fuite. Ensuite seulement autoriser une étape de calibration sur DEV ; figer les paramètres avant tout retour sur GOLD. Les 4 DEV ne rejoindront jamais le futur TRAIN.

ACTIVE LEARNING CANDIDATES :
208 fenêtres nouvelles examinées (204 hors réserve DEV) ; 163 RGB historiques audités séparément

ACTIVE LEARNING SELECTED :
10

SMALL BUILDING PATCHES :
4 (contexte attendu, à confirmer humainement)

DENSE / ADJACENT PATCHES :
2

SHADOW / LOW CONTRAST PATCHES :
2

FP-FOCUSED PATCHES :
2

DEV PATCHES :
4

TRAIN / DEV OVERLAP :
0

GOLD OVERLAP :
0

GOLD MODIFIED :
NO

AI PREANNOTATION USED :
YES

FULL MANUAL ANNOTATION REQUIRED :
NO

READY_FOR_AI_ASSISTED_CORRECTION :
YES

READY_FOR_DEV_CALIBRATION :
NO

NEXT STEP :
AI_ASSISTED_CORRECTION_14A9B
