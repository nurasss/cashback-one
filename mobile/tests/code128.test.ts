import { CODE128_PATTERNS, CODE_C, code128Bars, code128Values, code128Widths, isCode128Number, QUIET_ZONE_MODULES, START_B, START_C, STOP } from '../src/features/code128';

// Reference vectors. The element widths (bar, space, bar, …) were produced once from the encoder and then rendered to a bitmap
// with white quiet zones (module = 2 and 3 px) and decoded by an independent reader, zxing-cpp 3.1.1 (Python, Pillow 13.0.0).
// The reader returned exactly the digit string, including leading zeros, for every vector below. The even-length vectors flagged
// `pb` are also identical to the module output of python-barcode 0.16.1. See reports/MOBILE_FIRST_PACKAGE.md for the whole run
// (3202 numbers, 6404 images, 0 mismatches). The decoder is not part of the app or its lockfile.
const vectors: { number: string; widths: string; values: number[]; pb?: true }[] = [
  { number: '012345', widths: '2112322221223121311131231211422331112', values: [105, 1, 23, 45, 81, 106], pb: true },
  { number: '000000', widths: '2112322122222122222122222222212331112', values: [105, 0, 0, 0, 2, 106], pb: true },
  { number: '999999', widths: '2112321131411131411131411211422331112', values: [105, 99, 99, 99, 81, 106] },
  { number: '1234567', widths: '2112141232211131413121311131231411221341112331112', values: [104, 17, 99, 23, 45, 67, 79, 106] },
  { number: '12345678', widths: '2112321122321311233311212411121331212331112', values: [105, 12, 34, 56, 78, 47, 106], pb: true },
  { number: '00123456', widths: '2112322122221122321311233311211123312331112', values: [105, 0, 12, 34, 56, 43, 106], pb: true },
  { number: '0123456789', widths: '2112322221223121311131231411222121411421122331112', values: [105, 1, 23, 45, 67, 89, 73, 106], pb: true },
  { number: '0123456789012', widths: '2112141231221131411122321311233311212411122141211122321223122331112', values: [104, 16, 99, 12, 34, 56, 78, 90, 12, 7, 106] },
];

describe('Code 128 symbol table', () => {
  it('has 107 distinct patterns of the right shape', () => {
    expect(CODE128_PATTERNS).toHaveLength(107);
    expect(new Set(CODE128_PATTERNS).size).toBe(107);
    CODE128_PATTERNS.slice(0, 106).forEach(pattern => {
      expect(pattern).toMatch(/^[1-4]{6}$/);
      const widths = Array.from(pattern, Number);
      expect(widths.reduce((a, b) => a + b, 0)).toBe(11); // every symbol is 11 modules wide
      expect((widths[0]! + widths[2]! + widths[4]!) % 2).toBe(0); // bar widths of a symbol add up to an even number
    });
    expect(CODE128_PATTERNS[STOP]).toBe('2331112'); // 13 modules, ends with a 2-module bar
    expect(CODE128_PATTERNS[START_B]).toBe('211214');
    expect(CODE128_PATTERNS[START_C]).toBe('211232');
  });
});

