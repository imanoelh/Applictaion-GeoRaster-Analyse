# ÉTAPE 13Q.1 — Final Building Footprint Model Deep Benchmark

## Statut d'exécution

Le benchmark profond a été préparé dans `backend/data/models/building/experimental/benchmark_13Q1/` avec une comparaison reproductible sur les six patches TEST 13M, seuils 0,30 à 0,70, masques binaires, overlays et métriques pixel.

La sélection finale est **bloquée** :

- MODEL_F (SegFormer) : poids `best_segformer.pth` non présents localement;
- MODEL_G (DINOv3-S + UPerNet ONNX) : poids `model.onnx` non présents localement;
- MODEL_H (HOTOSM U-Net ResNet34) : poids locaux strictement chargeables, mais licence AGPL-3.0 et sorties historiques 13L non suffisantes pour le benchmark final complet F/G/H.

L'accès réseau direct aux dépôts de poids était indisponible. Aucun téléchargement partiel, aucune dépendance de production et aucune modification métier n'ont été effectués.

## Ce qui a été vérifié

- MODEL_C reste inchangé et reste le défaut de production.
- MODEL_H : `load_state_dict(strict=True)` réussi; smoke CPU 512×512 réussi; sortie `(1,3,256,256)` avec RGB `/255`.
- Six masques GT réparés ont été lus sans modification.
- Le script a produit une grille de seuils et des overlays comparatifs dans `benchmark_13Q1/`.
- Aucun raster complet ni benchmark 4096² n'a été lancé.
- Aucun candidat n'a été ajouté au registre.

Les chiffres exploratoires ne servent pas à promouvoir un modèle. Ils sont particulièrement sensibles au couple exact (prétraitement, sortie archivée, masque GT réparé) et ne remplacent pas le benchmark final demandé avec F et G réellement chargés.

## Décision

La décision est **NO_FINALIST_DECISION**. MODEL_C reste la baseline stable. Il n'est pas justifié de choisir MODEL_H seul sur la base de sorties historiques alors que les deux candidats prioritaires n'ont pas été chargés dans la même exécution.

## Reprise exacte

1. Mettre localement `best_segformer.pth` et `model.onnx` dans un dossier expérimental isolé.
2. Vérifier strictement leurs clés, formes, canaux et activation.
3. Rejouer les six patches avec le même preprocessing, le même seuil calibré et le même polygoniseur.
4. Calculer IoU, Dice/F1, précision, rappel, Boundary F1, distance de contour et matching objet.
5. Ne retenir au maximum que deux finalistes; ne modifier MODEL_C qu'après décision séparée.

---

CURRENT BASELINE :
DeepLabV3 / ResNet-50 (MODEL_C)

CANDIDATES DEEP BENCHMARKED :
NONE — benchmark final bloqué par l'absence des poids MODEL_F et MODEL_G

MODEL_F :
BLOCKED — WEIGHTS MISSING

MODEL_G :
BLOCKED — WEIGHTS MISSING

MODEL_H :
STRICT LOAD VALIDATED, DEEP FINALIST COMPARISON INCOMPLETE

MODEL_C BASELINE :
PRODUCTION UNCHANGED

BEST SMALL BUILDINGS :
NOT DETERMINED

BEST LARGE BUILDINGS :
NOT DETERMINED

BEST DENSE URBAN :
NOT DETERMINED

BEST BUILDING SEPARATION :
NOT DETERMINED

BEST BOUNDARY QUALITY :
NOT DETERMINED

LOWEST APPARENT FALSE POSITIVES :
NOT DETERMINED IN FINALIST RUN

BEST IOU :
NOT DETERMINED IN FINALIST RUN

BEST RECALL :
NOT DETERMINED IN FINALIST RUN

BEST PRECISION :
NOT DETERMINED IN FINALIST RUN

BEST OBJECT DETECTION :
NOT DETERMINED

FINALISTS :
NONE

REJECTED :
NONE FOR QUALITY; MODEL_F/MODEL_G BLOCKED TECHNICALLY

FULL RASTER :
NOT_RUN

PRODUCTION MODIFIED :
NO

MODEL_C :
DEFAULT UNCHANGED

NEXT STEP :
PROVIDE MODEL_F/MODEL_G WEIGHTS THEN RERUN 13Q.1
