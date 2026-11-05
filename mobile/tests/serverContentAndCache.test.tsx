import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import StatusScreen from '../app/(app)/status';
import { ApiClient } from '../src/api/client';
import { ApiError } from '../src/api/errors';
import { fetchAppContentWithCache, fetchPromotionsWithCache } from '../src/api/app';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import {
  clearAppCache,
  getCachedAppContent,
  getCachedPromotions,
  setCachedAppContent,
  setCachedPromotions,
} from '../src/storage/appCache';
import type { AppContent, Card, Promotions } from '../src/types/api';

const mockRequest = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({
    api: { request: mockRequest },
    session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'user-1' },
  }),
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const tier = { level: 1, name: 'Base', percent: '3', max_percent: '12', spend_total: '150000.0000', next_level: 2, next_threshold: '500000.0000', remaining: '350000.0000' };
const card: Card = {
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

const sampleContent: AppContent = {
  business_id: 'b-1',
  stores: [
    { id: 's1', title_ru: 'Магазин 1', title_kk: '1-дүкен', address_ru: 'ул. Абая, 1', address_kk: 'Абай к-сі, 1', map_url: null, sort_order: 1 },
  ],
  app_texts: {
    home_store_note_lead: { ru: 'Потратить баллы: ', kk: 'Ұпайларды жұмсау: ' },
    balance_delay_note: { ru: 'Серверный текст задержки', kk: 'Кідіріс туралы серверлік мәтін' },
  },
  updated_at: '2026-11-04T12:00:00Z',
};

const samplePromotions: Promotions = {
  banners: [{ id: 'b1', business_id: null, kind: 'banner', title: 'Баннер', subtitle: null, badge: null, body: null, image_url: null, starts_at: null, ends_at: null, is_new: true }],
  offers: [{ id: 'o1', business_id: null, kind: 'offer', title: 'Акция', subtitle: null, badge: null, body: null, image_url: null, starts_at: null, ends_at: null, is_new: false }],
  has_new: true,
};

function mountWith(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={query}>
      <I18nProvider initial={language}>
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}

function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}

