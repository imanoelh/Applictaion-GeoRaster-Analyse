# ÉTAPE 13Q — New Building Model Discovery and Fast Candidate Screening

## Périmètre et protection

Le screening est isolé sous `backend/data/models/building/experimental/benchmark_13Q/`. Aucun fichier de production n'a été modifié : MODEL_C reste le défaut, MODEL_D/MODEL_E restent expérimentaux, et ni le registre, ni les adapters, ni le frontend, ni les rasters TEST n'ont été changés. Aucun traitement 4096²/full-raster n'a été lancé.

## Découverte

| Candidat | Architecture / données | Licence annoncée | Poids | Décision de screening |
|---|---|---|---|---|
| MODEL_F | SegFormer, SpaceNet 2 Paris, RGB 512², masque binaire | MIT | `Abhatta7/building-footprint-segmentation/best_segformer.pth` | **Non exécuté** : poids absents localement; téléchargement bloqué par l'accès réseau de l'environnement |
| MODEL_G | DINOv3 ViT-S/16 + UPerNet, HOTOSM VHR, ONNX RGB→probabilité | CC-BY-4.0 + licence DINOv3 | `hotosm/dinov3s-buildings/model.onnx` | **Non exécuté** : poids absents localement; téléchargement bloqué |
| MODEL_H | U-Net ResNet34 SMP, tête instance 3 canaux, HOTOSM VHR | AGPL-3.0 | `benchmark_13L/hotosm_unet_instance/unet_bldg_instance.pth` | **Techniquement chargé strictement**; expérimental seulement |

Les fiches sources confirment pour MODEL_F les poids SegFormer et le jeu SpaceNet 2, et pour MODEL_G un graphe ONNX autonome avec fenêtre 256/stride 192 et sortie de probabilité bâtiment : [MODEL_F](https://huggingface.co/Abhatta7/building-footprint-segmentation), [MODEL_G](https://huggingface.co/hotosm/dinov3s-buildings). Ces informations ne remplacent pas un chargement local.

## Validation MODEL_H

- SHA256 : `99AA91E1...EF25DB7E1D` (artefact local déjà validé dans 13L).
- `load_state_dict(strict=True)` : succès; chargement mesuré `1.091 s`.
- Prétraitement : RGB `/255`, fenêtres natives 256×256, 4 fenêtres pour un patch 512×512.
- Sortie : `(1, 3, 256, 256)`; canal 0 utilisé comme probabilité bâtiment après sigmoid dans le benchmark antérieur.
- Smoke réel sur `GT_2024_difficult_02` : `1.139 s` pour quatre fenêtres CPU.
- Sorties probability/binary/polygons/overlays déjà présentes pour les 16 patches dans `benchmark_13L`; elles ont été réutilisées en lecture seule.

## Comparaison exploratoire sur les six patches 13M

Les masques GT réparés de `qa_13M1A` ont été utilisés uniquement pour une comparaison exploratoire. Ils restent une vérité terrain approximative et le split TEST reste verrouillé.

| Moteur | IoU | Dice/F1 | Précision | Rappel | Interprétation |
|---|---:|---:|---:|---:|---|
| MODEL_C | 0.303 | 0.465 | 0.585 | 0.386 | baseline plus prudente |
| MODEL_H | 0.439 | 0.610 | 0.491 | 0.807 | couverture supérieure, davantage de pixels positifs |

Les mesures objet et Boundary F1 n'ont pas été recalculées pour H dans cet environnement minimal; aucun classement de contours ni de faux positifs objet ne doit être déduit de ces seuls scores pixel. Les résultats C/D publiés en 13M.1B restent séparés et ne constituent pas une validation de H.

## Rejets et limites

- MODEL_F et MODEL_G restent des candidats documentés mais **non techniquement validés** tant que leurs poids ne sont pas disponibles dans l'environnement isolé.
- Aucun install de `transformers`, `terratorch` ou dépendance de production n'a été fait.
- Aucun candidat n'a été ajouté au ModelRegistry et aucune bascule de production n'a eu lieu.
- Le rapport ne recommande pas de remplacement sur ce run : la licence AGPL de MODEL_H et l'absence de validation complète F/G imposent une étape finalist séparée.

## Conclusion

CANDIDATES FOUND :
MODEL_F SegFormer; MODEL_G DINOv3-S/16 + UPerNet; MODEL_H HOTOSM U-Net ResNet34 instance

CANDIDATES TECHNICALLY VALID :
MODEL_H (strict local load and one real 512×512 smoke); MODEL_F/MODEL_G NOT_RUN_WEIGHTS_MISSING

MODEL_F :
NOT_RUN — WEIGHTS MISSING / NETWORK BLOCKED

MODEL_G :
NOT_RUN — WEIGHTS MISSING / NETWORK BLOCKED

MODEL_H :
VALIDATED LOCAL EXPERIMENTAL — AGPL-3.0

MODEL_C BASELINE :
PRODUCTION

BEST SMALL BUILDINGS :
NOT DETERMINED IN THIS SCREEN (H has higher recall, object ranking not completed)

BEST LARGE BUILDINGS :
NOT DETERMINED

BEST DENSE URBAN :
NOT DETERMINED

BEST BUILDING SEPARATION :
NOT DETERMINED

BEST BOUNDARY QUALITY :
NOT DETERMINED

LOWEST APPARENT FALSE POSITIVES :
MODEL_C (higher precision in the six-patch exploratory pixel comparison)

BEST IOU :
MODEL_H — 0.439 exploratory

BEST RECALL :
MODEL_H — 0.807 exploratory

BEST PRECISION :
MODEL_C — 0.585 exploratory

BEST OBJECT DETECTION :
NOT DETERMINED

FINALISTS :
NONE — complete finalist benchmark requires local MODEL_F/MODEL_G weights and object/boundary metrics

REJECTED :
MODEL_F and MODEL_G for this run only (weights unavailable); no quality rejection of the architectures

FULL RASTER :
NOT_RUN

PRODUCTION MODIFIED :
NO

MODEL_C :
DEFAULT UNCHANGED

NEXT STEP :
13Q.1 FINALIST DEEP BENCHMARK
