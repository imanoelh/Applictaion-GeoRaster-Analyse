export function normalizeHexPalette(palette: unknown): string[] {
  if (!Array.isArray(palette)) return [];
  return palette
    .map((color) => String(color ?? "").toLowerCase())
    .filter((color) => /^#[0-9a-f]{6}$/.test(color));
}

function hexToRgb(color: string): [number, number, number] {
  return [
    Number.parseInt(color.slice(1, 3), 16),
    Number.parseInt(color.slice(3, 5), 16),
    Number.parseInt(color.slice(5, 7), 16),
  ];
}

export function canRecolorPalette(sourcePalette: unknown, displayPalette: unknown): boolean {
  const source = normalizeHexPalette(sourcePalette);
  const display = normalizeHexPalette(displayPalette);
  return source.length > 0 && source.length === display.length;
}

export function recolorRgbaPixels(
  pixels: Uint8ClampedArray,
  sourcePalette: unknown,
  displayPalette: unknown,
): number {
  const source = normalizeHexPalette(sourcePalette);
  const display = normalizeHexPalette(displayPalette);
  if (source.length === 0 || source.length !== display.length) return 0;

  const replacements = new Map<number, [number, number, number]>();
  source.forEach((color, index) => {
    const [sourceR, sourceG, sourceB] = hexToRgb(color);
    replacements.set((sourceR << 16) | (sourceG << 8) | sourceB, hexToRgb(display[index]));
  });

  let changedPixels = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    if (pixels[index + 3] === 0) continue;
    const key = (pixels[index] << 16) | (pixels[index + 1] << 8) | pixels[index + 2];
    const replacement = replacements.get(key);
    if (!replacement) continue;
    if (
      pixels[index] !== replacement[0] ||
      pixels[index + 1] !== replacement[1] ||
      pixels[index + 2] !== replacement[2]
    ) {
      pixels[index] = replacement[0];
      pixels[index + 1] = replacement[1];
      pixels[index + 2] = replacement[2];
      changedPixels += 1;
    }
  }
  return changedPixels;
}
