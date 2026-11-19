# Étape 3 — Inférence Building

## Objectif

Introduire un moteur d’inférence générique et un adaptateur Building, indépendants de la source raster et du futur post-traitement.

## Chaîne technique

```text
PreparedTile
→ InferenceService
→ ModelRegistry["building"]
→ BuildingModelAdapter
→ tenseur PyTorch NCHW
→ probability_map
→ seuil
→ binary_mask
→ TilePrediction
```

`BaseModelAdapter` sépare GeoRaster du runtime du modèle. `InferenceService.iter_predictions` consomme et produit des générateurs : il n’accumule pas toutes les tuiles. Le registre charge une seule instance du modèle, à la première tuile valide.

L’exécution utilise `eval()` et `torch.inference_mode()`. Une sortie en logits reçoit une sigmoïde afin d’obtenir des probabilités dans `[0,1]`. Le NoData et le padding sont forcés à zéro après inférence.

## Contrats et erreurs

L’API technique est :

```http
POST /api/ai/inference/building
```

Elle renvoie les métadonnées du modèle, les nombres de tuiles, des agrégats et les temps, mais aucune matrice lourde. Un modèle absent ou invalide produit une erreur métier explicite ; aucune prédiction fictive n’est générée en production.

## Interprétation

Le seuil `0.50` est un seuil technique initial. Il n’est ni une mesure d’accuracy, ni une confiance globale, ni une calibration scientifique. Une carte de probabilités exprime la réponse du modèle par pixel ; elle ne compte pas directement les bâtiments.

**Statut : validée techniquement ; seuil non calibré.**

