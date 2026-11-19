# ETAPE 14A.11 — Hybrid teacher autonomous learning

## Decision

Un seul cycle experimental termine. C8 ne satisfait pas tous les criteres figes de staging. Aucun remplacement production. Etape suivante : `14A12_HYBRID_TEACHER_REFINEMENT`.

## Donnees et separation

- 12 TRAIN, 4 DEV existants non-GOLD. Les 10 nouveaux patches 14A9B sont completes par 2 RGB industriels historiquement TRAIN (14A2_2024_11 et 14A2_2025_11), sans reutilisation de leurs anciens labels. Ce ne sont pas de nouvelles scenes independantes.
- Overlap spatial TRAIN/DEV/GOLD : 0 ; RGB dupliques : 0. Aucun label humain historique ni GOLD utilise en apprentissage/calibration. Hashes des 78 fichiers GOLD identiques avant/apres et a la reference anterieure.
- TRAIN : 355 objets (101 petits <=50m2, 178 moyens >50–200m2, 76 grands >200m2). DEV : 149 (51/74/24). Ce sont des pseudo-labels, pas une nouvelle verite terrain.
- Tous les masques : grille native 512x512 du RGB, valeurs 0/1, meme CRS/transform/bounds, sans resampling. Les RGB de ce jeu utilisent leur CRS natif ; les GeoJSON et surfaces sont en EPSG:32637. QA 16/16 : validite, non-vide, surfaces, unicite, bounds testes en coordonnees pixel inversees (pas seulement bbox UTM).

## Contrat enseignants et hybride objet

C6 conserve son preprocessing RGB minmax global par patch, seuil0.30, composantes4, minimum479px. DIST3 ONNX CPU utilise RGB/255 puis ImageNet mean/std, quatre fenetres256 sans overlap par patch512, sigmoid des trois sorties mask/distance/boundary, watershed global des seeds distance>0.5 dans mask>=0.5. Une inference retournee par flip horizontal fournit une coherence d'augmentation.

Les labels d'instances DIST3 sont preserves. Consensus : IoU>=0.30 ou intersection/aireDIST3>=0.60. Choix de contour par proxy fixe boundary/compactness/confiance ; conservation des unites DIST3 face a un gros objet C6 fusionne. DIST3 seul : aire>=1m2, compactness>=0.08, aspect<=8, confiance/IoUflip (>=0.8/0.5 ou >=0.95/0.35), score de rejet<0.55. Pas de filtre479px sur ces objets. C6 seul : confiance>=0.85 et DIST3 moyen>=0.05 ; aucun n'a passe.

Regroupement conservateur : contact>=2px, faible frontiere interne, forte confiance, orientation compatible, meme composante C6, continuite de forme. 11 paires regroupees. Split conditionne a plusieurs cores C6 et une frontiere interne : 0 cas declenches. Ces operations ne garantissent pas une correction semantique humaine.

Le score `DIST3_FP_REJECTION_SCORE` combine confiance, coherence flip, forme, fraction background C6, texture et contexte route/sol nu du patch. Distances aux routes, probabilites sol nu, classes parking/vegetation : NON DISPONIBLES. Les 336 rejets ne sont donc pas des FP verifies. 417 propositions enseignants incertaines exclues (compteur de propositions pouvant se recouvrir, pas de batiments uniques). Les objets rejetes ne deviennent pas automatiquement du negatif ; seul le background concordant C6/DIST3/flip<0.05 est supervise.

254 consensus et253 DIST3 seuls ont ete appliques avant separation des contacts ; 3 consensus minuscules disparaissent lors des gaps, d'ou 251+253=504 objets finaux. Les gaps entre instances voisines sont supervises background (poids1), les contours externes ne sont pas erodes. Les pixels incertains ont poids0 : 999915. Les gaps sont une hypothese de separation, pas une GT humaine.

## Entrainement et calibration

C8 initialise strictement C6, backbone+classifier entrainables, aux gele et statistiques BN gelees, AdamW (2e-5 backbone,1e-4 head,weight_decay1e-4), BCE+Dice ponderees, clipping1, batch1 natif512. Poids objets A1/B0.6/C0.75, facteur aire clip(200/px,0.25,4), negatives0.7. Ordre par contexte et exemples petits/moyens/grands reponderes ; pas de garantie d'equilibre semantique parfait sur ce petit jeu.

3 epochs, seed1411 ; flips/rotations90/luminosite0.9–1.1. Patience2, maximum3. Le controle `qa/DEV_LOSS_AUDIT.json` recalcule la BCE depuis les predictions sauvegardees en float : le diagnostic uint8 d'un worker deja lance est conserve dans l'historique, corrige avant selection ; aucun effet sur le nombre d'epochs (patience2 ne pouvait arreter avant la troisieme), aucun reentrainement. Selection finale exclusivement par metriques objet DEV.

Grille DEV : seuils0.20/0.30/0.50, minimum4/32/128/479, NONE/OPEN3 sur chaque checkpoint. Contraintes : petits TP>C6, FP<=max(1.5*FP_C6,FP_C6+5), BoundaryF1 final>=95% C6. Labels DEV hybrides correles aux enseignants : le score est un accord de pseudo-labels, pas une mesure independante de precision reelle.

Freeze : epoch2, seuil0.5, minimum32, NONE, connexite4. DEV F1=0.447154, contraintes=FAIL. DEV C6 : F1=0.373737, petitsTP=1, FP=12. C8 : petitsTP=8, FP=42 (plafond=18), BoundaryF1 final=0.383152 (minimum=0.315729). Si aucune combinaison n'est admissible, meilleur F1 de repli fige et gate DEV refusee. SHA checkpoint `32f48ba94385206ed3e1cc8a156b73ac33810525f05a6bb3fd51b16c486a7576`. Freeze SHA `2ee4982a3537a16f62620c45a90dcfa8f7d338c3dd66f5379cd38baa275e9a20`.

