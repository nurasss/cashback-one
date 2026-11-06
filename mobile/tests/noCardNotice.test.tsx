import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import fs from 'fs';
import path from 'path';
import type { ReactElement } from 'react';
import Home from '../app/(app)/(tabs)/index';
import QrScreen from '../app/(app)/(tabs)/qr';
import CardsScreen from '../app/(app)/cards';
import StatusScreen from '../app/(app)/status';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { AppContent, Card, Profile, Promotions } from '../src/types/api';

const mockRequest = jest.fn();
const mockRouterPush = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));

jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return {
    router: {
      push: (...args: unknown[]) => mockRouterPush(...args),
      replace: jest.fn(),
      navigate: jest.fn(),
      back: jest.fn(),
      canGoBack: () => true,
    },
    useFocusEffect: (cb: () => void | (() => void)) => {
      React.useEffect(() => {
        const cleanup = cb();
        return () => {
          if (typeof cleanup === 'function') cleanup();
        };
      }, [cb]);
    },
  };
});

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) {
    return React.createElement(Text, { testID: 'qr-payload' }, value);
  };
});

const sampleCard: Card = {
  id: 'card-123',
  barcode: '1234567890123',
  balance: '1500.0000',
  is_blocked: false,
  updated_at: '2026-11-01T00:00:00Z',
  bound_at: '2026-11-01T00:00:00Z',
  bind_method: 'phone_auto',
  business: { id: 'biz-one', name: 'Supermarket One', branding: null },
  tier: {
    level: 1,
    name: 'Silver',
    percent: '3',
    max_percent: '10',
    spend_total: '10000',
    next_level: 2,
    next_threshold: '50000',
    remaining: '40000',
  },
};

const sampleProfile: Profile = {
  phone: '77011234567',
  first_name: 'Азамат',
  last_name: 'Нұрланұлы',
  email: null,
  birth_date: null,
  gender: null,
  city: 'Алматы',
  address: null,
  iin: null,
  company: null,
  avatar_url: null,
  language: 'ru',
};

const samplePromotions: Promotions = {
  has_new: false,
  banners: [
    {
      id: 'banner-1',
      business_id: null,
      kind: 'banner',
      title: 'Выиграй суперприз',
      subtitle: 'Призы каждую неделю',
      badge: null,
      body: 'Подробности в правилах акции',
      image_url: 'https://cdn.example.com/banner1.jpg',
      starts_at: null,
      ends_at: null,
      is_new: false,
    },
  ],
  offers: [
    {
      id: 'offer-1',
      business_id: null,
      kind: 'offer',
      title: 'Свежие яблоки',
      subtitle: null,
      badge: 'Суперцена',
      body: 'Скидка на все яблоки',
      image_url: 'https://cdn.example.com/apples.jpg',
      starts_at: null,
      ends_at: null,
      is_new: true,
    },
  ],
};

const sampleKeremetAppContent: AppContent = {
  business_id: 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0',
  stores: [
    {
      id: 'store-km-1',
      title_ru: 'Керемет Сауда',
      title_kk: 'Керемет Сауда',
      address_ru: 'ул. Абая, 100',
      address_kk: 'Абай к-сі, 100',
      sort_order: 1,
      map_url: 'https://maps.example.com/keremet',
    },
  ],
  app_texts: {
    home_store_note_lead: {
      ru: 'Адрес магазина: ',
      kk: 'Дүкен мекенжайы: ',
    },
  },
  updated_at: '2026-11-06T00:00:00Z',
};

const mountWith = (element: ReactElement, initialLang: 'ru' | 'kz' = 'ru') => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <I18nProvider initial={initialLang}>
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
};

const serve = (routes: Record<string, unknown>) => {
  mockRequest.mockReset();
  mockRequest.mockImplementation((path: string) => {
    for (const [route, response] of Object.entries(routes)) {
      if (path.startsWith(route)) return Promise.resolve(response);
    }
    return Promise.reject(new Error(`Unhandled: ${path}`));
  });
};

