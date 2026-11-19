# ÉTAPE 13N.2 — Real Orthophoto Hybrid User Test

Date : 2026-10-23

## Résumé

MODEL_C, MODEL_D et MODEL_E ont été comparés sur la même fenêtre réelle Maxar 2024 de 4096 × 4096 pixels, par le pipeline complet de résultats GeoRaster. Les trois requêtes ont utilisé le même raster validé, la même grille et le même réglage (tuiles 512 px, recouvrement 50 %, seuil 0,50, minimum 4 pixels, connectivité 8, sans simplification).

MODEL_E a terminé le pipeline et ses quatre exports. Il augmente la surface détectée en combinant les sorties de C et D, mais prend 22 min 55 s sur cette seule fenêtre et conserve les détections douteuses observées chez les deux modèles. Recommandation : garder MODEL_C par défaut, ne pas promouvoir MODEL_E et ne pas lancer le raster complet.

Les observations visuelles ci-dessous sont qualitatives : aucune vérité terrain humaine n’existe pour cette fenêtre. Elles ne constituent pas des mesures de précision, rappel ou F1.

## Raster et reproductibilité

- Source : `test-data/Oct 07, 2024/24OCT07075514-S3DS-200009702746_01_P001_COG.tif`.
- Fenêtre lue sans resampling : colonnes 2048–6143, lignes 2048–6143.
- Dérivé RGB identique pour les trois modèles : [`maxar_2024_window_x2048_y2048_4096_rgb.tif`](../test-data/diagnostics/13N2/maxar_2024_window_x2048_y2048_4096_rgb.tif).
- Dimensions : 4096 × 4096, 3 bandes uint8, EPSG:4326.
- Transform : `[3.072320997236484e-06, 0, 39.78542605015135, 0, -3.072320997236484e-06, 21.41943549782966, 0, 0, 1]`.
- Bounds : `[39.78542605015135, 21.40685127102498, 39.798010276956035, 21.41943549782966]`.
- RGB : bandes source R/G/B = 5/3/2, stretch p2p98 fixe précédemment validé : `[1778,1519,1135]` → `[7881,6829,5638]`.
- SHA256 du GeoTIFF RGB : `51110543bced9c0bb9741570bb489dc345a591f32d467c4d8df4977db97b3f03`.
- Identifiant utilisé par les trois requêtes : `ai-ortho-51110543bced-001127b57045-f13b1593c67f`.
- Les réponses C, D et E portent toutes cette même grille, ce CRS et ces bounds.

La fenêtre contient des quartiers denses, des bâtiments plus isolés, un grand ensemble de toits industriels, des routes, des ombres et du terrain ouvert. Le raster complet 96,5 MP n’a pas été exécuté.

## Paramètres et moteurs

| Moteur | Identifiant | Architecture et moteur | Tuiles traitées | Statut registre |
|---|---|---|---:|---|
| MODEL_C | `spacenet2_deeplab` | Torchvision DeepLabV3 / ResNet-50, ONNX Runtime | 225 | Défaut |
| MODEL_D | `whu_unetplusplus_effb4` | WHU U-Net++ / EfficientNet-B4, PyTorch | 225 | Experimental |
| MODEL_E | `hybrid_model_c_model_d` | Union binaire C + D, polygonisation commune | 225 + 225 | Experimental |

Le registre exposé par le backend 8011 indique `default=true` uniquement pour MODEL_C. MODEL_D et MODEL_E sont `default=false`. Aucun changement du modèle par défaut n’a été fait.

## Résultats réels

Le temps total est le temps extérieur mesuré pour chaque requête de résultats, incluant le pipeline et la sérialisation. 4096² = 16,78 MP.

| Mesure | MODEL_C | MODEL_D | MODEL_E |
|---|---:|---:|---:|
| Candidats / polygones | 892 | 2 187 | 1 733 |
| Surface totale | 322 605,68 m² | 276 168,26 m² | 436 725,13 m² |
| Surface moyenne | 361,67 m² | 126,28 m² | 252,01 m² |
| Temps total | 800,71 s (13 min 21 s) | 606,59 s (10 min 07 s) | 1 375,32 s (22 min 55 s) |
| Temps / MP | 47,73 s/MP | 36,16 s/MP | 81,98 s/MP |
| Pic mémoire | 1 270,2 MiB | 2 523,0 MiB* | 2 502,75 MiB** |

