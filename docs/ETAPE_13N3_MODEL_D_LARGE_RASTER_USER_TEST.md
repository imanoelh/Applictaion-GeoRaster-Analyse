# ÉTAPE 13N.3 — MODEL_D Large Real Orthophoto User Test

Date : 2026-10-23

## Résultat

MODEL_D a terminé une exécution complète sur le raster Maxar 2025 préparé de **10 292 × 9 378 pixels (96 518 376 pixels)**. La requête de résultats GeoRaster a répondu HTTP 200 après **3 658,85 s (60 min 58,85 s)**. Elle a produit 7 313 candidats. Le modèle n’a pas été promu : la durée approche une heure, les contours observés sont parfois fragmentés, et il n’existe pas de vérité terrain sur tout le raster pour comparer la qualité. MODEL_C reste le modèle par défaut; MODEL_D reste expérimental; MODEL_E n’a pas été exécuté.

## Raster et reproductibilité

- Source originale : test-data/Oct 07, 2024/25JUL28115945-S3DS-200009702745_01_P001_COG.tif (Maxar 2025, 1 323 007 113 octets).
- Raster préparé utilisé par l’API : backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif (134 079 119 octets).
- Raster ID : ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.
- RGB : bandes Maxar 5/3/2, étirées lors de la préparation Maxar; 3 bandes uint8.
- SHA-256 du raster RGB préparé : 8d42d0c39d12c36ff9581b933ca11c353e70df07cc0e69fd04193706a0aa09cc; correspond au content_sha256 du sidecar.
- CRS : EPSG:4326. Résolution : environ 3.182877e-06 degré/pixel. Transform et bounds proviennent du raster préparé et sont identiques à la grille du résultat.
- Résultat : même largeur, hauteur, CRS et bounds. Les 7 313 géométries sont dans les limites du raster.

Paramètres identiques au benchmark 13N.2 : MODEL_D whu_unetplusplus_effb4, tuiles 512 px, recouvrement 50 %, seuil 0,50, minimum 4 pixels, connectivité 8, sans ouverture/fermeture morphologique ni simplification. Le tiling donne 40 colonnes × 36 lignes, soit **1 440 tuiles**. L’inférence exécutée était MODEL_D seule; aucun appel d’inférence MODEL_C ou MODEL_E n’a été lancé.

Le post-traitement au-dessus de 25 MP a employé les tableaux disk-backed numpy.memmap et le seuil par fenêtres de lignes. L’image complète n’a pas été lue en un seul tableau RGB en RAM. L’espace temporaire vérifié avant le run était d’environ 35,8 Gio. Aucun OOM ni arrêt du backend n’a été observé. L’instance 8011 avait déjà des modèles chargés depuis 13N.2; le pic RAM mesuré est celui du processus serveur partagé, pas une mesure isolée des seuls poids MODEL_D.

## Performance

| Mesure | Résultat |
|---|---:|
| Temps HTTP externe, pipeline complet | 3 658,85 s / 60,98 min |
| Débit rapporté | 37,91 s/MP |
| Temps externe par tuile | 2,54 s/tuile |
| Temps interne postprocessing_time_ms | 3 545,22 s |
| Polygonisation | 87,74 s |
| Construction du résultat | 15,97 s |
| Sérialisation GeoJSON interne | 1,91 s |
| RAM du backend, pic échantillonné | environ 2 900 MiB de working set; environ 3 333 MiB de mémoire privée |

La métrique interne appelée postprocessing_time_ms couvre en fait le parcours du générateur de prédictions, donc chargement du modèle, tiling, inférence, fusion et post-traitement. L’API n’expose pas de durée séparée pour le chargement MODEL_D et l’inférence seule. Le temps total HTTP est mesuré séparément par le client et inclut toute la requête.

Comparaisons de référence fournies : MODEL_C complet environ 1 560 s; MODEL_D sur 4096², 606,59 s pour 225 tuiles (2,70 s/tuile). Ce run complet MODEL_D dure environ **2,35×** le temps historique MODEL_C complet. Le débit par tuile reste proche de celui de 13N.2. Une durée proche d’une heure est lente pour un traitement interactif de cette taille.

## Résultats et validité

- Candidats : **7 313**.
- Surface totale : **802 225,53 m²**.
- Surface moyenne : **109,70 m²**.
- Surface médiane : **23,83 m²**.
- Minimum : **0,46 m²**.
- Maximum : **61 011,39 m²**.
- Périmètre total : **339 917,69 m**; périmètre moyen : **46,48 m**.
- Géométries : 7 155 Polygon et 158 MultiPolygon.
- Géométries invalides/vides/de surface nulle : **0**.
- Objets hors bounds : **0**.
- Doublons exacts WKB : **0**.
- Grille : dimensions, CRS, bounds et transform vérifiés; aucun décalage raster/polygones détecté.
- GeoJSON : FeatureCollection valide, 7 313 features.

Ces candidats ne sont pas des bâtiments vérifiés terrain. Aucune précision, rappel ou F1 officiel n’est calculé.

## Contrôle visuel qualitatif

