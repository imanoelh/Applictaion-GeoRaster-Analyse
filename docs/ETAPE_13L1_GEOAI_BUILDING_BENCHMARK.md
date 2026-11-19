# ÉTAPE 13L.1 — GeoAI advanced building footprint benchmark

**Date de l’audit :** 21 octobre 2026  
**Portée :** benchmark expérimental; aucune intégration en production.

## Résumé

L’API officielle `geoai.timm_segmentation_from_hub` de GeoAI 0.43.1 a exécuté le modèle WHU U-Net++ / EfficientNet-B4 sur les 16 mêmes patches Maxar que l’étape 13L. Les poids WHU déjà présents dans l’arborescence expérimentale ont été réutilisés; aucun poids WHU n’a été retéléchargé. L’inférence est passée sous Windows avec le Python 3.12.10 / PyTorch CPU du backend et un chemin Python expérimental isolé. Les fichiers produits sont uniquement sous `backend/data/models/building/experimental/benchmark_13L1/`.

Les masques et probabilités ont la même grille raster (512 × 512, CRS, transform) que leurs orthophotos sources sur les 16 patches. Les 16 GeoJSON RAW sont lisibles et leurs géométries sont valides. Le compte total de composantes est 454 pour WHU contre 177 pour MODEL_C dans le benchmark 13L; cette différence de sorties ne constitue pas un score de qualité ni une preuve que WHU a détecté davantage de bâtiments réels.

La variante `geoai.orthogonalize()` n’a pas été exécutée : l’environnement Python actif ne contient pas le jeu complet de dépendances GeoAI de géométrie (`leafmap`, `rioxarray`, ainsi que les dépendances qui en découlent). La fonction d’inférence WHU a pu être éprouvée en installant ses modules manquants uniquement sous le dossier expérimental. Je n’ai pas complété l’installation d’une pile SIG complète juste pour contourner cette lacune. Le panneau correspondant dans la contact sheet est explicitement marqué **NOT RUN**.

DIST3 a été audité sans télécharger ses poids. Hugging Face affiche actuellement une fiche publique CC-BY-4.0 et les fichiers `best.pth` (81,6 MB) et `model.onnx` (77,7 MB). Mais la fiche déclare que la revue d’attribution des données sources d’entraînement est encore en attente et explique que le dépôt est privé. Selon le critère d’exploitabilité de cette étape, DIST3 est rejeté pour ce benchmark, sans inférence. Le panneau de la contact sheet est marqué **REJECTED, not downloaded**.

Sans annotations TEST humaines validées, aucune précision, rappel, F1 ou IoU GeoRaster n’est rapporté. L’étape 13M contient toujours des annotations vierges; aucun label n’a été lu pour cette comparaison.

## Environnement GeoAI et compatibilité

| Élément | État constaté |
|---|---|
| Version publiée | `geoai-py 0.43.1` |
| Licence GeoAI | MIT |
| Python | Python 3.12.10, dans la plage déclarée par la version publiée (>=3.12) |
| Backend utilisé | PyTorch 2.8.0 CPU; torchvision 0.23.0 CPU; SMP 0.5.0; timm déjà présent |
| Windows / CPU | Inference helper exécuté en local sur Windows CPU |
| ONNX | La bibliothèque publie un module/extra ONNX, mais le WHU testé ici a été exécuté en PyTorch; aucun export ONNX du WHU n’a été produit ou validé |
| Disponibilité dans le backend de production | `geoai` n’était pas installé dans `backend/.venv`; le package et les dépendances manquantes à l’inférence ont été installés dans `backend/data/models/building/experimental/benchmark_13L1/geoai_package` uniquement |
| Orthogonalisation | Non exécutable dans cet environnement faute de la chaîne GeoAI géométrie complète, notamment `leafmap` / `rioxarray` |
| Plugin QGIS | Non utilisé. Il peut servir à l’inspection, au diagnostic et à l’annotation; il n’est pas requis par GeoRaster |

