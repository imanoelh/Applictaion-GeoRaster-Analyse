# ÉTAPE 13I.1 — Runtime profile baseline

Date d'exécution : 19 octobre 2026. Profil collecté dans la copie `Georaster-19-10` sur le backend `8011` avec instrumentation temporaire, retirée après l'exécution.

## Résumé

Le parcours complet `POST /api/ai/results/building` a répondu HTTP 200. La requête a utilisé le raster préparé `ai-ortho-8d42d0c39d12-3882a676ca4a-3e970d60cef4`, MODEL_C `spacenet2_deeplab`, seuil 0,50, taille de tuile 512, recouvrement 0,20, batch configuré à 4 et paramètres de post-traitement/polygonisation identiques à la requête de référence.

La sortie est équivalente à la référence historique : **2 411 candidats** et **506 005,1354 m²**, soit 506 005,14 m² à deux décimales. La durée complète mesurée est **2 712,716 s** (45 min 12,7 s), contre la baseline annoncée de 2 610,72 s, soit environ +3,91 %. Cette comparaison inclut le coût du profilage temporaire et ne constitue pas une mesure non instrumentée.

Le passage initial au mauvais endpoint `/api/ai/inference/building` a été interrompu avant d'être retenu comme mesure. Le premier essai sur l'endpoint complet a ensuite rencontré un défaut de type dans le wrapper de profiling temporaire pour le dernier lot singleton. Le wrapper temporaire a été corrigé pour conserver la liste de sorties attendue; le code applicatif n'a pas été modifié. Le run final ci-dessous est le seul profil complet retenu.

## Runtime et baseline de tests

| Élément | Valeur observée |
|---|---|
| Python backend | 3.12.10 (`backend/.venv`) |
| PyTorch | 2.8.0+cpu |
| Torchvision | 0.23.0+cpu |
| NumPy | 2.5.4 |
| Rasterio | 1.5.2 |
| Shapely | 2.2.0 |
| Affine | 3.0.1 |
| pytest | 9.1.1 |
| Earth Engine Python API | 1.7.48 |
| Backend tests avant profilage | 227 passed, 0 failed; 19 subtests passed |
| PROJ/GDAL | Variables de processus pointées vers les données de la roue Rasterio de `.venv` pour éviter les chemins PROJ/GDAL hérités invalides |

Le serveur `8011` a été lancé avec cette interprétation Python. L'état GEE pendant le run était `enabled=true`, projet `gee-satellite-project-123456`, compte `imane19elhamri@gmail.com`, collection `COPERNICUS/S2_SR_HARMONIZED`. Le port 8010 n'a pas été touché.

## Configuration et sortie

| Paramètre | Valeur |
|---|---:|
| Raster | `ai-ortho-8d42d0c39d12-3882a676ca4a-3e970d60cef4` (COG préparé correspondant) |
| Dimensions | 10 292 × 9 378 |
| Pixels | 96 518 376 |
| Tuiles totales | 575 |
| Tuiles traitées par le modèle | 513 (62 ignorées) |
| Lots instrumentés | 139 appels; 513 tuiles cumulées; batch configuré 4 |
| Modèle | `spacenet2_deeplab` (MODEL_C) |
| Seuil | 0,50 |
| Candidats | 2 411 |
| Surface totale | 506 005,135444 m² |
| Pixels positifs | 4 353 556 |
| Pixels valides | 80 113 044 |
| HTTP | 200; réponse sérialisée 10 824 331 octets |

## Temps observés

Les pourcentages ci-dessous utilisent `TOTAL = 2 712,716 s`. Les phases imbriquées ne doivent pas être additionnées. En particulier, `POSTPROCESS_PROCESS_TOTAL` englobe le générateur paresseux et l'inférence; ce timer n'est pas classé comme un coût exclusif.

| Phase | Temps (s) | % du total | Remarque |
|---|---:|---:|---|
| MODEL_FORWARD | 2 606,2541 | 96,077 % | 139 appels; ~18,75 s par appel de lot; ~5,08 s par tuile traitée |
| CONNECTED_COMPONENTS | 31,5789 | 1,164 % | 1 appel; 4 353 556 pixels positifs inspectés |
| REMOVE_SMALL_OBJECTS | 27,3737 | 1,009 % | 1 appel; 4 353 718 pixels positifs en entrée |
| POLYGONIZATION_TOTAL | 7,2658 | 0,268 % | Inclut la génération Rasterio des formes et leur validation |
| MINMAX (froid, fenêtres) | 5,8193 | 0,215 % | 110 lectures; cache chaud ensuite ~0,0016 s |
| CLEANUP (memmap/résultat masque) | 5,5423 | 0,204 % | Durée enveloppante de nettoyage |
| MEMMAP_FLUSH | 5,3525 | 0,197 % | 2 flushes |
| MODEL_LOAD | 4,5233 | 0,167 % | Un chargement |
| RESULTS_BUILD | 3,9456 | 0,145 % | Timer enveloppant résultats/statistiques |
| TILE_READS | 3,5263 | 0,130 % | 575 lectures de fenêtre |
| GEOMETRY_CLEANUP_AND_REPROJECT | 3,2442 | 0,120 % | 2 411 géométries |
| MEMMAP_WRITE | 0,7430 | 0,027 % | 1 616 appels d'affectation |
| NUMPY_STACK | 0,7484 | 0,028 % | 134 appels mesurés |
| SERIALIZATION | 0,8398 | 0,031 % | 2 appels JSON |
| TORCH_TO_NUMPY | 0,5970 | 0,022 % | 417 conversions |
| PREPROCESS | 7,6221 | 0,281 % | Mesure cumulée des fenêtres; compte instrumenté 1 150 |
| RASTER_OPEN | 0,0254 | 0,001 % | 3 ouvertures |
| FUSION (incluant accès memmap) | 2,1598 | 0,080 % | 575 accumulations; temps CPU fusion hors accès memmap ~2,0794 s |
| NUMPY_TO_TORCH | 0,0089 | <0,001 % | 278 conversions |
| THRESHOLD_AND_MASK | 0,0575 | 0,002 % | 10 opérations |
| STATISTICS | 0,0029 | <0,001 % | Calcul des statistiques |
| GEOMETRY_CLEANUP | 0,3700 | 0,014 % | Validation de 2 411 formes |
| RASTERIO_SHAPES | 0,0018 | <0,001 % | Génération des formes |