describe('No card bind removed — Home, QR, Cards, Status', () => {
  const originalEnv = process.env.EXPO_PUBLIC_CLIENT;

  beforeEach(() => {
    mockRequest.mockReset();
    mockRouterPush.mockReset();
    delete process.env.EXPO_PUBLIC_CLIENT;
  });

  afterEach(() => {
    process.env.EXPO_PUBLIC_CLIENT = originalEnv;
  });

  describe('Home screen without card', () => {
    it('shows notice banner in Russian, balance 0,00, banners, and hot offers; no bind button', async () => {
      serve({
        '/me/cards': [],
        '/me/profile': sampleProfile,
        '/me/promotions': samplePromotions,
      });

      const screen = mountWith(<Home />, 'ru');

      // Notice banner in place of status block
      await waitFor(() => {
        expect(screen.getByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeTruthy();
      });
      expect(screen.getByTestId('no-card-notice')).toBeTruthy();

      // Balance defaults to 0,00
      expect(screen.getByText('0,00')).toBeTruthy();

      // Banners and offers from server are displayed normally
      await waitFor(() => {
        expect(screen.getByTestId('banner-carousel')).toBeTruthy();
      });
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', {
        nativeEvent: { layout: { width: 390, height: 200 } },
      });
      await waitFor(() => {
        expect(screen.getByText('Выиграй суперприз')).toBeTruthy();
      });
      expect(screen.getByText('Свежие яблоки')).toBeTruthy();

      // NO bind button or "Добавить карту" anywhere
      expect(screen.queryByText('Привязать карту')).toBeNull();
      expect(screen.queryByText('Добавьте карту лояльности')).toBeNull();
      expect(screen.queryByText('Картаны байлау')).toBeNull();
      expect(mockRouterPush).not.toHaveBeenCalled();

      screen.unmount();
    });

    it('shows notice banner in Kazakh without card', async () => {
      serve({
        '/me/cards': [],
        '/me/profile': sampleProfile,
        '/me/promotions': samplePromotions,
      });

      const screen = mountWith(<Home />, 'kz');

      await waitFor(() => {
        expect(screen.getByText('Дүкен базасында телефон нөміріңізге тіркелген карта табылмады. Дүкенге хабарласыңыз.')).toBeTruthy();
      });
      expect(screen.getByTestId('no-card-notice')).toBeTruthy();

      // Kazakh hot offers header
      expect(screen.getByText(kz.hotOffers)).toBeTruthy();
      expect(screen.queryByText('Картаны байлау')).toBeNull();

      screen.unmount();
    });

    it('with card: shows status card and balance as before, hides no-card notice', async () => {
      serve({
        '/me/cards': [sampleCard],
        '/me/profile': sampleProfile,
        '/me/promotions': samplePromotions,
      });

      const screen = mountWith(<Home />, 'ru');

      await waitFor(() => {
        expect(screen.getAllByText('1 500,00').length).toBeGreaterThanOrEqual(1);
      });
      expect(screen.queryByTestId('no-card-notice')).toBeNull();
      expect(screen.queryByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeNull();

      screen.unmount();
    });
  });

  describe('QR screen without card', () => {
    it('shows notice banner in Russian and Kazakh instead of button', async () => {
      serve({ '/me/cards': [] });

      const screenRu = mountWith(<QrScreen />, 'ru');
      await waitFor(() => {
        expect(screenRu.getByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeTruthy();
      });
      expect(screenRu.getByTestId('no-card-notice')).toBeTruthy();
      expect(screenRu.queryByTestId('qr-payload')).toBeNull();
      expect(screenRu.queryByText('Привязать карту')).toBeNull();
      screenRu.unmount();

      const screenKz = mountWith(<QrScreen />, 'kz');
      await waitFor(() => {
        expect(screenKz.getByText('Дүкен базасында телефон нөміріңізге тіркелген карта табылмады. Дүкенге хабарласыңыз.')).toBeTruthy();
      });
      expect(screenKz.getByTestId('no-card-notice')).toBeTruthy();
      expect(screenKz.queryByText('Картаны байлау')).toBeNull();
      screenKz.unmount();
    });
  });

  describe('Cards screen (Мои карты) without card', () => {
    it('empty list renders notice banner; no add/bind footer button', async () => {
      serve({ '/me/cards': [] });

      const screen = mountWith(<CardsScreen />, 'ru');
      await waitFor(() => {
        expect(screen.getByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeTruthy();
      });
      expect(screen.getByTestId('no-card-notice')).toBeTruthy();
      expect(screen.queryByText('Привязать карту')).toBeNull();
      expect(screen.queryByText('Картаны байлау')).toBeNull();

      screen.unmount();
    });

    it('with card: renders card item and actions', async () => {
      serve({ '/me/cards': [sampleCard] });

      const screen = mountWith(<CardsScreen />, 'ru');
      await waitFor(() => {
        expect(screen.getByText('Supermarket One')).toBeTruthy();
      });
      expect(screen.queryByTestId('no-card-notice')).toBeNull();
      expect(screen.queryByText('Привязать карту')).toBeNull();

      screen.unmount();
    });
  });

  describe('Status screen without card', () => {
    it('shows notice banner when no card is bound', async () => {
      serve({ '/me/cards': [], '/me/badges': { promotions_new: false, notifications_unread: 0 } });

      const screen = mountWith(<StatusScreen />, 'ru');
      await waitFor(() => {
        expect(screen.getByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeTruthy();
      });
      expect(screen.getByTestId('no-card-notice')).toBeTruthy();

      screen.unmount();
    });
  });

  describe('Keremet client without card', () => {
    it('shows notice banner, keremet stores block, banners and offers', async () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      serve({
        '/me/cards': [],
        '/me/profile': sampleProfile,
        '/me/promotions': samplePromotions,
        '/me/app-content': sampleKeremetAppContent,
      });

      const screen = mountWith(<Home />, 'ru');

      await waitFor(() => {
        expect(screen.getByText('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.')).toBeTruthy();
      });
      expect(screen.getByTestId('no-card-notice')).toBeTruthy();

      // Stores block appears for keremet even without a card
      await waitFor(() => {
        expect(screen.getByTestId('store-block')).toBeTruthy();
      });
      expect(screen.getByText(/ул\. Абая, 100/)).toBeTruthy();

      // Offers and banners still visible
      await waitFor(() => {
        expect(screen.getByTestId('banner-carousel')).toBeTruthy();
      });
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', {
        nativeEvent: { layout: { width: 390, height: 200 } },
      });
      await waitFor(() => {
        expect(screen.getByText('Выиграй суперприз')).toBeTruthy();
      });
      expect(screen.getByText('Свежие яблоки')).toBeTruthy();

      expect(screen.queryByText('Привязать карту')).toBeNull();

      screen.unmount();
    });
  });

  describe('Route and code structure verification', () => {
    it('app/(app)/bind.tsx does not exist', () => {
      const bindPath = path.resolve(__dirname, '../app/(app)/bind.tsx');
      expect(fs.existsSync(bindPath)).toBe(false);
    });

    it('CardScanner.tsx and BindForm.tsx do not exist', () => {
      expect(fs.existsSync(path.resolve(__dirname, '../src/features/CardScanner.tsx'))).toBe(false);
      expect(fs.existsSync(path.resolve(__dirname, '../src/features/BindForm.tsx'))).toBe(false);
    });

    it('app/(app)/_layout.tsx does not have bind route', () => {
      const layoutContent = fs.readFileSync(path.resolve(__dirname, '../app/(app)/_layout.tsx'), 'utf8');
      expect(layoutContent.includes('name="bind"')).toBe(false);
    });

    it('translation dictionaries do not contain old bind keys', () => {
      const ruDict = ru as Record<string, string>;
      const kzDict = kz as Record<string, string>;
      expect(ruDict.bind).toBeUndefined();
      expect(ruDict.noCardTitle).toBeUndefined();
      expect(ruDict.noCardBody).toBeUndefined();
      expect(ruDict.scanWithCamera).toBeUndefined();
      expect(ruDict.cameraPermissionTitle).toBeUndefined();
      expect(ruDict.cameraPermissionDenied).toBeUndefined();

      expect(kzDict.bind).toBeUndefined();
      expect(kzDict.noCardTitle).toBeUndefined();
      expect(kzDict.noCardBody).toBeUndefined();
      expect(kzDict.scanWithCamera).toBeUndefined();
      expect(kzDict.cameraPermissionTitle).toBeUndefined();
      expect(kzDict.cameraPermissionDenied).toBeUndefined();

      expect(ruDict.noCardNotice).toBe('Карта с вашим номером телефона не найдена в базе магазина. Пожалуйста, обратитесь в магазин.');
      expect(kzDict.noCardNotice).toBe('Дүкен базасында телефон нөміріңізге тіркелген карта табылмады. Дүкенге хабарласыңыз.');
    });
  });
});
