# Étape 13E.1 + 13F — MODEL_C par défaut et stabilisation

Date de validation : 19 octobre 2026. Cette étape fait de MODEL_C le modèle choisi par défaut pour Building Detection après la validation backend et E2E requise. MODEL_A est conservé et reste accessible par identifiant explicite `unet_resnet34`. Aucun échec de MODEL_C ne déclenche un repli silencieux vers MODEL_A.

MODEL_C reste signalé `EXPERIMENTAL` dans les métadonnées et les résultats : l’étape valide l’intégration et la reproductibilité technique, pas la précision scientifique. La ground truth reste différée.

## Environnement backend

La suite a été exécutée avec l’environnement virtuel déjà installé de la copie `Georaster-03-10`, sans y écrire et sans installer ou modifier de versions. Le `.venv` local de `Georaster-19-10` ne contient pas les dépendances backend. Versions vérifiées : Python 3.12.10, PyTorch 2.8.0+cpu, Torchvision 0.23.0+cpu, NumPy 2.5.4, Rasterio 1.5.2, Affine 3.0.1, Shapely 2.2.0 et pytest 7.4.0.

La machine de benchmark a 8 CPU logiques et environ 23,9 Go de mémoire physique. PyTorch/oneDNN MKLDNN est disponible et activé. Une exécution batch=4 a observé environ 1,88 Go de working set; batch=1 était autour de 0,82 Go. La mesure mémoire est un échantillon du processus Windows pendant les runs, pas une mesure instrumentée d’allocation par opérateur.

## Checkpoints

| Modèle | Taille | SHA256 final | Statut |
| --- | ---: | --- | --- |
| MODEL_A `unet_best.pt` | 97 919 546 octets | `6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987` | Présent, hash inchangé, backend conservé |
| MODEL_C `best_deeplab.pth` | 168 357 171 octets | `170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555` | Présent, strict load réussi |

L’adapter construit Torchvision DeepLabV3 / ResNet-50 et exécute `eval()` avec `torch.inference_mode()`. Le registre conserve une seule instance par choix de modèle; les chargements ultérieurs réutilisent le modèle en mémoire. Le test vérifie que `load_count` ne progresse pas sur un second `load()`.

## Baseline et optimisation mesurées

Rasters : `test-data/validation-results/maxar_rgb_derivatives/maxar_2025_rgb_p2p98.tif`, scène Maxar 2025 2048×2048, 3 bandes RGB uint8, EPSG:32637, résolution 0,35 m. Configuration commune : seuil 0,50, overlap 20 %, tuiles 512×512, 25 tuiles.

Baseline mesurée avant optimisation : batch=1 et PyTorch réglé à 2 threads pour correspondre au benchmark historique. Optimisation mesurée : PyTorch réglé à 4 threads et batch=4. Le réglage de threads est configurable par `SPACENET2_TORCH_THREADS` (défaut mesuré : 4; plafonné au nombre de CPU disponibles). Le batch est borné à 4 tuiles; les autres modes d’inférence conservent batch=1.

| Étape | Baseline | Optimisée finale | Méthode |
| --- | ---: | ---: | --- |
| Préparation locale raster | 0,061 s | 0,072 s | Validation/copie du GeoTIFF |
| Chargement froid MODEL_C | 4,530 s | 4,929 s | Premier `load()` et strict load |
| Ouverture/lecture métadonnées raster | <0,001 s | <0,001 s | Ouverture Rasterio |
| Calcul min/max RGB global | 0,357 s | 0,380 s | Fenêtres 1024 px, NoData exclu |
| Tiling + inférence + fusion jusqu’au masque | 219,933 s | 144,037 s | `build_building_mask` complet |
| Dont temps modèle (25 tuiles) | 217,123 s | 140,897 s | Somme chronométrée des appels d’inférence |
| Temps modèle par tuile | 8,685 s | 5,636 s | Inférence / 25 |
| Polygonisation | 0,351 s | 0,378 s | Service de polygonisation |
| Statistiques, résultat et sérialisation | 0,170 s | 0,199 s | `BuildingResultsService` |
| Exports GeoJSON + CSV + metadata JSON + ZIP | 0,065 s | 0,078 s | Sérialisation des quatre formats |
| **Temps total mesuré** | **225,468 s** | **150,073 s** | Préparation à la fin des exports |

