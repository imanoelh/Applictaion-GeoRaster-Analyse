import { Buffer } from "node:buffer";
import JSZip from "jszip";
import {
  AoiImportError,
  aoiGeometryAreaKm2,
  importAoiFromFiles,
  normalizeImportedGeoJson,
  parseKmlText,
} from "../src/lib/aoi-import.ts";

const RING = [
  [49.72, 25.41],
  [49.74, 25.41],
  [49.74, 25.43],
  [49.72, 25.43],
  [49.72, 25.41],
];

const WGS84_PRJ = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]';

function assert(condition: unknown, message: string) {
  if (!condition) throw new Error(message);
}

function almostEqual(actual: number, expected: number, digits = 5) {
  return Math.abs(actual - expected) < 10 ** -digits;
}

function writeInt16LE(buffer: Buffer, offset: number, value: number) {
  buffer.writeInt16LE(value, offset);
}

function writeInt32LE(buffer: Buffer, offset: number, value: number) {
  buffer.writeInt32LE(value, offset);
}

function writeInt32BE(buffer: Buffer, offset: number, value: number) {
  buffer.writeInt32BE(value, offset);
}

function writeDoubleLE(buffer: Buffer, offset: number, value: number) {
  buffer.writeDoubleLE(value, offset);
}

function buildPolygonShapefile(ring: number[][]) {
  const xs = ring.map((point) => point[0]);
  const ys = ring.map((point) => point[1]);
  const xmin = Math.min(...xs);
  const xmax = Math.max(...xs);
  const ymin = Math.min(...ys);
  const ymax = Math.max(...ys);
  const contentLengthWords = (4 + 32 + 4 + 4 + 4 + ring.length * 16) / 2;
  const recordBytes = 8 + contentLengthWords * 2;
  const shp = Buffer.alloc(100 + recordBytes);
  writeInt32BE(shp, 0, 9994);
  writeInt32BE(shp, 24, (100 + recordBytes) / 2);
  writeInt32LE(shp, 28, 1000);
  writeInt32LE(shp, 32, 5);
  writeDoubleLE(shp, 36, xmin);
  writeDoubleLE(shp, 44, ymin);
  writeDoubleLE(shp, 52, xmax);
  writeDoubleLE(shp, 60, ymax);
  writeInt32BE(shp, 100, 1);
  writeInt32BE(shp, 104, contentLengthWords);
  writeInt32LE(shp, 108, 5);
  writeDoubleLE(shp, 112, xmin);
  writeDoubleLE(shp, 120, ymin);
  writeDoubleLE(shp, 128, xmax);
  writeDoubleLE(shp, 136, ymax);
  writeInt32LE(shp, 144, 1);
  writeInt32LE(shp, 148, ring.length);
  writeInt32LE(shp, 152, 0);
  ring.forEach((point, index) => {
    writeDoubleLE(shp, 156 + index * 16, point[0]);
    writeDoubleLE(shp, 164 + index * 16, point[1]);
  });

  const shx = Buffer.alloc(108);
  shp.copy(shx, 0, 0, 100);
  writeInt32BE(shx, 24, 54);
  writeInt32BE(shx, 100, 50);
  writeInt32BE(shx, 104, contentLengthWords);

  const dbf = Buffer.alloc(66);
  dbf[0] = 0x03;
  writeInt16LE(dbf, 8, 66);
  writeInt16LE(dbf, 10, 1);
  dbf[32] = 0x0d;
  dbf[65] = 0x1a;

  return { shp, shx, dbf, prj: Buffer.from(WGS84_PRJ, "utf8") };
}

async function fileFrom(name: string, data: string | Buffer | Uint8Array, type: string) {
  const payload = typeof data === "string" ? data : new Uint8Array(data);
  return new File([payload], name, { type });
}

async function shapefileZip(includePrj = true) {
  const parts = buildPolygonShapefile(RING);
  const zip = new JSZip();
  zip.file("aoi.shp", parts.shp);
  zip.file("aoi.shx", parts.shx);
  zip.file("aoi.dbf", parts.dbf);
  if (includePrj) zip.file("aoi.prj", parts.prj);
  return zip.generateAsync({ type: "uint8array" });
}

async function kmzFromKml(kml: string) {
  const zip = new JSZip();
  zip.file("doc.kml", kml);
  return zip.generateAsync({ type: "uint8array" });
}

