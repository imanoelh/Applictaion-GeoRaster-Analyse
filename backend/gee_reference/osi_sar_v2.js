// OSI-SAR v2 reference — paste into Google Earth Engine Code Editor.
// Matches GeoRaster online OSI-SAR: one Sentinel-1 IW VV/VH scene, AND detection.
// COPERNICUS/S1_GRD already stores VV/VH in dB. Do not convert twice.

var VV_DARK = -18;
var VH_DARK = -25;
var CONTRAST_DB = 2.5;
var RADIUS_M = 500;
var MIN_PIX = 8;
var ANGLE_MIN = 30;
var ANGLE_MAX = 45;
var COAST_M = 150;

// Validation window used against GeoRaster: ~330 km2 marine AOI.
var aoi = ee.Geometry.Rectangle([49.90, 26.98, 50.10, 27.13]);
var start = '2026-08-01';
var endExclusive = '2026-09-09';

var col = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filterDate(start, endExclusive)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('resolution_meters', 10))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .sort('system:time_start', false);

print('AOI km2', aoi.area(1).divide(1e6));
print('Sentinel-1 scenes', col.size());
print('Scenes', col);

var scene = col.first(); // or ee.Image('COPERNICUS/S1_GRD/<system:index>')
print('scene id', scene.id());
print('date', ee.Date(scene.get('system:time_start')));
print('orbit pass', scene.get('orbitProperties_pass'));
print('relative orbit start', scene.get('relativeOrbitNumber_start'));
print('relative orbit stop', scene.get('relativeOrbitNumber_stop'));
print('platform', scene.get('platform_number'));

var img = scene.select(['VV', 'VH', 'angle']).clip(aoi);
var angleMask = img.select('angle').gt(ANGLE_MIN).and(img.select('angle').lt(ANGLE_MAX));
var wc = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').eq(80);
var gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence');
var water = wc.and(gsw.mask().not().or(gsw.gte(50))).focal_min({radius: COAST_M, units: 'meters'});
var valid = water.and(angleMask);

var vv = img.select('VV');
var vh = img.select('VH');
var contrast = vv.focal_mean({radius: RADIUS_M, kernelType: 'circle', units: 'meters'}).subtract(vv);
var osiRaw = vv.lt(VV_DARK).and(vh.lt(VH_DARK)).and(contrast.gte(CONTRAST_DB)).and(valid);
var candidate = osiRaw.and(osiRaw.selfMask().connectedPixelCount(100, true).unmask(0).gte(MIN_PIX));

print('IMPORTANT : un dark target SAR n\'est pas automatiquement du pétrole.');
print('Compare scene ID first, then pixels, with the same AOI.');

Map.centerObject(aoi, 11);
Map.addLayer(vv.updateMask(valid), {min: -25, max: 0}, 'VV dB');
Map.addLayer(vh.updateMask(valid), {min: -25, max: 0}, 'VH dB', false);
Map.addLayer(contrast.updateMask(valid), {min: 0, max: 6}, 'Local contrast VV', false);
Map.addLayer(osiRaw.selfMask(), {palette: ['#d7191c']}, 'OSI raw', false);
Map.addLayer(candidate.selfMask(), {palette: ['#d7191c']}, 'OSI-SAR - Oil Spill Suspect');
Map.addLayer(aoi, {color: 'yellow'}, 'AOI', false);