Le gain total mesuré est **1,50×** (225,468 / 150,073); l’inférence seule est **1,54×** plus rapide. Une autre exécution optimisée complète a donné 141,611 s au total et 131,824 s d’inférence; la variabilité observée est documentée, aucun minimum n’est présenté comme temps garanti.

Le temps `build_building_mask` inclut le parcours lazy du générateur d’inférence et ne peut donc pas être interprété comme temps de post-traitement seul. Pour isoler les opérations, un replay des probabilités de référence sur les mêmes 25 fenêtres chevauchantes a mesuré : lecture des rasters diagnostic 0,210 s, tiling/lectures RGB 0,303 s, normalisation RGB des 25 tuiles 0,168 s, accumulation/fusion 0,081 s, seuillage/nettoyage/composantes 2,268 s, polygonisation 0,206 s, statistiques/résultat/sérialisation 0,183 s. Ce replay isole la fusion et le seuillage sans refaire l’inférence; ces durées ne sont pas additionnées une seconde fois au total E2E.

## Essais d’optimisation et équivalence

- **Batch CPU** sur quatre tuiles Maxar fixées : batch=1 **7,861 s/tuile**, batch=2 **7,094 s/tuile**, batch=4 **6,951 s/tuile**. Les masques au seuil 0,50 sont identiques sur les quatre tuiles; l’écart maximal de probabilité batch=4 vs batch=1 est `1,1921e-7`.
- **Threads CPU** sur deux tuiles : 1 thread **14,180 s/tuile**, 2 threads **9,174 s/tuile**, 4 threads **5,645 s/tuile**. Les masques binaires sont identiques; l’écart maximal de probabilité 4 vs 2 threads est `1,79e-7`.
- **channels_last** : **10,776 s/tuile** sur quatre tuiles contre 7,861 s/tuile en format standard; écart maximal `1,85e-6`, masques identiques. C’est plus lent, donc non utilisé.
- **MKLDNN** est disponible/actif; aucun changement global backend n’a été apporté. `torch.compile` et ONNX n’ont pas été utilisés.
- Le min/max global est conservé par instance d’adapter, raster id, chemin, mtime, taille et bandes. Le test remplace `rasterio.open` par une erreur et vérifie qu’un second accès aux mêmes statistiques réutilise le cache.
- L’inférence continue à lire les raster en fenêtres. Le memmap, la fusion sur disque pour les grandes images et le seuillage par fenêtres restent présents.

Sur l’E2E batch=4 final, le pipeline a produit 25 tuiles, **156 762 pixels positifs**, **124 candidats**, surface totale **19 203,345 m²**, périmètre total **6 232,8 m**. La comparaison GeoJSON en EPSG:4326 avec le benchmark antérieur donne **124/124 géométries identiques**, **124/124 propriétés géométriques essentielles identiques** et écart de surface maximal **0 m²**. Le seuil reste 0,50 et le ratio d’overlap 20 %.

Les exports réels ont été produits : GeoJSON (492 939 octets), CSV (704), metadata JSON (1 311) et ZIP (149 521). L’API export reste limitée aux résultats Building.

## Bascule et validation

- Le registre, les requêtes backend omettant `model_id` et les paramètres frontend par défaut choisissent maintenant `spacenet2_deeplab`.
- L’interface Building normale n’affiche plus le sélecteur A/C; elle annonce DeepLabV3 ResNet-50, utilise les tuiles 512 et garde le seuil 0,50 verrouillé. Le parseur conserve la lecture des anciens résultats dont l’identifiant est absent comme MODEL_A pour ne pas réétiqueter des données historiques.
- MODEL_A est conservé backend et se choisit explicitement par `model_id="unet_resnet34"`. Aucun fallback automatique n’existe si MODEL_C est demandé et indisponible.
- Suite backend : **227 passed, 0 failed, 0 collection errors**.
- Frontend : tests complets réussis; build Vite client et SSR réussis. Le build émet seulement l’avertissement existant sur certains chunks >500 kB.
- Le test de grande image MODEL_C n’a pas été lancé faute de scène >2048 appropriée; les tests backend de memmap/fusion disk-backed/seuillage windowed passent.
- Ground truth différée; aucun fine-tuning ni Building Change Detection n’a été entrepris. Poids A et C inchangés. GEE, indices, classifications, change detection historique, mode offline, AOI et exports non-Building inchangés.
