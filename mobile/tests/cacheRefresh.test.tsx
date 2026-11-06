import React, { type ReactElement } from 'react';
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query';
import { render, waitFor, act, fireEvent } from '@testing-library/react-native';
import { ScrollView } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import { ApiError } from '../src/api/errors';
import { usePromotions } from '../src/api/app';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import {
  clearAppCache,
  getCachedAppContent,
  getCachedPromotions,
  getPromotionsCacheKey,
  setCachedAppContent,
  setCachedPromotions,
} from '../src/storage/appCache';
import type { AppContent, Card, Profile, Promotion, Promotions } from '../src/types/api';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));

const mockRequest = jest.fn();
const mockRequestWithMeta = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({
    api: {
      request: (...args: unknown[]) => mockRequest(...args),
      requestWithMeta: (...args: unknown[]) => mockRequestWithMeta(...args),
    },
    session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'test-user' },
  }),
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

jest.mock('../src/features/push', () => ({
  PushPermissionNotice: () => null,
}));

const tier = { level: 1, name: 'Base', percent: '3', max_percent: '12', spend_total: '150000.0000', next_level: 2, next_threshold: '500000.0000', remaining: '350000.0000' };
const sampleCard: Card = {
  id: 'card-1',
  barcode: '0123456789012',
  balance: '1250.0000',
  is_blocked: false,
  updated_at: '2026-10-01T00:00:00Z',
  bound_at: '2026-10-01T00:00:00Z',
  bind_method: 'phone_auto',
  business: { id: 'b-1', name: 'Supermarket', branding: null },
  tier,
};
const keremetCard: Card = {
  ...sampleCard,
  business: { id: 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0', name: 'Keremet', branding: null },
};
const sampleProfile: Profile = {
  phone: '+77058344326',
  language: 'ru',
  first_name: 'Иван',
  last_name: 'Иванов',
  email: null,
  gender: null,
  city: 'Алматы',
  address: null,
  birth_date: null,
  iin: null,
  company: null,
};

const cachedBanner: Promotion = {
  id: 'banner-cached',
  business_id: null,
  kind: 'banner',
  title: 'Старый кешированный баннер',
  subtitle: 'Скидки до 5%',
  badge: null,
  body: 'Старый текст',
  image_url: null,
  starts_at: null,
  ends_at: null,
  is_new: false,
};

const freshBanner: Promotion = {
  id: 'banner-fresh',
  business_id: null,
  kind: 'banner',
  title: 'Новый серверный баннер',
  subtitle: 'Кешбэк 20%',
  badge: 'NEW',
  body: 'Свежие условия',
  image_url: 'https://example.com/fresh.png',
  starts_at: null,
  ends_at: null,
  is_new: true,
};

const cachedAppContent: AppContent = {
  business_id: 'b-1',
  stores: [{ id: 's1', title_ru: 'Старый филиал', title_kk: 'Ескі филиал', address_ru: 'Старый адрес 1', address_kk: 'Ескі мекенжай 1', map_url: null, sort_order: 1 }],
  app_texts: { home_store_note_lead: { ru: 'Старый текст: ', kk: 'Ескі мәтін: ' } },
  updated_at: '2026-11-01T00:00:00Z',
};

const freshAppContent: AppContent = {
  business_id: 'b-1',
  stores: [{ id: 's2', title_ru: 'Новый супермаркет', title_kk: 'Жаңа супермаркет', address_ru: 'Новый адрес 10', address_kk: 'Жаңа мекенжай 10', map_url: null, sort_order: 1 }],
  app_texts: { home_store_note_lead: { ru: 'Свежий текст: ', kk: 'Жаңа мәтін: ' } },
  updated_at: '2026-11-06T12:00:00Z',
};

function mountScreen(element: ReactElement, queryClient?: QueryClient) {
  const query = queryClient ?? new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: 30000 },
      mutations: { retry: false },
    },
  });
  const screen = render(
    <QueryClientProvider client={query}>
      <I18nProvider initial="ru">
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  return { screen, query };
}

function setClientEnv(slug?: string) {
  if (!slug || slug === 'cashbackone') {
    delete process.env.EXPO_PUBLIC_CLIENT;
  } else {
    process.env.EXPO_PUBLIC_CLIENT = slug;
  }
}

