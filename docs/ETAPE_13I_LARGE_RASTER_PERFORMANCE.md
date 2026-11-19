# Étape 13I — Profilage des grands rasters

## Résultat de cette passe

**État : profilage statique effectué, profilage d’exécution bloqué. Aucune optimisation du code métier n’a été appliquée.** Le projet contient le raster préparé de référence et les checkpoints, mais le backend 8011 n’est pas démarré et `backend/.venv` ne contient ni PyTorch, ni NumPy, ni Rasterio. Les interpréteurs Python 3.10, 3.11 et 3.12 disponibles ne contiennent pas non plus ces dépendances. Installer un environnement PyTorch/Rasterio ou lancer une autre copie aurait changé les conditions de comparaison; aucune mesure de performance ne peut donc être rapportée honnêtement dans cet état.

Le répertoire n’a pas de métadonnées Git (`.git` absent), donc l’état des modifications antérieures ne peut pas être vérifié par `git diff` ou `git log`.

## Baseline connue

La baseline ci-dessous vient du résultat déjà communiqué avant cette passe, pas d’une nouvelle exécution :

| Mesure | Valeur de référence |
|---|---:|
| Raster | 10 292 × 9 378, RGB uint8 |
| Pixels | 96 518 376 |
| Tuiles | 575 |
| Modèle / seuil | `spacenet2_deeplab` / 0,50 |
| Batch configuré | 4 |
| Durée totale | 2 610,72 s (43,51 min) |
| `processing_time_ms` du masque | 2 585 388 ms (2 585,39 s) |
| Polygonisation annoncée | ~5 971 ms |
| Candidats / aire totale | 2 411 / 506 005,14 m² |
| RAM ou espace disque en échec | aucun problème signalé lors de cette exécution |

Ces durées ne sont pas un profil par étape. En particulier, `PostProcessingService.process()` démarre son chronomètre avant de consommer `predictions`, qui est un générateur paresseux. Le parcours de ce générateur effectue le chargement du modèle si nécessaire, la lecture et préparation des tuiles, les forwards PyTorch et leur fusion. Ainsi, les 2 585 388 ms ne sont **pas** une mesure isolée de fusion ou de post-traitement. La mesure de polygonisation est séparée dans `BuildingPolygonizationService`, mais les temps d’inférence, fusion, I/O memmap, seuil, statistiques et sérialisation n’ont pas de chronomètres isolés dans ce chemin.

## Constats vérifiés dans le code

- **Modèle chargé une fois par processus :** l’adapter garde `_model`, `load()` sort si le modèle est déjà chargé et protège le chargement avec un verrou. Le registre d’inférence est créé au niveau du module API. La durée du premier chargement et celle des requêtes suivantes n’ont pas été mesurées dans cette passe.
- **Min/max :** `_image_minmax()` parcourt des fenêtres 1 024 × 1 024, puis mémorise les deux valeurs dans un cache borné à 32 entrées, indexé par raster, chemin, taille/date et bandes. Pour le raster de référence, un cache froid implique jusqu’à 110 fenêtres statistiques (11 colonnes × 10 lignes); le cache chaud évite ce parcours. Durée réelle inconnue.
- **Lectures de tuiles :** `TilingService.iter_tiles()` garde son dataset Rasterio ouvert pendant la génération et lit les fenêtres successivement. Il n’y a pas d’ouverture/fermeture explicite par tuile. Avec 575 tuiles, on attend 575 lectures de fenêtres de tuiles, plus les 110 lectures min/max à cache froid, hors ouvertures de validation/métadonnées effectuées par le reste de l’application. Aucun compteur d’exécution n’a été ajouté.
- **Batch et tenseurs :** batch préféré 4. Le chemin batch empile les images avec `np.stack`, puis utilise `torch.from_numpy`; il exécute `torch.inference_mode()`. Le chemin vérifie `model.eval()` lors du chargement. La conversion/transfer et le forward ne sont pas chronométrés séparément.
- **Threading :** le nombre intra-op est fixé par `SPACENET2_TORCH_THREADS` (défaut 4, plafonné par `os.cpu_count()`). Le processus expose 8 CPU. Aucune matrice de tests batch/thread n’a été exécutée; aucun meilleur réglage ne peut être recommandé.
- **Memmap :** au-dessus de 25 MP, somme de probabilités, poids, validité et masque binaire sont disk-backed. Le seuil utilise des bandes de 1 024 lignes. `cleanup()` flush les tableaux à la fin, pas après chaque tuile. Taille de bloc non paramétrable observée pour le seuil. Durées lecture/écriture/flush et pic disque inconnus.
- **Fusion :** chaque résultat met à jour des tranches NumPy correspondant à sa fenêtre; pas de boucle Python par pixel constatée dans l’accumulation. Les opérations `np.where`, masques et validations restent exécutées par tuile.
- **Boucles Python par pixel :** elles existent dans `remove_small_objects()` et `connected_components()` (parcours en largeur et voisinage pixel par pixel). Leur coût sur le masque 96 MP n’est pas isolé. C’est une piste prioritaire à profiler, mais la remplacer avant mesure et comparaison de masque risquerait de changer les composantes ou les géométries.
- **Géométrie et métriques :** la polygonisation possède son propre temps global; statistiques et sérialisation GeoJSON ont des durées internes dans `BuildingResultsService`, mais les mesures du raster de référence ne sont pas retrouvées dans les artefacts disponibles.
- **Répertoire temporaire :** Python indique `%TEMP% = C:\Users\IMANE_~1\AppData\Local\Temp`. Le type du disque, son espace libre actuel et le pic occupé pendant le benchmark n’ont pas pu être établis (interrogation système refusée). La memmap utilise `tempfile.mkdtemp()` et aucun réglage `GEORASTER_AI_TEMP_DIR` n’a été trouvé dans le chemin examiné.
- **Progression :** logs de démarrage existants, mais pas de compteurs périodiques du type `TILES n/575` observés dans le pipeline étudié.

