export type Sensor = "Sentinel-2" | "Landsat 8";

export type SatImage = {
  id: string;
  name: string;
  sensor: Sensor;
  date: string;
  resolution: string;
  projection: string;
  cloud: number;
  bands: string[];
  size: string;
  region: string;
  status: "Available" | "Indexing" | "Archived";
  bbox: [number, number, number, number]; // south, west, north, east
};

export const images: SatImage[] = [
  {
    id: "img-1",
    name: "Sentinel-2 Riyadh 2025",
    sensor: "Sentinel-2",
    date: "2025-04-12",
    resolution: "10 m",
    projection: "EPSG:32638",
    cloud: 4,
    bands: ["B2", "B3", "B4", "B8", "B11", "B12"],
    size: "812 MB",
    region: "Riyadh",
    status: "Available",
    bbox: [24.6, 46.6, 24.8, 46.85],
  },
  {
    id: "img-2",
    name: "Sentinel-2 Jeddah 2025",
    sensor: "Sentinel-2",
    date: "2025-05-03",
    resolution: "10 m",
    projection: "EPSG:32637",
    cloud: 7,
    bands: ["B2", "B3", "B4", "B8", "B11", "B12"],
    size: "765 MB",
    region: "Jeddah",
    status: "Available",
    bbox: [21.38, 39.05, 21.65, 39.35],
  },
  {
    id: "img-3",
    name: "Landsat 8 Medina 2024",
    sensor: "Landsat 8",
    date: "2024-09-18",
    resolution: "30 m",
    projection: "EPSG:32637",
    cloud: 12,
    bands: ["B2", "B3", "B4", "B5", "B6", "B7"],
    size: "1.2 GB",
    region: "Medina",
    status: "Available",
    bbox: [24.35, 39.45, 24.65, 39.75],
  },
];

export type SpectralIndexLegendItem = {
  label: string;
  meaning: string;
  color: string;
};

export type SpectralIndex = {
  id:
    | "NDVI"
    | "NDBI"
    | "NDWI"
    | "BSI"
    | "SAVI"
    | "OSI_SAR"
    | "CHANGE_NDVI"
    | "CHANGE_NDWI"
    | "CHANGE_NDBI"
    | "CHANGE_BSI"
    | "CHANGE_SAVI"
    | "SUPERVISED_CLASSIFICATION"
    | "UNSUPERVISED_CLASSIFICATION";
  name: string;
  topic: string;
  description: string;
  bands: string[];
  palette: string[];
  legend: SpectralIndexLegendItem[];
};