La planche [13N3_model_d_contact_sheet.png](../test-data/diagnostics/13N3/13N3_model_d_contact_sheet.png) contient cinq aperçus 1024 × 1024 avec contours MODEL_D : résidentiel dense, petits bâtiments, toits industriels, toits complexes, routes/sol nu. Chaque fenêtre comprend aussi un overlay de masque semi-transparent et un masque binaire : voir les fichiers *_contours.png, *_mask_overlay.png et *_mask.png dans test-data/diagnostics/13N3/.

- Faux positifs apparents : **MEDIUM**. Les routes ne présentent pas une détection continue évidente dans l’échantillon; quelques objets de chantier/sol nu et les motifs triangulaires de certains grands toits produisent des contours fragmentés.
- Couverture des petits bâtiments : **MEDIUM**. Beaucoup de petits toits sont signalés dans la fenêtre dense, avec des contours parfois partiels ou fragmentés.
- Couverture urbaine dense : **GOOD visuellement** dans la fenêtre échantillonnée; cela ne valide pas les limites à l’échelle du raster complet.
- Ombres et végétation : observation visuelle non concluante dans ces cinq fenêtres.

Ces appréciations sont visuelles et qualitatives seulement; elles ne remplacent pas la comparaison avec des annotations humaines.

## Frontend et exports

- Frontend http://127.0.0.1:5184/ : HTTP 200.
- Preview orthophoto de l’API : HTTP 200, image/png, 7 161 835 octets; sauvegardée dans test-data/diagnostics/13N3/orthophoto_preview.png.
- Le code frontend relie l’orthophoto au Leaflet ImageOverlay et les résultats à LeafletGeoJSON (frontend/src/components/MapView.tsx); le panneau expose aussi les états aria-busy (frontend/src/features/ai-building/BuildingDetectionPanel.tsx).
- L’ouverture réelle de la carte dans un onglet n’a pas été terminée : la commande Computer Use a été arrêtée par Échap physique. Le routage HTTP, l’aperçu et le câblage source ont répondu; l’affichage navigateur interactif reste **non validé**.
- GeoJSON : HTTP 200, 7 313 features valides.
- CSV : HTTP 200, une ligne de statistiques; candidate_count=7313.
- Metadata JSON : HTTP 200, analysis_id cohérent.
- ZIP : HTTP 200, ZIP lisible avec building_candidates.geojson, building_statistics.csv et building_metadata.json; GeoJSON inclus avec 7 313 features.
- Vérifications export : [export_validation.json](../test-data/diagnostics/13N3/export_validation.json).

## État de l’intégration

Le registre après le run indique spacenet2_deeplab (MODEL_C) default=true, et MODEL_D default=false, experimental. MODEL_D reste EXPERIMENTAL; MODEL_E reste benchmark-only. Aucun fichier métier, modèle, traitement, export ou valeur par défaut n’a été modifié. Les tests frontend/backend et les builds n’ont pas été relancés pendant ce benchmark.

**Décision : MODEL_D_TOO_SLOW pour une promotion immédiate au mode utilisateur Enhanced.** Garder MODEL_D expérimental : les détections sur zones denses paraissent utiles, mais l’exécution de 61 minutes, les contours fragmentés sur toits complexes, l’absence de vérité terrain complète et l’absence de validation interactive navigateur ne justifient pas l’ajout d’un mode utilisateur promu.

## Artefacts

- Résultat API complet : [model_d_result.json](../test-data/diagnostics/13N3/model_d_result.json).
- Requête reproductible : [model_d_request.json](../test-data/diagnostics/13N3/model_d_request.json).
- Planche : [13N3_model_d_contact_sheet.png](../test-data/diagnostics/13N3/13N3_model_d_contact_sheet.png).
- QA géométrie/grille/échantillons : [qa_metrics.json](../test-data/diagnostics/13N3/qa_metrics.json).
- Exports et validation : export_model_d.geojson, export_model_d.csv, export_model_d_metadata.json, export_model_d.zip, [export_validation.json](../test-data/diagnostics/13N3/export_validation.json).

RASTER :
10292 x 9378

PIXELS :
96518376

MODEL :
MODEL_D / WHU U-Net++ EfficientNet-B4

STATUS :
EXPERIMENTAL

TILE COUNT :
1440

TOTAL TIME :
3658.85 s / 60.98 min

SECONDS PER MP :
37.91

SECONDS PER TILE :
2.54

RAM PEAK :
~2900 MiB working set échantillonné / ~3333 MiB mémoire privée

CANDIDATES :
7313

TOTAL AREA :
802225.53 m²

MAP DISPLAY :
PARTIAL — HTTP/preview/câblage vérifiés; affichage interactif navigateur non validé

EXPORTS :
VALIDATED

APPARENT FALSE POSITIVES :
MEDIUM

SMALL BUILDING COVERAGE :
MEDIUM

DENSE URBAN COVERAGE :
GOOD (qualitative)

PERFORMANCE :
TOO_SLOW

MODEL_C :
DEFAULT UNCHANGED

MODEL_D :
EXPERIMENTAL

MODEL_E :
BENCHMARK ONLY

FINAL DECISION :
MODEL_D_TOO_SLOW

NEXT STEP :
KEEP MODEL_D EXPERIMENTAL
