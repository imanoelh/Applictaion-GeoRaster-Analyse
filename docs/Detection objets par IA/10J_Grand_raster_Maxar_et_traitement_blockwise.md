# Étape 10J — Grand raster Maxar et traitement blockwise

## Diagnostic

Le raster préparé observé dans le frontend mesure `10292 × 9378`, soit `96 518 376` pixels. La configuration historique était `AI_POSTPROCESS_MAX_GLOBAL_PIXELS=25 000 000`. Avant cette correction, `PostProcessingService.process()` levait immédiatement `POSTPROCESSING_RASTER_TOO_LARGE` avant la fusion des tuiles. L’échec se situait donc en **POSTPROCESSING**, et non dans le tiling, le modèle ou la polygonisation.

À 96 518 376 pixels, un tableau `float32` vaut environ 386 MiB. Les deux accumulateurs de fusion représentaient déjà environ 772 MiB, auxquels s’ajoutaient les masques et buffers de nettoyage.

## Correction

- Le seuil historique reste la frontière de stratégie, il n’est pas augmenté arbitrairement.
- `pixel_count <= limite` conserve exactement le chemin mémoire existant.
- Au-delà, `probability_sum`, `weight_sum`, `valid_mask` et le masque binaire sont créés en `numpy.memmap` dans un répertoire temporaire.
- Les contributions des tuiles gardent la formule existante : `Pglobal = sum(probabilities) / sum(weights)`.
- Le seuil est appliqué par fenêtres de 1024 lignes.
- Les composants sont calculés sur le masque global disk-backed : les objets traversant une frontière de fenêtre ne sont donc pas coupés.
- Les routes post-processing et vectorisation libèrent les fichiers temporaires après succès; le mode STANDARD et le checkpoint restent inchangés.

## Vérifications

- Test synthétique `5001 × 5001` (>25 M pixels) : traitement disk-backed et nettoyage validés.
- Comparaison petit raster mémoire/memmap : probabilités et masque identiques.
- Tests post-processing : `12 passed`.
- Backend complet : `214 passed, 0 failed` dans l’environnement de test local.
- Frontend tests : succès.
- Frontend client + SSR build : succès.
- Backend relancé sur `127.0.0.1:8010`; frontend existant sur `127.0.0.1:5183`.

## Limites de validation terrain

Les COG Maxar originaux 2024/2025 et le `raster_id` de la session frontend ne sont pas présents dans le workspace; le parcours original Maxar n’a donc pas pu être rejoué ici. Les dérivés RGB locaux 2024/2025 disponibles sont des extraits `2048 × 2048`, et ne testent pas le cas 96 M pixels. La continuité géométrique a été vérifiée par le traitement global du masque, mais une exécution terrain complète reste nécessaire avec le fichier original.

## Statut

BUILDING ANALYSIS FAILURE — ROOT CAUSE :
`POSTPROCESSING_RASTER_TOO_LARGE` levé par la limite `AI_POSTPROCESS_MAX_GLOBAL_PIXELS=25 000 000` avant la fusion globale.

RASTER SIZE :
10292 × 9378

PIXEL COUNT :
96 518 376

GLOBAL PIXEL LIMIT :
25 000 000 (seuil de sélection de stratégie)

FAILURE STAGE :
POSTPROCESSING

LARGE RASTER PROCESSING :
VALIDÉ

BLOCKWISE PROBABILITY FUSION :
VALIDÉE

BOUNDARY CONTINUITY :
VALIDÉE

2025 ORIGINAL MAXAR END-TO-END :
ÉCHEC

2024 ORIGINAL MAXAR END-TO-END :
NON TESTÉ

STANDARD MODEL :
INCHANGÉ

BACKEND REGRESSION :
AUCUNE

FRONTEND BUILD :
SUCCESS
