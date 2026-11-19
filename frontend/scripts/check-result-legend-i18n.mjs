import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const catalog = fs.readFileSync(path.join(root, "src/data/mock.ts"), "utf8");
const translations = fs.readFileSync(path.join(root, "src/lib/result-legend-i18n.ts"), "utf8");
const mapRoute = fs.readFileSync(path.join(root, "src/routes/map.tsx"), "utf8");
const geeClient = fs.readFileSync(path.join(root, "../backend/app/gee_client.py"), "utf8");
const englishUi = JSON.parse(fs.readFileSync(path.join(root, "src/i18n/en.json"), "utf8"));
const arabicUi = JSON.parse(fs.readFileSync(path.join(root, "src/i18n/ar.json"), "utf8"));

const indicesBlock = catalog.slice(
  catalog.indexOf("export const indices"),
  catalog.indexOf("export const ndviStats"),
);
const ids = [...indicesBlock.matchAll(/\bid:\s*"([A-Z0-9_]+)"/g)].map((match) => match[1]);
const phrases = [...indicesBlock.matchAll(/(?:label|meaning):\s*"([^"]+)"/g)].map(
  (match) => match[1],
);
const translationBlock = translations.slice(
  translations.indexOf("export const RESULT_LEGEND_AR"),
  translations.indexOf("const RESULT_LEGEND_EN_ALIASES"),
);
const quotedEntries = [...translationBlock.matchAll(/^\s*"([^"]+)":\s*"([^"]+)",?$/gm)].map(
  (match) => [match[1], match[2]],
);
const identifierEntries = [
  ...translationBlock.matchAll(/^\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*"([^"]+)",?$/gm),
].map((match) => [match[1], match[2]]);
const translatedEntries = new Map([...quotedEntries, ...identifierEntries]);
const uniquePhrases = [...new Set(phrases)];
const missing = uniquePhrases.filter((phrase) => !translatedEntries.has(phrase));
const nonArabic = uniquePhrases.filter((phrase) => {
  const value = translatedEntries.get(phrase) ?? "";
  return value && !/[\u0600-\u06ff]/u.test(value);
});
const frenchInEnglishCatalog = uniquePhrases.filter((phrase) =>
  /\b(?:absence|couverture|faible|moyenne|forte|humidité|bâti|eau|végétation)\b/iu.test(phrase),
);

