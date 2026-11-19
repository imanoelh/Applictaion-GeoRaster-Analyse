export type AoiBBox = [[number, number], [number, number]];

export type AoiGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

export type AoiImportFormat = "geojson" | "shapefile" | "kml" | "kmz";

export type ImportedAoi = {
  bbox: AoiBBox;
  geometry: AoiGeometry;
  format: AoiImportFormat;
  featureCount: number;
};

export type AoiImportErrorCode =
  | "unsupported_format"
  | "invalid_file"
  | "empty_geometry"
  | "incomplete_shapefile"
  | "projection_error";

export const AOI_IMPORT_ERROR_MESSAGES: Record<AoiImportErrorCode, string> = {
  unsupported_format: "Unsupported file format. Use GeoJSON, Shapefile, KML or KMZ.",
  invalid_file: "The selected file is invalid or could not be read.",
  empty_geometry: "The file does not contain a valid polygon geometry.",
  incomplete_shapefile:
    "Incomplete Shapefile. Select the .shp with .shx and .dbf, or import a .zip. A .prj is required only when coordinates are not geographic WGS84.",
  projection_error: "Unable to determine or convert the file projection to WGS84.",
};

export class AoiImportError extends Error {
  code: AoiImportErrorCode;

  constructor(code: AoiImportErrorCode, detail?: string) {
    super(
      detail ? `${AOI_IMPORT_ERROR_MESSAGES[code]} ${detail}` : AOI_IMPORT_ERROR_MESSAGES[code],
    );
    this.name = "AoiImportError";
    this.code = code;
  }
}

const MAX_IMPORT_BYTES = 25 * 1024 * 1024;
const WEB_MERCATOR_ALIASES = ["3857", "900913", "3785", "web mercator", "pseudo-mercator"];
const WGS84_ALIASES = ["4326", "crs84", "wgs 84", "wgs84", "epsg:4326"];

function ringAreaKm2(ring: number[][]) {
  if (ring.length < 4) return 0;
  const meanLat =
    ((ring.reduce((sum, point) => sum + Number(point[1] || 0), 0) / ring.length) * Math.PI) / 180;
  const kmPerDegreeLongitude = 111.32 * Math.max(Math.cos(meanLat), 0.25);
  const kmPerDegreeLatitude = 110.57;
  let doubleArea = 0;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[index + 1];
    doubleArea +=
      x1 * kmPerDegreeLongitude * (y2 * kmPerDegreeLatitude) -
      x2 * kmPerDegreeLongitude * (y1 * kmPerDegreeLatitude);
  }
  return Math.abs(doubleArea) / 2;
}

export function aoiGeometryAreaKm2(geometry: AoiGeometry | null | undefined) {
  if (!geometry) return 0;
  const polygonArea = (polygon: number[][][]) => {
    const outer = polygon[0] ? ringAreaKm2(polygon[0]) : 0;
    const holes = polygon.slice(1).reduce((sum, ring) => sum + ringAreaKm2(ring), 0);
    return Math.max(outer - holes, 0);
  };
  if (geometry.type === "Polygon") return polygonArea(geometry.coordinates as number[][][]);
  return (geometry.coordinates as number[][][][]).reduce(
    (sum, polygon) => sum + polygonArea(polygon),
    0,
  );
}

function fileExt(name: string) {
  const lower = name.toLowerCase();
  const idx = lower.lastIndexOf(".");
  return idx >= 0 ? lower.slice(idx) : "";
}

function basename(name: string) {
  return name
    .replace(/^.*[/\\]/, "")
    .replace(/\.[^.]+$/, "")
    .toLowerCase();
}

function pair(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) return null;
  const x = Number(value[0]);
  const y = Number(value[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

function firstCoordinate(value: unknown): [number, number] | null {
  const asPair = pair(value);
  if (asPair) return asPair;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = firstCoordinate(item);
      if (found) return found;
    }
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return firstCoordinate(obj.coordinates ?? obj.geometry ?? obj.features ?? obj.geometries);
  }
  return null;
}

