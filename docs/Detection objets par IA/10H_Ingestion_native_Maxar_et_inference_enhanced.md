# Étape 10H — Ingestion native Maxar et inférence expérimentale

Date : 14 octobre 2026

## Résultat

Le workflow RGB standard reste inchangé. Un second workflow explicite est maintenant disponible pour les fichiers Maxar Multi-8 volumineux : upload resumable par chunks, détection prudente du profil, conversion streaming RGB 5/3/2 en `uint8` avec stretch p2-p98 par canal, puis réutilisation du pipeline `LocalRasterSource` → tuilage → modèle → post-traitement → polygonisation → résultats.

Le fichier original n’est jamais chargé entièrement en RAM. Le COG source est écrit progressivement dans un fichier temporaire isolé. La conversion lit et écrit par fenêtres Rasterio.

## Architecture d’upload

- Endpoint d’initialisation : `POST /api/ai/raster/local/maxar/init`.
- Chunks séquentiels : `POST /api/ai/raster/local/maxar/{upload_id}/chunk`.
- Finalisation atomique et préparation : `POST /api/ai/raster/local/maxar/{upload_id}/complete`.
- Chunk par défaut : 16 MiB, configurable par `AI_MAXAR_UPLOAD_CHUNK_BYTES`.
- Limite Maxar dédiée : 4 GiB par défaut, configurable par `AI_MAXAR_MAX_UPLOAD_BYTES`.
- Limite historique RGB standard : 512 MiB, inchangée.
- Nettoyage des fichiers `.part` et de l’état d’upload après finalisation ou erreur de validation.
- Identifiants et noms de fichiers contrôlés ; aucun chemin serveur n’est exposé.

## Profil et conversion

Le profil `maxar_multispectral_p2p98_v1` exige simultanément 8 bandes `uint16`, un CRS/géoréférencement valide et des indices Maxar compatibles dans le nom ou les métadonnées. Un TIFF 8 bandes arbitraire n’est pas accepté automatiquement.

Mapping confirmé pour les produits testés : R=5, G=3, B=2 (indices Rasterio 1-based). Les percentiles sont estimés par lecture décimée, puis chaque fenêtre est convertie avec ses bornes p2-p98. Le dérivé conserve CRS, transform, résolution, emprise et NoData. Le dérivé est ensuite traité par le contrat RGB existant ; aucun moteur Building parallèle n’a été créé.

Le cache dérivé est déterministe par hash source + version de profil. Les métadonnées de réponse signalent `input_source_profile`, le mapping 5/3/2, le stretch et `automatic_preparation=true`. L’interface affiche « Maxar multispectral detected · Preparing RGB input automatically » lorsque la préparation est terminée et expose une progression Uploading / Preparing RGB.

## Tests effectués

- Profil Maxar : identification, mapping, stretch, dtype, ColorInterp, conservation du géoréférencement : validé.
- API chunks : deux chunks, ordre séquentiel, assemblage et conversion RGB : validé sur un COG Maxar synthétique contrôlé.
- Import RGB uint8 historique : conservé.
- Backend : `212 passed, 0 failed`.
- Frontend tests : SUCCESS.
- Build client : SUCCESS.
- Build SSR : SUCCESS.

Les COG originaux Maxar 2024/2025 de 1,46 Go/1,32 Go ne sont pas présents dans le workspace courant ; leur upload navigateur réel n’a donc pas été certifié dans cette session. Le test API complet a utilisé le même contrat et le même chemin de chunks avec un COG synthétique 8 bandes. Aucun seuil, modèle de production, GEE, analyse historique ou export historique n’a été changé.

## Inférence améliorée

Aucun TTA ni multi-scale n’a été promu ou activé dans la production. La réponse modèle reste donc l’inférence standard `unet_best.pt`, avec le threshold 0,50. La raison est double : absence de ground truth et absence des COG originaux disponibles pour comparer proprement temps, mémoire, pixels positifs, fragmentation et candidats.

Les résultats précédents restent la référence non scientifique : 2024 = 13 candidats / 5 217 pixels positifs ; 2025 = 22 candidats / 7 193 pixels positifs. Aucun chiffre « après » n’est déclaré et aucune précision/rappel/F1/IoU n’est calculée.

## Modifications principales

- `backend/app/ai/services/maxar_multispectral_profile.py`
- `backend/app/ai/services/ai_raster_service.py`
- `backend/app/ai/api/ai_raster_routes.py`
- `backend/tests/test_maxar_native_ingest.py`
- `frontend/src/lib/georaster-api.ts`
- `frontend/src/features/ai-building/model.ts`
- `frontend/src/features/ai-building/BuildingDetectionPanel.tsx`
- `frontend/src/routes/map.tsx`

## MAXAR NATIVE INGESTION :
PARTIELLE

2024 ORIGINAL UPLOAD :
ÉCHEC — fichier original indisponible pour test end-to-end navigateur

2025 ORIGINAL UPLOAD :
ÉCHEC — fichier original indisponible pour test end-to-end navigateur

MANUAL RGB CONVERSION REQUIRED :
NON

MAXAR RGB PREPARATION :
AUTOMATIQUE

STANDARD INFERENCE :
VALIDÉE

TTA INFERENCE :
NON RETENUE

MULTISCALE INFERENCE :
NON RETENUE

MODEL CHECKPOINT :
INCHANGÉ

GROUND TRUTH :
ABSENT

SCIENTIFIC ACCURACY :
NON VALIDÉE

BACKEND REGRESSION :
AUCUNE

FRONTEND BUILD :
SUCCESS
