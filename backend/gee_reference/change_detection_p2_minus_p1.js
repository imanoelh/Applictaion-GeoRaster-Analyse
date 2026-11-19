/**
 * GeoRaster Change Detection reference graph (Code Editor).
 *
 * For each of NDVI, NDWI, NDBI, BSI, SAVI:
 *   INDEX_P1 = validated simple-index pipeline(period 1)
 *   INDEX_P2 = the same pipeline(period 2)
 *   DELTA    = INDEX_P2.subtract(INDEX_P1)   // never CLASS_P2 - CLASS_P1
 *
 * Sentinel-2: COPERNICUS/S2_SR_HARMONIZED, SCL-only mask, median composite.
 * Inclusive UI end date -> exclusive GEE bound (end + 1 day).
 * Native scale: NDVI/NDWI/SAVI 10 m; NDBI/BSI 20 m (B11).
 */
var aoi = ee.Geometry.Rectangle([46.5, 24.5, 46.7, 24.7]);
var cloudMax = 40;
var p1Start = '2024-01-01';
var p1EndInclusive = '2024-03-31';
var p2Start = '2025-01-01';
var p2EndInclusive = '2025-03-31';

function geeEndExclusive(inclusive) {
  return ee.Date(inclusive).advance(1, 'day');
}

function sclMask(image) {
  var scl = image.select('SCL');
  var keep = scl.eq(4).or(scl.eq(5)).or(scl.eq(6)).or(scl.eq(11));
  return image.updateMask(keep);
}

function periodCollection(start, endInclusive) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(start, geeEndExclusive(endInclusive))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloudMax))
    .map(sclMask);
}

function medianBands(collection, bands) {
  return collection.select(bands).median().clip(aoi);
}

function ndvi(collection) {
  var m = medianBands(collection, ['B4', 'B8']);
  return m.normalizedDifference(['B8', 'B4']).rename('NDVI');
}

function ndwi(collection) {
  var m = medianBands(collection, ['B3', 'B8']);
  return m.normalizedDifference(['B3', 'B8']).rename('NDWI');
}

function ndbi(collection) {
  var m = medianBands(collection, ['B8', 'B11']);
  return m.expression('(b11 - b8) / (b11 + b8)', {
    b11: m.select('B11'),
    b8: m.select('B8')
  }).rename('NDBI');
}

function bsi(collection) {
  var m = medianBands(collection, ['B2', 'B4', 'B8', 'B11']);
  return m.expression('((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2))', {
    b11: m.select('B11'),
    b4: m.select('B4'),
    b8: m.select('B8'),
    b2: m.select('B2')
  }).rename('BSI');
}

function savi(collection) {
  var m = medianBands(collection, ['B4', 'B8']);
  var red = m.select('B4').multiply(0.0001);
  var nir = m.select('B8').multiply(0.0001);
  return m.expression('((nir - red) / (nir + red + 0.5)) * 1.5', {
    nir: nir,
    red: red
  }).rename('SAVI');
}

function deltaFrom(builder, scale) {
  var c1 = periodCollection(p1Start, p1EndInclusive);
  var c2 = periodCollection(p2Start, p2EndInclusive);
  var i1 = builder(c1);
  var i2 = builder(c2);
  var common = i1.mask().and(i2.mask());
  return i2.subtract(i1).updateMask(common).reproject({crs: i2.projection(), scale: scale});
}

var builders = {
  NDVI: {fn: ndvi, scale: 10},
  NDWI: {fn: ndwi, scale: 10},
  NDBI: {fn: ndbi, scale: 20},
  BSI: {fn: bsi, scale: 20},
  SAVI: {fn: savi, scale: 10}
};

var selected = 'NDVI';
var spec = builders[selected];
var delta = deltaFrom(spec.fn, spec.scale);
Map.centerObject(aoi, 11);
Map.addLayer(delta, {min: -0.5, max: 0.5, palette: ['#a50026', '#f7f7f7', '#006837']}, selected + ' Δ = P2 - P1');
print(delta.reduceRegion({
  reducer: ee.Reducer.minMax().combine(ee.Reducer.mean(), '', true),
  geometry: aoi,
  scale: spec.scale,
  maxPixels: 1e8
}));
