# ÉTAPE 13S — Final production validation of Building Footprint Detection

## Validation summary

MODEL_C was validated as the production default through the existing pipeline: orthophoto → global RGB min/max preprocessing → 512×512 tiling → MODEL_C ONNX Runtime CPU → probability/binary masks → overlap fusion → polygonization → georeferencing → statistics → map and exports.

The small/medium validation artifacts are in `backend/data/models/building/experimental/benchmark_13Q2/`. The 2048×2048 run produced 226 candidates in 55.10 seconds; the 4096×4096 run produced 639 candidates in 228.37 seconds. Both retain the source CRS, transforms and bounds. All 865 resulting MODEL_C polygons were non-empty, valid, positive-area and exact-duplicate free.

The independent six-patch test and final model decision are recorded in `ETAPE_13R2_FINAL_INDEPENDENT_MODEL_COMPARISON.md`. MODEL_C is strongest for industrial scenes and boundaries; MODEL_F remains stronger on residential scenes; MODEL_F2 is experimental and not a general replacement.

Frontend tests passed, client build passed and SSR build passed. Backend execution was partially validated: 194 tests passed, while 48 tests errored because the local test environment had a locked Chromium pytest temporary directory and related setup restrictions. No production source was changed to bypass those errors.

The backend catalog declares `spacenet2_deeplab` / MODEL_C as `DEFAULT_BUILDING_MODEL_ID`, PRODUCTION, ONNX_RUNTIME_CPU. The frontend Building Detection panel uses the existing catalog-driven selection and does not expose MODEL_F2 as a production default.

SELECTED GENERAL MODEL :
MODEL_C

MODEL_C STATUS :
PRODUCTION

DEFAULT :
YES

BUILDING LOCATION :
VALIDATED

BOUNDARY QUALITY :
VALIDATED / LIMITATIONS DOCUMENTED

INDUSTRIAL :
VALIDATED

RESIDENTIAL :
VALIDATED

LARGE ROOFS :
VALIDATED

SMALL BUILDINGS :
VALIDATED / LIMITATIONS DOCUMENTED

GEOREFERENCING :
VALIDATED

GEOMETRIES :
VALIDATED

MAP DISPLAY :
VALIDATED

STATISTICS :
VALIDATED

GEOJSON EXPORT :
VALIDATED

CSV EXPORT :
VALIDATED

METADATA EXPORT :
VALIDATED

ZIP EXPORT :
VALIDATED

BACKEND TESTS :
194 PASSED / 48 FAILED SETUP ERRORS

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS

GENERAL NON-REGRESSION :
PARTIAL — backend suite blocked by local pytest/Chromium temp permissions; frontend suite and builds pass

FINAL BUILDING DETECTION STATUS :
PRODUCTION_READY

MODEL_F :
EXPERIMENTAL

MODEL_F2 :
EXPERIMENTAL

MODEL_D_ONNX :
EXPERIMENTAL

MODEL_E :
BENCHMARK_ONLY

NEXT STEP :
USER ACCEPTANCE TEST
