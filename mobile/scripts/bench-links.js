#!/usr/bin/env node
// Parsing-cost report for src/utils/links.ts (`splitLinks`). A measurement, not a pass/fail test: it prints timings and
// always exits 0, so machine load can never decide a functional result. Run: node scripts/bench-links.js
// Correctness of the same inputs is covered by tests/links.test.tsx.
/* global __dirname */
const fs = require('fs');
const path = require('path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'utils', 'links.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: 'commonjs', target: 'es2020' } }).outputText;
const mod = { exports: {} };
new Function('module', 'exports', compiled)(mod, mod.exports);
const { splitLinks } = mod.exports;

const inputs = [
  ['"[" x50000', '['.repeat(50000)],
  ['"[a](" x20000', '[a]('.repeat(20000)],
  ['"[" + 100k letters', `[${'a'.repeat(100000)}`],
  ['"[x](" + "(" x50000', `[x](${'('.repeat(50000)}`],
  ['named link, 100k URL', `[x](https://a.kz/${'a'.repeat(100000)})`],
  ['"www." x20000', 'www.'.repeat(20000)],
  ['"[x](" x5000 + URL', `${'[x]('.repeat(5000)}https://a.kz)`],
  ['"[a](www." x20000', '[a](www.'.repeat(20000)],
  ['"[a](https://( " x20000', '[a](https://( '.repeat(20000)],
  ['promotion limit 4000: "[a](" x1000', '[a]('.repeat(1000)],
  ['notification limit 2000: "[" x2000', '['.repeat(2000)],
  ['valid named links x200 (4000 chars)', '[a](https://a.kz/x) '.repeat(200)],
  ['valid named links x2000 (40000 chars)', '[a](https://a.kz/x) '.repeat(2000)],
  ['bare links x200', 'https://a.kz/x '.repeat(200)],
];

splitLinks('warm-up [a](https://a.kz) https://b.kz');
const load = require('os').loadavg().map(value => value.toFixed(1)).join(' / ');
process.stdout.write(`splitLinks cost (ms, best of 3). load average at start: ${load}\n`);
for (const [name, input] of inputs) {
  let best = Infinity;
  for (let run = 0; run < 3; run += 1) {
    const started = process.hrtime.bigint();
    splitLinks(input);
    best = Math.min(best, Number(process.hrtime.bigint() - started) / 1e6);
  }
  process.stdout.write(`${name.padEnd(42)} len ${String(input.length).padStart(7)}  ${best.toFixed(2).padStart(9)} ms\n`);
}