function looksGeographic(coord: [number, number]) {
  return Math.abs(coord[0]) <= 180 && Math.abs(coord[1]) <= 90;
}

function looksProjected(coord: [number, number]) {
  return Math.abs(coord[0]) > 180 || Math.abs(coord[1]) > 90;
}

function inverseWebMercator([x, y]: [number, number]): [number, number] {
  const r = 6378137;
  const lng = (x / r) * (180 / Math.PI);
  const lat = (2 * Math.atan(Math.exp(y / r)) - Math.PI / 2) * (180 / Math.PI);
  return [lng, lat];
}

function transformCoordinates(
  value: unknown,
  project: (xy: [number, number]) => [number, number],
): any {
  if (Array.isArray(value) && typeof value[0] === "number") {
    const asPair = pair(value);
    if (!asPair) return value;
    const [lng, lat] = project(asPair);
    return value.length > 2 ? [lng, lat, ...value.slice(2)] : [lng, lat];
  }
  if (Array.isArray(value)) return value.map((item) => transformCoordinates(item, project));
  if (value && typeof value === "object") {
    const obj = value as Record<string, any>;
    if (obj.coordinates)
      return { ...obj, coordinates: transformCoordinates(obj.coordinates, project) };
    if (obj.geometry) return { ...obj, geometry: transformCoordinates(obj.geometry, project) };
    if (Array.isArray(obj.features))
      return {
        ...obj,
        features: obj.features.map((feature: any) => transformCoordinates(feature, project)),
      };
    if (Array.isArray(obj.geometries))
      return {
        ...obj,
        geometries: obj.geometries.map((geometry: any) => transformCoordinates(geometry, project)),
      };
  }
  return value;
}

function closeRing(ring: number[][]) {
  if (ring.length < 3) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) return [...ring, [...first]];
  return ring;
}

function normalizePolygonCoordinates(coordinates: unknown): number[][][] | null {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return null;
  const rings = coordinates
    .map((ring) => {
      if (!Array.isArray(ring)) return [];
      return closeRing(
        ring.map((point) => pair(point)).filter((item): item is [number, number] => Boolean(item)),
      );
    })
    .filter((ring) => ring.length >= 4);
  return rings.length ? rings : null;
}

function normalizeMultiPolygonCoordinates(coordinates: unknown): number[][][][] | null {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return null;
  const polygons = coordinates
    .map((polygon) => normalizePolygonCoordinates(polygon))
    .filter((item): item is number[][][] => Boolean(item));
  return polygons.length ? polygons : null;
}

function geometryFromObject(input: any): AoiGeometry[] {
  if (!input || typeof input !== "object") return [];
  const type = String(input.type || "");
  if (type === "Feature") return geometryFromObject(input.geometry);
  if (type === "FeatureCollection") {
    return (Array.isArray(input.features) ? input.features : []).flatMap((feature: any) =>
      geometryFromObject(feature),
    );
  }
  if (type === "GeometryCollection") {
    return (Array.isArray(input.geometries) ? input.geometries : []).flatMap((geometry: any) =>
      geometryFromObject(geometry),
    );
  }
  if (type === "Polygon") {
    const coordinates = normalizePolygonCoordinates(input.coordinates);
    return coordinates ? [{ type: "Polygon", coordinates }] : [];
  }
  if (type === "MultiPolygon") {
    const coordinates = normalizeMultiPolygonCoordinates(input.coordinates);
    return coordinates ? [{ type: "MultiPolygon", coordinates }] : [];
  }
  return [];
}

function mergeGeometries(geometries: AoiGeometry[]): AoiGeometry | null {
  if (!geometries.length) return null;
  if (geometries.length === 1) return geometries[0];
  const parts: number[][][][] = [];
  for (const geometry of geometries) {
    if (geometry.type === "Polygon") parts.push(geometry.coordinates as number[][][]);
    else parts.push(...(geometry.coordinates as number[][][][]));
  }
  return { type: "MultiPolygon", coordinates: parts };
}