## Profil par étape

| Étape demandée | Mesure actuelle | Commentaire |
|---|---:|---|
| Ouverture / métadonnées raster | non mesurée | Entrée post-process ouvre le raster pour la grille; temps non isolé. |
| RGB / préparation raster | non mesurée | Lecture de fenêtres gérée par le générateur de tuiles. |
| Min/max | non mesuré | 110 fenêtres au premier passage, cache mémoire par raster ensuite. |
| Tiling / tile reads | non mesuré | 575 fenêtres; dataset gardé ouvert pendant l’itération. |
| Prétraitement / conversion NumPy→Torch | non mesurés | Pas de chronomètres spécifiques. |
| Forward modèle / batch | non mesurés | Inclus dans le chronomètre large du générateur. |
| Fusion / écritures memmap / poids | non mesurés | Inclus dans `processing_time_ms`; pas de sous-totaux. |
| Flush memmap | non mesuré | Flush final lors du cleanup. |
| Seuil / génération du masque | non mesurés | Seuil par bandes de 1 024 lignes. |
| Composantes / nettoyage | non mesurés | Algorithmes Python pixel par pixel présents. |
| Polygonisation | ~5 971 ms (baseline rapportée) | < 1 % du temps total annoncé; mesure à reconfirmer. |
| Statistiques / sérialisation | non mesurées | Code prévoit certains chronométrages mais aucune valeur de cette requête n’est disponible. |
| Nettoyage / total HTTP | total 2 610,72 s (baseline rapportée) | Pas de trace exploitable pour ventiler le delta. |

## État des optimisations et reprise

Aucune optimisation n’est appliquée et aucune comparaison avant/après ne peut être faite. Les poids MODEL_C et MODEL_A n’ont pas été modifiés. Aucun réglage de seuil, résolution, taille/recouvrement des tuiles, RGB, normalisation, sémantique de post-traitement, géométrie ou statistiques n’a été modifié. GEE, indices, classifications, Change Detection, exports et mode offline n’ont pas été touchés.

La prochaine mesure requiert de restaurer l’environnement exact ayant servi au backend 8011 (Python, PyTorch, Torchvision, Rasterio, NumPy, Shapely et dépendances), puis de démarrer uniquement cette instance sur 8011. Il faudra ajouter une instrumentation temporaire par étape, établir un profil baseline sur le raster déjà présent, profiler les masques intermédiaires, puis choisir et valider les optimisations sur les sorties exactes. En l’absence de ce profil, choisir une taille de batch, un nombre de threads ou un bloc memmap serait une supposition. Le test des cinq tailles de batch et des configurations CPU et blocs demandé dans l’étape 13I n’a donc pas été lancé.

