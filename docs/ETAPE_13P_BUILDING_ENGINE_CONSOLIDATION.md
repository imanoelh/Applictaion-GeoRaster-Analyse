# ÉTAPE 13P — Consolidation des moteurs Building et gel de la baseline

Date : 23 octobre 2026. Copie : Georaster-19-10.

## État constaté et consolidation

Avant 13P, le registry sélectionnait déjà MODEL_C par défaut, mais affichait encore `primary / not scientifically validated`. Son adapter se déclarait `experimental / candidate`. MODEL_E portait le statut experimental et figurait avec MODEL_D PyTorch dans le sélecteur normal. Le descriptif registry ne renseignait pas uniformément moteur, source, préprocessing, seuil et disponibilité. Les résultats des modèles simples n’exposaient pas un temps total ni un statut/moteur communs.

Ces descriptifs sont désormais consolidés dans **`backend/app/ai/config/building_model_catalog.py`**. Les identifiants restent identiques pour préserver la traçabilité et les scripts existants.

| Modèle | model_id | Statut | Moteur par défaut | Usage |
|---|---|---|---|---|
| A | `unet_resnet34` | LEGACY | PyTorch CPU | Référence legacy, sélection explicite API |
| C | `spacenet2_deeplab` | PRODUCTION | ONNX Runtime CPU | Seul moteur standard et défaut |
| D | `whu_unetplusplus_effb4` | EXPERIMENTAL | PyTorch CPU | Référence/debug/équivalence ONNX |
| D_ONNX | `whu_unetplusplus_effb4_onnx` | EXPERIMENTAL | ONNX Runtime CPU | Expérimental optimisé, sélection explicite API |
| E | `hybrid_model_c_model_d` | BENCHMARK_ONLY | Composite C + D | Benchmark/R&D explicite |

Chaque entrée expose model_id/id, display_name/name, architecture, engine, status, model_sources, input_size, threshold, preprocessing et availability. Les cinq moteurs sont disponibles dans l’environnement contrôlé. Le contrôle de disponibilité vérifie les fichiers et les modules installés ; les adapters conservent leurs contrôles stricts de hash et de contrat au chargement.

Les méthodes de registry gardent la sélection explicite. `set_default_model` refuse les moteurs LEGACY, EXPERIMENTAL et BENCHMARK_ONLY. Une ressource D_ONNX manquante retourne `MODEL_FILE_NOT_FOUND` sur sa seule sélection et ne déclenche ni chargement ni remplacement de C. Un C manquant produit aussi son erreur sans basculer vers D/E.

## Interface et résultats

L’interface normale affiche **Standard Building Detection**. Le sélecteur de moteurs R&D a été retiré ; aucun nouveau panneau expérimental n’a été créé. D_ONNX reste accessible explicitement par API. Les types et le parseur frontend reconnaissent aussi son identifiant pour lire correctement ces résultats. La carte, les contrôles de paramètres et le frontend hors Building ne sont pas refactorés.

Les métadonnées de résultat et leur export JSON renseignent désormais nom affiché, architecture, moteur effectivement utilisé, statut, seuil, temps de traitement et hash du checkpoint. Le temps de la route résultat couvre l’analyse complète jusqu’à la construction du résultat, avant l’encodage HTTP. Le statut scientifique reste NOT_VALIDATED. Les noms internes historiques de modèles/versions sont conservés comme identifiants d’artefacts.

Le nom « Experimental High-Recall Detection » ne constitue pas une promesse de supériorité scientifique. Les benchmarks 13M utilisent une Ground Truth approximative/réparée et ne permettent pas de généraliser une supériorité de contours ou de rappel.

## Préservation du pipeline et des données

Les empreintes SHA256 avant/après des cinq artefacts A, C PyTorch, C ONNX, D PyTorch et D ONNX sont identiques. Le fichier MODEL_A et sa configuration sont entièrement inchangés. La comparaison AST confirme que toutes les méthodes des cinq adapters, hors `get_model_info`, restent identiques. Les constantes de statut et les descriptifs des autres moteurs ont été harmonisés.

TilingService, PostProcessingService, BuildingPolygonizationService et le préprocessing de C sont inchangés. Les changements de résultats et d’exports Building ajoutent des métadonnées sans changer les statistiques, les géométries ou leurs algorithmes. Le seul changement dans la route de post-traitement est le libellé du statut E. Les empreintes des sources backend hors AI, incluant GEE/indices/classifications et exports généraux, sont inchangées. Aucun résultat scientifique archivé n’a été recalculé ou remplacé.

Ni full raster, ni benchmark 4096², ni recherche de nouveau modèle, ni fine-tuning n’ont été exécutés. Les services existants 8010/8011 n’ont pas été redémarrés. Les validations API utilisent les vraies routes et services dans une application FastAPI isolée qui importe le code courant ; le nouveau catalogue sera chargé dans un serveur déjà actif lors de son prochain démarrage.

## Smoke tests réels

