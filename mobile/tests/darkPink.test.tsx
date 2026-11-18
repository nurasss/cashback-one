import fs from 'fs';
import path from 'path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import { clearAppCache } from '../src/storage/appCache';
import { darkColors, lightColors } from '../src/theme';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { AppContent, Card, Profile } from '../src/types/api';

const mockRequest = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'u1' } }),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));

// WCAG relative luminance and contrast ratio.
const luminance = (hex: string) => {
  const channel = (offset: number) => { const v = parseInt(hex.slice(offset, offset + 2), 16) / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
};
const contrast = (a: string, b: string) => { const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]; return (hi + 0.05) / (lo + 0.05); };

const card: Card = { id: 'c1', barcode: '0123456789012', balance: '1250.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b-1', name: 'Shop', branding: null }, tier: null };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const app: AppContent = { business_id: 'b-1', stores: [{ id: 's1', title_ru: 'Магазин', title_kk: 'Дүкен', address_ru: 'ул. Абая, 1', address_kk: 'Абай к-сі, 1', map_url: null, sort_order: 1 }], app_texts: {}, updated_at: '2026-11-11T00:00:00Z' };

function mount(theme: 'light' | 'dark') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000, gcTime: Infinity }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={query}>
      <ThemeProvider initialPreference={theme}><I18nProvider initial="ru"><ActiveCardProvider><Home /></ActiveCardProvider></I18nProvider></ThemeProvider>
    </QueryClientProvider>,
  );
}
beforeEach(async () => {
  jest.clearAllMocks();
  await clearAppCache();
  mockRequest.mockImplementation((path: string) => {
    if (path.startsWith('/me/cards')) return Promise.resolve([card]);
    if (path.startsWith('/me/profile')) return Promise.resolve(profile);
    if (path.startsWith('/me/promotions')) return Promise.resolve({ banners: [], offers: [], has_new: false });
    if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
    if (path.startsWith('/me/app-content')) return Promise.resolve(app);
    return Promise.reject(new Error(`unexpected ${path}`));
  });
});

describe('dark theme: one pink for text, icons and links', () => {
  it('the dark theme has two reds: the brand fill and the lighter accent for text and icons', () => {
    expect(darkColors.primary).not.toBe(darkColors.primaryText);
    expect(lightColors.primary).toBe(lightColors.primaryText); // in the light theme they are the same, so nothing changes there
  });

  it('the accent for text and icons is readable (WCAG AA 4.5:1) on the dark surfaces it is used on', () => {
    for (const background of [darkColors.background, darkColors.surface, darkColors.softPrimary, darkColors.tint]) {
      expect(contrast(darkColors.primaryText, background)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each([['dark', darkColors.primaryText], ['light', lightColors.primaryText]] as const)('the "where can I spend" link on Home (%s) uses the accent token', async (theme, expected) => {
    const screen = mount(theme);
    await waitFor(() => { if (screen.queryByText(ru.whereToSpendBonuses) === null) throw new Error('not yet: the link'); });
    const style = StyleSheet.flatten(screen.getByText(ru.whereToSpendBonuses).props.style) as { color?: string };
    expect(style.color).toBe(expected);
  });

  it('no text, icon or link colour in the app uses the brand FILL token (only fills do); the one exception is a spinner on the white QR field', () => {
    const roots = ['app', 'src'];
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.(tsx|ts)$/.test(entry.name)) {
          const text = fs.readFileSync(full, 'utf8');
          text.split('\n').forEach((line, index) => {
            if (/color:\s*(c|colors)\.primary\b(?!Text|Pressed)/.test(line) || /(color|tintColor)=\{colors\.primary\}/.test(line)) offenders.push(`${path.relative(path.join(__dirname, '..'), full)}:${index + 1}`);
          });
        }
      }
    };
    roots.forEach(root => walk(path.join(__dirname, '..', root)));
    expect(offenders).toEqual(['src/features/DynamicQr.tsx:46']);
  });
});
