import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Appearance, useColorScheme } from 'react-native';
import { loadThemePreference, saveThemePreference, DEFAULT_THEME_PREFERENCE } from '../storage/themePreference';
import { colorsFor, lightColors, type Colors, type ColorScheme, type ThemePreference } from './index';

export interface ThemeState {
  colors: Colors;
  /** The scheme actually in effect (a `system` preference is resolved to light or dark). */
  scheme: ColorScheme;
  preference: ThemePreference;
  isDark: boolean;
  setPreference: (preference: ThemePreference) => void;
}

const fallback: ThemeState = { colors: lightColors, scheme: 'light', preference: 'light', isDark: false, setPreference: () => {} };
const Context = createContext<ThemeState | null>(null);

// Never block the first frame forever if storage hangs: fall back to the safe light look.
const LOAD_TIMEOUT_MS = 1500;

function syncNativeScheme(preference: ThemePreference) {
  // Aligns native surfaces (alerts, pickers, system bars) with the in-app choice. `unspecified` follows the device.
  try { Appearance.setColorScheme(preference === 'system' ? 'unspecified' : preference); } catch { /* not supported: JS colours still apply */ }
}

export function ThemeProvider({ children, initialPreference }: { children: ReactNode; initialPreference?: ThemePreference }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(initialPreference ?? DEFAULT_THEME_PREFERENCE);
  const [ready, setReady] = useState(initialPreference !== undefined);
  const system = useColorScheme();
  // Set as soon as the user (or a caller) picks a theme explicitly. A stored value read later must never override it;
  // comparing values is not enough, because an explicit `light` looks the same as the initial default.
  const chosenExplicitly = useRef(initialPreference !== undefined);

  useEffect(() => {
    if (initialPreference !== undefined) return;
    let cancelled = false;
    const timer = setTimeout(() => { if (!cancelled) setReady(true); }, LOAD_TIMEOUT_MS);
    void loadThemePreference().then(stored => {
      if (cancelled) return;
      if (!chosenExplicitly.current) setPreferenceState(stored);
      setReady(true);
    });
    return () => { cancelled = true; clearTimeout(timer); };
  }, [initialPreference]);

  useEffect(() => { if (ready) syncNativeScheme(preference); }, [preference, ready]);

  const setPreference = useCallback((next: ThemePreference) => {
    chosenExplicitly.current = true;
    setPreferenceState(next);
    setReady(true);
    void saveThemePreference(next);
  }, []);

  const scheme: ColorScheme = preference === 'system' ? (system === 'dark' ? 'dark' : 'light') : preference;
  const value = useMemo<ThemeState>(() => ({ colors: colorsFor(scheme), scheme, preference, isDark: scheme === 'dark', setPreference }), [scheme, preference, setPreference]);
  if (!ready) return null;
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useTheme(): ThemeState {
  return useContext(Context) ?? fallback;
}

/** Builds a StyleSheet for the current palette. `factory` must be a module-level function so the result is memoised per scheme. */
export function useThemedStyles<T>(factory: (colors: Colors) => T): T {
  const { colors } = useTheme();
  return useMemo(() => factory(colors), [factory, colors]);
}
