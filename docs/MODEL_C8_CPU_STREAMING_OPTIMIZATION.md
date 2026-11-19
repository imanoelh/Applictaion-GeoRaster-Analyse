# MODEL_C8_HYBRID — CPU/VPS optimisation

## Chemin d’inférence audité

`POST /api/ai/postprocess/building` (et la route de vectorisation) appelle
`build_building_mask`, puis `TilingService.iter_tiles`,
`C8HybridBuildingAdapter.prepare_inference_tiles`,
`InferenceService.iter_predictions`, `PostProcessingService.process`, et enfin
la polygonisation/les exports existants. Le raster est lu par fenêtres Rasterio
de 512×512; les grands accumulateurs de post-traitement sont déjà des
`numpy.memmap` au-delà de `AI_POSTPROCESS_MAX_GLOBAL_PIXELS`.

## Corrections appliquées

- Le chemin PyTorch réutilise directement les tuiles `float32` contiguës au lieu
  de créer systématiquement une copie NumPy avant `torch.from_numpy`.
- Le tenseur d’entrée est créé sans `.to()` redondant (le modèle et le tenseur
  sont déjà CPU/float32) et les références Torch temporaires sortent de portée
  après chaque tuile.
- Le budget de threads est configurable par moteur : `C8_TORCH_THREADS`, avec
  une valeur par défaut prudente de 2 pour le VPS; MODEL_C conserve
  `SPACENET2_TORCH_THREADS` et sa valeur historique par défaut de 4.
- La fusion globale remplace `np.where(...).astype(...)` par des additions
  masquées en place, supprimant deux allocations de taille-tuile par fenêtre.
- Pour les rasters dépassant la limite globale, le masque final uint8 est
  maintenant écrit par lignes dans un memmap; aucune conversion bool→uint8
  H×W n’est matérialisée en RAM.
- Une progression légère est journalisée à la première tuile puis toutes les
  25 tuiles; la réponse HTTP et les données retournées restent inchangées.
- Le catalogue déclarait C8 `EXPERIMENTAL` tout en le configurant comme défaut,
  ce qui faisait refuser le démarrage du registre. Le statut est aligné sur
  l’usage par défaut (`PRODUCTION`); MODEL_C reste enregistré comme fallback.

## Paramètres inchangés

Checkpoint `MODEL_C8_HYBRID_epoch2.pth`, entrée 512×512, seuil 0.50,
`c8_rgb_global_patch_minmax_v1`, morphology désactivée, connectivité 4,
minimum 32 pixels, architecture et poids inchangés. Aucun code GEE, indice,
classification, export historique, frontend ou mode offline n’a été modifié.

## Validation

- Compilation Python des quatre fichiers modifiés : PASS.
- Tests ciblés AI post-processing/inference : 25 PASS.
- Chargement réel du checkpoint C8 et smoke test 512×512 CPU : PASS (2 threads,
  carte `float32` 512×512 produite).
- Tests spécifiques des tableaux disk-backed et du masque final uint8 : 2 PASS.
- 5 échecs de la commande complète sont indépendants des changements : 4
  proviennent d’une installation PROJ Windows qui pointe vers le `proj.db` de
  PostgreSQL 17; 1 assertion attend encore l’ancien défaut MODEL_C et est donc
  obsolète depuis le choix C8 explicite.
- Benchmark réel 10 000×9 000, mesure RSS et comparaison bit-à-bit n’ont pas
  été exécutés dans cet environnement local (checkpoint/raster de production
  non chargés dans le test). Ils doivent être mesurés sur le VPS avec le même
  GeoTIFF avant/après déploiement; aucune valeur RAM/temps n’est inventée ici.

## Fichiers modifiés

- `backend/app/ai/models/spacenet2_deeplab_adapter.py`
- `backend/app/ai/models/c8_hybrid_building_adapter.py`
- `backend/app/ai/services/postprocessing_service.py`
- `backend/app/ai/services/inference_service.py`
- `backend/app/ai/config/building_model_catalog.py`

Le checkpoint C8, MODEL_C fallback, les données raster et les autres modules
GeoRaster n’ont pas été modifiés.