describe('App Cache Refresh & Background Invalidation', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    setClientEnv();
    await clearAppCache();
  });

  afterEach(async () => {
    setClientEnv();
    await clearAppCache();
  });

  describe('1. Promotions cache refresh on Home mount', () => {
    it('displays cached promotions immediately, refetches in background, and replaces with server data', async () => {
      // 1. Fill cache with old promotions
      const oldCachedPromos: Promotions = {
        banners: [cachedBanner],
        offers: [],
        has_new: false,
      };
      setCachedPromotions('test-user', oldCachedPromos, '"etag-old"', Date.now() - 60000);

      // Server will return fresh banner
      const serverPromos: Promotions = {
        banners: [freshBanner],
        offers: [],
        has_new: true,
      };

      let resolvePromotions!: (value: unknown) => void;
      const promotionsPromise = new Promise(resolve => {
        resolvePromotions = resolve;
      });

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return promotionsPromise;
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        if (path.startsWith('/me/app-content')) return Promise.resolve(cachedAppContent);
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      // Initially cached banner is visible in carousel immediately
      await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 200 } } });
      await waitFor(() => expect(screen.getByText('Старый кешированный баннер')).toBeTruthy());

      // Ensure /me/promotions was requested in background despite initialData
      expect(mockRequestWithMeta).toHaveBeenCalledWith(
        expect.stringContaining('/me/promotions'),
        expect.objectContaining({
          headers: { 'If-None-Match': '"etag-old"' },
        }),
      );

      // Now server responds with fresh banner
      await act(async () => {
        resolvePromotions({
          status: 200,
          data: serverPromos,
          etag: '"etag-fresh"',
        });
      });

      // Fresh banner replaces the cached one
      await waitFor(() => {
        expect(screen.getByLabelText(/Новый серверный баннер/)).toBeTruthy();
        expect(screen.queryByText('Старый кешированный баннер')).toBeNull();
      });

      // Cache is updated
      expect(getCachedPromotions('test-user')?.data.banners[0]?.title).toBe('Новый серверный баннер');
    });

    it('shows cached promotions without screen error when server is unavailable', async () => {
      setCachedPromotions('test-user', { banners: [cachedBanner], offers: [], has_new: false }, null, Date.now() - 60000);

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.reject(new ApiError('NETWORK_UNAVAILABLE'));
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        if (path.startsWith('/me/app-content')) return Promise.resolve(cachedAppContent);
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 200 } } });
      await waitFor(() => {
        expect(screen.getByText('Старый кешированный баннер')).toBeTruthy();
      });

      // No error notice is displayed
      expect(screen.queryByText('Не удалось загрузить данные')).toBeNull();
    });

    it('retains cached promotions on 304 Not Modified', async () => {
      setCachedPromotions('test-user', { banners: [cachedBanner], offers: [], has_new: false }, '"etag-304"', Date.now() - 60000);

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 304, data: null, etag: '"etag-304"' });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        if (path.startsWith('/me/app-content')) return Promise.resolve(cachedAppContent);
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 200 } } });
      await waitFor(() => {
        expect(screen.getByText('Старый кешированный баннер')).toBeTruthy();
      });

      expect(mockRequestWithMeta).toHaveBeenCalledWith(
        expect.stringContaining('/me/promotions'),
        expect.objectContaining({ headers: { 'If-None-Match': '"etag-304"' } }),
      );

      // Data is still present
      expect(screen.getByText('Старый кешированный баннер')).toBeTruthy();
    });
  });

  describe('2. App content cache refresh', () => {
    it('displays cached app content immediately, refetches in background, and replaces with server data', async () => {
      setCachedAppContent('test-user', 'b-1', cachedAppContent, '"etag-c-old"', Date.now() - 60000);

      let resolveAppContent!: (value: unknown) => void;
      const appContentPromise = new Promise(resolve => {
        resolveAppContent = resolve;
      });

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 200, data: { banners: [], offers: [], has_new: false }, etag: null });
        }
        if (path.includes('/me/app-content')) {
          return appContentPromise;
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      // Cached store address is visible immediately once card is mounted
      await waitFor(() => {
        expect(screen.getByText('Старый адрес 1')).toBeTruthy();
      });

      // Ensure /me/app-content was requested in background despite initialData
      expect(mockRequestWithMeta).toHaveBeenCalledWith(
        expect.stringContaining('/me/app-content?business_id=b-1'),
        expect.objectContaining({
          headers: { 'If-None-Match': '"etag-c-old"' },
        }),
      );

      // Server responds with fresh content
      await act(async () => {
        resolveAppContent({
          status: 200,
          data: freshAppContent,
          etag: '"etag-c-fresh"',
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Новый адрес 10')).toBeTruthy();
        expect(screen.queryByText('Старый адрес 1')).toBeNull();
      });

      expect(getCachedAppContent('test-user', 'b-1')?.data.stores[0]?.title_ru).toBe('Новый супермаркет');
    });

    it('shows cached app content without screen error when server is unavailable', async () => {
      setCachedAppContent('test-user', 'b-1', cachedAppContent, null, Date.now() - 60000);

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 200, data: { banners: [], offers: [], has_new: false }, etag: null });
        }
        if (path.includes('/me/app-content')) {
          return Promise.reject(new ApiError('NETWORK_UNAVAILABLE'));
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => {
        expect(screen.getByText('Старый адрес 1')).toBeTruthy();
      });
      expect(screen.queryByText('Не удалось загрузить данные')).toBeNull();
    });

    it('retains cached app content on 304 Not Modified', async () => {
      setCachedAppContent('test-user', 'b-1', cachedAppContent, '"etag-c-304"', Date.now() - 60000);

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 200, data: { banners: [], offers: [], has_new: false }, etag: null });
        }
        if (path.includes('/me/app-content')) {
          return Promise.resolve({ status: 304, data: null, etag: '"etag-c-304"' });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => {
        expect(screen.getByText('Старый адрес 1')).toBeTruthy();
      });

      expect(mockRequestWithMeta).toHaveBeenCalledWith(
        expect.stringContaining('/me/app-content?business_id=b-1'),
        expect.objectContaining({ headers: { 'If-None-Match': '"etag-c-304"' } }),
      );

      expect(screen.getByText('Старый адрес 1')).toBeTruthy();
    });
  });

  describe('3. Pull-to-refresh on Home triggers refetches', () => {
    it('refetches promotions, cards, profile, and app content on pull-to-refresh', async () => {
      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 200, data: { banners: [freshBanner], offers: [], has_new: false }, etag: null });
        }
        if (path.includes('/me/app-content')) {
          return Promise.resolve({ status: 200, data: freshAppContent, etag: null });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('banner-carousel')).toBeTruthy();
      });

      const initialPromoCalls = mockRequestWithMeta.mock.calls.filter(c => c[0].includes('/me/promotions')).length;
      const initialContentCalls = mockRequestWithMeta.mock.calls.filter(c => c[0].includes('/me/app-content')).length;
      const initialCardCalls = mockRequest.mock.calls.filter(c => c[0].startsWith('/me/cards')).length;
      const initialProfileCalls = mockRequest.mock.calls.filter(c => c[0].startsWith('/me/profile')).length;

      expect(initialPromoCalls).toBeGreaterThanOrEqual(1);
      expect(initialContentCalls).toBeGreaterThanOrEqual(1);
      expect(initialCardCalls).toBeGreaterThanOrEqual(1);
      expect(initialProfileCalls).toBeGreaterThanOrEqual(1);

      // Find ScrollView with RefreshControl
      const scrollView = screen.UNSAFE_getByType(ScrollView);
      const refreshControl = scrollView.props.refreshControl;
      expect(refreshControl).toBeDefined();

      // Trigger pull-to-refresh
      await act(async () => {
        refreshControl.props.onRefresh();
      });

      await waitFor(() => {
        const afterPromoCalls = mockRequestWithMeta.mock.calls.filter(c => c[0].includes('/me/promotions')).length;
        const afterContentCalls = mockRequestWithMeta.mock.calls.filter(c => c[0].includes('/me/app-content')).length;
        const afterCardCalls = mockRequest.mock.calls.filter(c => c[0].startsWith('/me/cards')).length;
        const afterProfileCalls = mockRequest.mock.calls.filter(c => c[0].startsWith('/me/profile')).length;

        expect(afterPromoCalls).toBeGreaterThan(initialPromoCalls);
        expect(afterContentCalls).toBeGreaterThan(initialContentCalls);
        expect(afterCardCalls).toBeGreaterThan(initialCardCalls);
        expect(afterProfileCalls).toBeGreaterThan(initialProfileCalls);
      });
    });
  });

  describe('4. General client vs Keremet client scoping', () => {
    it('requests /me/promotions without business_id for general client (cashbackone)', async () => {
      setClientEnv('cashbackone');

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          return Promise.resolve({ status: 200, data: { banners: [freshBanner], offers: [], has_new: false }, etag: null });
        }
        if (path.includes('/me/app-content')) {
          return Promise.resolve({ status: 200, data: freshAppContent, etag: null });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([sampleCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('banner-carousel')).toBeTruthy();
      });

      const promoCalls = mockRequestWithMeta.mock.calls.filter(c => c[0].includes('/me/promotions'));
      expect(promoCalls.length).toBeGreaterThanOrEqual(1);
      expect(promoCalls[0][0]).toBe('/me/promotions');
      expect(promoCalls[0][0]).not.toContain('business_id=');

      // General client cache key
      expect(getPromotionsCacheKey('test-user')).toBe('cashback-one.cache.v1:user:test-user:promotions');
    });

    it('requests /me/promotions with business_id for keremet client and invalidates empty cached response', async () => {
      setClientEnv('keremet');
      const keremetBizId = 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0';

      // Simulate the exact bug symptom:
      // Keremet user had an old empty cached promotion response from when promotions tab was first opened.
      const emptyKeremetCache: Promotions = { banners: [], offers: [], has_new: false };
      setCachedPromotions('test-user', emptyKeremetCache, '"empty-etag"', Date.now() - 60000);

      // Ensure cache key has keremet business_id
      expect(getPromotionsCacheKey('test-user')).toBe(
        `cashback-one.cache.v1:user:test-user:business:${keremetBizId}:promotions`,
      );

      const keremetFreshBanner: Promotion = {
        id: 'banner-keremet-1',
        business_id: keremetBizId,
        kind: 'banner',
        title: 'Керемет Бонус 10% Кешбэк',
        subtitle: 'Только в супермаркетах Keremet',
        badge: 'NEW',
        body: 'Условия Керемет',
        image_url: null,
        starts_at: null,
        ends_at: null,
        is_new: true,
      };

      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          expect(path).toContain(`business_id=${keremetBizId}`);
          return Promise.resolve({
            status: 200,
            data: { banners: [keremetFreshBanner], offers: [], has_new: true },
            etag: '"keremet-fresh-etag"',
          });
        }
        if (path.includes('/me/app-content')) {
          return Promise.resolve({ status: 200, data: freshAppContent, etag: null });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      mockRequest.mockImplementation((path: string) => {
        if (path.startsWith('/me/cards')) return Promise.resolve([keremetCard]);
        if (path.startsWith('/me/profile')) return Promise.resolve(sampleProfile);
        if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
        return Promise.reject(new Error(`unexpected request ${path}`));
      });

      const { screen } = mountScreen(<Home />);

      // On mount, /me/promotions?business_id=... is triggered despite empty cache,
      // and new banner appears!
      await waitFor(() => {
        expect(screen.getByTestId('banner-carousel')).toBeTruthy();
      });
      fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 200 } } });

      await waitFor(() => {
        expect(screen.getByText('Керемет Бонус 10% Кешбэк')).toBeTruthy();
      });

      // Cache is now updated with Keremet banner
      expect(getCachedPromotions('test-user')?.data.banners[0]?.title).toBe('Керемет Бонус 10% Кешбэк');
    });
  });

  describe('5. Return from background (focusManager)', () => {
    it('triggers refetch of stale query when focusManager receives focus', async () => {
      let fetchCount = 0;
      mockRequestWithMeta.mockImplementation((path: string) => {
        if (path.includes('/me/promotions')) {
          fetchCount++;
          return Promise.resolve({
            status: 200,
            data: {
              banners: [{ ...freshBanner, title: `Banner #${fetchCount}` }],
              offers: [],
              has_new: false,
            },
            etag: `"etag-${fetchCount}"`,
          });
        }
        return Promise.reject(new Error(`unexpected meta ${path}`));
      });

      function TestPromoViewer() {
        usePromotions();
        return null;
      }

      const queryClient = new QueryClient({
        defaultOptions: {
          queries: { retry: false, gcTime: Infinity, staleTime: 30000 },
        },
      });

      mountScreen(<TestPromoViewer />, queryClient);

      await waitFor(() => expect(fetchCount).toBe(1));

      // Make query stale by setting dataUpdatedAt 40s in the past
      const promoQuery = queryClient.getQueryCache().findAll()[0];
      expect(promoQuery).toBeDefined();
      promoQuery?.setData(
        { banners: [{ ...freshBanner, title: 'Banner #1' }], offers: [], has_new: false },
        { updatedAt: Date.now() - 40000, manual: true },
      );
      expect(promoQuery?.isStale()).toBe(true);

      // Simulate app backgrounding
      act(() => {
        focusManager.setFocused(false);
      });

      // Simulate app returning to active foreground
      await act(async () => {
        focusManager.setFocused(true);
      });

      // Refetch is triggered
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });
  });
});
