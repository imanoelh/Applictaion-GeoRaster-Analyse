# ÉTAPE 14A.3B-QA — MODEL_C3 benchmark sanity check

Le benchmark a été rejoué sur les mêmes RGB, les mêmes masques GT finaux et le seuil 0,50. MODEL_C3 et MODEL_C production n'ont pas été modifiés.

## Méthode de matching

Les objets prédits sont les composantes connexes du masque binaire MODEL_C3, utilisées comme polygones candidats reproductibles. Pour chaque paire GT/prédiction, l'IoU est calculé sur les pixels. Les paires sont triées par IoU décroissant, puis affectées par matching glouton one-to-one : un GT et une prédiction ne peuvent être utilisés qu'une seule fois. Les seuils 0,30, 0,50 et 0,70 sont calculés séparément.

Une prédiction couvrant plusieurs GT n'est pas comptée comme plusieurs matches. Les champs `merged` et `fragmented` comptent les recouvrements multiples au seuil considéré. La table complète contient une ligne unique pour chacun des 47 GT.

## Résultat

Le score objet précédent `0.9583` était incorrect : il provenait d'une métrique basée sur `min(nombre_GT, nombre_predictions)` et non d'un matching IoU one-to-one. Le recalcul strict donne F1 global 0,2041 à IoU 0,30, 0,1837 à IoU 0,50 et 0,0612 à IoU 0,70. Le rappel pixel 0,2165 est cohérent avec ce faible rappel objet. Il n'y a pas de fuite, mais l'ancienne métrique constitue un bug de benchmark.

OBJECT_METRICS_VALIDATED

ou

OBJECT_METRICS_OVEROPTIMISTIC

ou

OBJECT_METRICS_BUG_FOUND

La conclusion retenue est `OBJECT_METRICS_BUG_FOUND`. Active Learning est bloqué jusqu'à correction du benchmark objet.

LOCKED GT BUILDINGS :
47

PREDICTED BUILDINGS :
51

OBJECT IOU THRESHOLD 0.30 F1 :
0.2041

OBJECT IOU THRESHOLD 0.50 F1 :
0.1837

OBJECT IOU THRESHOLD 0.70 F1 :
0.0612

MISSED @0.30 :
37

MISSED @0.50 :
38

MISSED @0.70 :
44

FALSE POSITIVES @0.30 :
41

MERGED BUILDINGS :
0

FRAGMENTED BUILDINGS :
0

PIXEL RECALL :
0.2165

PIXEL VS OBJECT METRICS EXPLANATION :
Le rappel pixel faible est cohérent avec le matching strict. Le score objet 0.9583 précédent était optimiste et résultait d'un bug de comptage sans IoU one-to-one.

OBJECT METRICS :
BUG

MODEL_C3 :
UNCHANGED

PRODUCTION :
UNCHANGED

READY_FOR_ACTIVE_LEARNING_EXPANSION :
NO

NEXT STEP :
FIX OBJECT BENCHMARK
