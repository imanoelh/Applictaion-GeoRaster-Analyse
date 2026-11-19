# Étape 14A.15 — MODEL_C8 application-level precision refinement

## Périmètre et gel du modèle

Le checkpoint C8 utilisé est `14A11_hybrid_pipeline/models/MODEL_C8_HYBRID_epoch2.pth`.
SHA256 vérifié : `32f48ba94385206ed3e1cc8a156b73ac33810525f05a6bb3fd51b16c486a7576`.
Les poids n'ont pas été modifiés. GOLD n'a pas servi à choisir les paramètres.

La sélection a utilisé uniquement les quatre patches DEV non-GOLD `14A9B_DEV_11` à `14A9B_DEV_14`. Huit zones applicatives ont été créées dans `14A15_application_test_zones.geojson`. Les probabilités et les masques bruts sont conservés dans `BASELINE_C8_RAW`.

## Sélection DEV

Baseline : seuil 0,50, composante minimale 32, connectivité 4, morphologie désactivée.

Configuration candidate sélectionnée sur DEV : seuil 0,60, composante minimale 64, connectivité 4, morphologie désactivée. Elle améliore la précision et le F1 DEV, mais les labels DEV ne justifient pas une suppression sémantique agressive du sol nu ou des routes. Les scores `ARTIFACT_SCORE`, `BARE_SOIL_FP_SCORE`, `ROAD_FP_SCORE`, `LARGE_OBJECT_WARNING` et `FRAGMENT_MERGE_SCORE` sont donc des indicateurs conservatifs, pas des décisions de rejet automatiques.

## Gold one-shot après gel

Le Gold a été évalué une seule fois après la sélection DEV. Le candidat réduit les faux négatifs objets et augmente la précision, mais ne réduit pas les faux positifs et dégrade la qualité de frontière. Il ne satisfait donc pas le critère de promotion. Le fichier de configuration est conservé pour traçabilité avec `enabled=false`; l'application utilise automatiquement le fallback C8 baseline.

## Intégration applicative

Le même moteur `Building AI v2` lit le fichier de configuration s'il est cohérent avec l'identité et le SHA256 du checkpoint. Toute absence, erreur de lecture ou incohérence revient à seuil 0,50 / minimum 32 / connectivité 4 / morphologie OFF. MODEL_C production n'est pas touché.

## Tests

- Chargement strict C8 : PASS.
- Backend et Building API : PASS.
- Post-traitement C8 raffiné vérifié par API : PASS (le résultat renvoie les paramètres effectifs).
- Polygonisation, géoréférencement, statistiques : PASS.
- Exports GeoJSON, CSV, metadata JSON, ZIP : PASS dans le smoke test antérieur.
- Le fichier orthophoto ayant produit 4 335 candidats n'est pas conservé dans `backend/uploads` après la session précédente ; son compteur raffiné ne peut donc pas être revendiqué comme mesuré sur le même artefact. Le smoke test local reproductible est conservé dans le rapport d'intégration 14A.14.

MODEL :
MODEL_C8_HYBRID

WEIGHTS MODIFIED :
NO

BASELINE THRESHOLD :
0.50

REFINED THRESHOLD :
0.60 (candidate, disabled after Gold gate)

BASELINE MIN COMPONENT :
32

REFINED MIN COMPONENT :
64 (candidate, disabled after Gold gate)

BARE SOIL FILTER :
UNCERTAIN_ONLY_NO_HARD_REJECTION

ROAD FILTER :
UNCERTAIN_ONLY_NO_HARD_REJECTION

ARTIFACT FILTER :
CONSERVATIVE_FEATURE_SCORE_ONLY

POLYGON CLEANING :
LIGHT_REPAIR_NO_AGGRESSIVE_SIMPLIFICATION

FRAGMENT MERGE :
DISABLED_UNTIL_HUMAN_VALIDATION

GOLD BASELINE F1 :
0.4219

GOLD REFINED F1 :
0.4521

GOLD BASELINE PRECISION :
0.5934

GOLD REFINED PRECISION :
0.6146

GOLD BASELINE RECALL :
0.3273

GOLD REFINED RECALL :
0.3576

GOLD BASELINE FP :
37

GOLD REFINED FP :
37

GOLD SMALL RECALL :
3 / 38

GOLD BOUNDARY F1 :
0.2248 refined (baseline 0.3364)

REAL ORTHOPHOTO BASELINE CANDIDATES :
4335 (historical session result)

REAL ORTHOPHOTO REFINED CANDIDATES :
NOT_REPRODUCED — uploaded raster not persisted

REAL ORTHOPHOTO VISUAL QA :
PASS (DEV contact sheet); current 4335-candidate upload unavailable for a paired rerun

BUILDING API :
PASS

EXPORTS :
PASS

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

C8 REFINED READY FOR DEFAULT :
NO

NEXT STEP :

KEEP_C8_EXPERIMENTAL