\* MODEL_D a été mesuré dans le processus de benchmark où MODEL_C était déjà chargé. C’est le pic du processus cumulatif, pas une mesure isolée de D.

\** Pic `PeakWorkingSet64` du processus backend 8011 après la requête E, avec les deux modèles chargés. Le collecteur PowerShell dédié n’avait pas été armé avant le marqueur de démarrage; cette valeur OS post-run est utilisée à la place.

Dans la réponse E, les temps internes sont C = 754,91 s et D = 523,83 s; le temps total API est 1 362,23 s, et le temps extérieur mesuré est 1 375,32 s. Le champ `processing_metadata.model_c_inference_time_ms` et son équivalent D renvoient des valeurs en secondes alors que leur suffixe indique des millisecondes; le champ de temps présenté dans l’interface doit donc être corrigé séparément. Ce point n’a pas été modifié dans cette étape.

Le mode hybride prend 1,72× le temps de C et 2,27× celui de D. Sa surface totale est supérieure de 35 % à C et 58 % à D. E produit moins de polygones que D malgré l’union, car des régions adjacentes se regroupent dans la polygonisation commune.

## Vérification des masques, GeoJSON et de l’union

Les masques C et D sont des GeoTIFF binaires 4096 × 4096 (`{0,1}`), avec CRS, transform et bounds identiques au RGB. Chaque GeoJSON rasterisé sur cette même grille reproduit son masque d’origine exactement : XOR = 0 pixel pour C et D.

La réponse de MODEL_E confirme `fusion_method = UNION`, les modèles composants C et D, 225 tuiles par moteur, une polygonisation commune de 4 777,09 ms et 1 733 entités. Le GeoJSON E rasterisé sur la grille source diffère de l’union C OR D de 11 pixels sur 16 777 216 (IoU = 0,99999727), une différence de rasterisation sur les frontières. L’alignement est donc validé sans décalage spatial détectable.

Le service public de résultats ne retourne pas le masque global intermédiaire E. L’artefact `mask_model_e_union_from_c_or_d.tif` contient l’union pixel à pixel des masques binaires C et D; `mask_model_e_rasterized_geojson.tif` est le masque QA reconstruit depuis les polygones E réellement retournés. Cette limite de capture est conservée explicitement.

## Inspection visuelle qualitative

La planche est enregistrée dans [`contact_sheet_13N2_C_D_E.png`](../test-data/diagnostics/13N2/run/contact_sheet_13N2_C_D_E.png), et les trois contours superposés dans [`contours_C_D_E.png`](../test-data/diagnostics/13N2/run/contours_C_D_E.png).

- **Petits bâtiments : MODEL_D.** Il dessine plus de petites toitures dans les secteurs résidentiels.
- **Urbain dense : MODEL_D / MODEL_E.** D est plus détaillé; E couvre davantage d’emprises en cumulant les détections.
- **Grands bâtiments : MODEL_C / MODEL_E.** C propose des emprises plus larges; E conserve plus de couverture, mais inclut aussi les subdivisions douteuses des grandes toitures.
- **Toits complexes : MODEL_D.** Les détails apparaissent mieux, avec un risque accru de fragments.
- **Qualité de contours : MODEL_D, légère préférence visuelle.** Cette appréciation n’est pas validée par des annotations humaines sur cette fenêtre.
- **Faux positifs apparents : C = MEDIUM, D = HIGH, E = HIGH.** Les bandes de toits industriels et quelques détections dans des secteurs ouverts sont visuellement douteuses; sans GT, ce classement demeure indicatif.
- **Fragmentation : C = MEDIUM, D = HIGH, E = MEDIUM.** D découpe plus de détails; l’union E regroupe certaines zones, mais étend aussi les emprises.

E apporte de la couverture utile supplémentaire dans l’habitat dense, mais augmente les zones douteuses sur les toitures industrielles et le coût passe à près de 23 minutes. Son intérêt utilisateur est **MEDIUM**, et son coût pour une fenêtre de seulement 16,8 MP est **TOO_SLOW** pour en faire une option recommandée sur cette base non annotée.

## Frontend et exports