function bboxFromGeometry(geometry: AoiGeometry): AoiBBox {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const visit = (value: unknown) => {
    const asPair = pair(value);
    if (asPair) {
      minX = Math.min(minX, asPair[0]);
      maxX = Math.max(maxX, asPair[0]);
      minY = Math.min(minY, asPair[1]);
      maxY = Math.max(maxY, asPair[1]);
      return;
    }
    if (Array.isArray(value)) value.forEach(visit);
  };
  visit(geometry.coordinates);
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
    throw new AoiImportError("empty_geometry");
  }
  if (minX === maxX || minY === maxY) {
    throw new AoiImportError("empty_geometry");
  }
  if (minX < -180 || maxX > 180 || minY < -90 || maxY > 90) {
    throw new AoiImportError("projection_error");
  }
  return [
    [minY, minX],
    [maxY, maxX],
  ];
}

function extractCrsName(input: any): string {
  const crs = input?.crs?.properties?.name ?? input?.crs?.name ?? input?.crs ?? "";
  return String(crs).toLowerCase();
}

function isWgs84Name(name: string) {
  return !name || WGS84_ALIASES.some((alias) => name.includes(alias));
}

function isWebMercatorName(name: string) {
  return WEB_MERCATOR_ALIASES.some((alias) => name.includes(alias));
}

export function normalizeImportedGeoJson(input: unknown, format: AoiImportFormat): ImportedAoi {
  if (!input || typeof input !== "object") {
    throw new AoiImportError("invalid_file");
  }
  const geojson = input as Record<string, any>;
  const crsName = extractCrsName(geojson);
  const sample = firstCoordinate(
    geojson.coordinates ?? geojson.features ?? geojson.geometry ?? geojson,
  );
  if (!sample) throw new AoiImportError("empty_geometry");

  let prepared = geojson;
  if (isWebMercatorName(crsName) || (looksProjected(sample) && isWebMercatorName(crsName))) {
    prepared = transformCoordinates(geojson, inverseWebMercator);
  } else if (looksProjected(sample) && !isWgs84Name(crsName)) {
    throw new AoiImportError("projection_error");
  } else if (looksProjected(sample) && isWgs84Name(crsName) && !crsName) {
    throw new AoiImportError("projection_error");
  }

  const geometries = geometryFromObject(prepared);
  const geometry = mergeGeometries(geometries);
  if (!geometry) throw new AoiImportError("empty_geometry");
  const bbox = bboxFromGeometry(geometry);
  return {
    bbox,
    geometry,
    format,
    featureCount: geometries.length,
  };
}

function parseJsonText(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    throw new AoiImportError("invalid_file");
  }
}

function parseKmlCoordinates(text: string): number[][] {
  return text
    .trim()
    .split(/[\s\n]+/)
    .map((item) => item.split(",").map(Number))
    .filter((item) => item.length >= 2 && Number.isFinite(item[0]) && Number.isFinite(item[1]))
    .map(([lng, lat]) => [lng, lat]);
}

export function parseKmlText(text: string): Record<string, any> {
  if (
    !text ||
    (!/<(?:\w+:)?kml\b/i.test(text) &&
      !/<(?:\w+:)?polygon\b/i.test(text) &&
      !/<(?:\w+:)?coordinates\b/i.test(text))
  ) {
    throw new AoiImportError("invalid_file");
  }
  const polygons: number[][][][] = [];
  const polygonBlocks = text.matchAll(/<(?:\w+:)?Polygon\b[^>]*>([\s\S]*?)<\/(?:\w+:)?Polygon>/gi);
  for (const block of polygonBlocks) {
    const rings: number[][][] = [];
    const coordBlocks = block[1].matchAll(
      /<(?:\w+:)?coordinates\b[^>]*>([\s\S]*?)<\/(?:\w+:)?coordinates>/gi,
    );
    for (const coords of coordBlocks) {
      const ring = closeRing(parseKmlCoordinates(coords[1]));
      if (ring.length >= 4) rings.push(ring);
    }
    if (rings.length) polygons.push(rings);
  }
  if (!polygons.length) {
    throw new AoiImportError("empty_geometry");
  }
  return polygons.length === 1
    ? { type: "Polygon", coordinates: polygons[0] }
    : { type: "MultiPolygon", coordinates: polygons };
}