## Evaluation finale GOLD

Un seul passage C8 apres freeze, quatre patches/165 GT, petits38. Pas de generation hybride sur GOLD et pas de reparametrage apres resultat. Matching IoU>=0.30, maximum cardinalite puis IoU, strictement un-a-un ; chaque GT apparait une fois dans le CSV de matching. Merge/fragmentation : memes seuils d'intersection descriptifs que14A8/14A10. Les comparaisons C6/C7/DIST3 viennent des resultats caches, aucune nouvelle inference baseline.

| MODEL | TP | FP | FN | Precision | Recall | F1 | Small TP /38 | Boundary F1 | Merge | Fragment | CPU s/patch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MODEL_C6 | 37 | 11 | 128 | 0.7708 | 0.2242 | 0.3474 | 0 | 0.2829 | 14 | 0 | 6.060 |
| MODEL_C7_AUTO | 37 | 10 | 128 | 0.7872 | 0.2242 | 0.3491 | 0 | 0.2812 | 14 | 0 | 6.831 |
| UNET_DIST3 | 116 | 128 | 49 | 0.4754 | 0.7030 | 0.5672 | 14 | 0.5020 | 9 | 37 | 1.213 |
| MODEL_C8_HYBRID | 54 | 37 | 111 | 0.5934 | 0.3273 | 0.4219 | 3 | 0.3364 | 25 | 1 | 6.360 |


BoundaryF1 tableau : micro des comptes contours bruts a tolerance1px, conforme aux baselines ; objet : masque final apres postprocessing. Pixel brut C8 IoU=0.505823, Dice=0.671823. Medium recall=34/103, large=17/24. CPU : PyTorch4threads inference moyenne par512 apres warmup, hors chargement ; postprocessing=0.048s. Comparaison des temps descriptive (engines/dates differents), pas un benchmark intercale.

Criteres minimum declares avant entrainement : F1>0.3491, recall>0.2242424, petitTP>=1, missed<128, FP<=64, BF1>=0.2687692, CPU<=12.1924s, contraintesDEV. Resultat : `{"object_f1": true, "object_recall": true, "small": true, "missed": true, "false_positives": true, "boundary": true, "cpu": true, "dev_constraints": false}`. Les objectifs ambitieux ne sont pas des resultats forces.

### Lecture du resultat

C8 progresse face a C6/C7 en F1, recall et petits TP, avec moins de FP que DIST3. Il ne recupere toutefois que 3/38 petits contre14/38 pour DIST3, et presente 25 objets fusionnes contre14 pour C6 et9 pour DIST3. L'etudiant semantique n'a pas conserve la separation des instances de l'enseignant. C'est un constat des sorties finales ; son origine precise (labels, loss, architecture ou duree d'apprentissage) n'a pas ete isolee causalement. Le gain de F1 ne suffit pas a valider le staging : les contraintes DEV restent refusees. Les mentions « BETTER THAN » du bloc final comparent le F1 objet, pas toutes les dimensions de qualite.

## Integrite, limites et artefacts

10 fichiers de modeles historiques/enseignants compares a leurs SHA precedents ; tous identiques. Les RGB sources et protocoles/freeze sont intacts. Aucun fichier backend/app, frontend, registry ou production modifie par cette etape. Aucune promotion automatique ni export ONNX C8. Le teacher DIST3 a une licence CC-BY4 et une reserve d'attribution archivee en14A10 : revue necessaire avant toute diffusion/staging.

Ce resultat concerne quatre patches GOLD fixes : utilisation repetee de ce GOLD dans les experiences historiques, generalisation externe non demontree. Aucune annotation humaine nouvelle ne confirme les pseudo-labels ni les rejets. Cette limite demeure meme si les scores augmentent.

Artefacts sous `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/` : `protocol.json`, `hybrid_teacher/` (objets, decisions, masques, actions), `small_candidates/`, `hard_negatives/`, `qa/` (QA, hashes, contact sheet), `models/` (C8 epochs + historique), `calibration/` (grille et freeze), `gold_evaluation/` (matching, metriques, overlays, contact sheet), `14A11_global_comparison.csv`.

## Statut final

HYBRID TEACHER :
C6 + UNET_DIST3

PSEUDO LABELS TOTAL :
504 (355 TRAIN + 149 DEV)

CONSENSUS :
251

DIST3 ONLY ACCEPTED :
253

C6 ONLY ACCEPTED :
0

UNCERTAIN EXCLUDED :
417 propositions enseignants

DIST3 FP REJECTED :
336 rejets automatiques, FP non confirmes humainement

SMALL BUILDING PSEUDO LABELS :
152 (101 TRAIN + 51 DEV)

FRAGMENTS MERGED :
11

NEW MODEL :
MODEL_C8_HYBRID

DEV F1 :
0.4472 (accord pseudo-labels, pas GT humaine)

GOLD F1 :
0.4219

GOLD RECALL :
0.3273

GOLD SMALL RECALL :
3 / 38

GOLD FP :
37

GOLD MISSED :
111

GOLD BOUNDARY F1 :
0.3364

C6 F1 :
0.3474

UNET_DIST3 F1 :
0.5672

C8 BETTER THAN C6 :
YES

C8 BETTER THAN UNET_DIST3 :
NO

CANDIDATE READY FOR STAGING :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
14A12_HYBRID_TEACHER_REFINEMENT
