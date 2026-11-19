# Building AI — baseline production 13P

Date : **2026-10-23**. Copie : **Georaster-19-10/Georaster-19-10**.

Baseline documentaire figée après consolidation et contrôles : **FROZEN**. Aucun dépôt `.git` n’est présent à la racine ; aucune initialisation Git, aucun commit et aucun push n’ont été effectués.

## Configuration retenue

- Défaut backend/API/frontend : `spacenet2_deeplab` (**MODEL_C**, PRODUCTION).
- Moteur standard : ONNX Runtime CPU ; seuil 0,50 ; tuiles 512 px ; recouvrement frontend 0,20 préservé ; profil `full_raster_global_rgb_minmax_v1`.
- Paramètres de post-traitement frontend conservés : minimum objet 4 pixels, maximum trous 0, aucune ouverture/fermeture, noyau 3, une itération.
- Tiling, fusion, seuillage, polygonisation, statistiques et géométries inchangés. Les modifications des résultats/exports Building portent sur les métadonnées descriptives et le temps de traitement.
- A : LEGACY ; D et D_ONNX : EXPERIMENTAL ; E : BENCHMARK_ONLY. Aucun de ces moteurs ne peut devenir le défaut via `set_default_model`.
- Interface normale : uniquement Standard Building Detection. Sélection des moteurs de référence/R&D explicite par API.

Le catalogue exécuté et les métadonnées de disponibilité figurent dans `test-data/diagnostics/13P/smoke_validation.json`. La disponibilité a été vérifiée pour les cinq moteurs sans les charger tous. Les smoke tests n’ont instancié que C et D_ONNX.

## Empreintes des artefacts conservés

| Artefact | Taille en octets | SHA256 |
|---|---:|---|
| A `unet_best.pt` | 97919546 | `6cd2467e063696e9d41d409bda7751a9ccdb057d5adba251ab5a765d8d415987` |
| C `best_deeplab.pth` | 168357171 | `170c49e1f42737f5a4b3922b9fc58b25b6ba0a7dd7bf00b9186a92ccb84dc555` |
| C ONNX | 158461253 | `94661ded0bc79bbca99c03d55d817bcb7369d46eb13d7983ebf6ae711003fd45` |
| D `model.pth` | 84027346 | `922af7c96c0dc44256ab8b4d1a071f2151e0a921c997af80b55bb766bcc30dc6` |
| D_ONNX `model.onnx` | 80031737 | `62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6` |

Les cinq empreintes sont identiques avant/après 13P. E réutilise C et D ; il n’a pas de nouveau checkpoint.

## Environnement et reproductibilité

Python utilisé : `backend/.venv/Scripts/python.exe`, **3.12.10**. PyTorch 2.8.0 ; Torchvision 0.23.0 ; ONNX Runtime 1.22.1 ; Rasterio 1.5.2 ; Affine 3.0.1 ; SMP 0.5.0 ; NumPy 2.5.4.

Les contrôles backend utilisent `PROJ_LIB`/`PROJ_DATA` vers `backend/.venv/Lib/site-packages/rasterio/proj_data` et `GDAL_DATA` vers son `gdal_data`. L’environnement complet, les empreintes du code et les contrôles sont archivés dans :

- `test-data/diagnostics/13P/environment.json`
- `test-data/diagnostics/13P/before.json` et `source_before/`
- `test-data/diagnostics/13P/non_regression.json`
- `test-data/diagnostics/13P/freeze_manifest.json`

Le manifeste fige les sources contrôlées, les cinq poids et les résultats de validation. Il ne fige pas les credentials ni les processus déjà en mémoire. Les services existants sur 8010/8011 n’ont pas été redémarrés ; le nouveau catalogue sera chargé au prochain démarrage du backend. Les smoke tests chargent le code courant dans une application FastAPI isolée avec les vraies routes et les vrais services.

## Validation finale

| Contrôle | Résultat |
|---|---|
| Backend complet | **242 passed, 0 failed**, 19 subtests passed ; 111,84 s |
| Frontend `npm.cmd test` | SUCCESS — i18n, import AOI, Building |
| Build Vite client | SUCCESS — 23,27 s |
| Build Vite SSR | SUCCESS — 17,94 s |
| C, patch réel 512², requête sans model_id | HTTP 200, 2 candidats, ONNX_RUNTIME_CPU, PRODUCTION |
| D_ONNX, même patch, sélection explicite | HTTP 200, 4 candidats, ONNX_RUNTIME_CPU, EXPERIMENTAL |
| Preview | HTTP 200, PNG valide |
| GeoJSON/CSV/metadata/ZIP | HTTP 200 pour les deux moteurs |
| Géométries des smoke tests | Valides et non vides |
| Isolation des ressources absentes | Testée ; erreur explicite, aucune bascule vers un autre moteur |
| Méthodes adapters hors get_model_info | AST identique avant/après pour les cinq adapters |
| Sources générales hors Building | Empreintes identiques |

Ces smoke tests vérifient l’intégration et les contrats, pas la précision scientifique. Aucun nouveau full raster n’a été lancé en 13P. Les tests de la suite existante peuvent exercer PyTorch sur de petites entrées ; aucun benchmark lourd D/E n’a été relancé.

## Limites connues et références

- C : limites de contours/bâtiments manqués ; environ 26 min sur le raster complet historique, non remesurées ici.
- D : 60,98 min sur le full raster (13N.3).
- D_ONNX : 36,39 min sur le full raster, 7313 candidats, classe SLOW ; garde son statut expérimental (13O.1).
- E : environ 22 min 55 s sur 4096² ; non recommandé en usage normal (13N.2).
- GT 13M approximative/réparée ; aucun score scientifique officiel ajouté.
- Carte interactive et authentification GEE non revérifiées en 13P. La validation générale 13P porte sur les tests et l’intégrité des sources, pas sur un nouveau contrôle externe GEE.
- 3022 avertissements backend existants ; avertissement de taille des bundles client. Ils n’ont pas provoqué d’échec.

Priorité R&D retenue : **MODEL_C QUALITY IMPROVEMENT**, avec une GT humaine plus fiable pour mesurer les contours avant toute nouvelle modification du moteur standard. Cette étape 13P n’exécute ni fine-tuning ni recherche de nouveaux poids.
