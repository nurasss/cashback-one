import { getClientConfig } from '../config/client';

const clientPrimary = (() => {
  try {
    return getClientConfig().primary_color;
  } catch {
    return '#EE1D3E';
  }
})();

// Montserrat weights are separate font families on Android, so text styles use fontFamily, not fontWeight.
export const fonts = {
  regular: 'Montserrat_400Regular',
  medium: 'Montserrat_500Medium',
  semibold: 'Montserrat_600SemiBold',
  bold: 'Montserrat_700Bold',
  extrabold: 'Montserrat_800ExtraBold',
} as const;

export type ThemePreference = 'light' | 'dark' | 'system';
export type ColorScheme = 'light' | 'dark';

export const THEME_PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system'];

// Mixes `hex` towards white; used to make the brand accent readable as text on dark surfaces.
export function mixWithWhite(hex: string, amount: number): string {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) return hex;
  const value = parseInt(match[1]!, 16);
  const channel = (shift: number) => {
    const base = (value >> shift) & 255;
    return Math.round(base + (255 - base) * amount).toString(16).padStart(2, '0');
  };
  return `#${channel(16)}${channel(8)}${channel(0)}`.toUpperCase();
}

export interface Colors {
  background: string; surface: string; text: string; muted: string; placeholder: string; subtle: string;
  /** Brand fill (buttons, pills, badges). Identical in both themes. */
  primary: string;
  /** Brand accent for text and icons: equal to `primary` in light, lightened in dark for contrast. */
  primaryText: string;
  primaryPressed: string; onPrimary: string; softPrimary: string; tint: string;
  status: string; border: string; input: string; error: string; success: string; softSuccess: string; softError: string;
  shadow: string;
  /** Fill of a destructive button and the text on it: separate from `error` (text/icons), which is lightened in dark. */
  destructive: string; onDestructive: string;
  /** QR is always a black code on an opaque white field, in every theme. */
  qr: string; qrInk: string;
  // Semantic tokens for surfaces that used hard-coded colours before.
  overlay: string; overlayLight: string; cardBorder: string; track: string; dotInactive: string;
  mediaBackground: string; offerPink: string; offerGray: string; imagePlaceholder: string;
  statusGradientStart: string; statusGradientEnd: string; statusShadow: string; statusCaption: string;
  disabledBackground: string; disabledBorder: string; disabledText: string;
  secondaryDisabledBackground: string; secondaryDisabledBorder: string; secondaryDisabledText: string;
  avatarOverlay: string; walletBackground: string; walletBorder: string;
}

export const lightColors: Colors = {
  background: '#F4F4F6', surface: '#FFFFFF', text: '#111111', muted: '#6E6E76', placeholder: '#6C6C74', subtle: '#B4B4BA',
  primary: clientPrimary, primaryText: clientPrimary, primaryPressed: '#D0102F', onPrimary: '#FFFFFF', softPrimary: '#FDE9EC', tint: '#F8EEF0',
  status: '#F8BEB2', border: '#E7E7EB', input: '#F2F2F4', error: '#C8102E', success: '#1F8A4C', softSuccess: '#E8F5EC', softError: '#FFF1F0',
  shadow: '#1B1B1F',
  destructive: '#C8102E', onDestructive: '#FFFFFF',
  qr: '#FFFFFF', qrInk: '#000000',
  overlay: 'rgba(0,0,0,0.4)', overlayLight: 'rgba(0,0,0,0.35)', cardBorder: 'rgba(17,17,17,0.05)', track: '#ECECF0', dotInactive: '#D9D9DD',
  mediaBackground: '#EBEBEF', offerPink: '#FCE9EC', offerGray: '#F1F1F4', imagePlaceholder: 'rgba(0,0,0,0.03)',
  statusGradientStart: '#FFB2A4', statusGradientEnd: '#FFC4B6', statusShadow: '#F28A75', statusCaption: 'rgba(17,17,17,0.6)',
  disabledBackground: '#FDE9EC', disabledBorder: '#F5C9D1', disabledText: '#7E2333',
  secondaryDisabledBackground: '#E9E9EC', secondaryDisabledBorder: '#D6D6DB', secondaryDisabledText: '#5E5E66',
  avatarOverlay: 'rgba(255,255,255,0.7)', walletBackground: '#000000', walletBorder: '#000000',
};

export const darkColors: Colors = {
  background: '#0E0E11', surface: '#1A1A1F', text: '#F2F2F4', muted: '#A4A4AD', placeholder: '#92929C', subtle: '#7C7C86',
  primary: clientPrimary, primaryText: mixWithWhite(clientPrimary, 0.25), primaryPressed: '#D0102F', onPrimary: '#FFFFFF', softPrimary: '#3A1B22', tint: '#2B2024',
  status: '#7A3A34', border: '#2E2E35', input: '#26262C', error: '#FF7A88', success: '#4CCB7F', softSuccess: '#16301F', softError: '#3A1D21',
  shadow: '#000000',
  destructive: '#C41E32', onDestructive: '#FFFFFF',
  qr: '#FFFFFF', qrInk: '#000000',
  overlay: 'rgba(0,0,0,0.6)', overlayLight: 'rgba(0,0,0,0.55)', cardBorder: 'rgba(255,255,255,0.08)', track: '#33333A', dotInactive: '#4A4A52',
  mediaBackground: '#26262C', offerPink: '#2B1F23', offerGray: '#222227', imagePlaceholder: 'rgba(255,255,255,0.04)',
  statusGradientStart: '#4B2630', statusGradientEnd: '#5E303B', statusShadow: '#000000', statusCaption: 'rgba(242,242,244,0.7)',
  disabledBackground: '#3A1B22', disabledBorder: '#552731', disabledText: '#E8A3AF',
  secondaryDisabledBackground: '#26262C', secondaryDisabledBorder: '#34343C', secondaryDisabledText: '#8C8C96',
  avatarOverlay: 'rgba(26,26,31,0.7)', walletBackground: '#000000', walletBorder: '#3A3A42',
};

export function colorsFor(scheme: ColorScheme): Colors {
  return scheme === 'dark' ? darkColors : lightColors;
}

// Non-colour tokens are static. Colours are theme-dependent and are read through `useTheme()` (see ThemeProvider).
export const theme = {
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  radius: { sm: 12, md: 20, lg: 28, pill: 999 },
  font: { small: 13, body: 16, label: 18, title: 24, hero: 34, balance: 40 },
  touch: 48,
};
