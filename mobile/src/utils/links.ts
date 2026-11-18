// Link detection for notification and promotion texts. No full Markdown/HTML: the admin types plain text into the existing field.
//
// Supported formats (anything else stays plain text):
//   [Подробнее об акции](https://example.kz/path)   a named link: only the label is shown, the URL is hidden and opened on tap
//   https://example.com/path?x=1#y   http://example.com   HTTPS://EXAMPLE.COM   (scheme is lower-cased)
//   www.example.com/path             (opened as https://www.example.com/path)
// Named link rules: one line, label 1..300 chars of plain text (Unicode, no `[` `]`, no control or bidi-override characters);
// the URL goes in (...) with balanced parentheses, no whitespace or < >, at most 2048 chars, and must be a safe http(s)/www URL.
// The label is never parsed again, so a URL inside it does not become a second link. Invalid, unfinished or non-web markup
// (e.g. [x](javascript:alert(1)), [x](https://a.kz, [](https://a.kz)) is shown as ordinary text.
// Hosts may be Unicode (Cyrillic domains/paths). A bare URL ends at whitespace; sentence punctuation after it ( . , ; : ! ? … quotes,
// a closing bracket that has no opening one inside the URL) is kept as text and is not part of the link.
// Only http/https are ever returned, so javascript:, data:, file:, intent:, tel:, mailto: etc. can never be opened from here.
// Parsing is a single left-to-right pass; a `[` whose `(` is not followed by http(s):// or www. is rejected at once; only a real web-URL start costs up to ~2.4k characters of look-ahead.

export type TextSegment = { text: string; url?: string };

const CANDIDATE = /(?:https?:\/\/|www\.)[^\s<>]+/giu;
const TRAILING_PUNCTUATION = '.,;:!?…\'"”’»›*';
const WORD_BEFORE = /[\p{L}\p{N}_./@:-]/u;
const CLOSING_TO_OPENING: Record<string, string> = { ')': '(', ']': '[', '}': '{' };

function count(text: string, char: string): number {
  return text.split(char).length - 1;
}

// Returns the normalised web URL, or null when `raw` is not a safe http(s) URL.
export function toSafeWebUrl(raw: string): string | null {
  const value = /^www\./i.test(raw) ? `https://${raw}` : raw;
  const match = /^(https?):\/\/([^\s/?#]+)([^\s]*)$/i.exec(value);
  if (!match) return null;
  const [, scheme, authority, rest] = match;
  if (!scheme || !authority || authority.includes('@') || /[\\\u0000-\u001f]/u.test(value)) return null;
  const hostPort = /^([^:]+)(?::(\d{1,5}))?$/.exec(authority);
  const host = hostPort?.[1];
  if (!host || !/^[^\s.]+(\.[^\s.]+)+$/u.test(host) || host.startsWith('-') || host.endsWith('-')) return null;
  return `${scheme.toLowerCase()}://${authority}${rest ?? ''}`;
}

const MAX_LABEL = 300;
const MAX_URL = 2048;
const FORBIDDEN_IN_LABEL = /[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/u;
const FORBIDDEN_IN_URL = /[\s<>]/u;
const SUPPORTED_START = /(?:https?:\/\/|www\.)/iy; // sticky: checked at one position, before any long scan

type Named = { label: string; url: string; end: number };

// `text[start]` is `[`. Returns null unless a complete, valid `[label](url)` starts here.
function parseNamedLink(text: string, start: number): Named | null {
  const labelLimit = Math.min(text.length, start + 1 + MAX_LABEL + 1);
  let i = start + 1;
  for (; i < labelLimit; i++) {
    const char = text[i];
    if (char === ']') break;
    if (char === '[' || char === '\n' || char === '\r') return null;
  }
  if (i >= labelLimit || text[i] !== ']' || text[i + 1] !== '(') return null;
  const label = text.slice(start + 1, i);
  if (label.trim() === '' || FORBIDDEN_IN_LABEL.test(label)) return null;
  const urlStart = i + 2;
  // Cheap early exit: repeated `[a](` must not trigger a 2048-char scan each time. Only web URLs can ever be hidden links.
  SUPPORTED_START.lastIndex = urlStart;
  if (!SUPPORTED_START.test(text)) return null;
  const urlLimit = Math.min(text.length, urlStart + MAX_URL + 1);
  let depth = 1;
  let j = urlStart;
  for (; j < urlLimit; j++) {
    const char = text[j] ?? '';
    if (FORBIDDEN_IN_URL.test(char)) return null;
    if (char === '(') depth += 1;
    else if (char === ')') {
      depth -= 1;
      if (depth === 0) break;
    }
  }
  if (j >= urlLimit || depth !== 0) return null;
  const raw = text.slice(urlStart, j);
  const url = raw.length > 0 && raw.length <= MAX_URL ? toSafeWebUrl(raw) : null;
  return url ? { label, url, end: j + 1 } : null;
}

export function splitLinks(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  const candidates = new RegExp(CANDIDATE.source, CANDIDATE.flags);
  let cursor = 0;
  let pos = 0;
  let next: RegExpExecArray | null | undefined; // next bare-URL candidate at or after `pos` (cached between iterations)
  while (pos < text.length) {
    if (next === undefined || (next !== null && next.index < pos)) {
      candidates.lastIndex = pos;
      next = candidates.exec(text);
    }
    const bracket = text.indexOf('[', pos);
    const candidateStart = next ? next.index : Infinity;
    if (bracket >= 0 && bracket < candidateStart) {
      const named = parseNamedLink(text, bracket);
      if (named) {
        if (bracket > cursor) segments.push({ text: text.slice(cursor, bracket) });
        segments.push({ text: named.label, url: named.url });
        cursor = pos = named.end;
      } else {
        pos = bracket + 1;
      }
      continue;
    }
    if (!next) break;
    const start = next.index;
    pos = start + next[0].length;
    // `www.` inside a word or a longer host (e.g. "awww.x.kz", "a.www.x.kz") is not a link start.
    if (/^www\./i.test(next[0]) && start > 0 && WORD_BEFORE.test(text[start - 1] ?? '')) continue;
    let candidate = next[0];
    for (;;) {
      const last = candidate[candidate.length - 1] ?? '';
      const opening = CLOSING_TO_OPENING[last];
      if (TRAILING_PUNCTUATION.includes(last) || (opening !== undefined && count(candidate, last) > count(candidate, opening))) {
        candidate = candidate.slice(0, -1);
      } else break;
    }
    const url = toSafeWebUrl(candidate);
    if (!url) continue;
    if (start > cursor) segments.push({ text: text.slice(cursor, start) });
    segments.push({ text: candidate, url });
    cursor = start + candidate.length;
    pos = cursor;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments.length > 0 ? segments : [{ text }];
}

export function hasLinks(text: string): boolean {
  return splitLinks(text).some(segment => segment.url !== undefined);
}
