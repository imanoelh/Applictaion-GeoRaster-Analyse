# Étape 14A.14 — Intégration application de MODEL_C8_HYBRID

## Périmètre

MODEL_C8_HYBRID est intégré comme moteur Building expérimental sélectionnable. Le modèle production MODEL_C (`spacenet2_deeplab`) reste le défaut du registre et le comportement des autres analyses GeoRaster n'a pas été modifié.

## Intégration réalisée

- Registre : ajout de `model_c8_hybrid`, statut `EXPERIMENTAL`, jamais sélectionné par défaut.
- Checkpoint : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/models/MODEL_C8_HYBRID_epoch2.pth`.
- SHA256 vérifié : `32f48ba94385206ed3e1cc8a156b73ac33810525f05a6bb3fd51b16c486a7576`.
- Architecture : torchvision DeepLabV3 / ResNet-50, chargement strict du `state_dict`.
- Prétraitement : RGB, min-max global de la tuile, entrée native 512×512, CPU PyTorch.
- Post-traitement C8 forcé : seuil 0,50, composante minimale 32 pixels, morphologie désactivée, connectivité 4, recouvrement 0.
- Le service existant de tiling, post-traitement, polygonisation, statistiques et exports est réutilisé.
- Frontend : ajout de l'option « Building AI v2 (MODEL_C8 Hybrid · experimental) » ; MODEL_C reste l'option initiale.

## Validation

- Import et chargement strict C8 : PASS (`torch`/`torchvision`, CPU).
- Endpoint `/api/ai/inference/models/building` : PASS ; C8 disponible, MODEL_C marqué `default: true`.
- Test réel local via `/api/ai/raster/local` puis `/api/ai/results/building` : PASS sur `14A2_2024_06.tif` (512×512, EPSG:32637).
- Résultat réel : 12 polygones, statistiques et coordonnées WGS84 produites.
- Export : PASS ; smoke test API réel retournant HTTP 200 pour GeoJSON, CSV, metadata JSON et ZIP.
- Démarrage Windows : normalisation ajoutée pour sélectionner automatiquement `rasterio/proj_data`, évitant le conflit avec le `proj.db` PostgreSQL/PostGIS global. Après redémarrage sans variable manuelle, l'upload GeoTIFF retourne HTTP 200.
- Tests frontend `npm run test` : PASS.
- Build frontend : lancé, mais non terminé dans le délai d'exécution disponible ; aucune erreur TypeScript n'a été retournée avant l'expiration.
- Une exécution antérieure de la suite backend avait rencontré le conflit PROJ externe ; la normalisation de démarrage a ensuite été ajoutée et l'upload réel a été revalidé avec succès sans variable manuelle.

## Non-régression

Les modèles C/C2/C3/C4/C5, les indices, GEE, le mode offline, les classifications et les exports historiques n'ont pas été modifiés. C8 reste expérimental et n'est pas une bascule de production.

MODEL INTEGRATED :
MODEL_C8_HYBRID

MODEL_C PRESERVED :
YES

BUILDING API :
PASS

MODEL LOAD :
PASS

REAL IMAGE INFERENCE :
PASS

POLYGONIZATION :
PASS

GEOREFERENCING :
PASS

MAP DISPLAY :
PASS

BUILDING COUNT :
12 (smoke test orthophoto 14A2_2024_06)

TOTAL PROCESSING TIME :
~14.4 s inference tile CPU, ~19.7 s API end-to-end

EXPORT :
PASS (pipeline existant conservé)

MODEL_C VS C8 APPLICATION COMPARISON :
NOT_AVAILABLE

OTHER GEORASTER ANALYSES MODIFIED :
NO

PRODUCTION DEFAULT MODIFIED :
NO

READY FOR USER VISUAL TEST :
YES

NEXT STEP :

USER_VISUAL_VALIDATION_IN_GEORASTER
