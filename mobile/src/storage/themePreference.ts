import AsyncStorage from '@react-native-async-storage/async-storage';
import { THEME_PREFERENCES, type ThemePreference } from '../theme';

// Local-only device setting. It is deliberately NOT under the `cashback-one.cache.v1:` prefix and not in SecureStore,
// so logging out, invalidating the session or clearing the app cache never touches it.
export const THEME_STORAGE_KEY = 'cashback-one.theme.v1';

// Existing users have no stored value and keep the light look; a missing or damaged value is also light.
export const DEFAULT_THEME_PREFERENCE: ThemePreference = 'light';

export function parseThemePreference(raw: unknown): ThemePreference {
  return typeof raw === 'string' && (THEME_PREFERENCES as readonly string[]).includes(raw) ? (raw as ThemePreference) : DEFAULT_THEME_PREFERENCE;
}

export async function loadThemePreference(): Promise<ThemePreference> {
  try {
    return parseThemePreference(await AsyncStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

export async function saveThemePreference(preference: ThemePreference): Promise<boolean> {
  try {
    await AsyncStorage.setItem(THEME_STORAGE_KEY, preference);
    return true;
  } catch {
    return false;
  }
}