GeoAI n’est donc pas encore une dépendance backend prête à intégrer. L’inférence indépendante par Python a fonctionné, mais l’environnement GeoRaster courant ne fournit pas l’ensemble de la bibliothèque ni ses dépendances. La fonction WHU documentée utilise l’inférence par fenêtre; son helper reconstruit et recharge le modèle lors de chaque appel de fichier. Le temps mesuré ci-dessous est donc le temps du helper complet, chargement inclus, et non le temps pur d’un forward pass.

## Modèle WHU et preprocessing constaté

- Identifiant : `giswqs/whu-building-unetplusplus-efficientnet-b4`.
- Architecture : SMP U-Net++ avec encodeur EfficientNet-B4, 3 bandes, 2 classes, classes fond/bâtiment.
- Données du modèle : WHU Building Dataset, orthophotos aériennes déclarées à environ 0,3 m.
- Patch natif : RGB 512 × 512.
- Licence indiquée sur la fiche : Apache-2.0.
- Poids : checkpoint local déjà utilisé à l’étape 13L; chargé par l’API officielle depuis un cache Hub local alimenté avec ces fichiers locaux.
- Préprocessing dans la fonction GeoAI vérifiée : lit les bandes raster dans l’ordre source; si le maximum dépasse 1, divise les valeurs par 255; convertit en `float32`. Pas de normalisation ImageNet mean/std dans ce chemin d’inférence. Les patches Maxar ont trois bandes RGB et des valeurs uint8.
- Fenêtres 13L.1 : `window_size=512`, `overlap=0`, `batch_size=1`, `device="cpu"`. Les sources sont déjà des patches 512 × 512; chaque source passe donc une seule fenêtre sans chevauchement. Le seuil binaire est 0,50.
- Probabilités : GeoAI a enregistré deux bandes de probabilité normalisées; le masque binaire est écrit par le helper officiel. Les GeoJSON RAW ont ensuite été vectorisés à partir de ce masque par rasterio, connectivité 8, sans régularisation.

La fiche du modèle rapporte IoU/Dice sur son propre split WHU uniquement. Ces résultats ne sont pas transposés aux orthophotos Maxar de GeoRaster.

## Résultats d’exécution

| Mesure sur 16 patches identiques | Résultat |
|---|---:|
| Modèle WHU chargé par GeoAI | Succès; l’appel utilise le chargement strict par défaut de `load_state_dict` |
| Masques binaires | 16; valeurs `{0,1}`; taille 512 × 512 |
| Rasters de probabilité | 16; 2 bandes |
| Alignement masque/probabilités avec les sources | Exact pour les 16 (taille, transform affine, CRS) |
| GeoJSON RAW valides | 16/16 |
| Composantes polygonales WHU RAW | 454 au total |
| MODEL_C 13L, même ensemble | 177 composantes au total |
| Temps GeoAI WHU moyen, helper avec chargement | 3,510 s/patch |
| Temps GeoAI WHU moyen après la première tuile froide | 3,061 s/patch |
| Temps MODEL_C 13L moyen | 3,239 s/patch |
| Temps WHU 13L manuel, modèle chargé une seule fois | 2,578 s/patch |
| Pic mémoire GeoAI | 1 502 486 528 octets (1,40 GiB), working set du processus complet Python, pas du modèle isolé |
| Scores officiels calculés sur Maxar | Aucun; vérité terrain validée indisponible |

Le helper GeoAI complet est légèrement plus lent en moyenne que le chemin MODEL_C 13L, notamment parce qu’il recharge le checkpoint à chaque appel de patch. La comparaison d’inférence WHU 13L, avec le modèle déjà chargé une fois, est plus rapide que ce wrapper officiel. Ces temps sont issus de deux passages distincts sur le même CPU et doivent être lus comme une comparaison opérationnelle du code exécuté, pas comme un benchmark contrôlé de matériel.