## ÉTAPE 13I — LARGE RASTER PERFORMANCE

RASTER :
10292 x 9378

TOTAL PIXELS :
96518376

TILE COUNT :
575

MODEL :
spacenet2_deeplab

THRESHOLD :
0.50

BASELINE TOTAL TIME :
2610.72 s (rapport antérieur; non rejoué)

PROFILE BREAKDOWN :
RASTER_READ = NOT MEASURED
MINMAX = NOT MEASURED (110 windows on cold cache)
TILING = NOT MEASURED
PREPROCESS = NOT MEASURED
MODEL_INFERENCE = NOT MEASURED
NUMPY_TORCH_TRANSFER = NOT MEASURED
FUSION = NOT SEPARATELY MEASURED; included in process() timer
MEMMAP_IO = NOT MEASURED
THRESHOLD = NOT MEASURED
POLYGONIZATION = ~5971 ms (prior reported value; not rerun)
STATISTICS = NOT MEASURED
SERIALIZATION = NOT MEASURED
CLEANUP = NOT MEASURED

MAIN BOTTLENECK :
NOT ISOLATED. Existing 2585388 ms process() timer includes lazy tile generation, preprocessing, model forward, fusion and mask cleanup. Python pixel loops exist in small-object filtering and connected-components; their share is unknown.

OPTIMIZATIONS APPLIED :
NONE (runtime unavailable; no blind changes)

BEST BATCH SIZE :
NOT TESTED (configured 4)

BEST CPU THREAD CONFIG :
NOT TESTED (configured intra-op 4; machine reports 8 CPUs)

BEST MEMMAP BLOCK SIZE :
NOT TESTED (threshold currently processes 1024 rows at a time)

MEMMAP FLUSH STRATEGY :
Current: flush at result cleanup, not per tile; performance unmeasured

TEMP DIRECTORY :
C:\Users\IMANE_~1\AppData\Local\Temp (disk type and free space unavailable)

MODEL LOAD CACHED :
YES (code path; timing not measured)

MINMAX CACHED :
YES (in-process, up to 32 raster entries; cold/warm timing not measured)

DATASET REOPENING :
NOT_PER_TILE (tiling generator retains an open dataset; other pipeline opens remain)

BUFFER REUSE :
NO EVIDENCE; batch uses a fresh np.stack allocation

PYTHON PIXEL LOOPS :
FOUND (small-object removal and connected components; not removed)

OPTIMIZED INFERENCE TIME :
NOT RUN

OPTIMIZED FUSION TIME :
NOT RUN

OPTIMIZED TOTAL TIME :
NOT RUN

MEASURED SPEEDUP :
NOT AVAILABLE

TIME SAVED :
NOT AVAILABLE

OUTPUT EQUIVALENCE :
NOT RE-CHECKED; no optimization applied

CANDIDATES BEFORE :
2411 (previous validated result)

CANDIDATES AFTER :
NOT RUN

TOTAL AREA BEFORE :
506005.14 m² (previous validated result)

TOTAL AREA AFTER :
NOT RUN

MEMORY PEAK :
NOT MEASURED in this pass

DISK TEMP PEAK :
NOT MEASURED in this pass

LARGE RASTER STABILITY :
PREVIOUSLY VALIDATED; not rerun

BACKEND TESTS :
NOT RUN (runtime dependencies absent)

FRONTEND TESTS :
SUCCESS (all scripts passed)

CLIENT BUILD :
SUCCESS (4m 24s)

SSR BUILD :
SUCCESS (46.76s)

MODEL_C :
UNCHANGED

MODEL_A :
BACKEND RETAINED

GEE :
UNCHANGED

INDICES :
UNCHANGED

CLASSIFICATIONS :
UNCHANGED

CHANGE DETECTION :
UNCHANGED

OFFLINE MODE :
UNCHANGED

READY FOR PERFORMANCE ACCEPTANCE :
NO — no measured optimization or before/after validation

NEXT STEP :
RESTORE THE MATCHING PYTHON ENVIRONMENT AND BACKEND 8011, THEN PROFILE BASELINE BEFORE OPTIMIZATION