export const indices: SpectralIndex[] = [
  {
    id: "NDVI",
    name: "NDVI",
    topic: "Vegetation",
    description: "Assesses vegetation cover levels only.",
    bands: ["NIR", "Red"],
    palette: ["#a50026", "#d73027", "#f46d43", "#fdae61", "#fee08b", "#a6d96a", "#1a9850", "#006837"],
    legend: [
      {
        label: "< 0.00: water / negative values",
        meaning: "Negative NDVI values, commonly water or non-vegetated surfaces.",
        color: "#a50026",
      },
      {
        label: "0.00–0.08: bare soil / very dry desert",
        meaning: "Bare soil or very dry desert response.",
        color: "#d73027",
      },
      {
        label: "0.08–0.15: very low vegetation activity",
        meaning: "Very low vegetation activity or arid soil response.",
        color: "#f46d43",
      },
      {
        label: "0.15–0.25: very sparse vegetation",
        meaning: "Very sparse vegetation cover.",
        color: "#fdae61",
      },
      { label: "0.25–0.35: low vegetation", meaning: "Low vegetation cover.", color: "#fee08b" },
      {
        label: "0.35–0.50: moderate vegetation",
        meaning: "Moderate vegetation density.",
        color: "#a6d96a",
      },
      {
        label: "0.50–0.70: dense vegetation",
        meaning: "Dense vegetation cover.",
        color: "#1a9850",
      },
      {
        label: ">= 0.70: very dense vegetation",
        meaning: "Very dense and vigorous vegetation cover.",
        color: "#006837",
      },
    ],
  },
  {
    id: "NDBI",
    name: "NDBI",
    topic: "Built-up detection",
    description:
      "Highlights built-up and impervious surfaces using NDBI with supporting spectral and reference evidence.",
    bands: ["SWIR", "NIR"],
    palette: ["#f2eadf", "#f5b66f", "#ef6c3e", "#ff2a2a"],
    legend: [
      {
        label: "No built-up evidence",
        meaning: "No consistent built-up evidence in the combined observation.",
        color: "#f2eadf",
      },
      {
        label: "Potential impervious surface or road",
        meaning: "Spectral response compatible with roads or other impervious surfaces.",
        color: "#f5b66f",
      },
      {
        label: "Built-up area detected",
        meaning: "Built-up evidence identified by temporal or stable land-cover observations.",
        color: "#ef6c3e",
      },
      {
        label: "High-confidence built-up area",
        meaning: "Strong multi-source built-up evidence.",
        color: "#ff2a2a",
      },
    ],
  },
  {
    id: "NDWI",
    name: "NDWI",
    topic: "Surface Water",
    description: "Shows continuous surface-water response from Green and NIR bands.",
    bands: ["Green", "NIR"],
    palette: [
      "#8C510A",
      "#BF812D",
      "#DFC27D",
      "#F6E8C3",
      "#F5F5F5",
      "#C7EAE5",
      "#80CDC1",
      "#35978F",
      "#01665E",
    ],
    legend: [
      {
        label: "NDWI < -0.20: strong negative response",
        meaning: "Probable dry land or non-water surface.",
        color: "#8C510A",
      },
      {
        label: "-0.20–0.00: negative response",
        meaning: "Negative water response.",
        color: "#DFC27D",
      },
      {
        label: "0.00–0.10: transition",
        meaning: "Weak or transitional water response.",
        color: "#F5F5F5",
      },
      {
        label: "0.10–0.30: water-compatible response",
        meaning: "Response compatible with water, mixed water, or wet edges.",
        color: "#80CDC1",
      },
      {
        label: ">= 0.30: strong water response",
        meaning: "Strong surface-water response.",
        color: "#01665E",
      },
    ],
  },
  {
    id: "BSI",
    name: "BSI",
    topic: "Bare Soil",
    description: "Highlights bare or weakly covered soils.",
    bands: ["SWIR", "Red", "NIR", "Blue"],
    palette: [
      "#006837",
      "#31a354",
      "#78c679",
      "#c2e699",
      "#ffffcc",
      "#fed98e",
      "#fe9929",
      "#d95f0e",
      "#993404",
    ],
    legend: [
      {
        label: "BSI < -0.20: very negative",
        meaning: "Very negative BSI response; interpretation depends on surface and atmosphere.",
        color: "#006837",
      },
      {
        label: "-0.20–0.00: negative",
        meaning: "Negative BSI response, often covered or moist surfaces.",
        color: "#78c679",
      },
      {
        label: "0.00–0.10: transition",
        meaning: "Transition response between covered and exposed surfaces.",
        color: "#ffffcc",
      },
      {
        label: "0.10–0.20: probable bare soil",
        meaning: "Probable exposed bare soil response.",
        color: "#fe9929",
      },
      {
        label: "≥ 0.20: strong bare-soil signature",
        meaning: "Strong exposed-soil or dry mineral response.",
        color: "#993404",
      },
    ],
  },
  {
    id: "SAVI",
    name: "SAVI",
    topic: "Semi-arid Vegetation",
    description: "Assesses vegetation while reducing bare-soil influence.",
    bands: ["NIR", "Red"],
    palette: [
      "#8C510A",
      "#BF812D",
      "#DFC27D",
      "#F6E8C3",
      "#FFFFBF",
      "#D9EF8B",
      "#A6D96A",
      "#66BD63",
      "#1A9850",
      "#006837",
    ],
    legend: [
      {
        label: "< 0.10: no / very sparse vegetation",
        meaning: "Bare soil or absent vegetation after soil-background adjustment.",
        color: "#8C510A",
      },
      {
        label: "0.10–0.25: low vegetation",
        meaning: "Low vegetation response in a dry or semi-arid context.",
        color: "#DFC27D",
      },
      {
        label: "0.25–0.40: moderate vegetation",
        meaning: "Moderate vegetation cover with reduced soil influence.",
        color: "#FFFFBF",
      },
      {
        label: "0.40–0.60: dense vegetation",
        meaning: "Dense vegetation cover after soil-background adjustment.",
        color: "#A6D96A",
      },
      {
        label: ">= 0.60: very dense vegetation",
        meaning: "Very dense or highly active vegetation.",
        color: "#006837",
      },
    ],
  },
  {
    id: "OSI_SAR",
    name: "OSI-SAR",
    topic: "Oil Spill Suspect",
    description:
      "OSI-SAR – Oil Spill Suspect maps Potential Oil Slick Candidates from one Sentinel-1 IW VV/VH scene. Not a confirmed oil spill.",
    bands: ["Sentinel-1 VV", "Sentinel-1 VH", "Local contrast"],
    palette: ["#1f78b4", "#d7191c"],
    legend: [
      {
        label: "Normal water",
        meaning: "Water without a strong dark-slick SAR signal.",
        color: "#1f78b4",
      },
      {
        label: "Oil-spill suspect",
        meaning:
          "Dark SAR target that passed VV, VH, contrast, angle, water, and connected-pixel filters.",
        color: "#d7191c",
      },
    ],
  },
  {
    id: "CHANGE_NDVI",
    name: "NDVI Change Detection",
    topic: "Vegetation Change",
    description: "Compares NDVI between two periods to map vegetation loss, stability, and gain.",
    bands: ["NDVI T1", "NDVI T2", "Delta NDVI"],
    palette: ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"],
    legend: [
      {
        label: "Strong vegetation loss",
        meaning: "Large decrease in vegetation response.",
        color: "#a50026",
      },
      {
        label: "Moderate vegetation loss",
        meaning: "Moderate decrease in vegetation cover or vigor.",
        color: "#f46d43",
      },
      { label: "Stable area", meaning: "Limited NDVI change between periods.", color: "#fee08b" },
      {
        label: "Moderate vegetation gain",
        meaning: "Moderate increase in vegetation response.",
        color: "#a6d96a",
      },
      {
        label: "Strong vegetation gain",
        meaning: "Large increase in vegetation cover or vigor.",
        color: "#1a9850",
      },
    ],
  },
  {
    id: "CHANGE_NDWI",
    name: "NDWI Change Detection",
    topic: "Water / Moisture Change",
    description:
      "Compares NDWI between two periods to map water or moisture decrease, stability, and increase.",
    bands: ["NDWI T1", "NDWI T2", "Delta NDWI"],
    palette: ["#f2c46d", "#b8e65c", "#56e66f", "#22bff0", "#003bff"],
    legend: [
      {
        label: "Water/moisture disappearance",
        meaning: "Strong decrease of water or moisture signal.",
        color: "#f2c46d",
      },
      {
        label: "Moisture decrease",
        meaning: "Moderate decrease of humidity or water response.",
        color: "#b8e65c",
      },
      { label: "Stable area", meaning: "Limited NDWI change between periods.", color: "#56e66f" },
      {
        label: "Moisture increase",
        meaning: "Moderate increase of humidity or water response.",
        color: "#22bff0",
      },
      {
        label: "Probable water appearance",
        meaning: "Strong increase suggesting new or expanded water.",
        color: "#003bff",
      },
    ],
  },
  {
    id: "CHANGE_NDBI",
    name: "NDBI Change Detection",
    topic: "Built-up Change",
    description:
      "Compares continuous NDBI between two periods as NDBI_P2 minus NDBI_P1. An NDBI increase is not confirmed new construction.",
    bands: ["NDBI T1", "NDBI T2", "Delta NDBI"],
    palette: ["#2166AC", "#92C5DE", "#F7F7F7", "#F46D43", "#A50026"],
    legend: [
      {
        label: "Strong NDBI decrease",
        meaning: "Strong decrease of the NDBI spectral response.",
        color: "#2166AC",
      },
      {
        label: "Moderate NDBI decrease",
        meaning: "Moderate decrease of the NDBI response.",
        color: "#92C5DE",
      },
      { label: "Stable area", meaning: "Limited NDBI change between periods.", color: "#F7F7F7" },
      {
        label: "Moderate NDBI increase",
        meaning: "Moderate increase of the NDBI response; bare soil can also raise NDBI.",
        color: "#F46D43",
      },
      {
        label: "Strong NDBI increase",
        meaning: "Strong increase of the NDBI response; not automatically new urbanization.",
        color: "#A50026",
      },
    ],
  },
  {
    id: "CHANGE_BSI",
    name: "BSI Change Detection",
    topic: "Bare Soil Change",
    description:
      "Compares BSI between two periods to map bare-soil decrease, stability, and exposure increase.",
    bands: ["BSI T1", "BSI T2", "Delta BSI"],
    palette: ["#f5ecd9", "#e4c58d", "#c99a5d", "#9f6d3c", "#6f4422"],
    legend: [
      {
        label: "Strong bare-soil decrease",
        meaning: "Strong reduction of exposed bare soil.",
        color: "#f5ecd9",
      },
      {
        label: "Moderate bare-soil decrease",
        meaning: "Moderate reduction of bare-soil response.",
        color: "#e4c58d",
      },
      { label: "Stable area", meaning: "Limited BSI change between periods.", color: "#c99a5d" },
      {
        label: "Moderate bare-soil increase",
        meaning: "Moderate increase of exposed soil.",
        color: "#9f6d3c",
      },
      {
        label: "Strong bare-soil increase",
        meaning: "Strong increase of bare or exposed mineral surface.",
        color: "#6f4422",
      },
    ],
  },
  {
    id: "CHANGE_SAVI",
    name: "SAVI Change Detection",
    topic: "Vegetation Change",
    description:
      "Compares SAVI between two periods to map vegetation-cover loss, stability, and gain.",
    bands: ["SAVI T1", "SAVI T2", "Delta SAVI"],
    palette: ["#8c510a", "#d8b365", "#f6e8c3", "#a6d96a", "#006837"],
    legend: [
      {
        label: "Strong vegetation-cover loss",
        meaning: "Large decrease in SAVI vegetation response.",
        color: "#8c510a",
      },
      {
        label: "Moderate vegetation-cover loss",
        meaning: "Moderate vegetation-cover decrease.",
        color: "#d8b365",
      },
      { label: "Stable area", meaning: "Limited SAVI change between periods.", color: "#f6e8c3" },
      {
        label: "Moderate vegetation-cover gain",
        meaning: "Moderate increase in vegetation cover.",
        color: "#a6d96a",
      },
      {
        label: "Strong vegetation-cover gain",
        meaning: "Strong increase in vegetation cover.",
        color: "#006837",
      },
    ],
  },
  {
    id: "SUPERVISED_CLASSIFICATION",
    name: "SUPERVISED CLASSIFICATION",
    topic: "Land Cover",
    description: "Creates an automatic land-cover classification for the selected area.",
    bands: [],
    palette: [
      "#2b83ba",
      "#1a9850",
      "#a6d96a",
      "#d7191c",
      "#dfc27d",
      "#80cdc1",
      "#01665e",
      "#ffffff",
    ],
    legend: [
      { label: "Water", meaning: "Open water or permanent water surfaces.", color: "#2b83ba" },
      {
        label: "Dense vegetation / trees",
        meaning: "Tree cover and dense natural vegetation.",
        color: "#1a9850",
      },
      {
        label: "Crops / low vegetation",
        meaning: "Cropland, grassland, shrubland, or low vegetation.",
        color: "#a6d96a",
      },
      {
        label: "Built-up area",
        meaning: "Urban, industrial, road, or impervious surfaces.",
        color: "#d7191c",
      },
      {
        label: "Bare soil / sand",
        meaning: "Exposed soil, sand, desert, or sparse mineral surfaces.",
        color: "#dfc27d",
      },
      {
        label: "Wetland",
        meaning: "Wetland areas when detected by the reference data.",
        color: "#80cdc1",
      },
      {
        label: "Mangrove / specific vegetation",
        meaning: "Mangrove or specific coastal vegetation where present.",
        color: "#01665e",
      },
      { label: "Snow / ice", meaning: "Snow or ice where present.", color: "#ffffff" },
    ],
  },
  {
    id: "UNSUPERVISED_CLASSIFICATION",
    name: "UNSUPERVISED CLASSIFICATION",
    topic: "Land Cover Clustering",
    description:
      "Creates an automatic land-cover classification for the selected area based on spectral similarities.",
    bands: [],
    palette: ["#2b83ba", "#1a9850", "#a6d96a", "#d7191c", "#dfc27d", "#80cdc1", "#bdbdbd"],
    legend: [
      {
        label: "Water",
        meaning: "Cluster interpreted from high NDWI and low vegetation response.",
        color: "#2b83ba",
      },
      {
        label: "Dense vegetation",
        meaning: "Cluster interpreted from high NDVI or SAVI.",
        color: "#1a9850",
      },
      {
        label: "Crops / low vegetation",
        meaning: "Cluster interpreted from moderate vegetation response.",
        color: "#a6d96a",
      },
      {
        label: "Built-up area",
        meaning: "Cluster interpreted from high built-up spectral response.",
        color: "#d7191c",
      },
      {
        label: "Bare soil / sand",
        meaning: "Cluster interpreted from high bare-soil response and low vegetation.",
        color: "#dfc27d",
      },
      {
        label: "Wetland / mixed class",
        meaning: "Cluster interpreted from mixed moisture and vegetation response.",
        color: "#80cdc1",
      },
      {
        label: "Uninterpreted cluster",
        meaning: "Cluster without a clear spectral interpretation.",
        color: "#bdbdbd",
      },
    ],
  },
];