Entrée inchangée : `benchmark_13M_test/images/GT_2024_industrial_02.tif`, 512 × 512 pixels. Le patch TEST est lu uniquement ; aucune annotation ni aucun split n’est modifié. Un cache propre aux diagnostics 13P reçoit l’upload et le raster préparé.

| Contrôle | MODEL_C | MODEL_D_ONNX |
|---|---|---|
| Sélection | Requête sans model_id | model_id explicite |
| Résultat HTTP | 200 | 200 |
| Runtime retourné | ONNX_RUNTIME_CPU | ONNX_RUNTIME_CPU |
| Statut retourné | PRODUCTION | EXPERIMENTAL |
| Candidats | 2 | 4 |
| Durée de requête observée | 4,916 s | 6,512 s |
| Géométries | Valides, non vides | Valides, non vides |
| GeoJSON/CSV/metadata/ZIP | 4 × HTTP 200 | 4 × HTTP 200 |

Preview : HTTP 200 et signature PNG valide. Le nombre de features correspond aux statistiques et à l’export GeoJSON. Les ZIP contiennent les trois fichiers attendus. Les identités et durées de l’export metadata sont cohérentes avec le résultat. Seuls C et D_ONNX ont été instanciés par ce script. Les deux durées sont des observations de smoke test, pas un benchmark de vitesse ni une comparaison scientifique.

Preuves : `test-data/diagnostics/13P/smoke_validation.json`, résultats JSON, preview et exports associés. La carte interactive n’a pas été revérifiée en 13P.

## Tests et nettoyage

- Backend final complet : **242 passed, 0 failed**, 19 subtests passed, 3022 warnings, **111,84 s**.
- Le premier passage a eu 238 succès et 4 échecs d’assertions sur les anciens libellés de C. Les contrats attendus ont été actualisés pour PRODUCTION/Standard Building Detection, sans altérer leurs vérifications de prédiction ; la suite complète finale est passée.
- Six nouveaux cas de tests couvrent les cinq descriptifs, le défaut unique, le refus de promotion D/D_ONNX/E, l’isolation d’un moteur absent et l’absence de fallback.
- Frontend : tests i18n, AOI et Building réussis ; contrôles ajoutés pour le nom standard et l’absence d’options D/E/D_ONNX dans l’UI normale.
- Builds client et SSR : SUCCESS. Les avertissements de taille de bundle n’empêchent pas les builds.

Audit de nettoyage : les répertoires de benchmarks 13L–13O, checkpoints, Ground Truth, GeoJSON et artefacts scientifiques ont été conservés. Seuls les deux répertoires de scratch créés par les tests 13P (`backend/.pytest-runtime/13P-full-20261023` et `13P-final-20261023`) ont été supprimés après vérification de leurs chemins. Ils contenaient 146 fichiers temporaires, 250 800 654 octets au total. Aucun cache général n’a été purgé. L’inventaire est dans `cleanup_audit.json`.

## Baseline figée et priorité

Documents créés : `BUILDING_AI_MODEL_STATUS.md`, `BUILDING_AI_PRODUCTION_BASELINE_13P.md` et le présent rapport. Le manifeste `test-data/diagnostics/13P/freeze_manifest.json` archive les hashes du code et des poids, les contrôles et l’environnement. La racine ne contient pas de dépôt Git ; aucun Git n’a été modifié.

Les références de performance restent : C ~26 min (historique), D 60,98 min sur full raster (13N.3), D_ONNX 36,39 min sur full raster (13O.1), E ~22 min 55 s sur 4096² (13N.2). Aucune promotion D/D_ONNX/E n’est décidée.

La priorité retenue est **MODEL_C QUALITY IMPROVEMENT** : consolider la Ground Truth et mesurer les limites de contours du moteur standard avant une nouvelle modification. Ce rapport ne démarre pas cette étape.

MODEL_A STATUS :
LEGACY

MODEL_C STATUS :
PRODUCTION

MODEL_C DEFAULT :
YES

MODEL_D STATUS :
EXPERIMENTAL

MODEL_D_ONNX STATUS :
EXPERIMENTAL

MODEL_E STATUS :
BENCHMARK_ONLY

STANDARD USER ENGINE :
MODEL_C

EXPERIMENTAL HIGH-RECALL ENGINE :
MODEL_D_ONNX

MODEL_C FULL RASTER REFERENCE :
~26 min

MODEL_D PYTORCH FULL RASTER :
60.98 min

MODEL_D_ONNX FULL RASTER :
36.39 min

MODEL_E :
NOT RECOMMENDED FOR NORMAL USE

BACKEND TESTS :
242 PASSED / 0 FAILED

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS

MODEL_C SMOKE TEST :
SUCCESS

MODEL_D_ONNX SMOKE TEST :
SUCCESS

GENERAL NON-REGRESSION :
VALIDATED

PRODUCTION BASELINE :
FROZEN

NEXT R&D PRIORITY :
MODEL_C QUALITY IMPROVEMENT