describe('Code 128 encoding of card numbers', () => {
  it.each(vectors)('$number encodes to the independently decoded reference', ({ number, widths, values }) => {
    expect(code128Widths(number)?.join('')).toBe(widths);
    expect(code128Values(number)).toEqual(values);
  });

  it('computes the checksum from the specification, by hand', () => {
    // (105 + 1·1 + 23·2 + 45·3) mod 103 = 287 mod 103 = 81
    expect(code128Values('012345')).toEqual([105, 1, 23, 45, 81, 106]);
    // 0123456789012: Start B, '0' (16), Code C, then pairs 12 34 56 78 90 12:
    // 104 + 16·1 + 99·2 + 12·3 + 34·4 + 56·5 + 78·6 + 90·7 + 12·8 = 1964, and 1964 mod 103 = 7
    const odd = [104, 16, 99, 12, 34, 56, 78, 90, 12];
    expect(odd.reduce((sum, symbol, index) => sum + symbol * Math.max(1, index), 0) % 103).toBe(7);
    expect(code128Values('0123456789012')?.at(-2)).toBe(7);
  });

  it('uses set C for even length and Start B + one digit + set C for odd length', () => {
    expect(code128Values('123456')?.[0]).toBe(START_C);
    expect(code128Values('123456')).not.toContain(START_B);
    const odd = code128Values('1234567')!;
    expect(odd.slice(0, 3)).toEqual([START_B, 17, CODE_C]); // '1' in set B = 49 − 32 = 17
    expect(odd.at(-1)).toBe(STOP);
  });

  it('keeps every digit, including leading zeros, for every allowed length', () => {
    for (let length = 4; length <= 13; length += 1) {
      const number = '0'.repeat(length - 1) + '7';
      const values = code128Values(number)!;
      // data symbols (without start, checksum, stop and the set switch) must reproduce the string exactly
      const odd = length % 2 === 1;
      const data = values.slice(odd ? 3 : 1, -2);
      const text = (odd ? String(values[1]! + 32 - 48) : '') + data.map(value => String(value).padStart(2, '0')).join('');
      expect(text).toBe(number);
    }
  });

  it('measures symbol width as 11 modules per symbol plus the 13-module stop', () => {
    expect(code128Bars('012345')?.modules).toBe(11 * 5 + 13); // start + 3 pairs + checksum, then stop
    expect(code128Bars('1234567')?.modules).toBe(11 * 7 + 13); // start B + digit + set C + 3 pairs + checksum
    expect(code128Bars('1234567890123')?.modules).toBe(11 * 10 + 13); // 13 digits: start B + digit + set C + 6 pairs + checksum
    expect(QUIET_ZONE_MODULES).toBeGreaterThanOrEqual(10);
  });

  it('returns bars that start at a bar, never overlap and end with the stop bar', () => {
    const encoded = code128Bars('0123456789012')!;
    expect(encoded.bars[0]).toEqual({ x: 0, width: 2 });
    encoded.bars.forEach((bar, index) => {
      if (index > 0) expect(bar.x).toBeGreaterThan(encoded.bars[index - 1]!.x + encoded.bars[index - 1]!.width - 1);
    });
    const last = encoded.bars.at(-1)!;
    expect(last.x + last.width).toBe(encoded.modules);
    expect(last.width).toBe(2);
  });

  it.each(['', '123', '12345678901234', '1234567890123456', '12345a', ' 123456', '123 456', '１２３４５６', '12.3456', '-123456'])('rejects %j', input => {
    expect(isCode128Number(input)).toBe(false);
    expect(code128Values(input)).toBeNull();
    expect(code128Widths(input)).toBeNull();
    expect(code128Bars(input)).toBeNull();
  });

  it('rejects values that are not strings', () => {
    expect(isCode128Number(123456 as unknown)).toBe(false);
    expect(isCode128Number(null)).toBe(false);
    expect(isCode128Number(undefined)).toBe(false);
  });

  it('accepts exactly 4 and 13 digits', () => {
    expect(isCode128Number('0000')).toBe(true);
    expect(isCode128Number('9999999999999')).toBe(true);
  });

  // 4-digit numbers are new with the 4–13 card number rule. The reference symbol values and checksums are computed
  // by hand from the spec: '0000' → (105 + 0·1 + 0·2) mod 103 = 2, '0001' → (105 + 0·1 + 1·2) mod 103 = 4,
  // '1234' → (105 + 12·1 + 34·2) mod 103 = 82. The widths round-trip through the table-based decoder below.
  it('encodes a 4-digit card number correctly, keeping leading zeros', () => {
    expect(code128Values('0000')).toEqual([105, 0, 0, 2, 106]);
    expect(code128Values('0001')).toEqual([105, 0, 1, 4, 106]);
    expect(code128Values('1234')).toEqual([105, 12, 34, 82, 106]);
    expect(code128Bars('0001')?.modules).toBe(11 * 4 + 13); // start + 2 pairs + checksum, then stop
    const lookup = new Map(CODE128_PATTERNS.map((pattern, index) => [pattern, index]));
    for (const number of ['0000', '0001', '1234']) {
      const widths = code128Widths(number)!.join('');
      const symbols: number[] = [];
      for (let i = 0; i + 6 <= widths.length - 7; i += 6) symbols.push(lookup.get(widths.slice(i, i + 6))!);
      expect(widths.slice(-7)).toBe(CODE128_PATTERNS[STOP]);
      expect([...symbols, STOP]).toEqual(code128Values(number));
      expect(symbols.slice(1, -1).map(value => String(value).padStart(2, '0')).join('')).toBe(number);
    }
  });

  // Extra consistency check with our own table: decode the widths back to symbols and compare. This is circular on its own
  // and is not the evidence for correctness (the independent decoder above is); it guards against refactoring mistakes.
  it('round-trips through a table-based decoder for all lengths', () => {
    const lookup = new Map(CODE128_PATTERNS.map((pattern, index) => [pattern, index]));
    for (const { number, widths } of vectors) {
      const symbols: number[] = [];
      for (let i = 0; i + 6 <= widths.length - 7; i += 6) symbols.push(lookup.get(widths.slice(i, i + 6))!);
      expect(widths.slice(-7)).toBe(CODE128_PATTERNS[STOP]);
      const [start, ...rest] = symbols;
      const checksum = rest.pop()!;
      expect((start! + rest.reduce((sum, symbol, index) => sum + symbol * (index + 1), 0)) % 103).toBe(checksum);
      const odd = start === START_B;
      const text = odd ? String(rest[0]! - 16) + rest.slice(2).map(v => String(v).padStart(2, '0')).join('') : rest.map(v => String(v).padStart(2, '0')).join('');
      expect(text).toBe(number);
    }
  });
});