describe('Server content and offline cache', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await clearAppCache();
  });

  describe('Status screen balance delay note', () => {
    it('shows balance_delay_note from server when provided', async () => {
      serve({
        '/me/cards': [card],
        '/me/badges': { promotions_new: false, notifications_unread: 0 },
        '/me/app-content': sampleContent,
      });

      const screen = mountWith(<StatusScreen />);
      await waitFor(() => expect(screen.getByText('Серверный текст задержки')).toBeTruthy());
      screen.unmount();
    });

    it('shows balance_delay_note in Kazakh when language is kz', async () => {
      serve({
        '/me/cards': [card],
        '/me/badges': { promotions_new: false, notifications_unread: 0 },
        '/me/app-content': sampleContent,
      });

      const screen = mountWith(<StatusScreen />, 'kz');
      await waitFor(() => expect(screen.getByText('Кідіріс туралы серверлік мәтін')).toBeTruthy());
      screen.unmount();
    });

    it('falls back to built-in balanceDelayNote when server text is null or empty', async () => {
      const emptyNoteContent: AppContent = {
        ...sampleContent,
        app_texts: { home_store_note_lead: null, balance_delay_note: null },
      };
      serve({
        '/me/cards': [card],
        '/me/badges': { promotions_new: false, notifications_unread: 0 },
        '/me/app-content': emptyNoteContent,
      });

      const screen = mountWith(<StatusScreen />);
      await waitFor(() => expect(screen.getByText(ru.balanceDelayNote)).toBeTruthy());
      screen.unmount();
    });
  });

  describe('ETag, 304 and 404 handling', () => {
    it('sends If-None-Match when cached ETag exists and returns cached data on 304', async () => {
      const mockRequestWithMeta = jest.fn();
      const mockApi = {
        request: jest.fn(),
        requestWithMeta: mockRequestWithMeta,
      } as unknown as ApiClient;

      // 1. Initial 200 response with ETag
      mockRequestWithMeta.mockResolvedValueOnce({
        data: sampleContent,
        status: 200,
        etag: '"etag-123"',
      });

      const initial = await fetchAppContentWithCache(mockApi, 'user-1', 'b-1');
      expect(initial).toEqual(sampleContent);
      expect(getCachedAppContent('user-1', 'b-1')?.etag).toBe('"etag-123"');

      // 2. Subsequent request: sends If-None-Match
      mockRequestWithMeta.mockResolvedValueOnce({
        data: null,
        status: 304,
        etag: '"etag-123"',
      });

      const conditional = await fetchAppContentWithCache(mockApi, 'user-1', 'b-1');
      expect(mockRequestWithMeta).toHaveBeenLastCalledWith(
        '/me/app-content?business_id=b-1',
        expect.objectContaining({ headers: { 'If-None-Match': '"etag-123"' } }),
      );
      expect(conditional).toEqual(sampleContent);
    });

    it('returns null on 404 CUSTOMER_RESOURCE_NOT_FOUND without throwing', async () => {
      const mockRequestWithMeta = jest.fn().mockRejectedValue(
        new ApiError('CUSTOMER_RESOURCE_NOT_FOUND', 404),
      );
      const mockApi = {
        request: jest.fn(),
        requestWithMeta: mockRequestWithMeta,
      } as unknown as ApiClient;

      const result = await fetchAppContentWithCache(mockApi, 'user-1', 'other-biz');
      expect(result).toBeNull();
    });
  });

  describe('Offline fallback from storage cache', () => {
    it('returns cached app-content when network fails', async () => {
      setCachedAppContent('user-1', 'b-1', sampleContent, '"etag-1"');

      const mockRequestWithMeta = jest.fn().mockRejectedValue(new ApiError('NETWORK_UNAVAILABLE'));
      const mockApi = {
        request: jest.fn(),
        requestWithMeta: mockRequestWithMeta,
      } as unknown as ApiClient;

      const result = await fetchAppContentWithCache(mockApi, 'user-1', 'b-1');
      expect(result).toEqual(sampleContent);
    });

    it('returns cached promotions when network fails', async () => {
      setCachedPromotions('user-1', samplePromotions, '"etag-p"');

      const mockRequestWithMeta = jest.fn().mockRejectedValue(new ApiError('NETWORK_UNAVAILABLE'));
      const mockApi = {
        request: jest.fn(),
        requestWithMeta: mockRequestWithMeta,
      } as unknown as ApiClient;

      const result = await fetchPromotionsWithCache(mockApi, 'user-1');
      expect(result).toEqual(samplePromotions);
    });
  });

  describe('Logout clears cache', () => {
    it('clearAppCache purges all cached entries from memory and storage', async () => {
      setCachedAppContent('user-1', 'b-1', sampleContent, '"etag-1"');
      setCachedPromotions('user-1', samplePromotions, '"etag-p"');

      expect(getCachedAppContent('user-1', 'b-1')).not.toBeNull();
      expect(getCachedPromotions('user-1')).not.toBeNull();

      await clearAppCache();

      expect(getCachedAppContent('user-1', 'b-1')).toBeNull();
      expect(getCachedPromotions('user-1')).toBeNull();
    });
  });

  describe('Cold start and concurrency race safety', () => {
    it('returns cached app-content and promotions from AsyncStorage on cold start when network fails', async () => {
      const contentEntry = { data: sampleContent, etag: '"etag-cold-1"', cachedAt: Date.now() };
      const promoEntry = { data: samplePromotions, etag: '"etag-cold-p"', cachedAt: Date.now() };

      await AsyncStorage.setItem('cashback-one.cache.v1:user:cold-user:business:b-1:app-content', JSON.stringify(contentEntry));
      await AsyncStorage.setItem('cashback-one.cache.v1:user:cold-user:promotions', JSON.stringify(promoEntry));

      let isolatedFetchAppContent!: typeof fetchAppContentWithCache;
      let isolatedFetchPromotions!: typeof fetchPromotionsWithCache;
      let isolatedGetCachedContent!: typeof getCachedAppContent;
      let isolatedGetCachedPromos!: typeof getCachedPromotions;

      jest.isolateModules(() => {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const cacheMod = require('../src/storage/appCache');
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const appMod = require('../src/api/app');
        isolatedFetchAppContent = appMod.fetchAppContentWithCache;
        isolatedFetchPromotions = appMod.fetchPromotionsWithCache;
        isolatedGetCachedContent = cacheMod.getCachedAppContent;
        isolatedGetCachedPromos = cacheMod.getCachedPromotions;
      });

      const mockApi = {
        request: jest.fn().mockRejectedValue(new ApiError('NETWORK_UNAVAILABLE')),
        requestWithMeta: jest.fn().mockRejectedValue(new ApiError('NETWORK_UNAVAILABLE')),
      } as unknown as ApiClient;

      const content = await isolatedFetchAppContent(mockApi, 'cold-user', 'b-1');
      const promotions = await isolatedFetchPromotions(mockApi, 'cold-user');

      expect(content).toEqual(sampleContent);
      expect(promotions).toEqual(samplePromotions);
      expect(isolatedGetCachedContent('cold-user', 'b-1')?.data).toEqual(sampleContent);
      expect(isolatedGetCachedPromos('cold-user')?.data).toEqual(samplePromotions);
    });

    it('sends If-None-Match from AsyncStorage on cold start and returns cached response on 304', async () => {
      const contentEntry = { data: sampleContent, etag: '"etag-cold-304"', cachedAt: Date.now() };
      const promoEntry = { data: samplePromotions, etag: '"etag-promo-304"', cachedAt: Date.now() };

      await AsyncStorage.setItem('cashback-one.cache.v1:user:cold-304-user:business:b-1:app-content', JSON.stringify(contentEntry));
      await AsyncStorage.setItem('cashback-one.cache.v1:user:cold-304-user:promotions', JSON.stringify(promoEntry));

      let isolatedFetchAppContent!: typeof fetchAppContentWithCache;
      let isolatedFetchPromotions!: typeof fetchPromotionsWithCache;

      jest.isolateModules(() => {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const appMod = require('../src/api/app');
        isolatedFetchAppContent = appMod.fetchAppContentWithCache;
        isolatedFetchPromotions = appMod.fetchPromotionsWithCache;
      });

      const mockRequestWithMeta = jest.fn().mockImplementation((url: string, init?: { headers?: Record<string, string> }) => {
        if (url.includes('/me/app-content')) {
          expect(init?.headers?.['If-None-Match']).toBe('"etag-cold-304"');
          return Promise.resolve({ status: 304, data: null, etag: '"etag-cold-304"' });
        }
        if (url.includes('/me/promotions')) {
          expect(init?.headers?.['If-None-Match']).toBe('"etag-promo-304"');
          return Promise.resolve({ status: 304, data: null, etag: '"etag-promo-304"' });
        }
        return Promise.reject(new Error(`unexpected url: ${url}`));
      });

      const mockApi = {
        request: jest.fn(),
        requestWithMeta: mockRequestWithMeta,
      } as unknown as ApiClient;

      const content = await isolatedFetchAppContent(mockApi, 'cold-304-user', 'b-1');
      const promotions = await isolatedFetchPromotions(mockApi, 'cold-304-user');

      expect(content).toEqual(sampleContent);
      expect(promotions).toEqual(samplePromotions);
    });

    it('clearAppCache during pending initAppCache leaves memoryCache empty after completion', async () => {
      const contentEntry = { data: sampleContent, etag: '"etag-race"', cachedAt: Date.now() };
      await AsyncStorage.setItem('cashback-one.cache.v1:user:race-user:business:b-1:app-content', JSON.stringify(contentEntry));

      let resolveGate!: () => void;
      const gate = new Promise<void>(resolve => {
        resolveGate = resolve;
      });

      const origMultiGet = AsyncStorage.multiGet;
      const multiGetSpy = jest.spyOn(AsyncStorage, 'multiGet').mockImplementation(async (keys: readonly string[]) => {
        await gate;
        return origMultiGet(keys);
      });

      let isolatedCacheMod!: typeof import('../src/storage/appCache');
      jest.isolateModules(() => {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        isolatedCacheMod = require('../src/storage/appCache');
      });

      // initAppCache is in-flight waiting inside multiGet
      const initP = isolatedCacheMod.initAppCache();

      // Trigger clearAppCache concurrently
      const clearP = isolatedCacheMod.clearAppCache();

      // Release gate so multiGet can finish
      resolveGate();

      await Promise.all([initP, clearP]);

      expect(isolatedCacheMod.getCachedAppContent('race-user', 'b-1')).toBeNull();
      expect(isolatedCacheMod.getCachedPromotions('race-user')).toBeNull();

      multiGetSpy.mockRestore();
    });
  });
});
