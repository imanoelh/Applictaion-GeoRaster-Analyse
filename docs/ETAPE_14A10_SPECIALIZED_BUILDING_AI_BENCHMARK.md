# 14A.10 — Modèles Building spécialisés : audit et benchmark GOLD

## Décision

**Nouveau teacher spécialisé trouvé : UNET_DIST3.** F1=0.5672, rappel=0.7030, SMALL=14/38. Les nouvelles détections appariées aux GT absentes de C6 sont quantifiées ci-dessous. Aucune promotion : **128 FP et 37 fragmentations** imposent un filtrage/consensus et une validation non-GOLD ultérieurs. L'objectif de cette étape était discovery/intégration expérimentale/benchmark, pas C8 ; aucun entraînement exécuté.

## Audit public et traçabilité

Neuf offres/modèles audités ; quatre exports/checkpoints chargés sur un patch non-GOLD ; trois candidats retenus pour les quatre GOLD. CSV complet `14A10_external_model_candidates.csv` : toutes les colonnes demandées, sources, licences, poids, taille et statuts. Les métadonnées, fiches et révisions des dépôts sont archivées sous sources/.

- [U-Net dist3](https://huggingface.co/nilsho01/unet-effb4-dist3-buildings) : modèle Building avec trois têtes ; entraînement VHR spécialisé, input256. Carte CC-BY-4.0, mais attribution de certaines sources encore à revoir selon l'auteur. Poids ONNX figés, SHA256 `e1c14b893d738a660d99a5f456fc68c04077a09fcb8f88a0bcd577d72b40a735`. Usage expérimental seulement ; aucune conclusion de conformité production.
- [HOT/Lund](https://huggingface.co/LundAISociety/hot-models) : export DINOv3-S distillé récent, 47 Mo. Forward CPU réussi, sortie uint8 à quatre cartes. Le contrat complet de décodage des vecteurs et de flow n'a pas été retrouvé : INCOMPATIBLE pour ce benchmark, pas de masque inventé. La variante v1.0 conserve aussi une recette non reproduite ; le dépôt de code référencé retourne 404. Le modèle contact séparé renvoie HTTP401 à l'API ; aucun contournement.
- [SegFormer SpaceNet](https://huggingface.co/Abhatta7/building-footprint-segmentation) : anciens poids F déjà présents, architecture différente de C6 ; runtime restauré dans le sandbox, strict load passé. Ce n'est pas un nouveau checkpoint découvert, mais sa première évaluation reproductible sur ce GOLD dans ce travail.
- [DINOv3-S publié](https://huggingface.co/geobase/dinov3s-buildings) : ancien MODEL_G, hash identique au graphe S du dépôt [HOT](https://huggingface.co/kshitijrajsharma/dinov3-hot-buildings), maintenant évalué par un **adapter sémantique canal0**. Les paramètres de couleur viennent du preprocessor de la variante S ; ne pas les confondre avec ceux du L. L'adapter n'est pas une reproduction de tout le pipeline fAIr watershed/régularisation. Les déclarations de licence du miroir et de l'amont diffèrent ; revue nécessaire avant déploiement.
- [Mask2Former OpenEarthMap](https://huggingface.co/mfaytin/mask2former-satellite) : neuf classes de couverture du sol, non retenu comme spécialiste d'instances Building. [HRNet-W32](https://huggingface.co/Uve1048/hrnet-w32-footprint) : candidat Building, mais dépend de MMSegmentation ; pas installé pour cette sélection. DINOv3-L ONNX public de 1,42 Go : non retenu pour coût de ce screening CPU ; cela ne signifie pas un échec de chargement.

## Sandbox et protocole figé

Tout est isolé dans `14A10_specialized_benchmark/`. Deux nouveaux ONNX téléchargés, contrôlés contre tailles et SHA256 LFS ; F/G locaux conservés intacts. Dépendances post-traitement et Transformers installées par `--target` dans les seuls sous-dossiers expérimentaux. Aucun paquet du runtime production changé. Cache HF redirigé ensuite vers le sandbox et réseau d'inférence désactivé. Les sources distantes sont archivées comme texte, jamais importées/exécutées.

`protocol.json` + SHA256 écrits **avant tout GOLD**. Smoke sur 14A9B_AL_01, sortie512, valeurs finies, postprocessing testé hors GOLD. Codes de sortie **0** pour les quatre forwards et les trois post-traitements retenus. Voir PROCESS_EXITS/BENCHMARK_EXITS et logs. Aucun réglage issu de GOLD, aucun sweep, aucun nouvel entraînement.

Contrats figés :

1. **UNET_DIST3** : RGB/255 + ImageNet, quatre fenêtres natives256 sans resize ; fusion des trois cartes puis masque>=0,50, graines EDT>0,50, watershed sur -distance(mask), conformément à l'exemple publié. Pas de filtre479. Les **IDs d'instances** sont conservés pendant la polygonisation ; les bâtiments accolés ne sont pas refusionnés par une conversion binaire. La tête boundary existe, mais l'exemple d'inférence publié exploite mask+EDT, pas explicitement la troisième tête. Les limites internes des tuiles peuvent affecter les prédictions.
2. **SEGFORMER_F** : RGB/255, input512, logits128 interpolés bilinéairement puis sigmoid, seuil0,50, connexité8, minimum4px ; recette historique figée avant GOLD.
3. **DINO_S_SEMANTIC** : RGB/255 + ImageNet selon son preprocessor ; fenêtres256/stride192 avec bord terminal, moyenne des probabilités dans les recouvrements ; canal0 sigmoid, seuil publié0,4371 et minimum publié2,6465m². Pas de watershed ni simplification/régularisation géométrique ; cette variante sémantique peut fusionner des voisins.

Chaque candidat READY a effectué une seule série d'inférences sur les quatre mêmes RGB, après warmup synthétique, à quatre threads CPU. Même GT humain de 165 features, dont38 SMALL<=50m². MEDIUM>50–200m² et LARGE>200m² restent les strates descriptives 14A.9A. Aucune image/GT changée.

## Résultats GOLD — primaire IoU objet >=0,30

| Modèle | TP | FP | FN/Missed | Precision | Recall | F1 | SMALL TP/38 | MEDIUM | LARGE | Merged | Fragmented | Boundary F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C6 archivé | 37 | 11 | 128 | 0,7708 | 0,2242 | 0,3474 | 0/38 | 25/103 | 12/24 | 14 | 0 | 0,2829 |
| C7 archivé | 37 | 10 | 128 | 0,7872 | 0,2242 | 0,3491 | 0/38 | 25/103 | 12/24 | 14 | 0 | 0,2812 |
| UNET_DIST3 | 116 | 128 | 49 | 0.4754 | 0.7030 | 0.5672 | 14/38 | 83/103 | 19/24 | 9 | 37 | 0.5020 |
| DINO_S_SEMANTIC | 65 | 58 | 100 | 0.5285 | 0.3939 | 0.4514 | 6/38 | 43/103 | 16/24 | 29 | 4 | 0.4034 |
| SEGFORMER_F | 26 | 60 | 139 | 0.3023 | 0.1576 | 0.2072 | 1/38 | 19/103 | 6/24 | 12 | 8 | 0.1912 |

SMALL_FN explicites : UNET_DIST3=24 ; DINO_S_SEMANTIC=32 ; SEGFORMER_F=37. SMALL recalls respectifs : 0,3684 / 0,1579 / 0,0263. Les chiffres sont issus du matching un-à-un, pas de simples pixels positifs.

| Modèle | GT détectés absents de C6 | Dont SMALL | GT C6 perdus | Pixel IoU | Dice | CPU inference s | Postprocessing s |
|---|---:|---:|---:|---:|---:|---:|---:|
| UNET_DIST3 | 79 | 14 | 0 | 0.5374 | 0.6991 | 1.213 | 0.187 |
| DINO_S_SEMANTIC | 40 | 6 | 12 | 0.4946 | 0.6618 | 12.764 | 0.066 |
| SEGFORMER_F | 9 | 1 | 20 | 0.2619 | 0.4151 | 1.209 | 0.047 |

Les temps sont des moyennes par patch512 hors chargement/warmup, mesurées dans des workers séparés. Ils incluent les quatre ou neuf fenêtres nécessaires selon le modèle. C6 historique n'a pas été remesuré simultanément : comparaison de coût indicative, sensible à la charge/cache.

## Sanity check et limites

165 lignes GT uniques par modèle, aucune prédiction créditée à plusieurs GT ; toutes les paires retenues ont été revérifiées par intersection/union géométrique >=0,30. Le maximum de cardinalité puis IoU est le même matcher que 14A.8. Nombre d'IDs raster finaux égal au nombre d'objets vectoriels. Archives RGB et masques GT comparées pixel par pixel à leurs sources réelles. Les métriques objet utilisent les instances finales ; Pixel IoU/Dice/Boundary F1 utilisent la carte binaire brute au seuil, comme la baseline14A.8. BoundaryF1 micro avec tolérance1pixel, sans wrap. Merged/Fragmented : règles de couverture30% identiques à14A.8.

Sensibilité **du scoring seulement**, jamais un réglage des prédictions : pour le meilleur candidat, F1@IoU0,30=0.5672, @0,50=0.4597, @0,70=0.3130. La configuration ne change pas. Les overlays résidentiel et dense UNET ont été examinés : davantage de toits appariables et de séparations, mais aussi sur-segmentation et objets non appariés. Les FP sont relatifs aux annotations GOLD ; aucun audit sémantique exhaustif de ces128 FP n'est revendiqué.

**Teacher complémentaire ne signifie pas modèle prêt pour production.** UNET améliore F1, recall, small recall, missed, fusions et BoundaryF1, mais sa précision baisse à0,4754 et ses FP passent de11/10 à128. La fragmentation37 est une autre limite. La suite doit étudier un hybride et filtrer/calibrer exclusivement sur non-GOLD, sans imposer de nouveau paramètre à partir des erreurs GOLD. Les licences/attributions et la provenance des données externes doivent être revues. Le recouvrement éventuel des données d'entraînement publiques avec ce site ne peut pas être certifié à partir de ces seules fiches. Ce GOLD réutilisé est un benchmark interne, pas un nouveau test externe vierge.

## Protection et livrables

78 fichiers GOLD hashés avant/après : identiques. Quatre fichiers modèles et protocole SHA256 inchangés. MODEL_C production conservé ; aucun changement API/frontend/GEE/indices/exports/offline. Aucun C8, aucun pseudo-label training, aucun hybride entraîné. CSV candidats, contrats, sources épinglées, sortiesprobabilités/instances, métriques par patch et globales, matching, sensibilité et planche comparative sont livrés dans le sandbox.

## Statut final

MODELS AUDITED :
9

MODELS READY :
3

MODELS BENCHMARKED :
3

C6 F1 :
0.3474

C7 F1 :
0.3491

BEST NEW MODEL :
UNET_DIST3 — U-Net / EfficientNet-B4 dist3

BEST NEW F1 :
0.5672

BEST NEW RECALL :
0.7030

BEST NEW SMALL RECALL :
14 / 38

BEST NEW MISSED :
49

BEST NEW FP :
128

BEST NEW BOUNDARY F1 :
0.5020

BEST NEW MERGED :
9

BEST NEW CPU TIME :
1.213 s inference + 0.187 s postprocessing / patch 512x512

NEW MODEL BETTER THAN C7 :
YES

NEW SPECIALIZED TEACHER FOUND :
YES

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
14A11_HYBRID_TEACHER_AUTONOMOUS_LEARNING