### Lecture visuelle limitée

La contact sheet montre une plus grande couverture et davantage de composantes WHU sur plusieurs scènes résidentielles denses; les scènes vides/difficiles restent à zéro sur certaines tuiles. Cela peut refléter plus de petits objets candidats, des faux positifs, des séparations différentes ou des contours plus larges. Sans annotation de référence, on ne peut pas établir lesquels sont des toits réels, mesurer les bâtiments manqués/fusionnés, ni départager précisément le fit des contours. Le modèle WHU reste un candidat expérimental; la supériorité géométrique n’est pas démontrée.

## WHU orthogonalization

La documentation GeoAI expose `geoai.orthogonalize(input_path, output_path=None, epsilon=0.2, min_area=10, min_segments=4, area_tolerance=0.7, detect_triangles=True)`. L’exemple bâtiment officiel passe `epsilon=2.0`. Le test demandé n’a pas été exécuté; aucun polygone n’a donc été remplacé ou présenté comme « WHU orthogonalisé ». La contact sheet réserve une colonne à cette variante avec l’état **NOT RUN**. Il faut d’abord valider l’environnement complet et relancer la comparaison en gardant le masque et les polygones RAW comme référence.

## DIST3 — U-Net EfficientNet-B4 dist3

La fiche décrit trois sorties (`mask`, distance normalisée par instance, frontière), entrée 256 × 256, normalisation ImageNet et séparation par watershed avec les seeds issus de `(distance > 0.5) & mask`. Elle indique un seuil de masque 0,50. Les chiffres WHU/HOTOSM publiés dans sa fiche sont propres à ses jeux d’évaluation et ne sont pas un benchmark Maxar GeoRaster.

Le dépôt Hugging Face est actuellement consultable publiquement et liste les poids PyTorch et ONNX. Cependant, le texte de licence et de provenance mentionne une attribution en attente pour des sources tierces (Open Buildings / Microsoft Building Footprints) et affirme que le dépôt est privé pour cette raison. Aucun fichier de poids n’a été téléchargé. DIST3 n’a pas été exécuté et est **REJECTED FOR THIS BENCHMARK** en attendant que la provenance et les conditions d’usage soient clarifiées par le détenteur du modèle.

## Comparaison, décision et reprise

| Pipeline | Résultat ici | Conclusion permise |
|---|---|---|
| MODEL_C / ONNX Runtime CPU | Baseline 13L disponible; 3,239 s/patch; 177 composantes sur 16 tuiles | Reste la baseline stable, inchangée |
| WHU RAW / helper GeoAI | Inférence réalisée; 3,510 s/patch chargement inclus; 454 composantes | Candidat visuel à valider par vérité terrain; aucune promotion |
| WHU + `geoai.orthogonalize()` | Pas exécuté, dépendances non disponibles dans l’environnement backend courant | Pas de conclusion sur contours orthogonalisés |
| DIST3 + watershed | Poids non téléchargés, provenance à résoudre | Rejeté pour ce benchmark; aucune comparaison d’inférence |

**Meilleur masque démontré :** aucun modèle ne peut être déclaré meilleur sur Maxar sans vérité terrain. WHU est le candidat visuel à examiner ensuite.  
**Meilleurs footprints :** non déterminés; orthogonalisation non exécutée et aucune annotation de référence.  
**Meilleure séparation d’instances :** non déterminée; DIST3 non exécuté.  
**Meilleure vitesse parmi les chemins exécutés ici :** MODEL_C (3,239 s/patch); WHU manuel chargé une seule fois (étape 13L, 2,578 s/patch) est plus rapide que le helper GeoAI complet.  
**Décision :** `NEED_GROUND_TRUTH`; garder MODEL_C comme baseline et laisser WHU expérimental.

## Intégrité et modifications

