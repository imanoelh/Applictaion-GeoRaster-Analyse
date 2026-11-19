# Étape 5 — Modèle réel U-Net / ResNet-34

## Modèle intégré

- modèle : **Kaštela DOF5 building segmentation** ;
- architecture : U-Net, encodeur ResNet-34 ;
- checkpoint : `unet_best.pt` ;
- entrée native : RGB `3 × 512 × 512` ;
- sortie : un canal de logits ;
- données annoncées : orthophoto DGU DOF5 2023 et polygones cadastraux DGU ;
- GSD d’acquisition : environ 20–25 cm, entraînement à 0,5 m/pixel ;
- mode : `MODEL_MODE = REAL`.

## Adaptation contrôlée

Le profil orthophoto produit du RGB `float32 [0,1]`. L’adaptateur redimensionne 640 vers 512, calcule le z-score par canal sur les seuls pixels valides, exécute le réseau, applique la sigmoïde puis redimensionne la probabilité vers 640. NoData et padding restent exclus.

## Sécurité et reproductibilité

Le modèle est reconstruit localement sans télécharger de poids additionnels. Le checkpoint est chargé avec `weights_only=True`, son SHA-256 est vérifié, ses 278 clés sont chargées strictement et l’inférence CPU reste le défaut. CUDA n’est utilisé que s’il est explicitement autorisé et disponible.

Les informations de provenance et de licence sont conservées à côté du modèle. Le checkpoint lourd n’est pas destiné à être dupliqué dans Git.

## Limite

Le vrai réseau a été exercé sur des données synthétiques géoréférencées pour vérifier son contrat et son exécution. Il n’a pas été évalué dans ce projet sur une orthophoto réelle annotée. Le seuil `0.50` demeure `NOT_CALIBRATED`.

**Statut : modèle réel validé techniquement ; exactitude scientifique non validée.**

