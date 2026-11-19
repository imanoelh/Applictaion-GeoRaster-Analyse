# 14A.9-AUTO — Cycle autonome expérimental unique

## Décision

**CANDIDATE_REJECTED**. Le pipeline a exécuté un seul cycle complet. PASS signifie exécution et traçabilité, pas qualité suffisante pour production. MODEL_C reste production ; aucun registry, backend ou frontend modifié.

Sur ce cycle, le gain de F1 provient d'un seul FP en moins (10 contre 11), sans aucun TP supplémentaire : 37 TP, 128 FN, 0/38 SMALL comme C6. Il ne répond donc pas à l'objectif de récupération des petits bâtiments. Sur DEV pseudo, le meilleur F1 passe de 0,1928 pour C6 à 0,2012 pour le repli C7 choisi, mais les petits objets appariés passent de 3/90 à 2/90 ; les contraintes DEV ne sont pas satisfaites. Les 72 micro-fragments et les propositions souvent partielles montrent une limite des pseudo-labels de ce cycle. Leur responsabilité causale exacte n'est pas isolée par une ablation : ne pas attribuer cet échec à un unique paramètre ni annoncer qu'un entraînement plus long suffirait. La prochaine génération devra améliorer les données non-GOLD et la qualité des pseudo-objets ; aucune nouvelle génération n'est lancée ici.

## Protocole et données

`protocol.json` et son SHA256 ont été écrits avant les prédictions et l'entraînement. Quatorze RGB nouveaux de 14A.9B sont réutilisés automatiquement avec leur affectation fixe : 10 TRAIN, 4 DEV, emprises séparées de plus de 20 m entre elles et des crops historiques protégés. Aucun GT prétendument humain de 14A.9C n'est utilisé. Pas de réaffectation des anciens TRAIN/VAL/TEST ; overlap TRAIN/DEV/GOLD=0. Le même parent Maxar reste partagé : validation spatiale interne, pas validation d'acquisition externe.

La sélection de ce cycle est bornée au pool éligible de 14 fenêtres déjà préparées ; ce n'est pas une exploration exhaustive des 208 fenêtres de screening. Les indicateurs de désaccord, proximité du seuil et petites composantes sont archivés par les cartes de consensus/mining. Le lanceur `scripts/run_14A9_auto_cycle.py` enchaîne les étapes sans intervention, refuse les redémarrages silencieux d'un entraînement partiel et une seconde tentative GOLD. Le premier lanceur PowerShell a été refusé par la politique locale ; aucun changement de politique système n'a été effectué. Aucun cycle suivant n'est lancé. Les générations futures doivent utiliser un nouvel espace d'artefacts/protocole et de nouvelles données non-GOLD ; pas de boucle ouverte.

## Audit des teachers

C, C3, C6 et D ont réellement chargé et prédit les 14 RGB. C/C3/D utilisent ONNX CPU ; C6 PyTorch CPU ; 4 threads. E est dérivé de C+D, donc pas de vote indépendant. C2/C4/C5 sont reproductibles historiquement mais non sélectionnés comme votes supplémentaires d'une famille corrélée, plus faible lors du benchmark existant. F/F2 : transformers indisponible dans le runtime stable ; A/H : SMP absent ; G : sémantique des canaux non résolue. Aucun téléchargement ou installation. L'audit local des 13 modèles et les contrats réutilisés sont conservés dans qa/.

Les trois DeepLab sont **corrélés** : 3 votes ne sont pas trois preuves indépendantes. Le soutien de D est obligatoire pour le tier A. Un fort consensus n'est pas une preuve de vérité, en particulier lorsque tous les teachers manquent le même petit toit.

## Pseudo-labels et petits objets

Tier A : au moins 3 votes, D>=0,50, moyenne>=0,60, différence D/flip<=0,15. Tier B : D>=0,95 et D-flip>=0,90 hors A. Tier C : incertain, poids nul. Tier D : tous les teachers et D-flip<=0,05, proxy background. Poids A=1, B=0,35, C=0, D=0,5. Aucun filtre 479 px pour créer les positifs pseudo : composantes à partir de 1 pixel, géométrie valide et aire tracée.

**287 objets TRAIN**, **117 objets DEV**, **303 petites propositions <=50 m²** au total. Les vecteurs GeoJSON conservent source, modèle, votes, confiance, accord de frontière, aire, tier, méthode et usage TRAIN. Masques et poids sont enregistrés séparément ; ce ne sont pas des GT humaines. Le mining conserve aussi les réponses C6 0,10–0,30 et les composantes pré-filtre <479 comme candidats incertains, sans les injecter automatiquement comme positifs.

La QA technique des 404 objets confirme géométries valides, OOB=0 sur la grille pixel native, doublons=0, masques binaires et grilles identiques aux RGB. **72 objets font moins de 4 pixels** : certaines petites propositions sont des fragments, pas des bâtiments complets. L'inspection des overlays AL04/AL09/DEV11 l'illustre. Il ne faut pas annoncer 303 petits bâtiments réels récupérés. Les 82 823 pixels A et 109 065 pixels B donnent environ 68 % de poids positif au tier A après pondération ; les 760 192 pixels incertains sont ignorés. Ces contrôles ne prouvent pas la justesse sémantique des pseudo-labels.

Les négatifs sont des **proxies de consensus-background** : aucun algorithme de segmentation sémantique routes/sol/ombres n'a été inventé. Deux contextes TRAIN route/sol nu sont inclus ; leur faible réponse multi-teacher apporte des pixels négatifs pondérés. Les désaccords roof-like restent ignorés, jamais déclarés vrais négatifs sur cette seule base. Des bâtiments manqués par tous les modèles peuvent malgré tout contaminer le background : limite importante du pseudo-supervisé.