- Aucun fichier du backend production, adapter, registry, indices, postprocessing, polygonisation, exports ou frontend n’a été modifié.
- MODEL_C n’a pas été édité; son checkpoint conserve le SHA-256 `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555`.
- Les masques WHU GeoAI sont identiques pixel à pixel aux masques WHU du benchmark 13L sur les 16 patches.
- Aucun poids DIST3 téléchargé; aucun fine-tuning; aucun changement aux labels 13M verrouillés.
- Fichiers nouveaux : scripts de benchmark/validation/contact sheet, package expérimental isolé et sorties WHU sous le dossier expérimental `benchmark_13L1`.
- Aucune suite de tests complète n’a été lancée, car cette étape n’a pas modifié le code produit.

## Sources officielles consultées

- [GeoAI 0.43.1 sur PyPI — licence, version, Python](https://pypi.org/project/geoai-py/0.43.1/)
- [Installation GeoAI — notes Windows et méthodes d’installation](https://github.com/opengeos/geoai/blob/main/docs/installation.md)
- [API `timm_segmentation_from_hub` et détails d’inférence](https://opengeoai.org/timm_segment/)
- [Exemple officiel de détection bâtiment WHU et paramètres `orthogonalize`](https://opengeoai.org/examples/building_detection_whu/)
- [Carte de modèle WHU](https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4)
- [Carte DIST3 : architecture, usage, limites et provenance](https://huggingface.co/nilsho01/unet-effb4-dist3-buildings)
- [Fichiers publiés DIST3 et tailles indiquées](https://huggingface.co/nilsho01/unet-effb4-dist3-buildings/tree/main)

## Résultats et artefacts locaux

- Script GeoAI WHU : [benchmark_geoai_13L1.py](../scripts/benchmark_geoai_13L1.py)
- Validation des sorties : [validate_geoai_13L1_outputs.py](../scripts/validate_geoai_13L1_outputs.py)
- Rendu contact sheet : [render_geoai_13L1_comparison.py](../scripts/render_geoai_13L1_comparison.py)
- Contact sheet : `backend/data/models/building/experimental/benchmark_13L1/outputs/contact_sheet_13L1.png`
- Résultats par patch : `backend/data/models/building/experimental/benchmark_13L1/outputs/whu_geoai/results.json`
- Résumé temps/mémoire : `backend/data/models/building/experimental/benchmark_13L1/outputs/whu_geoai/summary.json`
- Contrôles grille / géométries / moyennes : `backend/data/models/building/experimental/benchmark_13L1/outputs/validation_summary.json`

GEOAI VERSION :
0.43.1

GEOAI BACKEND USABLE :
NO — inference validated in isolated benchmark path; production backend lacks GeoAI and the complete geometry dependency chain

WHU MODEL :
VALIDATED — official helper inference completed on all 16 patches

WHU RAW BOUNDARIES :
454 valid RAW component polygons; visually broader/more numerous on dense scenes than MODEL_C, but boundary accuracy not measurable without reference labels

WHU ORTHOGONALIZED :
NOT RUN — `leafmap` / `rioxarray` dependency chain unavailable in current runtime

DIST3 MODEL :
REJECTED — no weights downloaded; source-data attribution/license provenance unresolved

BEST MASK :
NOT DETERMINED — WHU is an experimental visual candidate; no GeoRaster ground truth scores

BEST POLYGONS :
NOT DETERMINED — orthogonalization was not executed; no validated roof truth

BEST BUILDING SEPARATION :
NOT DETERMINED — DIST3 not run

BEST SPEED :
MODEL_C official end-to-end path among executed 13L.1 routes (3.239 s/patch); WHU manual 13L with one model load was 2.578 s/patch

MODEL_C :
UNCHANGED

PRODUCTION :
UNCHANGED

RECOMMENDED MODEL :
KEEP MODEL_C as baseline; keep WHU experimental pending ground-truth review

NEXT STEP :
GROUND TRUTH VALIDATION