async function parseZip(buffer: ArrayBuffer) {
  const JSZip = (await import("jszip")).default;
  return JSZip.loadAsync(buffer);
}

async function filesFromShapefileZip(buffer: ArrayBuffer): Promise<File[]> {
  const zip = await parseZip(buffer);
  const files: File[] = [];
  for (const [name, entry] of Object.entries(zip.files)) {
    const zipEntry = entry as { dir?: boolean; async: (kind: string) => Promise<Uint8Array> };
    if (zipEntry.dir) continue;
    const ext = fileExt(name);
    if (![".shp", ".shx", ".dbf", ".prj", ".cpg"].includes(ext)) continue;
    const data = await zipEntry.async("uint8array");
    files.push(new File([data], name.replace(/^.*[/\\]/, ""), { type: "application/octet-stream" }));
  }
  if (!files.some((file) => fileExt(file.name) === ".shp")) {
    throw new AoiImportError("incomplete_shapefile");
  }
  return files;
}

async function parseShapefileFromZip(buffer: ArrayBuffer) {
  const zipFiles = await filesFromShapefileZip(buffer);
  const hasPrj = zipFiles.some((file) => fileExt(file.name) === ".prj");
  const shpMod: any = await import("shpjs");
  const parseZipFn = shpMod.parseZip ?? shpMod.default;
  try {
    const parsed = await parseZipFn(buffer);
    const geojson = Array.isArray(parsed)
      ? { type: "FeatureCollection", features: parsed.flatMap((item: any) => item.features ?? []) }
      : parsed;
    const sample = firstCoordinate(geojson);
    if (sample && looksProjected(sample) && !hasPrj) {
      throw new AoiImportError(
        "projection_error",
        "Add the matching .prj, or export the shapefile in geographic WGS84.",
      );
    }
    return geojson;
  } catch (error) {
    if (error instanceof AoiImportError) throw error;
    try {
      return await parseLooseShapefile(zipFiles);
    } catch (fallback) {
      if (fallback instanceof AoiImportError) throw fallback;
      const message = error instanceof Error ? error.message : "";
      if (/prj|projection|proj/i.test(message)) throw new AoiImportError("projection_error");
      if (/shp|shapefile|dbf|shx|layers/i.test(message)) {
        throw new AoiImportError("incomplete_shapefile");
      }
      throw new AoiImportError("invalid_file");
    }
  }
}

async function parseLooseShapefile(files: File[]) {
  const shpFile = files.find((file) => fileExt(file.name) === ".shp");
  if (!shpFile) throw new AoiImportError("incomplete_shapefile");
  const stem = basename(shpFile.name);
  const sidecar = (ext: string) =>
    files.find((file) => fileExt(file.name) === ext && basename(file.name) === stem);
  const dbfFile = sidecar(".dbf");
  const prjFile = sidecar(".prj");
  const cpgFile = sidecar(".cpg");
  const shpMod: any = await import("shpjs");
  const parseShapefile = shpMod.default ?? shpMod;
  try {
    const shpBuffer = await shpFile.arrayBuffer();
    const prjText = prjFile ? await prjFile.text() : undefined;
    const cpgText = cpgFile ? await cpgFile.text() : undefined;
    let parsed;
    try {
      parsed = await parseShapefile({
        shp: shpBuffer,
        dbf: dbfFile ? await dbfFile.arrayBuffer() : undefined,
        prj: prjText,
        cpg: cpgText,
      });
    } catch {
      parsed = await parseShapefile({ shp: shpBuffer, prj: prjText });
    }
    const sample = firstCoordinate(parsed);
    if (sample && looksProjected(sample) && !prjFile) {
      throw new AoiImportError(
        "projection_error",
        "Add the matching .prj, or export the shapefile in geographic WGS84.",
      );
    }
    return parsed;
  } catch (error) {
    if (error instanceof AoiImportError) throw error;
    throw new AoiImportError("invalid_file");
  }
}