## Apprentissage réel et sélection DEV

Trois epochs CPU réellement effectuées depuis le checkpoint C6 intact. Seuls classifier et backbone.layer4 entraînables, BatchNorm en mode évaluation ; taille native 512, batch1, AdamW lr1e-5, BCE+Dice pondérées. Flips, rotations90 et luminosité0,9–1,1 ; pas de resize. Cohérence par flip du teacher D avant pondération, pas de promesse de consistency loss étudiant non implémentée. Trois checkpoints distincts et leurs prédictions DEV sont conservés.

Calibration **DEV uniquement** : 3 epochs × seuils [0,20;0,30;0,50] × min_component [4;64;128;479] × morphologie [NONE;OPEN3] = **72 configurations**. Object matching un-à-un maximal à IoU>=0,30. Objectif Object F1 avec rappel small amélioré d'au moins une détection DEV, FP<=max(1,5×baseline,baseline+3), Boundary F1 final>=95% baseline. Si aucune configuration admissible, le meilleur F1 est quand même figé pour documenter le cycle, mais le gate DEV reste FAILED et interdit le staging.

Sélection : epoch **2**, seuil **0.5**, minimum **479 px**, morphologie **OPEN3**, contraintes DEV **False**. F1 DEV **0.2012**. **Le DEV est pseudo-labellisé : ce score mesure l'accord avec l'ensemble, pas une précision humaine et pas une preuve de généralisation.** Le biais du teacher et l'initialisation C6 imposent cette réserve.

Checkpoint, prétraitement et postprocessing sont figés dans `FROZEN_CANDIDATE.json` avec SHA256 **avant** de lire les prédictions GOLD du candidat. Une seule inférence par patch GOLD, sans TTA, avec un warmup synthétique exclu du temps. Aucun retuning après GOLD.

## GOLD final humain — comparaison stricte

| Mesure | C6 historique | C7 AUTO figé |
|---|---:|---:|
| Object F1 | 0.3474 | 0.3491 |
| Object Precision | 0.7708 | 0.7872 |
| Object Recall | 0.2242 | 0.2242 |
| TP / FP / FN | 37 / 11 / 128 | 37 / 10 / 128 |
| Small recall | 0/38 | 0/38 |
| Medium recall >50–200 m² | — | 25/103 |
| Large recall >200 m² | — | 12/24 |
| Boundary F1 raw, micro | 0.2829 | 0.2812 |
| Pixel IoU raw | 0.3603 | 0.3584 |
| Dice raw | 0.5298 | 0.5277 |
| Merged / Fragmented | 14 / 0 | 14 / 0 |
| CPU inference moyenne s/tile | 6.060 | 6.831 |

Les objets utilisent le masque final après morphologie/filtre, comme 14A.8. Pour comparaison historique, Pixel/Boundary raw utilisent le masque au seuil avant filtre ; C7 fournit aussi les métriques finales séparées (IoU=0.3410, Dice=0.5086, Boundary macro=0.2030). Le temps C6 est archivé, pas une remesure simultanée ; charge CPU/cache peuvent varier. Aucune conclusion de vitesse fine sur cette seule comparaison.

## Gates préenregistrés

F1 et recall strictement supérieurs à C6 ; FN<128 ; small recall>=0,10 (au moins 4/38) ; FP<=17 ; Boundary raw>=95% de 0,282915 ; CPU<=12,192 s/tile ; contraintes DEV satisfaites.

| Gate | Résultat |
|---|---|
| object_f1 | PASS |
| object_recall | FAIL |
| missed | FAIL |
| small | FAIL |
| false_positives | PASS |
| boundary | PASS |
| cpu | PASS |
| dev_constraints | FAIL |

La décision est mécanique : tous les gates doivent passer. Aucun assouplissement après consultation du GOLD. Un échec ne déclenche ni nouvel entraînement ni nouvelle grille sur le GOLD. Le GOLD a déjà servi à plusieurs étapes historiques : référence interne fixe, pas nouveau test externe vierge.

## Intégrité et sorties

78 fichiers GOLD SHA256 avant/après identiques. Les quatre poids teachers, les 14 RGB et le fichier freeze sont inchangés. Toutes les sorties sont dans `14A9_auto_pipeline/` ; aucun modèle expérimental précédent écrasé. Les poids C7 restent dans models/ et ne sont enregistrés dans aucun registry production. Les planches finales montrent RGB, C6 archivé et C7 figé avec les mêmes GT, sans sélection d'exemples pour ajuster les paramètres.

## Statut final

GOLD MANUAL REANNOTATION REQUIRED :
NO

TRAIN MANUAL ANNOTATION REQUIRED :
NO

AUTOMATIC TEACHERS :
MODEL_C, MODEL_C3, MODEL_C6, MODEL_D (+ D horizontal-flip consistency)

AUTO TRAIN OBJECTS :
287

AUTO DEV OBJECTS :
117

SMALL BUILDING PSEUDO-LABELS :
303 (TRAIN + DEV)

HARD NEGATIVES :
2 patches TRAIN de contexte route/sol nu, consensus-background uniquement

NEW MODEL :
MODEL_C7_AUTO (epoch 2)

DEV OBJECT F1 :
0.2012 (pseudo-labels, pas GT humaine)

GOLD OBJECT F1 :
0.3491

GOLD OBJECT RECALL :
0.2242

GOLD SMALL RECALL :
0.0000 (0 / 38)

GOLD FP :
10

GOLD MISSED :
128

BASELINE C6 F1 :
0.3474

BASELINE C6 RECALL :
0.2242

AUTOMATIC PIPELINE :
PASS

CANDIDATE BETTER THAN C6 :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
AUTONOMOUS_DATA_EXPANSION
