# ÉTAPE 13O.1 — Validation complète MODEL_D_ONNX

## Résultat

Le moteur expérimental `whu_unetplusplus_effb4_onnx` a terminé l’analyse du raster complet de 10 292 × 9 378 pixels. L’exécution a utilisé ONNX Runtime CPU, 4 threads, et le pipeline réel du backend : préparation RGB existante, tuiles 512 × 512 avec recouvrement 50 %, seuil 0,5, post-traitement et polygonisation habituels. Le modèle n’a pas été promu.

Le test a été exécuté dans un processus d’application isolé avec FastAPI TestClient, afin de charger la version actuelle du code sans interrompre ni remplacer les services présents sur les ports 8010/8011. Cela valide les routes et leurs réponses HTTP dans le code courant ; le navigateur et l’interaction frontend n’ont pas été testés.

## Entrée et moteur

- Raster : `backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif`
- Taille : 134 079 119 octets ; SHA256 `8d42d0c39d12c36ff9581b933ca11c353e70df07cc0e69fd04193706a0aa09cc`
- Dimensions : 10 292 × 9 378, soit 96 518 376 pixels, 3 bandes uint8
- CRS : EPSG:4326 ; transform, bounds et nodata identiques à la référence 13N.3 (nodata 0)
- Model ID : `whu_unetplusplus_effb4_onnx`
- Architecture : WHU U-Net++ / EfficientNet-B4, ONNX Runtime CPU
- SHA256 ONNX : `62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6`
- Statut à l’exécution : expérimental ; 4 threads
- Tuiles : 512 px, overlap 0,5, seuil 0,5 ; aucune ouverture/fermeture morphologique ; minimum objet 4 pixels
- Tuiles totales : 1 440 ; inférées : 1 300 ; ignorées par le contrôle de validité : 140

MODEL_C n’a pas été exécuté et reste le modèle par défaut. MODEL_D PyTorch n’a pas été exécuté. Aucun modèle, indice, classification, export historique ou traitement GEE n’a été modifié.

## Profiling

Temps mesurés dans l’appel API complet (secondes) :

| Étape | Temps |
|---|---:|
| Chargement du modèle | 1,365 s |
| Lecture raster | 8,095 s |
| Préprocessing / normalisation | 6,402 s |
| Préparation des tuiles et métadonnées | 2,611 s |
| Génération des tuiles | 17,108 s |
| Forward du modèle | 2 004,083 s (92,89 % du temps résultat API) |
| Assemblage / fusion des masques | 4,748 s |
| Post-traitement total | 2 126,058 s |
| Polygonisation | 15,204 s |
| Statistiques et résultats | 8,993 s |
| Préparation des exports | 11,494 s |
| Résultat API complet | 2 157,573 s |
| Preview HTTP | 6,875 s |
| Résultat + preview + 4 exports | 2 183,438 s |

La durée de post-traitement instrumentée inclut le forward ONNX ; le champ de profilage `postprocess_residual_s` rapporte 104,868 s hors forward. Le forward est le principal coût.

- 1 440 tuiles : moyenne d’inférence 1,542 s/tile ; médiane 1,478 s ; p95 1,979 s
- Débit : 22,354 s/Mpixel
- Mémoire processus : pic RSS externe mesuré 1 926,1 MiB ; pic privé non mesuré
- RAM disponible minimale système échantillonnée : 1 771 MiB
- Durée end-to-end avec preview et exports : 2 183,44 s (36,39 min)

La mesure mémoire interne du script d’orchestration s’est révélée indisponible (valeur nulle) ; les valeurs ci-dessus viennent du moniteur externe Windows (`Get-Process.PeakWorkingSet64` et compteur mémoire), échantillonné à environ 0,5 s. Elles sont retenues comme mesures du run.

## Résultats et comparaison au baseline

| Métrique | MODEL_D_ONNX | Baseline MODEL_D PyTorch | Écart |
|---|---:|---:|---:|
| Temps de référence | 2 157,57 s analyse API | 3 658,85 s | −1 501,28 s (−25,02 min) |
| Candidats | 7 313 | 7 313 | 0 |
| Surface totale | 802 224,944 m² | 802 225,525 m² | −0,581 m² |

