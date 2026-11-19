import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import {
  BUILDING_LAYER_STYLE,
  DEFAULT_BUILDING_PARAMETERS,
  buildingErrorMessage,
  buildingPopupFields,
  buildingQualityLabel,
  buildingSourceNotice,
  isValidWgs84Bounds,
  parseBuildingAnalysisResult,
} from "../src/features/ai-building/model.ts";
import { createBuildingAnalysisFixture } from "./fixtures/building-analysis.mts";

const panelSource = await readFile(
  new URL("../src/features/ai-building/BuildingDetectionPanel.tsx", import.meta.url),
  "utf8",
);
const mapSource = await readFile(new URL("../src/components/MapView.tsx", import.meta.url), "utf8");
const routeSource = await readFile(new URL("../src/routes/map.tsx", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../src/lib/georaster-api.ts", import.meta.url), "utf8");

// A-C: menu, Building subtype and the authorized parameter form.
assert.match(routeSource, /AI Object Detection/);
assert.match(panelSource, /Buildings/);
assert.equal(DEFAULT_BUILDING_PARAMETERS.model_id, "spacenet2_deeplab");
assert.equal(DEFAULT_BUILDING_PARAMETERS.tile_size, 512);
assert.doesNotMatch(panelSource, /aria-label=.*Detection model/);
assert.match(panelSource, /DeepLabV3 ResNet-50/);
assert.doesNotMatch(panelSource, /<option value="unet_resnet34">/);
assert.doesNotMatch(panelSource, /<option value="(?:whu_unetplusplus_effb4(?:_onnx)?|hybrid_model_c_model_d)">/);
assert.match(panelSource, /Standard Building Detection/);
assert.match(panelSource, /scientifically validated/);
for (const parameter of Object.keys(DEFAULT_BUILDING_PARAMETERS))
  assert.match(panelSource, new RegExp(parameter));

// D-F/O: launch, indeterminate loading, centralized API call, validation and mapped errors.
assert.match(routeSource, /runBuildingAnalysis/);
assert.match(panelSource, /animate-spin/);
assert.match(apiSource, /\/api\/ai\/results\/building/);
assert.match(apiSource, /parseBuildingAnalysisResult/);
assert.match(apiSource, /10 \* 60 \* 1000/);
assert.equal(
  buildingErrorMessage(new Error("MODEL_NOT_CONFIGURED"), "en"),
  "The Building model is not configured on the server.",
);
assert.equal(
  buildingErrorMessage(new Error("RASTER_CRS_MISSING"), "en"),
  "The raster must include a valid CRS.",
);
assert.match(
  buildingErrorMessage(
    new Error('{"detail":{"code":"LOCAL_RASTER_INVALID","message":"Le GeoTIFF depasse la taille maximale autorisee (536870912 octets)."}}'),
    "en",
  ),
  /512 MiB upload limit/,
);

// G-I: realistic success, zero result and statistics contract.
const result = parseBuildingAnalysisResult(createBuildingAnalysisFixture(10));
assert.equal(result.candidate_count, 10);
assert.equal(result.model_id, "unet_resnet34");
assert.equal(result.statistics.candidate_count, 10);
assert.ok(result.statistics.total_area_m2! > 0);
const zeroResult = parseBuildingAnalysisResult(createBuildingAnalysisFixture(0));
assert.equal(zeroResult.candidate_count, 0);
assert.equal(zeroResult.feature_collection.features.length, 0);
assert.equal(zeroResult.statistics.mean_area_m2, null);
assert.match(panelSource, /No building candidates detected/);
const candidateResult = parseBuildingAnalysisResult({
  ...createBuildingAnalysisFixture(1),
  model_id: "spacenet2_deeplab",
  model_architecture: "DeepLabV3 ResNet-50",
  model_checkpoint_hash: "170c49e1f42737f5a4b3922b9fc58b25b6ba0a7dd7bf00b9186a92ccb84dc555",
  tile_size: 512,
  preprocessing_profile: "full_raster_global_rgb_minmax_v1",
});
assert.equal(candidateResult.model_id, "spacenet2_deeplab");
assert.equal(candidateResult.tile_size, 512);
assert.equal(
  buildingErrorMessage(new Error("MODEL_FILE_NOT_FOUND"), "en"),
  "The selected Building model checkpoint is missing on the server.",
);

// J-N: one GeoJSON layer, valid bounds/zoom, popup fields, visibility and cleanup.
assert.equal((mapSource.match(/<LeafletGeoJSON/g) ?? []).length, 1);
assert.match(mapSource, /buildingResult\.feature_collection as unknown as GeoJsonObject/);
assert.ok(isValidWgs84Bounds(result.wgs84_bounds));
assert.equal(isValidWgs84Bounds({ left: 10, right: 9, bottom: 1, top: 2 }), false);
assert.match(mapSource, /result\.candidate_count === 0/);
assert.deepEqual(
  buildingPopupFields(result.feature_collection.features[0].properties).map(([label]) => label),
  ["ID", "Type", "Area", "Perimeter", "Pixels", "Model", "Threshold"],
);
assert.notDeepEqual(BUILDING_LAYER_STYLE.normal, BUILDING_LAYER_STYLE.hover);
assert.notDeepEqual(BUILDING_LAYER_STYLE.normal, BUILDING_LAYER_STYLE.selected);
assert.match(routeSource, /setShowBuildingLayer/);
assert.match(routeSource, /clearBuildingResult/);
assert.match(mapSource, /AI Building Candidates/);

// Step 11 exports: controls exist only in the result block and use the centralized API client.
const resultBlockIndex = panelSource.indexOf("{result && (");
const exportBlockIndex = panelSource.indexOf("Export building candidates");
assert.ok(resultBlockIndex >= 0 && exportBlockIndex > resultBlockIndex);
assert.match(panelSource, /format="geojson"/);
assert.match(panelSource, /format="csv"/);
assert.match(panelSource, /format="zip"/);
assert.match(panelSource, /exportingFormat !== null/);
assert.match(apiSource, /\/api\/ai\/results\/building\/export/);
assert.match(apiSource, /AI_BUILDING_EXPORT_FAILED/);
assert.match(apiSource, /URL\.createObjectURL/);
assert.match(routeSource, /downloadBuildingExport\(buildingResult, format\)/);
assert.match(routeSource, /AI Building export failed/);
assert.match(routeSource, /clearBuildingResult/);

// P-Q: scientifically explicit source and quality labels.
assert.match(buildingSourceNotice("sentinel2", "en"), /integration-test source/);
assert.match(buildingSourceNotice("orthophoto", "en"), /high-resolution source is recommended/);
assert.equal(buildingQualityLabel("integration_test", "en"), "Integration test mode");
assert.equal(
  buildingQualityLabel("real_model_unvalidated", "en"),
  "Real model — accuracy not yet validated",
);

// Contract/performance: 10, 100, 1,000 and 2,500 features parse as one collection.
for (const count of [10, 100, 1000, 2500]) {
  const fixture = createBuildingAnalysisFixture(count, "real_model_unvalidated");
  const started = performance.now();
  const parsed = parseBuildingAnalysisResult(fixture);
  const durationMs = performance.now() - started;
  assert.equal(parsed.feature_collection.features.length, count);
  assert.ok(durationMs < 5000, `${count} features took ${durationMs.toFixed(1)} ms to validate`);
  process.stdout.write(
    `Building fixture ${count.toLocaleString()} features: ${durationMs.toFixed(1)} ms\n`,
  );
}

process.stdout.write("AI Building frontend contract and integration checks passed.\n");