**TOP_1_BOTTLENECK :** `MODEL_FORWARD`, 2 606,254 s (96,077 % du total).

**TOP_2_BOTTLENECK :** `CONNECTED_COMPONENTS`, 31,579 s (1,164 %), parmi les phases exclusives mesurées hors forward.

**TOP_3_BOTTLENECK :** `REMOVE_SMALL_OBJECTS`, 27,374 s (1,009 %), parmi les phases exclusives mesurées hors forward.

Le timer `POSTPROCESS_PROCESS_TOTAL` vaut 2 695,308 s (99,36 % du total), mais il contient les appels du générateur paresseux et presque toute l'inférence; il ne représente pas un coût additionnel. `MODEL_ADAPTER_TOTAL` vaut 2 609,034 s et contient lui aussi `MODEL_FORWARD`.

## Memmap, mémoire et limites instrumentales

- Répertoire temporaire : `C:\Users\IMANE_~1\AppData\Local\Temp`.
- Espace libre avant : 45 155 266 560 octets; après : 44 904 423 424 octets; diminution nette observée : 250 843 136 octets. Cette différence nette n'est pas un pic temporaire strict.
- Écritures memmap logiques instrumentées : 2 338 111 328 octets; lectures logiques : 3 965 869 744 octets. Ce sont des volumes d'accès observés, non une mesure du trafic physique disque.
- Temps des appels d'écriture memmap : 0,743 s; lectures de vues mappées : 0,0366 s; flush : 5,353 s; nettoyage : 5,542 s.
- Le wrapper mesure l'accès aux vues NumPy mappées, pas le temps des défauts de page Windows; les lectures disque physiques ne peuvent donc pas être isolées par cette mesure.
- Le compteur du pic de mémoire de travail et celui du pic d'espace temporaire n'ont pas renvoyé de valeur exploitable (0). La mémoire système disponible est passée d'environ 8,30 Go avant à 6,28 Go après; cela ne mesure pas le pic propre au processus.
- Certaines durées sont imbriquées et les timers instrumentés ajoutent une surcharge. Les valeurs exclusives utilisées pour classer les bottlenecks sont signalées séparément.

## Changements et état final

Aucune optimisation ni modification métier n'a été appliquée. Le seul changement durant l'exécution a concerné le script temporaire d'instrumentation sous `backend/.pytest-runtime`, pour corriger le type de retour du lot singleton. MODEL_A, MODEL_C, le registre, l'inférence métier, les traitements, les indices, exports et classifications sont restés inchangés. Les tests backend ont été exécutés avant ce profilage et n'ont pas été modifiés.

```text
ÉTAPE 13I.1 — RUNTIME PROFILE BASELINE

BACKEND 8011 :
RUNNING

PYTHON :
3.12.10

TORCH :
2.8.0+cpu

TORCHVISION :
0.23.0+cpu

NUMPY :
2.5.4

RASTERIO :
1.5.2

BACKEND TESTS :
227 PASSED / 0 FAILED

RASTER :
10292 x 9378

PIXELS :
96518376

TILE COUNT :
575

MODEL :
spacenet2_deeplab

BATCH SIZE :
4

TOTAL TIME :
2712.716 s

RASTER_OPEN :
0.025 s

MINMAX :
5.819 s

TILE_READS :
3.526 s

PREPROCESS :
7.622 s

NUMPY_STACK :
0.748 s

NUMPY_TO_TORCH :
0.009 s

MODEL_FORWARD :
2606.254 s

TORCH_TO_NUMPY :
0.597 s

FUSION :
2.160 s

MEMMAP_WRITE :
0.743 s

MEMMAP_READ :
0.037 s mapped-view overhead; 3965869744 logical bytes

MEMMAP_FLUSH :
5.353 s

THRESHOLD :
0.058 s

REMOVE_SMALL_OBJECTS :
27.374 s

CONNECTED_COMPONENTS :
31.579 s

POLYGONIZATION :
7.266 s

GEOMETRY_CLEANUP :
0.370 s geometry validation; 3.244 s cleanup/reprojection

STATISTICS :
0.003 s

SERIALIZATION :
0.840 s

CLEANUP :
5.542 s

TOP_1_BOTTLENECK :
MODEL_FORWARD — 2606.254 s (96.077%)

TOP_2_BOTTLENECK :
CONNECTED_COMPONENTS — 31.579 s (1.164%)

TOP_3_BOTTLENECK :
REMOVE_SMALL_OBJECTS — 27.374 s (1.009%)

CANDIDATES :
2411

TOTAL AREA :
506005.1354 m²

OUTPUT EQUIVALENCE :
VALIDATED

OPTIMIZATION APPLIED :
NO

READY_FOR_13I_2_OPTIMIZATION :
YES

NEXT STEP :
13I.2 OPTIMIZE MEASURED BOTTLENECK
```
