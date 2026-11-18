import { Linking } from 'react-native';
import { toSafeWebUrl } from '../utils/links';

// A store map link must be a plain https URL. Anything else (http, geo:, javascript:, an address without a host) is not opened.
export function toSafeMapUrl(raw: string | null | undefined): string | null {
  if (typeof raw !== 'string') return null;
  const url = toSafeWebUrl(raw.trim());
  return url !== null && url.toLowerCase().startsWith('https://') ? url : null;
}

// Opens the link in whatever app or browser the phone offers. Resolves false when the link is unusable or nothing could open it,
// so the caller can tell the user instead of failing silently. canOpenURL is not used: on Android 11+ it reports false for https
// links unless the app declares package visibility, which would block a link that openURL can open.
export async function openMapUrl(raw: string | null | undefined): Promise<boolean> {
  const url = toSafeMapUrl(raw);
  if (url === null) return false;
  try {
    await Linking.openURL(url);
    return true;
  } catch {
    return false;
  }
}
