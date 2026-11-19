# ÉTAPE 14A.7A — Préparation de la GT de validation supplémentaire

## Résultat

14 nouveaux patches 512×512 sont prêts pour annotation humaine : 3 RESIDENTIAL, 4 DENSE, 3 INDUSTRIAL, 2 DIFFICULT, 2 ROAD_BARE_SOIL. Aucun modèle, entraînement ou fine-tuning lancé. Aucun masque GT généré. GT initiale : 0 entité Polygon.

Dossier : `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_validation_expansion/`.

## Audit des 8 recommandations 14A.7

Le rapport `docs/ETAPE_14A7_EXTENDED_INTERNAL_VALIDATION_MODEL_C6.md` et son inventaire ont été relus. Les 8 fichiers existent, leurs pixels sont lisibles, leurs dimensions/bandes/CRS/transforms et SHA256 sont consignés dans `manifests/14A7_validation_manifest.json`.

| Anciens candidats VAL | Origine | Décision |
|---|---|---|
| 14A2_2024_03, 14A2_2025_03 | 14A2_expansion/val/rgb/ | Exclus : recouvrement avec le ROI historique 13L3 AOI_03_dense_urban |
| 14A2_2024_07, 14A2_2025_07 | 14A2_expansion/val/rgb/ | Exclus : recouvrement avec 13L3 AOI_04_adjacent_roofs |
| 13R_industrial_005_06656_03072 | maxar_v1/industrial_targeted_13R/images/val/ | Exclu : sélection TRAIN effective du manifest corrigé 13R1B pour F2 |
| 13R_industrial_011_08192_06656 | même dossier | Même exclusion |
| 13R_industrial_017_05120_08192 | même dossier | Même exclusion |
| 13R_industrial_023_01024_01536 | même dossier | Même exclusion |

Le champ historique `split=val` de certaines entrées 13R ne reflète pas leur présence dans le tableau `train` réellement sélectionné. Les flags C3/C4/C5/C6 restent NO pour ces quatre fichiers ; l'exposition F2 est indiquée séparément dans le JSON. Les 8 ne sont pas ajoutés au projet d'annotation. Ils restent référencés avec ELIGIBLE=NO ; aucune ancienne donnée n'est changée.

## Audit des nouvelles zones

La couverture des manifests et du code C2/C3/C4/C5/C6, calibration, 14A.1 à 14A.6 et historiques 13M/13Q/13R/13L est conservée dans `qa/14A7A_historical_manifest_coverage.json`, avec chemins et hashes. Les footprints des petits RGB historiques et les emprises déclarées des anciens tests sont protégés conservativement, y compris lorsque les anciens catalogues ne correspondent pas aux géoréférencements réels.

136 emprises protégées ; recherche de fenêtres 512×512 dans le grand RGB existant ; rejet de toute intersection avec les zones protégées dilatées de 20 m. 90 fenêtres examinées, 68 rejetées, 22 admissibles au filtrage spatial, puis 14 retenues après examen de la planche RGB. Les 14 fenêtres sont mutuellement disjointes. Les preuves sont dans `qa/14A7A_protected_footprints.json`, `qa/14A7A_screening_candidates.json`, `qa/14A7A_RGB_scene_screening.png`.

Source : `backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif`, acquisition Maxar du 28 juillet 2025. Les fenêtres et SHA256 sont inscrits dans le manifest. Lecture complète, 3 bandes uint8, 512×512, égalité exacte des pixels avec la fenêtre parent, transform et CRS conservés, sans rééchantillonnage.

**Limite scientifique :** même orthophoto et grand parent que certains crops historiques. Aucune emprise de crop TRAIN/calibration/benchmark connue n'est réutilisée, mais il s'agit d'une validation géographiquement disjointe INTERNE à une acquisition, pas d'une validation externe indépendante par acquisition. La proximité de scènes et les dépendances d'acquisition limitent la généralisation mesurable. La qualification INDUSTRIAL est visuelle/provisoire, notamment pour le compound du patch 09 ; elle ne certifie pas l'usage des bâtiments. Les patches DIFFICULT et ROAD_BARE_SOIL ne sont pas déclarés négatifs automatiquement.

## Patches retenus

| patch_id | Catégorie | Fenêtre source (voir JSON pour détails) |
|---|---|---|
| 14A7_VAL_2025_RESIDENTIAL_01 | RESIDENTIAL | @{row=3072; col=9216; height=512; width=512} |
| 14A7_VAL_2025_RESIDENTIAL_02 | RESIDENTIAL | @{row=4096; col=7168; height=512; width=512} |
| 14A7_VAL_2025_RESIDENTIAL_03 | RESIDENTIAL | @{row=6144; col=6144; height=512; width=512} |
| 14A7_VAL_2025_DENSE_04 | DENSE | @{row=6144; col=8192; height=512; width=512} |
| 14A7_VAL_2025_DENSE_05 | DENSE | @{row=7168; col=6144; height=512; width=512} |
| 14A7_VAL_2025_DENSE_06 | DENSE | @{row=7168; col=7168; height=512; width=512} |
| 14A7_VAL_2025_DENSE_07 | DENSE | @{row=7168; col=8192; height=512; width=512} |
| 14A7_VAL_2025_INDUSTRIAL_08 | INDUSTRIAL | @{row=1024; col=3072; height=512; width=512} |
| 14A7_VAL_2025_INDUSTRIAL_09 | INDUSTRIAL | @{row=2048; col=4096; height=512; width=512} |
| 14A7_VAL_2025_INDUSTRIAL_10 | INDUSTRIAL | @{row=2048; col=7168; height=512; width=512} |
| 14A7_VAL_2025_DIFFICULT_11 | DIFFICULT | @{row=2048; col=8192; height=512; width=512} |
| 14A7_VAL_2025_DIFFICULT_12 | DIFFICULT | @{row=8192; col=4096; height=512; width=512} |
| 14A7_VAL_2025_ROAD_BARE_SOIL_13 | ROAD_BARE_SOIL | @{row=1024; col=4096; height=512; width=512} |
| 14A7_VAL_2025_ROAD_BARE_SOIL_14 | ROAD_BARE_SOIL | @{row=4096; col=9216; height=512; width=512} |

