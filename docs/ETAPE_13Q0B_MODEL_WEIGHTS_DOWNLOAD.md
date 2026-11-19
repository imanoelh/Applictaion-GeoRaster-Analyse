# ÉTAPE 13Q.0B — Automatic Download of MODEL_F and MODEL_G Weights

## Résultat

Les deux poids ont été téléchargés dans l'espace expérimental isolé :

| Modèle | Fichier | Taille | SHA256 | Vérification |
|---|---|---:|---|---|
| MODEL_F | `benchmark_13Q0B/model_f_segformer/best_segformer.pth` | 14,948,025 octets | `10487CC6C8C32FA998605543C203EB00E3B3B5D70664515B246CFB2883AC13A1` | checkpoint PyTorch lisible |
| MODEL_G | `benchmark_13Q0B/model_g_dinov3s/model.onnx` | 219,574,600 octets | `9A28E28403ACCC06C70A3104AEDB31ECA50401ED23C8BA4314B26357C25E9043` | ONNX Runtime CPU chargeable |

Les URLs utilisées sont les artefacts publiés par [Abhatta7/building-footprint-segmentation](https://huggingface.co/Abhatta7/building-footprint-segmentation) et [hotosm/dinov3s-buildings](https://huggingface.co/hotosm/dinov3s-buildings). La fiche MODEL_F décrit SegFormer, SpaceNet 2 et des patches 512×512; la fiche MODEL_G décrit un graphe ONNX RGB pour la probabilité bâtiment avec fenêtres 256 et seuil par défaut 0,4371.

## Contrôles techniques

### MODEL_F

- `torch.load(..., weights_only=True)` : succès.
- Type : `OrderedDict`.
- 208 tenseurs.
- Clés SegFormer présentes : `model.segformer.encoder.*`, `model.decode_head.*`.
- Tête finale : `model.decode_head.classifier.weight` de forme `(1,256,1,1)` : sortie binaire à logit unique.
- Le paquet `transformers` n'est pas installé dans `backend/.venv`; aucune dépendance de production n'a été installée. L'inférence F reste à faire dans l'environnement expérimental approprié.

### MODEL_G

- `onnxruntime.InferenceSession` CPU : succès.
- Entrée : `image`, `[1,3,256,256]`, `float32`.
- Sortie : `logits`, `[1,3,256,256]`, `float32`.
- Smoke test réel sur une fenêtre du patch `GT_2024_difficult_02` : sortie finie, min `-6.0181`, max `4.7977`.
- Le graphe expose trois canaux logits; le canal bâtiment exact doit être confirmé avec la documentation/inférence officielle avant toute métrique comparative. Il n'a donc pas été injecté dans le pipeline GeoRaster.

## Protection

- MODEL_A, MODEL_C, MODEL_D et MODEL_E inchangés.
- ModelRegistry, adapters, PostProcessing, polygonisation, statistiques, exports et frontend inchangés.
- Aucun modèle n'a été placé dans un chemin de production.
- Aucun full raster et aucun fine-tuning exécutés.

## Reprise

L'étape suivante est 13Q.1 : construire l'adapter expérimental F et le wrapper G, confirmer preprocessing et canal bâtiment, puis lancer le benchmark profond sur les six patches TEST.

DOWNLOAD STATUS :
COMPLETE

MODEL_F WEIGHTS :
DOWNLOADED / HASH VALIDATED

MODEL_G WEIGHTS :
DOWNLOADED / HASH VALIDATED

MODEL_F CHECKPOINT :
STRUCTURALLY VALIDATED — INFERENCE NOT RUN

MODEL_G ONNX :
LOADED AND SMOKE VALIDATED

PRODUCTION MODIFIED :
NO

MODEL_C :
DEFAULT UNCHANGED

NEXT STEP :
13Q.1 FINALIST DEEP BENCHMARK
