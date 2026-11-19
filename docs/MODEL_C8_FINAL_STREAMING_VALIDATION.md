# MODEL_C8_HYBRID — validation finale du streaming

## Réponses factuelles

1. **GeoTIFF complet en RAM pendant l’inférence : NON.** Le chemin C8 passe par
   `TilingService.iter_tiles`; `PreprocessingService.preprocess_window` appelle
   `dataset.read(..., window=window, masked=True)` pour une seule fenêtre.
   Le `dataset.read(out_shape=...)` de `preview.png` est un chemin d’aperçu,
   pas l’inférence.
2. **Fenêtres 512×512 : OUI.** `Window(col_offset, row_offset, valid_width,
   valid_height)` est créé pour chaque tuile et transmis à Rasterio.
3. **Image RGB H×W×3 conservée : NON.** Seules `source_rgb`, `image` et
   `valid_mask` de la tuile courante existent; la génératrice libère la tuile
   précédente avant la suivante.
4. **Probabilités float32 H×W en RAM : NON pour 10 000×9 000.** Au-delà de
   `AI_POSTPROCESS_MAX_GLOBAL_PIXELS` (25 M par défaut), `probability_sum` et
   `weight_sum` sont des `numpy.memmap`. Pour un petit raster sous ce seuil,
   ils restent volontairement en RAM.
5. **Toutes les tuiles/logits accumulés : NON.** `preferred_batch_size=1` pour
   C8; un seul output est fusionné puis relâché avant la fenêtre suivante.
6. **Masque final : uint8.** Pour les grands rasters, il est écrit par lignes
   dans `binary.u8` memmap; aucune conversion bool→uint8 H×W en RAM n’est faite.
7. **Buffers :** les buffers de tuile sont recréés pour chaque fenêtre, ce qui
   est le comportement streaming attendu; les accumulateurs globaux sont
   réutilisés et disk-backed pour les grands rasters.

## Preuves de code

- Lecture windowed : `backend/app/ai/services/preprocessing_service.py:93`.
- Création/émission des tuiles : `backend/app/ai/services/tiling_service.py:82-107`.
- Global min/max C8 également parcouru par fenêtres :
  `backend/app/ai/models/spacenet2_deeplab_adapter.py:223-225`.
- Accumulateurs memmap : `backend/app/ai/services/postprocessing_service.py:202-218`.
- Masque uint8 disk-backed : `backend/app/ai/services/postprocessing_service.py:315-326`.
- Batch 1 et `torch.inference_mode()` :
  `backend/app/ai/models/c8_hybrid_building_adapter.py:23` et
  `backend/app/ai/models/spacenet2_deeplab_adapter.py:119`.

## Tests exécutés

- Smoke test checkpoint C8 réel, CPU, tuile 512×512 : PASS.
- Tests disk-backed/masque final : 2 PASS.
- Tests IA ciblés : 25 PASS.
- Un GeoTIFF local 10 662×9 715 est présent et a été inspecté. Le benchmark
  complet C8 de cette image n’a pas été mené à terme dans l’environnement de
  validation local : le pré-scan global min/max et les centaines de forwards
  CPU dépassent la fenêtre d’exécution disponible. Il n’est donc pas honnête
  de fournir une RAM RSS maximale, un temps total ou une comparaison de nombre
  de bâtiments comme s’ils avaient été mesurés.

## Verdict

La preuve statique et les tests ciblés confirment un pipeline C8 windowed,
streaming par tuile, batch 1, avec fusion memmap. Le redéploiement VPS peut être
préparé, mais le GO opérationnel définitif reste conditionné à un run complet
sur le VPS (même GeoTIFF) avec mesure RSS/swap et comparaison de masque.
