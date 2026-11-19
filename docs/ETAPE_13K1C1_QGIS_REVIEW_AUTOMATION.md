# ÉTAPE 13K.1C.1 — QGIS Review Automation

## Résultat

Le workspace QGIS pour le pilote de trois patches est préparé dans `backend/data/fine_tuning/buildings/maxar_v1/qgis/13K1C_assisted_review.qgz`. Le projet a été généré avec PyQGIS 3.40.14, écrit puis rouvert pour vérifier les groupes, couches, sources, signets et extensions. Le lancement par le `.bat` a démarré `qgis-ltr-bin.exe`; le processus QGIS était présent et répondait. L’interface de contrôle n’a pas exposé sa fenêtre principale pour une inspection visuelle, donc la visibilité à l’écran n’est pas attestée séparément.

Le pilote reste celui du rapport 13K.1C, vérifié contre `metadata/review_priority.csv`:

| Groupe QGIS | Patch | Candidats | Couches |
|---|---|---:|---|
| `01_DENSE` | `GT_2024_residential_02` | 36 | RGB + review |
| `02_MEDIUM` | `GT_2024_dense_02` | 15 | RGB + review |
| `03_ZERO_CANDIDATE` | `GT_2024_difficult_01` | 0 | RGB + review vide |

Le patch sans proposition conserve son GeoJSON vide et reste éditable pour dessiner des bâtiments manquants. Le projet ne charge aucune couche `pre_annotations/` ni `annotations/`.

## Projet et édition

Les nouvelles features recoivent un ID unique `*_MANUAL_*`, le patch_id, la date source, `source=MANUAL_ADDITION`, `review_status=NOT_REVIEWED` et une surface calculee. L'annotateur doit verifier chaque nouvelle feature explicitement.

Le projet comprend les trois groupes demandés, un GeoTIFF 512 × 512 et une couche `REVIEW_BUILDINGS` par groupe. La création échoue explicitement si l’identifiant ou le nombre de candidats ne correspond plus au CSV, si le raster n’est pas 512 × 512, si le CRS/bounds divergent des métadonnées, si un GeoJSON n’est pas valide ou si son fournisseur n’offre pas l’édition des attributs, géométries, créations et suppressions.

Les rasters sont affichés en composition RGB 1/2/3 avec étirement 0–255. Les GeoJSON de revue sont au-dessus des rasters avec remplissage rouge transparent et contour visible. Le formulaire du champ `review_status` propose `NOT_REVIEWED`, `IN_REVIEW`, `REVIEWED`, `VALIDATED`; aucun statut n’est affecté automatiquement. Les champs existants restent accessibles, avec les alias utiles `building_id`, `source`, `review_status`, `confidence_mean`, `area_m2`. Les outils d’édition natifs de QGIS peuvent créer/supprimer des features et modifier sommets/géométries; les opérations restent dans le GeoJSON `review/` associé.

Le projet ouvre sur le patch dense et contient trois bookmarks (`01_DENSE`, `02_MEDIUM`, `03_ZERO_CANDIDATE`). Le surlignage de sélection reste celui de QGIS. Les changements aux propositions brutes et aux annotations finales ne sont pas écrits au chargement.

## Scripts

- `scripts/build_13K1C_qgis_project.py` construit le projet depuis le CSV du pilote avec le Python PyQGIS installé.
- `scripts/open_13K1C_qgis_review.bat` utilise `GEORASTER_QGIS_EXE` uniquement s’il pointe vers un exécutable existant; sinon il utilise exactement `C:\Program Files\QGIS 3.40.14\bin\qgis-ltr-bin.exe`. Il crée le projet s’il manque, puis lance QGIS avec le projet.
- `scripts/finalize_13K1C_review.bat` appelle `scripts/finalize_13K1C_review.py` dans `backend/.venv`.
- Le finaliseur exige, pour chaque patch pilote, `metadata/<patch_id>.json: review_status=VALIDATED`, un `reviewer` et toutes les features marquées `REVIEWED` ou `VALIDATED`. Il exécute ensuite le promoteur déjà existant puis `building_annotation_workflow.py`, lequel valide les annotations, génère les masques/overlays et met à jour ses rapports. Le patch sans feature peut être validé vide seulement si le réviseur l’a effectivement contrôlé.

Le garde-fou a été exécuté avant toute revue: il a refusé le finaliseur avec code 2 et a indiqué les prérequis manquants. Il n’a modifié aucun fichier. Les 16 patches restent `NOT_ANNOTATED`, aucun masque pilote n’a été créé, et les propositions/annotations n’ont pas été promues. Il n’y a eu aucun entraînement et aucun changement aux modèles ni au pipeline Building de production.

## Lancement

La commande utilisateur est `scripts/open_13K1C_qgis_review.bat`. Après l’édition humaine, enregistrer chaque GeoJSON dans `review/`; mettre les features examinées à `REVIEWED` (ou `VALIDATED` après contrôle final), puis renseigner manuellement l’état `VALIDATED` et le nom du réviseur dans les trois JSON de `metadata/`. Exécuter ensuite `scripts/finalize_13K1C_review.bat`. Le finaliseur s’arrête si l’un de ces états manque.

## État final

ÉTAPE 13K.1C.1 — QGIS REVIEW AUTOMATION

QGIS EXE :
C:\Program Files\QGIS 3.40.14\bin\qgis-ltr-bin.exe

QGIS FOUND :
YES

QGIS VERSION :
3.40.14-Bratislava

PROJECT CREATED :
YES

PROJECT PATH :
backend/data/fine_tuning/buildings/maxar_v1/qgis/13K1C_assisted_review.qgz

PILOT PATCHES :
3

RGB LAYERS :
3 / 3

REVIEW LAYERS :
3 / 3

DENSE PATCH :
READY

MEDIUM PATCH :
READY

ZERO-CANDIDATE PATCH :
READY

EDITABLE REVIEW LAYERS :
YES

BOOKMARKS :
CREATED

WINDOWS BAT LAUNCHER :
CREATED

QGIS LAUNCH TEST :
SUCCESS (processus répondant; fenêtre principale non exposée pour inspection visuelle)

AUTO VALIDATION :
DISABLED

HUMAN REVIEW REQUIRED :
YES

MODEL_C :
UNCHANGED

MODEL_A :
UNCHANGED

ONNX :
UNCHANGED

PRODUCTION PIPELINE :
UNCHANGED

READY_FOR_HUMAN_REVIEW :
YES

NEXT STEP :
REVIEW 3 PATCHES IN QGIS /
FIX QGIS WORKSPACE
