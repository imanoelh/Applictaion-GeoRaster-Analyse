import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  ImageOverlay,
  Rectangle,
  LayersControl,
  ScaleControl,
  useMap,
  useMapEvents,
  CircleMarker,
  Polygon,
  Polyline,
  Popup,
  Tooltip,
  GeoJSON as LeafletGeoJSON,
} from "react-leaflet";
import L from "leaflet";
import type { Feature, GeoJsonObject, Geometry } from "geojson";
import type { SatImage, SpectralIndex } from "@/data/mock";
import { Layers, Crosshair } from "lucide-react";
import { canRecolorPalette, recolorRgbaPixels } from "@/lib/palette-recolor";
import {
  BUILDING_LAYER_STYLE,
  buildingPopupFields,
  isValidWgs84Bounds,
  type BuildingAnalysisResult,
  type BuildingFeatureProperties,
} from "@/features/ai-building/model";

type AoiGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

type Props = {
  selectedImage: SatImage | null;
  aoi: [[number, number], [number, number]] | null;
  aoiGeometry?: AoiGeometry | null;
  aoiParts?: {
    part_id: string;
    row: number;
    column: number;
    geojson: AoiGeometry;
    area_km2: number;
  }[];
  selectedPartIds?: string[];
  onToggleAoiPart?: (partId: string) => void;
  aoiFitNonce?: number;
  showAoi: boolean;
  showRaster: boolean;
  showResult: boolean;
  rasterOpacity: number;
  resultOpacity: number;
  drawMode: "rectangle" | "point" | "polygon" | null;
  basemap: "osm" | "satellite" | "googleSatellite" | "terrain" | "light";
  onAoiDrawn: (bbox: [[number, number], [number, number]]) => void;
  resultIndex: SpectralIndex | null;
  rasterTileUrl?: string | null;
  rasterImageUrl?: string | null;
  rasterImageBounds?: [[number, number], [number, number]] | null;
  resultTileUrl?: string | null;
  resultSourcePalette?: string[] | null;
  resultDisplayPalette?: string[] | null;
  samples?: any[];
  classes?: any[];
  resultClasses?: any[];
  legendTitle?: string;
  legendDirection?: "ltr" | "rtl";
  legendNote?: string;
  continuousLegend?: { min: number; max: number; palette: string[] } | null;
  recenterTitle?: string;
  onSampleCreated?: (sample: { type: string; geometry: any; properties?: any }) => void;
  onResultTileError?: () => void;
  buildingResult?: BuildingAnalysisResult | null;
  showBuildingLayer?: boolean;
  buildingFitNonce?: number;
};

class LocalPaletteGridLayer extends L.GridLayer {
  constructor(
    private readonly tileUrl: string,
    private readonly sourcePalette: string[],
    private readonly displayPalette: string[],
    private readonly onTileError: (() => void) | undefined,
    options: L.GridLayerOptions,
  ) {
    super(options);
  }

  public override createTile(coords: L.Coords, done: L.DoneCallback): HTMLElement {
    const canvas = document.createElement("canvas");
    const size = this.getTileSize();
    canvas.width = size.x;
    canvas.height = size.y;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    const image = new Image();
    image.crossOrigin = "anonymous";

    image.onload = () => {
      if (!context) {
        done(undefined, canvas);
        return;
      }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      try {
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        recolorRgbaPixels(imageData.data, this.sourcePalette, this.displayPalette);
        context.putImageData(imageData, 0, 0);
      } catch {
        // If pixel access is blocked by the remote tile host, preserve the
        // original tile instead of replacing it with an empty layer.
      }
      done(undefined, canvas);
    };
    image.onerror = () => {
      this.onTileError?.();
      done(new Error("Unable to load the classified result tile"), canvas);
    };
    image.src = L.Util.template(this.tileUrl, {
      x: coords.x,
      y: coords.y,
      z: coords.z,
      s: "a",
      r: L.Browser.retina ? "@2x" : "",
    });
    return canvas;
  }
}

