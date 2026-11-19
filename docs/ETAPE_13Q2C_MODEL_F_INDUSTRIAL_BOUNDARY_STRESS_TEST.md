# ÉTAPE 13Q.2C — MODEL_F Industrial Roof and Boundary Quality Stress Test

## Résultat du diagnostic

Les deux patches industriels TEST ont été réutilisés sans modification. MODEL_F est très performant sur le patch industriel 2025 mais presque totalement silencieux sur le patch industriel 2024 : probabilité médiane dans le GT `0,0096`, maximum `0,0825`. Un simple seuil ne peut donc pas récupérer ce bâtiment.

Cela indique principalement une **limitation de domaine / matériaux de toiture**, plutôt qu'un mauvais seuil global. Le même preprocessing RGB `/255` donne une réponse élevée sur l'industriel 2025 (médiane `0,9818`) et quasi nulle sur l'industriel 2024.

## Métriques industrielles

| Modèle | IoU | rappel | Boundary F1 exploratoire |
|---|---:|---:|---:|
| MODEL_C | **0,811** | **0,960** | **0,231** |
| MODEL_F | 0,376 | 0,468 | 0,066 |

Les métriques de contour utilisent la GT réparée approximative et restent à faible confiance. MODEL_C est meilleur sur les deux scènes industrielles et sur les limites observées.

## Threshold sweep limité MODEL_F

Sur les industriels, les valeurs 0,35 à 0,60 donnent des IoU de 0,372 à 0,378; le meilleur point exploratoire est `0,60`, mais le rappel baisse encore. Sur les scènes résidentielles/difficiles, le seuil 0,35 est meilleur que 0,50 en IoU/rappel, mais dégrade le compromis global et ne corrige pas l'industriel 2024. Aucun nouveau seuil n'est retenu pour la production.

## Conclusion

Le problème principal est classé `MODEL_F_INDUSTRIAL_DOMAIN_LIMITATION`. Une correction de seuil n'est pas prometteuse. MODEL_F reste pertinent pour les scènes résidentielles/difficiles, tandis que MODEL_C est plus sûr pour les toitures industrielles et les contours. Aucun fine-tuning, changement de preprocessing, changement de tiling, intégration ou promotion n'a été effectué.

INDUSTRIAL GT BUILDINGS :
2 patches industriels, 1 feature GT principale par patch

MODEL_C INDUSTRIAL IOU :
0.811

MODEL_F INDUSTRIAL IOU :
0.376

MODEL_C INDUSTRIAL RECALL :
0.960

MODEL_F INDUSTRIAL RECALL :
0.468

MODEL_C INDUSTRIAL BOUNDARY F1 :
0.231 exploratory

MODEL_F INDUSTRIAL BOUNDARY F1 :
0.066 exploratory

MODEL_C LARGE BUILDING DETECTION :
BEST INDUSTRIAL PROVISIONAL

MODEL_F LARGE BUILDING DETECTION :
FAILED ON 2024 INDUSTRIAL / GOOD ON 2025 INDUSTRIAL

MODEL_C SMALL BUILDING DETECTION :
NOT DETERMINED

MODEL_F SMALL BUILDING DETECTION :
NOT DETERMINED

MODEL_F BASELINE THRESHOLD :
0.50

BEST EXPLORATORY MODEL_F THRESHOLD :
0.60 INDUSTRIAL ONLY, NOT ADOPTED

INDUSTRIAL IMPROVEMENT :
NONE — threshold sweep does not recover 2024 industrial roof

RESIDENTIAL IMPACT :
0.35 improves exploratory recall/IoU, but is not globally adopted

PRIMARY FAILURE CAUSE :
MODEL_F_INDUSTRIAL_DOMAIN_LIMITATION

BEST INDUSTRIAL MODEL :
MODEL_C

BEST RESIDENTIAL MODEL :
MODEL_F

BEST BOUNDARY QUALITY :
MODEL_C

BEST GENERAL FOOTPRINT MODEL :
INCONCLUSIVE / CONTEXT-DEPENDENT

MODEL_F PRODUCTION READY :
NO

PRODUCTION MODIFIED :
NO

MODEL_C DEFAULT :
YES

NEXT STEP :
KEEP MODEL_C
