# Building AI — statuts des moteurs

Baseline 13P, 23 octobre 2026. La source de vérité exécutable des rôles, noms et statuts est `backend/app/ai/config/building_model_catalog.py`. Le registry et les descriptifs runtime utilisent ce catalogue. Les anciens rapports sont des observations historiques ; leurs anciens libellés ne définissent pas le statut actuel.

| Modèle | model_id | Architecture | Moteur | Statut / rôle |
|---|---|---|---|---|
| MODEL_A | `unet_resnet34` | U-Net / ResNet-34 | PyTorch CPU | **LEGACY** — référence conservée |
| MODEL_C | `spacenet2_deeplab` | DeepLabV3 / ResNet-50 | ONNX Runtime CPU par défaut | **PRODUCTION** — Standard Building Detection, seul défaut |
| MODEL_D | `whu_unetplusplus_effb4` | WHU U-Net++ / EfficientNet-B4 | PyTorch CPU | **EXPERIMENTAL** — référence, debug, reproductibilité |
| MODEL_D_ONNX | `whu_unetplusplus_effb4_onnx` | WHU U-Net++ / EfficientNet-B4 | ONNX Runtime CPU | **EXPERIMENTAL** — Experimental High-Recall Detection |
| MODEL_E | `hybrid_model_c_model_d` | Union binaire C + D | Composite C ONNX + D PyTorch | **BENCHMARK_ONLY** — R&D |

Le qualificatif « High-Recall » décrit le rôle expérimental envisagé. Il ne garantit pas une meilleure précision ou un meilleur rappel sur une nouvelle orthophoto. Le statut PRODUCTION de C décrit son usage logiciel ; les résultats conservent `scientific_accuracy_status=NOT_VALIDATED`.

## Décision, qualité et performances

| Modèle | Observations et limites | Performance de référence | Motif du statut |
|---|---|---|---|
| A | Modèle historique préservé ; aucune nouvelle évaluation 13P | Non remesurée | Compatibilité et référence legacy |
| C | Pipeline stable ; limites de contours et bâtiments manqués documentées en 13J/13M ; aucune garantie scientifique générale | Raster réel ~96,5 MP : **~26 min**, référence historique fournie ; non rejouée en 13P | Standard déjà intégré et validé techniquement |
| D | Couverture supérieure sur certains patches, avec davantage de composantes supplémentaires ; GT 13M approximative/réparée | Raster complet : **3658,85 s / 60,98 min**, 7313 candidats (13N.3) | Trop lent pour le workflow normal ; utile pour la référence PyTorch |
| D_ONNX | Comportement quasi équivalent à D : 4 pixels différents sur le test 4096² de 13O ; même nombre de candidats sur le raster complet | **36,39 min**, 1440 tuiles, 7313 candidats ; pic RSS 1926,1 MiB (13O.1) | Optimisation réussie, mais classe SLOW ; aucune promotion |
| E | L’union ajoute de la couverture et conserve aussi les détections douteuses des composants | **~22 min 55 s sur 4096²** (13N.2) | Trop coûteux ; benchmark uniquement |

Les durées historiques ne couvrent pas toutes les mêmes étapes ni les mêmes grilles. Elles restent des références attribuées à leurs rapports, pas un nouveau classement de performance 13P. Les mesures de 13M.1B sont un benchmark d’ingénierie sur une GT approximative, pas des scores scientifiques officiels.

## Usage et disponibilité

L’interface normale propose uniquement **Standard Building Detection (MODEL_C)**. Aucun panneau de moteurs R&D n’a été ajouté. D, D_ONNX, E et A restent accessibles par leur `model_id` explicite dans l’API pour les usages autorisés de référence/R&D. Aucun moteur expérimental n’est appelé par défaut ou en secours.

`GET /api/ai/inference/models/building` décrit les cinq moteurs : identifiants, nom, architecture, moteur, statut, sources, taille d’entrée, seuil, préprocessing et disponibilité. `AVAILABLE` vérifie la présence des fichiers et des modules ; le strict load vérifie ensuite les hashes et le contrat runtime. Une ressource expérimentale absente produit une erreur sur sa sélection explicite et laisse C indépendant.

Les sources de poids restent dans `backend/data/models/building/`. Les chemins contenant `experimental/` sont conservés pour ne pas déplacer les artefacts ; ce nom de dossier ne détermine pas le statut logiciel de C.

- A : `kastela-dof5/unet_best.pt` ; préprocessing legacy intact, grille 640 et entrée modèle effective 512 dans la configuration actuelle.
- C : `experimental/spacenet2-deeplab/best_deeplab.pth` et `onnx/spacenet2_deeplab_main.onnx` ; RGB min-max global du raster, 512 px, seuil 0,5.
- D : `experimental/whu_unetplusplus_effb4/model.pth` ; RGB float32 / 255, 512 px, recouvrement 50 %, seuil 0,5.
- D_ONNX : même poids source que D et `onnx/model.onnx` ; même préprocessing, taille et recouvrement que D, 4 threads ONNX.
- E : sources C + D, préprocessing propre à chaque composant, union binaire à seuil 0,5, 512 px et recouvrement 50 %.

L’override diagnostique existant `SPACENET2_ENGINE=pytorch` est préservé. Le catalogue le signale ; le défaut en son absence reste ONNX. Aucune bascule silencieuse n’existe si un artefact manque.

Les résultats et l’export de métadonnées indiquent le `model_id`, le nom affiché, l’architecture, le moteur effectif, le statut, le seuil, le temps de traitement en secondes et le hash du checkpoint. Les noms internes historiques de modèle/version sont préservés pour la traçabilité.

Références : `ETAPE_13M1B_FAST_MODEL_COMPARISON.md`, `ETAPE_13N2_REAL_ORTHOPHOTO_HYBRID_USER_TEST.md`, `ETAPE_13N3_MODEL_D_LARGE_RASTER_USER_TEST.md`, `ETAPE_13O_MODEL_D_PERFORMANCE_OPTIMIZATION.md`, `ETAPE_13O1_MODEL_D_ONNX_FULL_RASTER_VALIDATION.md`.
