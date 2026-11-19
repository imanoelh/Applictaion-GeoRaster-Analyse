# ÉTAPE 14A.3B-QA2 — Unified strict object benchmark

Les trois modèles ont été rejoués avec la même entrée RGB, le même preprocessing min-max, le seuil 0,50 et les mêmes masques GT des deux patches verrouillés. Aucun entraînement ni changement de modèle n'a été effectué.

Le matcher unique utilise une matrice complète GT×prédictions et une affectation Hungarian à maximum d'IoU. Après affectation, le seuil IoU est appliqué séparément à 0,30, 0,50 et 0,70. Chaque GT et chaque prédiction ne peuvent être associés qu'une seule fois. Les cas merged/fragmented sont comptés comme relations multiples et ne deviennent jamais plusieurs vrais positifs.

Le recalcul strict confirme l'anomalie précédente : MODEL_C3 passe de l'ancien Object F1 0,9583 à 0,2041 à IoU 0,30. Le recall objet C3 est supérieur à C et C2, mais 41 faux positifs restent présents sur 51 prédictions. Le résultat est donc une amélioration réelle mais partielle, insuffisante pour Active Learning automatique sans validation supplémentaire.

Les matrices IoU sont incluses dans `qa/14A3B_QA2_summary.json`, la table GT par GT contient 47 lignes et le diagnostic de seuils est séparé. Les métriques de distance moyenne de frontière restent non disponibles dans cette implémentation rasterisée; les métriques pixel et Boundary F1 sont calculées avec la même logique pour les trois modèles.

GT BUILDINGS :
47

MODEL_C PREDICTIONS :
34

MODEL_C OBJECT F1 @0.30 :
0.1728

MODEL_C OBJECT RECALL @0.30 :
0.1489

MODEL_C FALSE POSITIVES @0.30 :
27

MODEL_C MISSED @0.30 :
40

MODEL_C2 PREDICTIONS :
41

MODEL_C2 OBJECT F1 @0.30 :
0.1591

MODEL_C2 OBJECT RECALL @0.30 :
0.1489

MODEL_C2 FALSE POSITIVES @0.30 :
34

MODEL_C2 MISSED @0.30 :
40

MODEL_C3 PREDICTIONS :
51

MODEL_C3 OBJECT F1 @0.30 :
0.2041

MODEL_C3 OBJECT RECALL @0.30 :
0.2128

MODEL_C3 FALSE POSITIVES @0.30 :
41

MODEL_C3 MISSED @0.30 :
37

MODEL_C3 PIXEL IOU :
0.1819

MODEL_C3 PIXEL RECALL :
0.2165

MODEL_C3 BOUNDARY F1 @1PX :
0.2140

BEST MODEL PIXEL :
MODEL_C3

BEST MODEL BOUNDARY :
MODEL_C3

BEST MODEL OBJECT :
MODEL_C3 (F1 strict 0.2041, mais avec 41 faux positifs)

MODEL_C3 THRESHOLD DIAGNOSTIC :
Le seuil 0,50 donne le meilleur Object F1 @0,30 (0,2041) parmi 0,30/0,40/0,50/0,60; aucun nouveau seuil n'est promu.

OBJECT BENCHMARK IMPLEMENTATION :
VALIDATED

MODEL_C :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 :
UNCHANGED

PRODUCTION :
UNCHANGED

DECISION :
MODEL_C3_PARTIAL_REAL_IMPROVEMENT

READY_FOR_ACTIVE_LEARNING_EXPANSION :
NO

NEXT STEP :
FIX OBJECT BENCHMARK / EXPAND INDEPENDENT GROUND TRUTH
