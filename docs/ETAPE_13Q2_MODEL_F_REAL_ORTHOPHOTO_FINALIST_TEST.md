# ÉTAPE 13Q.2 — MODEL_F SegFormer Real Orthophoto Finalist Test

## Dataset et méthode

La même orthophoto Maxar historique a été utilisée pour les deux moteurs :
`backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif`, 10 292×9 378, RGB, résolution ~3,182877e-6 degré/pixel. Deux fenêtres ont été testées : 2 048×2 048 et 4 096×4 096. Aucun traitement du raster complet 96,5 MP n'a été lancé.

Les deux modèles ont reçu les mêmes tuiles 512×512 sans modification des pixels sources. MODEL_C a utilisé son min-max RGB global documenté; MODEL_F a utilisé RGB `/255`, son checkpoint SegFormer B0 et un seuil 0,50. Les sorties sont écrites sous `backend/data/models/building/experimental/benchmark_13Q2/`.

## Résultats quantitatifs

Les surfaces ci-dessous sont exprimées en **unités² du CRS source géographique**. Elles ne sont pas annoncées comme m², car le raster de test est en coordonnées longitude/latitude.

| Fenêtre | Modèle | Candidats | Pixels positifs | Surface source² | Temps | s/MP |
|---|---|---:|---:|---:|---:|---:|
| 2048² | MODEL_C | 226 | 300 394 | 3,0432e-6 | 55,10 s | 13,14 |
| 2048² | MODEL_F | 221 | 835 806 | 8,4673e-6 | 16,81 s | 4,01 |
| 4096² | MODEL_C | 639 | 1 265 777 | 1,2823e-5 | 228,37 s | 13,61 |
| 4096² | MODEL_F | 709 | 2 968 880 | 3,0077e-5 | 64,14 s | 3,82 |

MODEL_F est environ 3,3× plus rapide sur ces fenêtres CPU. Il marque 2,8× à 3,0× plus de pixels positifs que MODEL_C, ce qui indique une couverture supérieure mais aussi un risque accru de faux positifs. Aucun IoU n'est calculé sur ces zones sans Ground Truth.

## Alignement et inspection visuelle

Pour chaque fenêtre et chaque modèle : probability map, masque binaire, GeoJSON et overlay ont été produits. Les sorties ont la même taille, transform, CRS et bounds que la fenêtre source. Aucun offset ni décalage de mosaïque n'a été observé.

La planche comparative est `backend/data/models/building/experimental/benchmark_13Q2/contact_sheet_13Q2.png`. L'inspection montre que MODEL_F récupère davantage de toitures, notamment dans les blocs urbains denses et les grands toits. MODEL_C est plus conservateur et produit visuellement moins de surface positive. La qualité des limites de toit et la séparation fine restent à confirmer par annotations locales; la couverture supplémentaire de MODEL_F ne suffit pas à déclarer une supériorité définitive.

## Décision

Les deux tests 2 048² et 4 096² réussissent techniquement. MODEL_F est exploitable en R&D et présente un avantage de vitesse et de rappel visuel apparent. Il reste expérimental : aucune modification de registry, frontend, API ou défaut production n'a été faite. Une validation avec Ground Truth représentative est requise avant une intégration expérimentale contrôlée.

---

MODEL_C :
PRODUCTION BASELINE

MODEL_F :
SEGFORMER FINALIST

2048 TEST :
SUCCESS

4096 TEST :
SUCCESS

MODEL_C 2048 CANDIDATES :
226

MODEL_F 2048 CANDIDATES :
221

MODEL_C 2048 TIME :
55.10 s (13.14 s/MP)

MODEL_F 2048 TIME :
16.81 s (4.01 s/MP)

MODEL_C 4096 CANDIDATES :
639

MODEL_F 4096 CANDIDATES :
709

MODEL_C 4096 TIME :
228.37 s (13.61 s/MP)

MODEL_F 4096 TIME :
64.14 s (3.82 s/MP)

BEST BUILDING DETECTION :
MODEL_F (provisional visual coverage)

BEST BUILDING LOCATION :
SIMILAR — visual review required

BEST SMALL BUILDINGS :
MODEL_F (more apparent detections; unvalidated)

BEST DENSE URBAN :
MODEL_F (more coverage; unvalidated)

BEST BUILDING SEPARATION :
SIMILAR — no Ground Truth local

BEST COMPLEX ROOFS :
SIMILAR — no Ground Truth local

BEST BOUNDARY QUALITY :
SIMILAR — manual review required

LOWEST FALSE POSITIVES :
MODEL_C (more conservative apparent coverage)

BEST OVERALL FOOTPRINT QUALITY :
MODEL_F PROVISIONAL, NEEDS GROUND TRUTH

MODEL_F PERFORMANCE :
GOOD

FULL RASTER :
NOT_RUN

PRODUCTION MODIFIED :
NO

MODEL_C DEFAULT :
YES

FINAL DECISION :
MODEL_F_NEEDS_MORE_TESTING

NEXT STEP :
ADDITIONAL MODEL_F TEST