async function detectZipKind(file: File): Promise<"shapefile" | "kmz" | "geojson"> {
  const zip = await parseZip(await file.arrayBuffer());
  const names = Object.keys(zip.files).map((name) => name.toLowerCase());
  if (names.some((name) => name.endsWith(".shp"))) return "shapefile";
  if (names.some((name) => name.endsWith(".kml"))) return "kmz";
  if (names.some((name) => name.endsWith(".geojson") || name.endsWith(".json"))) return "geojson";
  throw new AoiImportError("unsupported_format");
}

async function geoJsonFromZip(file: File) {
  const zip = await parseZip(await file.arrayBuffer());
  const entry = Object.values(zip.files).find((item: any) => {
    const name = String(item.name || "").toLowerCase();
    return !item.dir && (name.endsWith(".geojson") || name.endsWith(".json"));
  });
  if (!entry) throw new AoiImportError("invalid_file");
  return parseJsonText(await (entry as any).async("string"));
}

async function kmlFromKmz(file: File) {
  const zip = await parseZip(await file.arrayBuffer());
  const entry = Object.values(zip.files).find((item: any) => {
    const name = String(item.name || "").toLowerCase();
    return !item.dir && name.endsWith(".kml");
  });
  if (!entry) throw new AoiImportError("invalid_file");
  return parseKmlText(await (entry as any).async("string"));
}

function ensureReadableFiles(files: File[]) {
  if (!files.length) throw new AoiImportError("invalid_file");
  const oversized = files.find((file) => file.size > MAX_IMPORT_BYTES);
  if (oversized) throw new AoiImportError("invalid_file", "The file exceeds 25 MB.");
}

export async function importAoiFromFiles(files: File[]): Promise<ImportedAoi> {
  ensureReadableFiles(files);
  const named = files.filter((file) => file.name);
  const exts = named.map((file) => fileExt(file.name));
  const hasShp = exts.includes(".shp");
  const zipFile = named.find((file) => fileExt(file.name) === ".zip");
  const kmzFile = named.find((file) => fileExt(file.name) === ".kmz");
  const kmlFile = named.find((file) => fileExt(file.name) === ".kml");
  const geojsonFile = named.find((file) => [".geojson", ".json"].includes(fileExt(file.name)));

  try {
    if (kmzFile) {
      return normalizeImportedGeoJson(await kmlFromKmz(kmzFile), "kmz");
    }
    if (kmlFile) {
      return normalizeImportedGeoJson(parseKmlText(await kmlFile.text()), "kml");
    }
    if (zipFile) {
      const kind = await detectZipKind(zipFile);
      if (kind === "shapefile") {
        return normalizeImportedGeoJson(
          await parseShapefileFromZip(await zipFile.arrayBuffer()),
          "shapefile",
        );
      }
      if (kind === "kmz") {
        return normalizeImportedGeoJson(await kmlFromKmz(zipFile), "kmz");
      }
      return normalizeImportedGeoJson(await geoJsonFromZip(zipFile), "geojson");
    }
    if (hasShp) {
      return normalizeImportedGeoJson(await parseLooseShapefile(named), "shapefile");
    }
    if (geojsonFile) {
      return normalizeImportedGeoJson(parseJsonText(await geojsonFile.text()), "geojson");
    }
    if (exts.some((ext) => [".shx", ".dbf", ".prj", ".cpg"].includes(ext))) {
      throw new AoiImportError("incomplete_shapefile");
    }
    throw new AoiImportError("unsupported_format");
  } catch (error) {
    if (error instanceof AoiImportError) throw error;
    throw new AoiImportError("invalid_file");
  }
}

export function aoiImportUserMessage(error: unknown) {
  if (error instanceof AoiImportError) return AOI_IMPORT_ERROR_MESSAGES[error.code];
  return AOI_IMPORT_ERROR_MESSAGES.invalid_file;
}