const backendLegendSections = [
  geeClient.slice(
    geeClient.indexOf("CHANGE_DETECTION_CONFIG"),
    geeClient.indexOf("S2_SR_REFLECTANCE_SCALE"),
  ),
  geeClient.slice(geeClient.indexOf("INDEX_CONFIG"), geeClient.indexOf("INDEX_BANDS_BY_SENSOR")),
  geeClient.slice(geeClient.indexOf("LAND_COVER_CLASSES"), geeClient.indexOf("_GEE_INITIALIZED")),
];
const backendLegendTerms = [
  ...new Set(
    backendLegendSections.flatMap((section) => [
      ...[...section.matchAll(/\([^\n]*?,\s*[^\n]*?,\s*"([^"]+)",\s*"#[0-9A-Fa-f]+"\)/g)].map(
        (match) => match[1],
      ),
      ...[...section.matchAll(/\{"code":\s*\d+,\s*"name":\s*"([^"]+)"/g)].map((match) => match[1]),
    ]),
  ),
];
const backendDescriptionSections = [
  geeClient.slice(
    geeClient.indexOf("NDBI_RAW_CLASS_DESCRIPTIONS"),
    geeClient.indexOf("def _describe_raw_ndbi_classes"),
  ),
  geeClient.slice(
    geeClient.indexOf("    descriptions = [", geeClient.indexOf("def _compute_ndbi_classes")),
    geeClient.indexOf("    classified =", geeClient.indexOf("def _compute_ndbi_classes")),
  ),
];
const backendDescriptionTerms = [
  ...new Set(
    backendDescriptionSections.flatMap((section) =>
      [...section.matchAll(/^\s*"([^"]+)",?$/gm)].map((match) => match[1]),
    ),
  ),
];
backendLegendTerms.push(...backendDescriptionTerms);
const untranslatedBackendTerms = backendLegendTerms.filter((phrase) => {
  const value = translatedEntries.get(phrase) ?? "";
  return !value || !/[\u0600-\u06ff]/u.test(value);
});

const mapTranslationBlock = mapRoute.slice(
  mapRoute.indexOf("const MAP_AR_TEXT"),
  mapRoute.indexOf("const MAP_INDEX_AR"),
);
const mapQuotedEntries = [...mapTranslationBlock.matchAll(/^\s*"([^"]+)":\s*"([^"]+)",?$/gm)];
const mapIdentifierEntries = [
  ...mapTranslationBlock.matchAll(/^\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*"([^"]+)",?$/gm),
];
const mapTranslations = new Map(
  [...mapQuotedEntries, ...mapIdentifierEntries].map((match) => [match[1], match[2]]),
);
const mapTextTerms = [
  ...new Set(
    [...mapRoute.matchAll(/mapText\(\s*"([^"]+)"\s*,\s*language/g)].map((match) => match[1]),
  ),
];
const missingMapTerms = mapTextTerms.filter((phrase) => !mapTranslations.has(phrase));

const englishUiKeys = Object.keys(englishUi).sort();
const arabicUiKeys = Object.keys(arabicUi).sort();
const missingArabicUiKeys = englishUiKeys.filter((key) => !arabicUiKeys.includes(key));
const extraArabicUiKeys = arabicUiKeys.filter((key) => !englishUiKeys.includes(key));
const untranslatedArabicUi = englishUiKeys.filter((key) => {
  const value = String(arabicUi[key] ?? "");
  const intentionallyEnglish = new Set(["language.english"]);
  return (
    !value ||
    (!/[\u0600-\u06ff]/u.test(value) &&
      !/^(?:GeoTIFF|PNG|CSV|PDF)$/i.test(value) &&
      !intentionallyEnglish.has(key))
  );
});

if (ids.length !== 13) {
  throw new Error(`Expected 13 analyses, found ${ids.length}: ${ids.join(", ")}`);
}
if (missing.length) {
  throw new Error(`Missing Arabic legend translations:\n${missing.join("\n")}`);
}
if (nonArabic.length) {
  throw new Error(`Translations without Arabic text:\n${nonArabic.join("\n")}`);
}
if (frenchInEnglishCatalog.length) {
  throw new Error(
    `French text found in the English legend catalog:\n${frenchInEnglishCatalog.join("\n")}`,
  );
}
if (untranslatedBackendTerms.length) {
  throw new Error(
    `Missing or non-Arabic translations for backend legend terms:\n${untranslatedBackendTerms.join("\n")}`,
  );
}
if (missingMapTerms.length) {
  throw new Error(`Missing Arabic map translations:\n${missingMapTerms.join("\n")}`);
}
if (missingArabicUiKeys.length || extraArabicUiKeys.length || untranslatedArabicUi.length) {
  throw new Error(
    [
      missingArabicUiKeys.length
        ? `Missing Arabic UI keys:\n${missingArabicUiKeys.join("\n")}`
        : "",
      extraArabicUiKeys.length ? `Extra Arabic UI keys:\n${extraArabicUiKeys.join("\n")}` : "",
      untranslatedArabicUi.length
        ? `Arabic UI values without Arabic text:\n${untranslatedArabicUi.join("\n")}`
        : "",
    ]
      .filter(Boolean)
      .join("\n"),
  );
}

console.log(
  `Bilingual UI OK: ${ids.length} analyses, ${uniquePhrases.length} catalog legend terms, ${backendLegendTerms.length} backend legend terms, ${mapTextTerms.length} map terms, ${englishUiKeys.length} shared UI keys.`,
);