Speedup complet sur le temps API résultat : **1,696×**. Les prédictions ont le même nombre de candidats et une surface totale presque identique. Aucune identité pixel stricte n’a été exigée ; ce résultat confirme le comportement d’ingénierie équivalent demandé.

Statistiques retournées : moyenne 109,698 m² ; médiane 23,828 m² ; minimum 0,465 m² ; maximum 61 011,390 m². Périmètre total : 339 916,280 m.

## Contrôles géométriques, API et exports

- 7 313 géométries : 7 155 Polygon et 158 MultiPolygon
- Géométries vides ou invalides : 0
- Géométries hors bounds raster : 0
- Doublons exacts : 0
- CRS résultat conforme au raster : oui
- Route résultat de l’application : HTTP 200 ; model ID retourné conforme à MODEL_D_ONNX
- Preview `GET /api/ai/raster/{raster_id}/preview.png` : HTTP 200, `image/png`, 7 161 835 octets
- GeoJSON : HTTP 200, 7 313 features, 25 520 056 octets
- CSV : HTTP 200, 807 octets
- Metadata JSON : HTTP 200, 1 565 octets, model ID ONNX
- ZIP : HTTP 200, 3 124 218 octets ; contient GeoJSON, CSV et metadata JSON
- Carte frontend interactive : non exécutée (`NOT_RUN`)

Le résultat API rapporte le seuil et l’identifiant ONNX. Le registre et la pré-vérification ont confirmé le statut expérimental et le maintien de MODEL_C par défaut. Le test n’a pas écrit dans les fichiers de modèles ou dans la configuration de production.

Les artefacts techniques du run sont sous `test-data/diagnostics/13O1/` : pré-vérification, résultat brut, preview, exports, journal, progression et mesure mémoire.

## Décision

La durée totale de 36,39 minutes se situe dans la classe **SLOW (35–45 min)**. La mémoire mesurée est de 1 926,1 MiB et le traitement complet a réussi. Suivant les seuils de cette étape, MODEL_D_ONNX reste expérimental et n’est pas activé comme mode utilisateur renforcé. Aucune suite de tests n’a été relancée, car aucun fichier de code métier n’a été modifié.

RASTER :
10292 x 9378

PIXELS :
96518376

ENGINE :
ONNX_RUNTIME_CPU

MODEL :
MODEL_D_ONNX

TILES :
1440 (1300 inférées, 140 ignorées)

TOTAL TIME :
2183.44 s (résultat + preview + exports)

TOTAL MINUTES :
36.39

PYTORCH BASELINE :
3658.85 s / 60.98 min

FULL SPEEDUP :
1.70 x (temps résultat API)

TIME SAVED :
25.02 min

SECONDS PER MP :
22.35

SECONDS PER TILE :
1.54 s moyen ; 1.48 s médian ; 1.98 s p95 (tuiles inférées)

MODEL_FORWARD PERCENT :
92.89 % (du temps résultat API)

PROCESS PEAK RAM :
1926.1 MiB RSS

CANDIDATES :
7313

PYTORCH BASELINE CANDIDATES :
7313

CANDIDATE DELTA :
0

TOTAL AREA :
802224.944 m² (delta −0.581 m²)

GEOMETRIES :
VALID

BOUNDS :
VALID

EXPORTS :
VALIDATED

MAP API :
VALIDATED

MAP INTERACTIVE :
NOT_RUN

MODEL_C :
DEFAULT UNCHANGED

MODEL_D PYTORCH :
PRESERVED

MODEL_D_ONNX :
EXPERIMENTAL

MODEL_E :
UNCHANGED

PERFORMANCE CLASS :
SLOW

FINAL DECISION :
MODEL_D_ONNX_STILL_TOO_SLOW

NEXT STEP :
KEEP MODEL_D_ONNX EXPERIMENTAL
