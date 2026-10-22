// Code 128 (ISO/IEC 15417) for card numbers: 6–15 ASCII digits, kept as a string so leading zeros survive.
// Digits are packed in set C (two per symbol). An odd count starts in set B for the first digit, then switches to C.

// Element widths of symbols 0–106: bar, space, bar, space, bar, space (the stop symbol has a seventh element).
const PATTERNS = [
  '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
  '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
  '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
  '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
  '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
  '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
  '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
  '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
  '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
  '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
  '114131', '311141', '411131', '211412', '211214', '211232', '2331112',
] as const;

export const CODE128_PATTERNS: readonly string[] = PATTERNS;
export const START_B = 104;
export const START_C = 105;
export const CODE_C = 99;
export const STOP = 106;
export const QUIET_ZONE_MODULES = 10;

export const isCode128Number = (value: unknown): value is string => typeof value === 'string' && /^[0-9]{6,15}$/.test(value);

/** Symbol values: start, data, checksum, stop. Returns null for anything that is not a 6–15 digit string. */
export function code128Values(value: string): number[] | null {
  if (!isCode128Number(value)) return null;
  const odd = value.length % 2 === 1;
  const values: number[] = [];
  let rest = value;
  if (odd) {
    values.push(START_B, value.charCodeAt(0) - 32, CODE_C); // set B: character value = ASCII − 32
    rest = value.slice(1);
  } else {
    values.push(START_C);
  }
  for (let i = 0; i < rest.length; i += 2) values.push(Number(rest.slice(i, i + 2)));
  const checksum = values.reduce((sum, symbol, index) => sum + symbol * (index === 0 ? 1 : index), 0) % 103;
  values.push(checksum, STOP);
  return values;
}

/** Alternating bar/space widths in modules, starting with a bar. */
export function code128Widths(value: string): number[] | null {
  const values = code128Values(value);
  if (!values) return null;
  return values.flatMap(symbol => Array.from(CODE128_PATTERNS[symbol]!, Number));
}

/** Bars as module offsets, without quiet zones; `modules` is the symbol width (the quiet zones are added by the renderer). */
export function code128Bars(value: string): { bars: { x: number; width: number }[]; modules: number } | null {
  const widths = code128Widths(value);
  if (!widths) return null;
  const bars: { x: number; width: number }[] = [];
  let x = 0;
  widths.forEach((width, index) => {
    if (index % 2 === 0) bars.push({ x, width });
    x += width;
  });
  return { bars, modules: x };
}