const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>AOI</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              49.72,25.41,0 49.74,25.41,0 49.74,25.43,0 49.72,25.43,0 49.72,25.41,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>`;

const geojson = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "AOI" },
      geometry: { type: "Polygon", coordinates: [RING] },
    },
  ],
};

async function expectError(files: File[], code: string) {
  try {
    await importAoiFromFiles(files);
    throw new Error(`Expected ${code}`);
  } catch (error) {
    assert(error instanceof AoiImportError, `Expected AoiImportError, got ${error}`);
    assert(error.code === code, `Expected ${code}, got ${(error as AoiImportError).code}`);
  }
}

async function run() {
  const fromGeoJsonObject = normalizeImportedGeoJson(geojson, "geojson");
  assert(fromGeoJsonObject.format === "geojson", "geojson format");
  assert(almostEqual(fromGeoJsonObject.bbox[0][0], 25.41), "geojson south");
  assert(almostEqual(fromGeoJsonObject.bbox[0][1], 49.72), "geojson west");
  assert(fromGeoJsonObject.geometry.type === "Polygon", "geojson polygon");
  const rectangleArea = aoiGeometryAreaKm2(fromGeoJsonObject.geometry);
  const triangleArea = aoiGeometryAreaKm2(normalizeImportedGeoJson({
    type: "Polygon",
    coordinates: [[RING[0], RING[1], RING[2], RING[0]]],
  }, "kml").geometry);
  assert(triangleArea > 0 && triangleArea < rectangleArea * 0.6, "polygon area uses geometry rather than bbox");

  const mercator = normalizeImportedGeoJson({
    type: "Polygon",
    crs: { type: "name", properties: { name: "EPSG:3857" } },
    coordinates: [[
      [5535455.0, 2923085.0],
      [5537680.0, 2923085.0],
      [5537680.0, 2925570.0],
      [5535455.0, 2925570.0],
      [5535455.0, 2923085.0],
    ]],
  }, "geojson");
  assert(mercator.bbox[0][0] > 25 && mercator.bbox[0][0] < 26, "mercator reprojected");

  const fromKmlText = parseKmlText(kml);
  const fromKml = normalizeImportedGeoJson(fromKmlText, "kml");
  assert(almostEqual(fromKml.bbox[1][0], 25.43), "kml north");

  const geojsonFile = await importAoiFromFiles([await fileFrom("aoi.geojson", JSON.stringify(geojson), "application/geo+json")]);
  const kmlFile = await importAoiFromFiles([await fileFrom("aoi.kml", kml, "application/vnd.google-earth.kml+xml")]);
  const kmzFile = await importAoiFromFiles([await fileFrom("aoi.kmz", await kmzFromKml(kml), "application/vnd.google-earth.kmz")]);
  const shpFile = await importAoiFromFiles([await fileFrom("aoi.zip", await shapefileZip(), "application/zip")]);
  const shpWithoutPrj = await importAoiFromFiles([
    await fileFrom("aoi.zip", await shapefileZip(false), "application/zip"),
  ]);
  const looseParts = buildPolygonShapefile(RING);
  const looseShapefile = await importAoiFromFiles([
    await fileFrom("aoi.shp", looseParts.shp, "application/octet-stream"),
    await fileFrom("aoi.shx", looseParts.shx, "application/octet-stream"),
    await fileFrom("aoi.dbf", looseParts.dbf, "application/octet-stream"),
  ]);

  for (const [label, result] of [["geojson", geojsonFile], ["kml", kmlFile], ["kmz", kmzFile], ["shapefile", shpFile], ["shapefile-no-prj", shpWithoutPrj], ["shapefile-loose", looseShapefile]] as const) {
    assert(almostEqual(result.bbox[0][0], 25.41), `${label} south`);
    assert(almostEqual(result.bbox[0][1], 49.72), `${label} west`);
    assert(almostEqual(result.bbox[1][0], 25.43), `${label} north`);
    assert(almostEqual(result.bbox[1][1], 49.74), `${label} east`);
    assert(result.geometry.type === "Polygon" || result.geometry.type === "MultiPolygon", `${label} polygon`);
  }

  await expectError([await fileFrom("notes.txt", "hello", "text/plain")], "unsupported_format");
  await expectError([await fileFrom("empty.geojson", JSON.stringify({ type: "FeatureCollection", features: [] }), "application/geo+json")], "empty_geometry");
  await expectError([await fileFrom("points.geojson", JSON.stringify({ type: "Point", coordinates: [49.72, 25.41] }), "application/geo+json")], "empty_geometry");
  await expectError([await fileFrom("broken.geojson", "{not json", "application/geo+json")], "invalid_file");
  await expectError([await fileFrom("only.dbf", partsPlaceholder(), "application/octet-stream")], "incomplete_shapefile");
  await expectError([await fileFrom("aoi.shp", Buffer.from("not-a-shape"), "application/octet-stream")], "invalid_file");
  await expectError([await fileFrom("projected.geojson", JSON.stringify({
    type: "Polygon",
    coordinates: [[[500000, 2800000], [501000, 2800000], [501000, 2801000], [500000, 2800000]]],
  }), "application/geo+json")], "projection_error");

  console.log("AOI import tests OK: GeoJSON, KML, KMZ, Shapefile ZIP with/without .prj, loose shapefile, and error cases.");
}

function partsPlaceholder() {
  return Buffer.from("x");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
