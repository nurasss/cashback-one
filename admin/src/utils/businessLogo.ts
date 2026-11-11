export type BusinessLogoSource =
  | { ok: true; src: string }
  | { ok: false; reason: 'invalid' | 'https' };

export function resolveBusinessLogoSource(url: string | null | undefined): BusinessLogoSource {
  if (!url) return { ok: false, reason: 'invalid' };
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol !== 'https:' && parsed.origin !== window.location.origin) {
      return { ok: false, reason: 'https' };
    }
    return { ok: true, src: parsed.href };
  } catch {
    return { ok: false, reason: 'invalid' };
  }
}