function LocallyRecoloredTileLayer({
  url,
  sourcePalette,
  displayPalette,
  opacity,
  onTileError,
}: {
  url: string;
  sourcePalette: string[];
  displayPalette: string[];
  opacity: number;
  onTileError?: () => void;
}) {
  const map = useMap();
  const sourcePaletteKey = sourcePalette.join(",");
  const displayPaletteKey = displayPalette.join(",");

  useEffect(() => {
    const layer = new LocalPaletteGridLayer(url, sourcePalette, displayPalette, onTileError, {
      opacity,
      zIndex: 450,
      className: "georaster-result-tile georaster-local-palette-tile",
      tileSize: 256,
    });

    layer.addTo(map);
    return () => {
      layer.removeFrom(map);
    };
  }, [displayPaletteKey, map, onTileError, opacity, sourcePaletteKey, url]);

  return null;
}

function Coordinates() {
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  useMapEvents({
    mousemove(e) {
      setPos({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return (
    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-[400] bg-card/95 border rounded-md px-3 py-1 text-xs font-mono shadow-sm pointer-events-none">
      {pos ? `${pos.lat.toFixed(5)}°N, ${pos.lng.toFixed(5)}°E` : "—"}
    </div>
  );
}

function Recenter({ target }: { target: [number, number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.setView([target[0], target[1]], target[2]);
  }, [target, map]);
  return null;
}

function geoJsonToLatLngs(
  geometry: AoiGeometry,
): L.LatLngExpression[][] | L.LatLngExpression[][][] {
  const ringToLatLngs = (ring: number[][]) =>
    ring.map(([lng, lat]) => [lat, lng] as [number, number]);
  if (geometry.type === "Polygon") {
    return (geometry.coordinates as number[][][]).map(ringToLatLngs);
  }
  return (geometry.coordinates as number[][][][]).map((polygon) => polygon.map(ringToLatLngs));
}

/** High-contrast AOI outline only: bold orange stroke, no fill (keeps imagery readable). */
const AOI_PATH_OPTIONS = {
  color: "#c2410c",
  weight: 4,
  fillColor: "#f97316",
  fillOpacity: 0,
  fill: false,
  opacity: 1,
} as const;

function boundsFromGeometry(geometry: AoiGeometry) {
  const points: [number, number][] = [];
  const visit = (value: unknown) => {
    if (
      Array.isArray(value) &&
      value.length >= 2 &&
      typeof value[0] === "number" &&
      typeof value[1] === "number"
    ) {
      points.push([value[1] as number, value[0] as number]);
      return;
    }
    if (Array.isArray(value)) value.forEach(visit);
  };
  visit(geometry.coordinates);
  if (points.length === 0) return L.latLngBounds([0, 0], [0, 0]);
  return L.latLngBounds(points);
}

function FitAoi({
  aoi,
  geometry,
  nonce,
}: {
  aoi: [[number, number], [number, number]] | null;
  geometry?: AoiGeometry | null;
  nonce?: number;
}) {
  const map = useMap();
  useEffect(() => {
    if (!nonce || !aoi) return;
    const bounds = geometry ? boundsFromGeometry(geometry) : L.latLngBounds(aoi[0], aoi[1]);
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 16, animate: true });
    }
  }, [aoi, geometry, map, nonce]);
  return null;
}

function FitBuildingBounds({ result, nonce }: { result: BuildingAnalysisResult | null; nonce: number }) {
  const map = useMap();
  useEffect(() => {
    if (!nonce || !result || result.candidate_count === 0 || !isValidWgs84Bounds(result.wgs84_bounds)) return;
    const { left, bottom, right, top } = result.wgs84_bounds;
    map.fitBounds([[bottom, left], [top, right]], { padding: [36, 36], maxZoom: 19, animate: true });
  }, [map, nonce, result]);
  return null;
}

function buildingPopupContent(properties: BuildingFeatureProperties) {
  const container = document.createElement("div");
  container.className = "min-w-[210px] text-xs";
  const heading = document.createElement("div");
  heading.className = "mb-2 font-semibold";
  heading.textContent = "AI Building Candidate";
  container.appendChild(heading);
  for (const [label, value] of buildingPopupFields(properties)) {
    const row = document.createElement("div");
    row.className = "grid grid-cols-[72px_1fr] gap-2 border-t py-1";
    const key = document.createElement("span");
    key.className = "text-slate-500";
    key.textContent = label;
    const content = document.createElement("span");
    content.textContent = value;
    row.append(key, content);
    container.appendChild(row);
  }
  return container;
}

function DrawHandler({
  active,
  onDone,
}: {
  active: boolean;
  onDone: (bbox: [[number, number], [number, number]]) => void;
}) {
  const map = useMap();
  const startRef = useRef<L.LatLng | null>(null);
  const rectRef = useRef<L.Rectangle | null>(null);

  useEffect(() => {
    if (!active) return;
    map.dragging.disable();
    map.getContainer().style.cursor = "crosshair";

    const onDown = (e: L.LeafletMouseEvent) => {
      startRef.current = e.latlng;
      if (rectRef.current) {
        rectRef.current.remove();
        rectRef.current = null;
      }
    };
    const onMove = (e: L.LeafletMouseEvent) => {
      if (!startRef.current) return;
      const bounds = L.latLngBounds(startRef.current, e.latlng);
      if (!rectRef.current) {
        rectRef.current = L.rectangle(bounds, {
          color: "#c2410c",
          weight: 4,
          fill: false,
          fillOpacity: 0,
          opacity: 1,
          dashArray: "4 4",
        }).addTo(map);
      } else {
        rectRef.current.setBounds(bounds);
      }
    };
    const onUp = (e: L.LeafletMouseEvent) => {
      if (!startRef.current) return;
      const s = startRef.current;
      const end = e.latlng;
      startRef.current = null;
      const sw: [number, number] = [Math.min(s.lat, end.lat), Math.min(s.lng, end.lng)];
      const ne: [number, number] = [Math.max(s.lat, end.lat), Math.max(s.lng, end.lng)];
      if (rectRef.current) {
        rectRef.current.remove();
        rectRef.current = null;
      }
      onDone([sw, ne]);
    };

    map.on("mousedown", onDown);
    map.on("mousemove", onMove);
    map.on("mouseup", onUp);
    return () => {
      map.off("mousedown", onDown);
      map.off("mousemove", onMove);
      map.off("mouseup", onUp);
      map.dragging.enable();
      map.getContainer().style.cursor = "";
      if (rectRef.current) {
        rectRef.current.remove();
        rectRef.current = null;
      }
    };
  }, [active, map, onDone]);

  return null;
}

function PointHandler({
  active,
  onCreate,
}: {
  active: boolean;
  onCreate: (latlng: L.LatLng) => void;
}) {
  const map = useMap();
  useEffect(() => {
    if (!active) return;
    map.dragging.disable();
    map.getContainer().style.cursor = "crosshair";

    const onClick = (e: L.LeafletMouseEvent) => {
      onCreate(e.latlng);
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
      map.dragging.enable();
      map.getContainer().style.cursor = "";
    };
  }, [active, map, onCreate]);
  return null;
}

function PolygonHandler({
  active,
  onCreate,
}: {
  active: boolean;
  onCreate: (coords: L.LatLng[]) => void;
}) {
  const map = useMap();
  const vertsRef = useRef<L.LatLng[]>([]);
  const polyRef = useRef<L.Polyline | null>(null);

  useEffect(() => {
    if (!active) return;
    map.dragging.disable();
    map.getContainer().style.cursor = "crosshair";

    const onClick = (e: L.LeafletMouseEvent) => {
      vertsRef.current.push(e.latlng);
      if (!polyRef.current) {
        polyRef.current = L.polyline(vertsRef.current, {
          color: "#06b6d4",
          weight: 2,
          dashArray: "4 4",
        }).addTo(map);
      } else {
        polyRef.current.setLatLngs(vertsRef.current);
      }
    };

    const onDbl = () => {
      if (vertsRef.current.length < 3) {
        vertsRef.current = [];
        if (polyRef.current) {
          polyRef.current.remove();
          polyRef.current = null;
        }
        return;
      }
      const coords = vertsRef.current.slice();
      vertsRef.current = [];
      if (polyRef.current) {
        polyRef.current.remove();
        polyRef.current = null;
      }
      onCreate(coords);
    };

    map.on("click", onClick);
    map.on("dblclick", onDbl);

    return () => {
      map.off("click", onClick);
      map.off("dblclick", onDbl);
      map.dragging.enable();
      map.getContainer().style.cursor = "";
      if (polyRef.current) {
        polyRef.current.remove();
        polyRef.current = null;
      }
      vertsRef.current = [];
    };
  }, [active, map, onCreate]);
  return null;
}

const BASEMAPS = {
  osm: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: "© OpenStreetMap",
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "Esri World Imagery",
  },
  googleSatellite: {
    url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr: "Google Satellite",
  },
  terrain: {
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr: "© OpenTopoMap",
  },
  light: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr: "© CARTO",
  },
};