- Backend 8011 : démarré avec le code actuel; modèle list endpoint = HTTP 200, C par défaut, D/E expérimentaux.
- Frontend 5184 : page d’accueil = HTTP 200; `.env.local` dirige les appels vers `http://127.0.0.1:8011`.
- `BuildingDetectionPanel` contient les libellés C, D et E, l’état de chargement `aria-busy` et le libellé hybride expérimental. Le client utilise `fetch` sans timeout artificiel; l’appel E a abouti en 1 375 s.
- `GET /api/ai/raster/{raster_id}/preview.png` : HTTP 200, image PNG reçue.
- Le composant Leaflet comprend `ImageOverlay` et le rendu GeoJSON. La carte n’a pas été manipulée dans un navigateur : l’environnement CUA n’expose aucun navigateur/app, donc l’alignement visuel dans l’interface ne peut pas être déclaré validé à l’écran.
- Exports MODEL_E : GeoJSON HTTP 200 (1 733 entités, 8,92 MB); CSV HTTP 200 (CSV de statistiques, une ligne de données); metadata JSON HTTP 200; ZIP HTTP 200 avec `building_candidates.geojson`, `building_metadata.json` et `building_statistics.csv`.
- Les fichiers d’export et les réponses brutes sont dans `test-data/diagnostics/13N2/run/`.

## Runtime, changements et limites

Le premier upload a révélé que l’environnement système `PROJ_LIB` pointait vers la base ancienne de PostgreSQL. Le processus backend 8011 a été redémarré avec les bases PROJ/GDAL de sa venv Rasterio; le fichier de configuration du projet n’a pas été modifié. Les ports 5184 et 8011 répondent après le benchmark. Le port 8010 n’a pas été touché.

Aucun modèle, checkpoint, traitement, registre, export historique ou source métier n’a été modifié. Aucun fine-tuning, test complet de 96,5 MP ou test suite n’a été lancé. Les artefacts QA sont limités à `test-data/diagnostics/13N2/`.

Le contrôle visuel du frontend interactif reste à faire dans un navigateur disponible. La sélection modèle, l’appel API, le preview PNG, le FeatureCollection, les statistiques et les quatre exports ont été contrôlés via l’API/le code.

## Décision

La complémentarité C/D existe visuellement, mais le critère de coût opérationnel bloque MODEL_E sur ce test : 22 min 55 s pour 16,8 MP, pic processus ~2,44 GiB, faux positifs apparents élevés et aucune vérité terrain locale. Ne pas lancer le raster complet et ne pas promouvoir E. Garder MODEL_C comme défaut; conserver D et E expérimentaux en attendant une validation humaine représentative et un gain de performance.

TEST RASTER :
Maxar 2024, fenêtre x=2048 y=2048, raster RGB GeoTIFF `maxar_2024_window_x2048_y2048_4096_rgb.tif`

DIMENSIONS :
4096 x 4096 (16.78 MP)

MODEL_C CANDIDATES :
892

MODEL_D CANDIDATES :
2187

MODEL_E CANDIDATES :
1733

MODEL_C AREA :
322605.68 m2

MODEL_D AREA :
276168.26 m2

MODEL_E AREA :
436725.13 m2

MODEL_C TIME :
800.71 s (47.73 s/MP)

MODEL_D TIME :
606.59 s (36.16 s/MP)

MODEL_E TIME :
1375.32 s (81.98 s/MP)

MODEL_C RAM :
1270.2 MiB

MODEL_D RAM :
2523.0 MiB (cumulative process with MODEL_C resident)

MODEL_E RAM :
2502.75 MiB (backend `PeakWorkingSet64`)

SMALL BUILDINGS :
MODEL_D

DENSE URBAN :
MODEL_E

LARGE BUILDINGS :
MODEL_E

COMPLEX ROOFS :
MODEL_D

BOUNDARY QUALITY :
MODEL_D (qualitative, slight preference)

FALSE POSITIVES :
C=MEDIUM
D=HIGH
E=HIGH

FRAGMENTATION :
C=MEDIUM
D=HIGH
E=MEDIUM

MODEL_E USER VALUE :
MEDIUM

MODEL_E PERFORMANCE :
TOO_SLOW

MAP DISPLAY :
FAILED — frontend non inspectable dans un navigateur de cette session; endpoints et données API validés

EXPORTS :
VALIDATED

DEFAULT MODEL :
MODEL_C

MODEL_D :
EXPERIMENTAL

MODEL_E :
EXPERIMENTAL

FINAL DECISION :
MODEL_E_TOO_SLOW

NEXT STEP :
KEEP MODEL_C DEFAULT
