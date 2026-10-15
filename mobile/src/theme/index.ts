// Montserrat weights are separate font families on Android, so text styles use fontFamily, not fontWeight.
export const fonts = {
  regular: 'Montserrat_400Regular',
  medium: 'Montserrat_500Medium',
  semibold: 'Montserrat_600SemiBold',
  bold: 'Montserrat_700Bold',
  extrabold: 'Montserrat_800ExtraBold',
} as const;

export const theme = {
  colors: {
    background: '#F4F4F6', surface: '#FFFFFF', text: '#111111', muted: '#8E8E93', subtle: '#B4B4BA',
    primary: '#EE1D3E', primaryPressed: '#D0102F', onPrimary: '#FFFFFF', softPrimary: '#FDE9EC', tint: '#F8EEF0',
    status: '#F8BEB2', border: '#E7E7EB', input: '#F2F2F4', error: '#C8102E', success: '#1F8A4C', softError: '#FFF1F0',
    qr: '#FFFFFF', shadow: '#1B1B1F',
  },
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  radius: { sm: 12, md: 20, lg: 28, pill: 999 },
  font: { small: 13, body: 16, label: 18, title: 24, hero: 34, balance: 40 },
  touch: 48,
};