## GT et projet QGIS

- `gt_vector/14A7_independent_validation_gt.gpkg` : table `buildings_gt`, Polygon, EPSG:32637, UTF-8, 0 feature ; champs patch_id/building_id/scene_type/source/review_status.
- Valeurs par défaut : MANUAL, UNREVIEWED ; vues par patch avec patch_id et scène préremplis, building_id UUID.
- `qgis/14A7_INDEPENDENT_VALIDATION_ANNOTATION.qgz` construit avec l'API QGIS 3.40.14 à partir des réglages du projet fonctionnel 14A5A, sans modifier cette référence.
- 30 couches : 14 RGB, 14 vues GT filtrées, 1 couche GT canonique, 1 couche de limites de patches explicitement distincte de la GT ; 14 signets ; groupes catégorie/patch ; contour GT vert transparent, labels patch_id ; première paire visible.
- RGB natifs EPSG:4326 ; projet/GT EPSG:32637. Reprojection d'affichage QGIS uniquement. Aucun fichier RGB reprojeté/modifié. La future rasterisation utilisera les CRS/transforms exacts des RGB.
- Tests PyQGIS : tous providers valides, 0 chemin cassé, entrée/sortie d'édition sans modification sur les 15 vues GT, création et persistance d'un polygone uniquement dans une copie temporaire, GT réelle toujours vide ; sauvegarde et deux relectures du projet réussies. Exécution du builder terminée avec code 0.
- Test réel QGIS Desktop **3.40.14-Bratislava**, instance dédiée et profil propre sans plugins : ouverture PASS, 30 couches, RGB 14/14, GT 15 vues vides, 14 signets, 0 source cassée, édition sans modification PASS, sauvegarde PASS, réouverture PASS. Cycle de contrôle 16,81 s. Preuve : `qa/14A7A_desktop_qa.json` et image du canvas `qa/14A7A_desktop_canvas.png`, inspectée : RGB et label visibles. Le premier lancement a rencontré un comptage non initialisé ; le lancement dédié de contrôle puis la réouverture ont passé toutes les assertions. Le contrôle graphique Windows par le helper n'était pas disponible : les vérifications Desktop utilisent l'API iface de l'application réellement lancée, pas une simple lecture XML.
- Notice pratique : `README_ANNOTATION.md`. Une seule vue GT doit être éditée/sauvegardée à la fois.
- `gt_masks/` reste vide. Aucun pseudo-label, OSM ou résultat IA dans la GT.

## Récupération 14A5B séparée

Original ouvert en lecture seule immuable, SHA256 vérifié avant/après, inchangé. SQLite magic `SQLite format 3`, application_id 1196444487 (GPKG), intégrité SQLite OK, tables GeoPackage présentes. Cause : le byte de flags des 85 blobs déclarait « sans enveloppe » (1), alors qu'une enveloppe XY de 32 octets précédait réellement le WKB. Le lecteur standard cherchait donc le WKB au mauvais offset.

Seule la copie `annotations/14A5B_recovered_copy.gpkg` a été réparée : flags d'enveloppe corrigés, schéma de géométrie mixte normalisé par GDAL dans la copie. Vérification FID+WKB binaire exacte 85/85, 85 géométries valides, 0 invalide, lecture OGR 85/85, SQLite integrity OK. Preuve `qa/14A5B_readonly_audit_and_recovery.json`. Ce fichier reste TRAIN historique, exclu de la validation et absent du projet QGIS.

## Non-régression et suite

Aucun fichier suivi existant modifié d'après git status ; livrables ajoutés seulement. Originaux GT/RGB/manifests conservés. MODEL_C production, C2/C3/C4/C5/C6, frontend et API inchangés. Aucun entraînement, fine-tuning ou inférence. L'étape 14A.7 demeure non exécutable tant que l'annotation humaine et sa QA ne sont pas terminées.

BASE VAL RGB FOUND :
8 / 8

ADDITIONAL RESIDENTIAL :
3

ADDITIONAL DENSE :
4

TOTAL VALIDATION CANDIDATES :
22 audités (8 anciens exclus + 14 nouveaux retenus)

ELIGIBLE INDEPENDENT PATCHES :
14 (indépendance spatiale interne ; acquisition commune)

TRAIN LEAKAGE :
0 / 14

GT INITIAL FEATURES :
0

QGIS PROJECT :
READY

14A5B RECOVERY STATUS :
RECOVERED_COPY

READY_FOR_MANUAL_ANNOTATION :
YES

14A7 EXECUTABLE :
NO

NEXT STEP :
MANUAL_ANNOTATION_14A7_GT