export const ndviStats = {
  min: -0.21,
  max: 0.86,
  mean: 0.43,
  std: 0.18,
  surface: 1245,
  pixels: 124500,
};

export const ndviClasses = [
  { name: "Very low", surface: 120, pct: 9.6, color: "#a50026" },
  { name: "Low", surface: 250, pct: 20.1, color: "#f46d43" },
  { name: "Moderate", surface: 410, pct: 32.9, color: "#fee08b" },
  { name: "High", surface: 330, pct: 26.5, color: "#a6d96a" },
  { name: "Very high", surface: 135, pct: 10.9, color: "#1a9850" },
];

export const ndviHistogram = Array.from({ length: 24 }, (_, i) => {
  const v = -0.2 + (i * 1.05) / 24;
  const d = v - 0.43;
  const count = Math.round(2400 * Math.exp(-(d * d) / 0.05) + Math.random() * 200);
  return { bin: v.toFixed(2), count };
});

export type Analysis = {
  id: string;
  name: string;
  date: string;
  image: string;
  index: SpectralIndex["id"];
  area: string;
  status: "Completed" | "Running" | "Failed";
};

export const analyses: Analysis[] = [
  {
    id: "an-101",
    name: "NDVI Riyadh Green Cover",
    date: "2026-05-14",
    image: "Sentinel-2 Riyadh 2025",
    index: "NDVI",
    area: "1 245 ha",
    status: "Completed",
  },
  {
    id: "an-100",
    name: "NDWI Jeddah Coastal Moisture",
    date: "2026-05-12",
    image: "Sentinel-2 Jeddah 2025",
    index: "NDWI",
    area: "412 ha",
    status: "Completed",
  },
  {
    id: "an-099",
    name: "NDBI Riyadh Urban Expansion",
    date: "2026-05-10",
    image: "Sentinel-2 Riyadh 2025",
    index: "NDBI",
    area: "986 ha",
    status: "Running",
  },
  {
    id: "an-098",
    name: "BSI Riyadh Bare Soil",
    date: "2026-05-08",
    image: "Sentinel-2 Riyadh 2025",
    index: "BSI",
    area: "2 130 ha",
    status: "Completed",
  },
  {
    id: "an-097",
    name: "SAVI Medina Semi-arid Vegetation",
    date: "2026-05-05",
    image: "Landsat 8 Medina 2024",
    index: "SAVI",
    area: "770 ha",
    status: "Failed",
  },
  {
    id: "an-096",
    name: "Riyadh Land Cover Classification",
    date: "2026-05-03",
    image: "Sentinel-2 Riyadh 2025",
    index: "SUPERVISED_CLASSIFICATION",
    area: "1 980 ha",
    status: "Completed",
  },
  {
    id: "an-095",
    name: "Riyadh Unsupervised Land Cover",
    date: "2026-05-02",
    image: "Sentinel-2 Riyadh 2025",
    index: "UNSUPERVISED_CLASSIFICATION",
    area: "1 980 ha",
    status: "Completed",
  },
];

export const dashboardStats = {
  images: images.length,
  analyses: 47,
  indices: indices.length,
  exports: 18,
};