export function MapView(props: Props) {
  const {
    selectedImage,
    aoi,
    aoiGeometry = null,
    aoiParts = [],
    selectedPartIds = [],
    onToggleAoiPart,
    aoiFitNonce = 0,
    showAoi,
    showRaster,
    showResult,
    rasterOpacity,
    resultOpacity,
    drawMode,
    basemap,
    onAoiDrawn,
    resultIndex,
    rasterTileUrl,
    rasterImageUrl,
    rasterImageBounds,
    resultTileUrl,
    resultSourcePalette,
    resultDisplayPalette,
    samples,
    classes,
    resultClasses,
    legendTitle = "Legend",
    legendDirection = "ltr",
    legendNote,
    continuousLegend,
    recenterTitle = "Recenter map",
    onSampleCreated,
    onResultTileError,
    buildingResult = null,
    showBuildingLayer = false,
    buildingFitNonce = 0,
  } = props;

  const propsSamples = samples ?? [];
  const propsOnSampleCreated = onSampleCreated;
  const legendItems =
    (resultClasses ?? []).length > 0
      ? (resultClasses ?? []).map((item: any, idx: number) => {
          const label = item.label ?? item.name ?? `Class ${idx + 1}`;
          const matchedLegend = (resultIndex?.legend ?? []).find(
            (entry) =>
              entry.label === label ||
              entry.label === item.name ||
              entry.label === item.label ||
              (typeof label === "string" &&
                typeof entry.label === "string" &&
                label.toLowerCase().includes(String(entry.label).toLowerCase())),
          );
          return {
            key: item.name ?? item.label ?? `class-${idx}`,
            label,
            // Never fall back by array index: supervised class order ≠ mock legend order.
            meaning: item.meaning ?? item.description ?? matchedLegend?.meaning ?? "",
            color: item.color ?? "#94a3b8",
          };
        })
      : (resultIndex?.legend ?? []).map((item, idx) => ({
          key: item.label ?? `legend-${idx}`,
          label: item.label,
          meaning: item.meaning,
          color: item.color,
        }));
  const classesMap = useMemo(() => {
    const m: Record<string, any> = {};
    (classes ?? []).forEach((c: any) => {
      if (c.id) m[c.id] = c;
      if (c.code != null) m[String(c.code)] = c;
    });
    return m;
  }, [classes]);

  const [recenter, setRecenter] = useState<[number, number, number] | null>(null);
  const buildingLayerRef = useRef<L.GeoJSON | null>(null);
  const selectedBuildingIdRef = useRef<string | null>(null);

  useEffect(() => {
    selectedBuildingIdRef.current = null;
    buildingLayerRef.current?.closePopup();
  }, [buildingResult?.analysis_id, showBuildingLayer]);

  useEffect(() => {
    if (selectedImage) {
      const [s, w, n, e] = selectedImage.bbox;
      setRecenter([(s + n) / 2, (w + e) / 2, 11]);
    }
  }, [selectedImage]);

  const rasterBounds: [[number, number], [number, number]] | null = selectedImage
    ? [
        [selectedImage.bbox[0], selectedImage.bbox[1]],
        [selectedImage.bbox[2], selectedImage.bbox[3]],
      ]
    : null;

  const bm = BASEMAPS[basemap];
  const useLocalResultPalette =
    canRecolorPalette(resultSourcePalette, resultDisplayPalette) &&
    resultSourcePalette!.some(
      (color, index) => color.toLowerCase() !== resultDisplayPalette![index]?.toLowerCase(),
    );

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[23.8859, 45.0792]}
        zoom={5}
        className="h-full w-full"
        zoomControl={true}
      >
        <TileLayer
          key={basemap}
          url={bm.url}
          attribution={bm.attr}
          crossOrigin="anonymous"
          className="georaster-basemap-tile"
        />
        <ScaleControl position="bottomleft" />
        <Recenter target={recenter} />
        <FitAoi aoi={aoi} geometry={aoiGeometry} nonce={aoiFitNonce} />
        <FitBuildingBounds result={buildingResult} nonce={buildingFitNonce} />
        <DrawHandler active={drawMode === "rectangle"} onDone={onAoiDrawn} />
        <PointHandler
          active={drawMode === "point"}
          onCreate={(latlng) => {
            if (propsOnSampleCreated)
              propsOnSampleCreated({
                type: "Point",
                geometry: { type: "Point", coordinates: [latlng.lng, latlng.lat] },
              });
          }}
        />
        <PolygonHandler
          active={drawMode === "polygon"}
          onCreate={(coords) => {
            if (propsOnSampleCreated) {
              const ring = coords.map((p) => [p.lng, p.lat]);
              if (ring.length > 0) ring.push([...ring[0]]);
              propsOnSampleCreated({
                type: "Polygon",
                geometry: { type: "Polygon", coordinates: [ring] },
              });
            }
          }}
        />

        {/* Real GEE RGB tile when available; fallback rectangle for mock/offline mode */}
        {showRaster && rasterTileUrl && (
          <TileLayer
            key={rasterTileUrl}
            url={rasterTileUrl}
            opacity={rasterOpacity}
            crossOrigin="anonymous"
            zIndex={300}
            className="georaster-source-tile"
          />
        )}
        {showRaster && !rasterTileUrl && rasterImageUrl && rasterImageBounds && (
          <ImageOverlay
            key={rasterImageUrl}
            url={rasterImageUrl}
            bounds={rasterImageBounds}
            opacity={rasterOpacity}
            zIndex={300}
            className="georaster-local-orthophoto"
          />
        )}
        {showRaster && !rasterTileUrl && rasterBounds && !aoiGeometry && aoiParts.length === 0 && (
          <Rectangle
            bounds={rasterBounds}
            pathOptions={{
              color: "#1e40af",
              weight: 1,
              fillColor: "#3b82f6",
              fillOpacity: 0.15 * rasterOpacity,
              dashArray: "6 4",
            }}
          />
        )}

        {/* Real GEE index tile when available; fallback classes for mock/offline mode */}
        {showResult && resultTileUrl && useLocalResultPalette && (
          <LocallyRecoloredTileLayer
            url={resultTileUrl}
            sourcePalette={resultSourcePalette!}
            displayPalette={resultDisplayPalette!}
            opacity={resultOpacity}
            onTileError={onResultTileError}
          />
        )}
        {showResult && resultTileUrl && !useLocalResultPalette && (
          <TileLayer
            key={resultTileUrl}
            url={resultTileUrl}
            opacity={resultOpacity}
            crossOrigin="anonymous"
            zIndex={450}
            className="georaster-result-tile"
            maxNativeZoom={resultIndex?.id === "OSI_SAR" ? 13 : undefined}
            eventHandlers={onResultTileError ? { tileerror: onResultTileError } : undefined}
          />
        )}

        {showBuildingLayer && buildingResult && buildingResult.candidate_count > 0 && (
          <LeafletGeoJSON
            key={buildingResult.analysis_id}
            ref={buildingLayerRef}
            data={buildingResult.feature_collection as unknown as GeoJsonObject}
            style={() => ({ ...BUILDING_LAYER_STYLE.normal })}
            onEachFeature={(
              feature: Feature<Geometry, BuildingFeatureProperties>,
              layer: L.Layer,
            ) => {
              const path = layer as L.Path;
              const id = feature.properties.object_id;
              path.bindPopup(buildingPopupContent(feature.properties));
              path.on({
                mouseover: () => {
                  if (selectedBuildingIdRef.current !== id) path.setStyle({ ...BUILDING_LAYER_STYLE.hover });
                },
                mouseout: () => {
                  path.setStyle({ ...(selectedBuildingIdRef.current === id ? BUILDING_LAYER_STYLE.selected : BUILDING_LAYER_STYLE.normal) });
                },
                click: () => {
                  selectedBuildingIdRef.current = id;
                  buildingLayerRef.current?.eachLayer((candidate) => {
                    if (candidate instanceof L.Path) candidate.setStyle({ ...BUILDING_LAYER_STYLE.normal });
                  });
                  path.setStyle({ ...BUILDING_LAYER_STYLE.selected });
                },
              });
            }}
          />
        )}

        {/* Samples visualization */}
        {propsSamples &&
          propsSamples.map((s) => {
            try {
              const geom =
                s.geometry ??
                (typeof s.geometry_json === "string"
                  ? JSON.parse(s.geometry_json)
                  : s.geometry_json) ??
                s.geometry_json_text ??
                s.geometry_json;
              const classInfo = classesMap?.[s.class_id] || classesMap?.[String(s.class_code)];
              const color = classInfo?.color ?? "#f97316";
              if (!geom) return null;
              if (geom.type === "Point") {
                const [lng, lat] = geom.coordinates;
                return (
                  <CircleMarker
                    key={s.id ?? `${lng}-${lat}`}
                    center={[lat, lng]}
                    radius={6}
                    pathOptions={{ color, fillColor: color, fillOpacity: 0.9, weight: 2 }}
                  >
                    <Popup>
                      <div className="min-w-[160px]">
                        <div className="font-semibold">{classInfo?.name ?? s.class_id}</div>
                        <div className="text-xs text-muted-foreground">
                          {s.usage ?? s.quality_status ?? ""}
                        </div>
                      </div>
                    </Popup>
                    <Tooltip>{classInfo?.name ?? s.class_id}</Tooltip>
                  </CircleMarker>
                );
              }
              if (geom.type === "Polygon") {
                const coords = geom.coordinates[0].map(([lng, lat]: any) => [lat, lng]);
                return (
                  <Polygon
                    key={s.id ?? coords.length}
                    positions={coords}
                    pathOptions={{ color, weight: 1, fillOpacity: 0.25 }}
                  >
                    <Popup>
                      <div className="min-w-[160px]">
                        <div className="font-semibold">{classInfo?.name ?? s.class_id}</div>
                        <div className="text-xs text-muted-foreground">
                          {s.usage ?? s.quality_status ?? ""}
                        </div>
                      </div>
                    </Popup>
                  </Polygon>
                );
              }
              return null;
            } catch (err) {
              return null;
            }
          })}
        {/* AOI parts: equal-area split of the imported AOI; click one to analyse it alone. */}
        {showAoi &&
          aoiParts.map((part) => {
            const active = selectedPartIds.includes(part.part_id);
            // With a selection active, the cells left out are dimmed. They are
            // already clipped to the AOI, so nothing is painted outside it.
            const dimmed = selectedPartIds.length > 0 && !active;
            return (
              <Polygon
                key={part.part_id}
                positions={geoJsonToLatLngs(part.geojson)}
                pathOptions={{
                  color: active ? AOI_PATH_OPTIONS.color : "#fb923c",
                  weight: active ? 4 : 2,
                  fillColor: dimmed ? "#0f172a" : AOI_PATH_OPTIONS.fillColor,
                  // Outline-first: no fill on active/idle cells so imagery stays visible.
                  // Dimmed (deselected) cells keep a light veil for selection feedback only.
                  fillOpacity: dimmed ? 0.35 : 0,
                  fill: dimmed,
                  opacity: 1,
                  dashArray: active ? undefined : "4 4",
                }}
                eventHandlers={{ click: () => onToggleAoiPart?.(part.part_id) }}
              >
                <Tooltip sticky>
                  R{part.row}C{part.column} - {part.area_km2.toFixed(2)} km2
                </Tooltip>
              </Polygon>
            );
          })}
        {showAoi && aoiGeometry && aoiParts.length === 0 && (
          <Polygon positions={geoJsonToLatLngs(aoiGeometry)} pathOptions={{ ...AOI_PATH_OPTIONS }} />
        )}
        {showAoi && aoi && !aoiGeometry && (
          <Rectangle bounds={aoi} pathOptions={{ ...AOI_PATH_OPTIONS }} />
        )}

        <Coordinates />
      </MapContainer>

      <button
        onClick={() => {
          if (selectedImage) {
            const [s, w, n, e] = selectedImage.bbox;
            setRecenter([(s + n) / 2 + Math.random() * 1e-6, (w + e) / 2, 11]);
          }
        }}
        title={recenterTitle}
        className="absolute top-3 right-3 z-[400] bg-card border rounded-md p-2 shadow-sm hover:bg-muted"
      >
        <Crosshair className="h-4 w-4" />
      </button>

      {/* Legend */}
      {showResult && resultIndex && (
        <div
          dir={legendDirection}
          className="absolute bottom-12 right-3 z-[400] bg-card/95 border rounded-md p-3 shadow-sm text-xs w-72 max-h-[45vh] overflow-auto"
        >
          <div className="flex items-center gap-1.5 mb-1 font-semibold">
            <Layers className="h-3.5 w-3.5" />
            {legendTitle} - {resultIndex.id}
          </div>
          <p className="mb-2 text-[11px] text-muted-foreground">{resultIndex.topic}</p>
          {legendNote ? (
            <p className="mb-2 rounded border border-amber-300/70 bg-amber-50 px-2 py-1.5 text-[10px] leading-snug text-amber-950">
              {legendNote}
            </p>
          ) : null}
          {continuousLegend && continuousLegend.palette.length > 1 ? (
            <div className="mb-2 space-y-1">
              <div
                className="h-2.5 w-full rounded-sm border"
                style={{
                  background: `linear-gradient(to right, ${continuousLegend.palette.join(", ")})`,
                }}
              />
              <div className="flex justify-between text-[10px] tabular-nums text-muted-foreground">
                <span>
                  {Number.isFinite(continuousLegend.min)
                    ? continuousLegend.min.toFixed(2)
                    : "min"}
                </span>
                <span>
                  {Number.isFinite(continuousLegend.max)
                    ? continuousLegend.max.toFixed(2)
                    : "max"}
                </span>
              </div>
            </div>
          ) : null}
          <div className="space-y-1.5">
            {legendItems.map((item) => (
              <div
                key={item.key ?? item.label}
                className="flex items-start gap-2 rounded-sm border bg-card/80 px-2 py-1.5"
              >
                <span
                  className="mt-0.5 h-3 w-3 shrink-0 rounded-sm border"
                  style={{ background: item.color }}
                />
                <div className="min-w-0">
                  <p className="font-medium leading-tight">{item.label}</p>
                  <p className="text-[10px] leading-snug text-muted-foreground">{item.meaning}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {showBuildingLayer && buildingResult && (
        <div className="absolute bottom-12 left-3 z-[400] rounded-md border bg-card/95 px-3 py-2 text-xs shadow-sm">
          <div className="flex items-center gap-2 font-semibold">
            <span className="h-3 w-3 rounded-sm border-2 border-violet-700 bg-violet-300/60" />
            AI Building Candidates
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">{buildingResult.candidate_count.toLocaleString()} candidates · accuracy not validated</p>
        </div>
      )}
    </div>
  );
}

