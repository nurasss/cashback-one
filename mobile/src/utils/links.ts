// Plain-text link detection for notification and promotion texts. No Markdown/HTML: the admin pastes a URL into the text field.
//
// Supported formats (anything else stays plain text):
//   https://example.com/path?x=1#y   http://example.com   HTTPS://EXAMPLE.COM   (scheme is lower-cased)
//   www.example.com/path             (opened as https://www.example.com/path)
// Hosts may be Unicode (Cyrillic domains/paths). A URL ends at whitespace; sentence punctuation after it ( . , ; : ! ? … quotes,
// a closing bracket that has no opening one inside the URL) is kept as text and is not part of the link.
// Only http/https are ever returned, so javascript:, data:, file:, intent:, tel:, mailto: etc. can never be opened from here.

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

export function splitLinks(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(CANDIDATE)) {
    const start = match.index ?? 0;
    if (start < cursor) continue;
    // `www.` inside a word or a longer host (e.g. "awww.x.kz", "a.www.x.kz") is not a link start.
    if (/^www\./i.test(match[0]) && start > 0 && WORD_BEFORE.test(text[start - 1] ?? '')) continue;
    let candidate = match[0];
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
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments.length > 0 ? segments : [{ text }];
}

export function hasLinks(text: string): boolean {
  return splitLinks(text).some(segment => segment.url !== undefined);
}
