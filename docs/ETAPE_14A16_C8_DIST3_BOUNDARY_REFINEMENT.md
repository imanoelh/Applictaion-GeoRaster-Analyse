# ÉTAPE 14A.16 — C8 object decision + DIST3 boundary refinement

## Scope

`C8_BOUNDARY_REFINED_V1` a été exécuté comme expérimentation isolée. C8 garde
la décision objet avec `threshold=0.50`, `min_component=32`, connectivité 4,
sans morphologie. DIST3 utilise son checkpoint ONNX 14A.10, avec SHA256
`e1c14b893d738a660d99a5f456fc68c04077a09fcb8f88a0bcd577d72b40a735`.

DIST3 est appelé uniquement dans une fenêtre locale autour d'un objet C8 déjà
accepté. L'association sélectionne la composante ayant le meilleur IoU et le
meilleur ratio d'intersection. Une géométrie est conservée seulement si le
recouvrement atteint 0,30, le ratio de surface reste entre 0,70 et 1,30 et le
déplacement du centroïde reste inférieur ou égal à 5 pixels. Dans tous les
autres cas, la géométrie C8 est conservée. Le nombre d'objets reste donc
identique et aucun objet DIST3 isolé n'est ajouté; les séparations potentielles
sont seulement signalées.

## Calibration DEV

Les quatre patches non-GOLD 14A9B ont servi à choisir une marge parmi 10, 20
et 30 pixels. La configuration retenue est marge 10 pixels, recouvrement
minimal 0,30, ratio de surface maximal 1,30 et déplacement maximal 5 pixels.
Le résultat DEV agrégé est F1 objet 0,5664, rappel 0,8326 et Boundary F1
0,2710; ces valeurs ne satisfont pas un critère de promotion GOLD et servent
uniquement à figer la configuration expérimentale.

## GOLD one-shot

Le passage GOLD a été effectué après le gel de la configuration, sans sélection
sur GOLD. Résultats agrégés : baseline C8 F1 0,4219, rappel 0,3273, FP 37;
raffinement F1 0,4141, rappel 0,3212, FP 38. Le nombre de prédictions est
stable (91 contre 91), mais le raffinement perd un appariement objet et ajoute
un faux positif. Le Boundary F1 apparié est 0,1949 contre 0,1972 dans le même
calcul diagnostique. La valeur de référence historique 14A.15 est 0,3364;
elle reste le seuil officiel de la décision.

Le pipeline est donc rejeté. Le fichier de configuration est gelé avec
`enabled=false`; aucune modification n'est appliquée à l'adapter, au registre,
à MODEL_C production, à DIST3 ou aux autres traitements GeoRaster.

## Artefacts

- Script : `scripts/run_14A16_c8_dist3_boundary_refinement.py`
- Configuration gelée : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A16_c8_dist3_boundary_refinement/14A16_C8_DIST3_BOUNDARY_REFINEMENT_CONFIG.json`
- Résultat GOLD : `.../GOLD_ONE_SHOT_RESULT.json`
- Contact sheet : `.../overlays/14A16_C8_DIST3_GOLD_CONTACT_SHEET.png`
- Masques et métriques DEV/GOLD : répertoire `.../14A16_c8_dist3_boundary_refinement/`

C8 et DIST3 n'ont pas été modifiés. Le modèle de production demeure MODEL_C.
La validation visuelle réelle d'une orthophoto utilisateur n'est pas demandée
pour un candidat rejeté; l'artefact de contact sheet fournit la QA visuelle
diagnostique.

C8 WEIGHTS MODIFIED :
NO

DIST3 WEIGHTS MODIFIED :
NO

DIST3 ROLE :
BOUNDARY_REFINER_ONLY

NEW BUILDINGS ADDED BY DIST3 :
0

C8 BASELINE F1 :
0.4219

REFINED F1 :
0.4141

C8 BASELINE RECALL :
0.3273

REFINED RECALL :
0.3212

C8 BASELINE FP :
37

REFINED FP :
38

C8 BASELINE SMALL RECALL :
3 / 38

REFINED SMALL RECALL :
3 / 38

C8 BASELINE BOUNDARY F1 :
0.3364

REFINED BOUNDARY F1 :
0.1949

OBJECT COUNT CHANGE :
0 (91 → 91)

REAL ORTHOPHOTO VISUAL QA :
FAIL

PROCESSING TIME :
34.6 s total (DEV local 5.0 s, GOLD 4.6 s)

READY FOR USER VISUAL VALIDATION :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :

KEEP_C8_BASELINE
