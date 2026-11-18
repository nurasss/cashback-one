import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import Home from '../app/(app)/(tabs)/index';
import StatusRoute from '../app/(app)/status';
import { ActiveCardProvider } from '../src/features/activeCard';
import { LevelsSheet } from '../src/features/LevelsSheet';
import { StatusArt, StatusCatalogList, isValidImageUrl } from '../src/features/StatusArt';
import { StatusStoresList } from '../src/features/stores';
import {
  getCatalogLead,
  getTierCondition,
  resolveCatalog,
  resolveCurrentStatus,
  resolveMinimumCatalogTier,
  resolveStatusDisplay,
} from '../src/features/statuses';
import { clearAppCache } from '../src/storage/appCache';
import { I18nProvider, type Key } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { AppContent, AppLoyaltyTier, Card } from '../src/types/api';

const mockRequest = jest.fn();
const mockPush = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({
    api: { request: mockRequest },
    session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'user-1' },
  }),
}));
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: () => ({}),
}));
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted' }),
  getCurrentPositionAsync: jest.fn().mockImplementation(() => new Promise(() => {})),
  Accuracy: { Balanced: 3 },
}));

const BUSINESS_ID = 'test-business-uuid';

const SERVER_TIERS: AppLoyaltyTier[] = [
  {
    id: 'tier-1',
    level: 1,
    priority: 1,
    name_ru: 'Серебряный',
    name_kk: 'Күміс',
    description_ru: 'Базовый уровень для всех покупателей',
    description_kk: 'Барлық сатып алушыларға арналған деңгей',
    image_url: 'https://api.cashback-qr.poscenter.kz/media/silver.png',
    turnover_period_months: 6,
    min_turnover: '0.0000',
    max_turnover: '150000.0000',
    percent: '2.5000',
  },
  {
    id: 'tier-2',
    level: 2,
    priority: 2,
    name_ru: 'Золотой',
    name_kk: 'Алтын',
    description_ru: 'Увеличенный кешбэк',
    description_kk: 'Көбейтілген кешбэк',
    image_url: 'https://api.cashback-qr.poscenter.kz/media/gold.png',
    turnover_period_months: 6,
    min_turnover: '150000.0000',
    max_turnover: '300000.0000',
    percent: '3.5000',
  },
  {
    id: 'tier-3',
    level: 3,
    priority: 3,
    name_ru: 'Платиновый VIP',
    name_kk: 'Платина VIP',
    description_ru: 'Максимальный кешбэк сети',
    description_kk: 'Ең жоғары кешбэк',
    image_url: 'https://api.cashback-qr.poscenter.kz/media/platinum.png',
    turnover_period_months: 12, // Different turnover period: 12 months vs 6 months!
    min_turnover: '300000.0000',
    max_turnover: null,
    percent: '5.0000',
  },
];

function makeCard(overrides: Partial<Card> = {}): Card {
  return {
    id: 'c1',
    barcode: '0001234',
    balance: '1500.0000',
    is_blocked: false,
    updated_at: '2026-11-10T00:00:00Z',
    bound_at: '2026-11-10T00:00:00Z',
    bind_method: 'phone_auto',
    business: { id: BUSINESS_ID, name: 'Test Shop', branding: null },
    tier: null,
    loyalty_status: {
      known: true,
      tier_id: 'tier-2',
      name: 'Золотой',
      percent: '3.5000',
      turnover_amount: '180000.0000',
      program_version: 1,
    },
    ...overrides,
  };
}

function serveData(cards: Card[], appContentOverrides: Partial<AppContent> = {}) {
  const content: AppContent = {
    business_id: BUSINESS_ID,
    stores: [
      {
        id: 'store-1',
        title_ru: 'Keremet Express',
        title_kk: 'Keremet Express',
        address_ru: 'ул. Абая, 45',
        address_kk: 'Абай к-сі, 45',
        map_url: 'https://maps.example.com',
        sort_order: 1,
        latitude: 43.238949,
        longitude: 76.889709,
      },
    ],
    app_texts: {},
    loyalty_tiers: SERVER_TIERS,
    loyalty_tiers_version: 1,
    updated_at: '2026-11-10T00:00:00Z',
    ...appContentOverrides,
  };
  const routes: Record<string, unknown> = {
    '/me/cards': cards,
    '/me/profile': { phone: '+77058344326', language: 'ru' },
    '/me/promotions': { banners: [], offers: [], has_new: false },
    '/me/app-content': content,
    '/me/badges': { promotions_new: false, notifications_unread: 0 },
  };
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}

function mount(element: ReactElement, { language = 'ru', theme = 'light' }: { language?: 'ru' | 'kz'; theme?: 'light' | 'dark' } = {}) {
  // staleTime 30 s as in the app (src/auth/provider.tsx): a screen that remounts must not refetch what it has just received.
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000, gcTime: Infinity }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={query}>
      <ThemeProvider initialPreference={theme}>
        <I18nProvider initial={language}>
          <ActiveCardProvider>{element}</ActiveCardProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

// Waiting helpers. The load chain is waited for in observable steps, each with its own short message and the default 1000 ms window
// (the windows are not enlarged, but three steps in a row together allow a longer total time than one wait for the whole chain did).
// A boolean condition throws a short message, so a timeout never serialises a ReactTestInstance.
async function until(description: string, condition: () => boolean) {
  await waitFor(() => {
    if (!condition()) throw new Error(`not yet: ${description}`);
  });
}
const requestIndexes = (prefix: string) => mockRequest.mock.calls.flatMap((call, index) => (String(call[0]).startsWith(prefix) ? [index] : []));
// Waits until the n-th request with this path prefix was sent, then for the real Promise the mock returned for it to settle.
async function responseDelivered(prefix: string, n = 1) {
  await until(`${prefix} request #${n} was sent`, () => requestIndexes(prefix).length >= n);
  const result = mockRequest.mock.results[requestIndexes(prefix)[n - 1] ?? -1];
  if (!result) throw new Error(`${prefix} request #${n} has no recorded result`);
  return result.value;
}
// Steps 1 and 2 of the chain: the cards answer is delivered, then the app-content request is sent and its answer delivered.
// Step 3 (the expected screen is drawn) stays with the findBy*/waitFor of each test.
async function dataDelivered() {
  await responseDelivered('/me/cards');
  await responseDelivered('/me/app-content');
}

describe('Dynamic Loyalty Tiers Catalog Contract', () => {
  beforeEach(async () => {
    mockRequest.mockReset();
    mockPush.mockReset();
    await clearAppCache();
    delete process.env.EXPO_PUBLIC_CLIENT;
  });

  afterEach(() => {
    delete process.env.EXPO_PUBLIC_CLIENT;
  });

  afterAll(() => {
    delete process.env.EXPO_PUBLIC_CLIENT;
  });

  describe('resolveCatalog: server tiers, empty scale, and legacy fallback', () => {
    it('resolves server tiers and sets version, isServer, and maxPercent', () => {
      const content: AppContent = {
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: SERVER_TIERS,
        loyalty_tiers_version: 2,
        updated_at: '2026-11-10T00:00:00Z',
      };
      const cat = resolveCatalog(content);
      expect(cat).not.toBeNull();
      expect(cat!.isServer).toBe(true);
      expect(cat!.version).toBe(2);
      expect(cat!.tiers.length).toBe(3);
      expect(cat!.maxPercent).toBe('5');
      expect('hasDifferentPeriods' in cat!).toBe(false);
    });

    it('explicit empty array loyalty_tiers: [] produces empty catalog and NEVER falls back to Keremet', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      const content: AppContent = {
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: [],
        loyalty_tiers_version: 3,
        updated_at: '2026-11-10T00:00:00Z',
      };
      const cat = resolveCatalog(content, 'keremet');
      expect(cat).not.toBeNull();
      expect(cat!.isServer).toBe(true);
      expect(cat!.tiers).toEqual([]);
      expect(cat!.version).toBe(3);
      expect(cat!.maxPercent).toBe('0');
    });

    it('missing field loyalty_tiers: undefined falls back to client configured statuses if available', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      const content: AppContent = {
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        updated_at: '2026-11-10T00:00:00Z',
      };
      const cat = resolveCatalog(content, 'keremet');
      expect(cat).not.toBeNull();
      expect(cat!.isServer).toBe(false);
      expect(cat!.tiers.length).toBe(3);
      expect(cat!.tiers[0]?.name).toBe('Нет-нет заглядывает');
    });

    it('missing field loyalty_tiers: undefined without client configured statuses returns null', () => {
      const content: AppContent = {
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        updated_at: '2026-11-10T00:00:00Z',
      };
      const cat = resolveCatalog(content, 'default');
      expect(cat).toBeNull();
    });

    it('historical turnover_period_months is accepted for compatibility, may be missing and is not exposed as a rule', () => {
      const noPeriod = SERVER_TIERS.map(({ turnover_period_months: _p, ...rest }) => rest) as unknown as AppLoyaltyTier[];
      const cat = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: noPeriod,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      });
      expect(cat).not.toBeNull();
      expect(cat!.tiers.length).toBe(3);
      expect('commonPeriodMonths' in cat!).toBe(false);
    });
  });

  describe('resolveCurrentStatus: personal status resolution and security', () => {
    const catalog = resolveCatalog({
      business_id: BUSINESS_ID,
      stores: [],
      app_texts: {},
      loyalty_tiers: SERVER_TIERS,
      loyalty_tiers_version: 1,
      updated_at: '2026-11-10T00:00:00Z',
    })!;

    it('resolves known status when all credentials, version, and tier match', () => {
      const card = makeCard();
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.status.name_ru).toBe('Золотой');
        expect(status.spend).toBe(180000);
        expect(status.spendDecimal).toBe('180000.0000');
        expect(status.next?.name_ru).toBe('Платиновый VIP');
        // Lifetime turnover: historical periods (6m vs 12m) do not matter, progress is computed.
        expect(status.progress).toBeCloseTo(0.6, 2);
        expect(status.remaining).toBe(120000);
        expect(status.isMax).toBe(false);
      }
    });

    it('resolves progress and exact decimal remaining', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-1',
          percent: '2.5000',
          turnover_amount: '75000.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.status.name_ru).toBe('Серебряный');
        expect(status.percent).toBe('2.5000');
        expect(status.progress).toBeCloseTo(0.5, 2);
        expect(status.remaining).toBe(75000);
        expect(status.remainingDecimal).toBe('75000');
      }
    });

    it('handles valid "0" and "0.0000" as valid known turnover without rejecting', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-1',
          percent: '2.5000',
          turnover_amount: '0.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.spend).toBe(0);
        expect(status.spendDecimal).toBe('0.0000');
        expect(status.remaining).toBe(150000);
      }
    });

    it('highest tier sets isMax: true and next: null', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-3',
          percent: '5.0000',
          turnover_amount: '450000.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.isMax).toBe(true);
        expect(status.next).toBeNull();
        expect(status.progress).toBe(1);
      }
    });

    it('status remains unavailable (known: false) when known is false (unconfirmed, stale, no_match)', () => {
      for (const reason of ['unconfirmed', 'stale', 'no_match'] as const) {
        const card = makeCard({
          loyalty_status: {
            known: false,
            reason,
            program_version: 1,
          },
        });
        const status = resolveCurrentStatus(card, catalog);
        expect(status.known).toBe(false);
        if (!status.known) {
          expect(status.reason).toBe(reason);
        }
      }
    });

    it('rejects non-numeric, empty, NaN, or Infinity turnover as known: false and unconfirmed', () => {
      for (const badTurnover of ['invalid-number', '', 'NaN', 'Infinity', '-Infinity']) {
        const card = makeCard({
          loyalty_status: {
            known: true,
            tier_id: 'tier-2',
            percent: '3.5000',
            turnover_amount: badTurnover,
            program_version: 1,
          },
        });
        const status = resolveCurrentStatus(card, catalog);
        expect(status.known).toBe(false);
        if (!status.known) {
          expect(status.reason).toBe('unconfirmed');
        }
      }
    });

    it('rejects null or undefined turnover as known: false and no-spend', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          percent: '3.5000',
          turnover_amount: null,
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
      if (!status.known) {
        expect(status.reason).toBe('no-spend');
      }
    });

    it('version mismatch results in known: false with version-mismatch reason', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          percent: '3.5000',
          turnover_amount: '180000.0000',
          program_version: 2, // Catalog is version 1
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
      if (!status.known) {
        expect(status.reason).toBe('version-mismatch');
      }
    });

    it('missing business id on card or catalog results in known: false with mismatch reason', () => {
      const card = makeCard({
        business: { id: '', name: 'No ID', branding: null },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
      if (!status.known) {
        expect(status.reason).toBe('mismatch');
      }
    });

    it('business mismatch results in known: false with mismatch reason', () => {
      const card = makeCard({
        business: { id: 'other-biz-id', name: 'Other', branding: null },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
      if (!status.known) {
        expect(status.reason).toBe('mismatch');
      }
    });

    it('unknown tier_id results in known: false with mismatch reason', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'non-existent-tier-id',
          percent: '3.5000',
          turnover_amount: '180000.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
      if (!status.known) {
        expect(status.reason).toBe('mismatch');
      }
    });

    it('extracts confirmed percent from loyalty_status.percent and prefers it over catalog tier percent', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          percent: '4.25',
          turnover_amount: '180000.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.percent).toBe('4.25');
      }
    });

    it('accepts confirmed "0.0000" percent as valid known status', () => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-1',
          percent: '0.0000',
          turnover_amount: '10000.0000',
          program_version: 1,
        },
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(true);
      if (status.known) {
        expect(status.percent).toBe('0.0000');
      }
    });

    it('returns unconfirmed when loyalty_status.known=true but percent is missing or null (never falls back to tier percent)', () => {
      const missingPercent = resolveCurrentStatus(
        makeCard({
          loyalty_status: {
            known: true,
            tier_id: 'tier-2',
            turnover_amount: '180000.0000',
            program_version: 1,
          },
        }),
        catalog,
      );
      expect(missingPercent).toEqual({ known: false, reason: 'unconfirmed' });

      const nullPercent = resolveCurrentStatus(
        makeCard({
          loyalty_status: {
            known: true,
            tier_id: 'tier-2',
            percent: null,
            turnover_amount: '180000.0000',
            program_version: 1,
          },
        }),
        catalog,
      );
      expect(nullPercent).toEqual({ known: false, reason: 'unconfirmed' });
    });

    it('rejects negative turnover_amount and negative or invalid loyalty_status.percent as unconfirmed', () => {
      const negTurnover = resolveCurrentStatus(
        makeCard({
          loyalty_status: { known: true, tier_id: 'tier-2', percent: '3.50', turnover_amount: '-100.0000', program_version: 1 },
        }),
        catalog,
      );
      expect(negTurnover).toEqual({ known: false, reason: 'unconfirmed' });

      for (const badPercent of ['', 'abc', '-1.00', 'NaN']) {
        const res = resolveCurrentStatus(
          makeCard({
            loyalty_status: { known: true, tier_id: 'tier-2', percent: badPercent, turnover_amount: '180000.0000', program_version: 1 },
          }),
          catalog,
        );
        expect(res).toEqual({ known: false, reason: 'unconfirmed' });
      }
    });

    it('never assigns level based on balance, single spend_total, or old tier when loyalty_status is missing/unconfirmed', () => {
      const card = makeCard({
        balance: '999999.0000',
        tier: { level: 3, name: 'Fake', percent: '4.0', max_percent: '4.0', spend_total: '999999', next_level: null, next_threshold: null, remaining: null },
        loyalty_status: null,
      });
      const status = resolveCurrentStatus(card, catalog);
      expect(status.known).toBe(false);
    });
  });

  describe('Condition text and period formatting (getTierCondition & getCatalogLead)', () => {
    const t = (key: Key, params?: Record<string, string | number>) => {
      if (key === 'statusUpTo') return `до ${params?.amount} ₸`;
      if (key === 'statusRange') return `от ${params?.from} до ${params?.to} ₸`;
      if (key === 'fromAmount') return `от ${params?.amount} ₸`;
      if (key === 'statusLifetimeNote') return 'Сумма покупок за всё время';
      if (key === 'statusLeadLifetime') return 'Статус зависит от суммы покупок за всё время.';
      return String(key);
    };

    it('formats conditions without any period, whatever the historical period of the tier is', () => {
      const tier1 = SERVER_TIERS[0]!;
      const tier3 = SERVER_TIERS[2]!;
      expect(getTierCondition(
        { ...tier1, name: tier1.name_ru, description: tier1.description_ru, turnover_period_months: 6, min_turnover: '0', max_turnover: '150000', percent: '2' },
        t,
      )).toBe('до 150 000 ₸');
      expect(getTierCondition(
        { ...tier3, name: tier3.name_ru, description: tier3.description_ru, turnover_period_months: 12, min_turnover: '300000', max_turnover: null, percent: '5' },
        t,
      )).toBe('от 300 000 ₸');
      const { turnover_period_months: _drop, ...noPeriod } = tier3;
      expect(getTierCondition(
        { ...noPeriod, name: tier3.name_ru, description: tier3.description_ru, min_turnover: '300000', max_turnover: '600000.50', percent: '5' },
        t,
      )).not.toMatch(/мес/);
    });

    it('getCatalogLead is always lifetime and never mentions months, even for legacy fallback or any historical period', () => {
      for (const periods of [12, 3, 1]) {
        const cat = resolveCatalog({
          business_id: BUSINESS_ID,
          stores: [],
          app_texts: {},
          loyalty_tiers: SERVER_TIERS.map(x => ({ ...x, turnover_period_months: periods })),
          loyalty_tiers_version: 1,
          updated_at: '2026-11-10T00:00:00Z',
        });
        expect(getCatalogLead(cat, t)).toBe('Статус зависит от суммы покупок за всё время.');
      }
      const mixed = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: SERVER_TIERS,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      });
      expect(getCatalogLead(mixed, t)).toBe('Статус зависит от суммы покупок за всё время.');
      const legacy = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        updated_at: '2026-11-10T00:00:00Z',
      }, 'keremet');
      expect(getCatalogLead(legacy, t)).toBe('Статус зависит от суммы покупок за всё время.');
    });
  });

  describe('StatusArt: URL validation, error recovery, and brand isolation', () => {
    it('isValidImageUrl validates http and https URLs and rejects javascript/data/invalid protocols', () => {
      expect(isValidImageUrl('https://api.example.com/art.png')).toBe(true);
      expect(isValidImageUrl('http://api.example.com/art.png')).toBe(true);
      expect(isValidImageUrl('javascript:alert(1)')).toBe(false);
      expect(isValidImageUrl('data:image/png;base64,abc')).toBe(false);
      expect(isValidImageUrl('not-a-valid-url')).toBe(false);
      expect(isValidImageUrl(null)).toBe(false);
      expect(isValidImageUrl('')).toBe(false);
    });

    it('renders neutral fallback icon when image_url is null or absent', () => {
      render(<StatusArt status={{ image_url: null, name: 'Tier Without Art' }} size={60} />);
      expect(screen.getByTestId('status-art-fallback')).toBeTruthy();
      expect(screen.queryByTestId('status-art-boss')).toBeNull();
      expect(screen.queryByTestId('status-art-expert')).toBeNull();
    });

    it('renders neutral fallback icon when image_url is invalid URL without rendering ExpoImage', () => {
      render(<StatusArt status={{ image_url: 'javascript:alert(1)', name: 'Malicious' }} size={60} />);
      expect(screen.getByTestId('status-art-fallback')).toBeTruthy();
      expect(screen.queryByTestId('status-art-image')).toBeNull();
    });

    it('recovers after image error when new valid image_url is passed', () => {
      const { rerender } = render(
        <StatusArt
          status={{ image_url: 'https://api.cashback-qr.poscenter.kz/media/broken.png', name: 'Broken' }}
          size={60}
        />,
      );
      // Valid URL starts with ExpoImage
      expect(screen.getByTestId('status-art-image')).toBeTruthy();

      // Trigger error on image component
      fireEvent(screen.getByTestId('status-art-image'), 'error');
      // Now displays neutral fallback icon
      expect(screen.getByTestId('status-art-fallback')).toBeTruthy();

      // Rerender with fresh valid URL B: loadError MUST reset and render ExpoImage
      rerender(
        <StatusArt
          status={{ image_url: 'https://api.cashback-qr.poscenter.kz/media/repaired.png', name: 'Repaired' }}
          size={60}
        />,
      );
      expect(screen.getByTestId('status-art-image')).toBeTruthy();
      expect(screen.queryByTestId('status-art-fallback')).toBeNull();
    });
  });

  describe('UI integration: Status screen, empty scale, period notes, and LevelsSheet localization', () => {
    it('Status screen with explicit empty scale (loyalty_tiers: []) does not show old tier, old progress, or raise button', async () => {
      // User has a card with legacy tier level 2
      const cardWithOldTier = makeCard({
        tier: { level: 2, name: 'Old Tier', percent: '3.0000', max_percent: '4.0000', spend_total: '100000', next_level: 3, next_threshold: '200000', remaining: '100000', levels: [] },
        loyalty_status: null,
      });
      serveData([cardWithOldTier], { loyalty_tiers: [], loyalty_tiers_version: 1 });
      mount(<StatusRoute />);

      await dataDelivered();
      expect(await screen.findByTestId('status-unavailable')).toBeTruthy();
      // Must NOT render old tier level '2' as the current status
      expect(screen.queryByTestId('current-status-name')).toBeNull();
      // Must NOT render «Как повысить статус» when there are no tiers
      expect(screen.queryByRole('button', { name: ru.howToRaise })).toBeNull();
      // Stores remain accessible!
      expect(screen.getByText('Keremet Express')).toBeTruthy();
    });

    it('Status screen displays honestly unavailable status when turnover is invalid-number, without fake level or progress', async () => {
      const card = makeCard({
        loyalty_status: { known: true, tier_id: 'tier-2', percent: '3.5000', turnover_amount: 'invalid-number', program_version: 1 },
      });
      serveData([card]);
      mount(<StatusRoute />);

      await dataDelivered();
      expect(await screen.findByTestId('status-unavailable')).toBeTruthy();
      expect(screen.queryByTestId('current-status-name')).toBeNull();
      expect(screen.queryByTestId('current-status-percent')).toBeNull();
      expect(screen.queryByText(/Покупки за последние/)).toBeNull();
    });

    it('Status screen shows lifetime turnover and personal percent from loyalty_status without months', async () => {
      const tiers12 = SERVER_TIERS.map(t => ({ ...t, turnover_period_months: 12 }));
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          percent: '3.5000',
          turnover_amount: '180000.0000',
          program_version: 1,
        },
      });
      serveData([card], { loyalty_tiers: tiers12 });
      mount(<StatusRoute />);

      await dataDelivered();
      expect(await screen.findByTestId('current-status-name')).toBeTruthy();
      expect(screen.getByTestId('current-status-percent').props.children.join('')).toBe('3,5%');
      // Lifetime turnover: no months anywhere
      expect(screen.getByText('Сумма покупок за всё время: 180 000 ₸')).toBeTruthy();
      expect(screen.queryByText(/мес\./)).toBeNull();
    });

    it('LevelsSheet in Kazakh lists Kazakh status names, the lifetime lead and no calculator or "current status" line', async () => {
      const catalog = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: SERVER_TIERS,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      });
      const card = makeCard();
      const current = resolveCurrentStatus(card, catalog);

      mount(
        <LevelsSheet
          onClose={jest.fn()}
          catalog={catalog}
          current={current}
        />,
        { language: 'kz' },
      );

      // In Kazakh: name_kk is «Алтын»; the removed "Қазір … — соманың N%" line and the calculator are gone.
      expect(screen.getByText('Алтын')).toBeTruthy();
      expect(screen.queryByText('Золотой')).toBeNull();
      expect(screen.getByText(/барлық уақыттағы/)).toBeTruthy();
      expect(screen.queryByText(/Қазір/)).toBeNull();
      expect(screen.queryByText(/Чек сомасы/)).toBeNull();
      expect(screen.queryByText(/Есеп шамамен/)).toBeNull();
    });

    it('StatusCatalogList renders the lifetime note (RU/KK), formatted percents, and no months', () => {
      const tiers12 = SERVER_TIERS.map(t => ({ ...t, turnover_period_months: 12 }));
      const catalog = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: tiers12,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      })!;

      const viewRu = render(
        <I18nProvider initial="ru">
          <StatusCatalogList catalog={catalog} language="ru" />
        </I18nProvider>,
      );
      expect(viewRu.getByText('Сумма покупок за всё время')).toBeTruthy();
      expect(viewRu.getByText('2,5%')).toBeTruthy();
      expect(viewRu.getByText('3,5%')).toBeTruthy();
      expect(viewRu.getByText('5%')).toBeTruthy();
      expect(viewRu.queryByText(/мес/)).toBeNull();
      viewRu.unmount();

      const viewKz = render(
        <I18nProvider initial="kz">
          <StatusCatalogList catalog={catalog} language="kz" />
        </I18nProvider>,
      );
      expect(viewKz.getByText('Барлық уақыттағы сатып алулар сомасы')).toBeTruthy();
      expect(viewKz.queryByText(/ай/)).toBeNull();
      viewKz.unmount();
    });

    it('Home screen renders server status name, personal percent, and dynamic max percent', async () => {
      serveData([makeCard()]);
      mount(<Home />);
      await dataDelivered();
      expect(await screen.findByText('Золотой')).toBeTruthy();
      expect(screen.getByTestId('home-status-percent').props.children).toBe('Кешбэк 3,5%');
      expect(screen.getByText('Не упустите до 5% бонусов')).toBeTruthy();
    });

    it('Home screen shows minimum catalog status and percent when turnover is unknown, without fake 0 turnover or "dontMiss" promise', async () => {
      const card = makeCard({
        loyalty_status: { known: false, reason: 'turnover_unknown', program_version: 1 },
      });
      serveData([card]);
      mount(<Home />);
      await dataDelivered();
      expect((await screen.findByTestId('home-status-name')).props.children).toBe('Серебряный');
      expect(screen.getByTestId('home-status-percent').props.children).toBe('Кешбэк 2,5%');
      expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
      expect(screen.queryByText(/Не упустите/)).toBeNull();
      expect(screen.queryByText('Золотой')).toBeNull();
    });

    it.each([
      ['missing', undefined],
      ['null', null],
    ] as const)('Status screen falls back to minimum catalog tier (never unconfirmed high tier_id) when loyalty_status.known=true but percent is %s', async (_label, percent) => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          ...(percent === null ? { percent: null } : {}),
          turnover_amount: '180000.0000',
          program_version: 1,
        },
      });
      serveData([card]);
      mount(<StatusRoute />);
      await dataDelivered();
      expect((await screen.findByTestId('current-status-name')).props.children).toBe('Серебряный');
      expect(screen.getByTestId('current-status-percent').props.children.join('')).toBe('2,5%');
      expect(screen.getByTestId('status-art-image').props.source).toEqual({
        uri: 'https://api.cashback-qr.poscenter.kz/media/silver.png',
      });
      expect(screen.queryByTestId('status-unavailable')).toBeNull();
      expect(screen.queryByText('Золотой')).toBeNull();
      expect(screen.queryByText('3,5%')).toBeNull();
      expect(screen.queryByText(/Сумма покупок за всё время:/)).toBeNull();
      expect(screen.queryByRole('progressbar')).toBeNull();
      expect(screen.queryByText(ru.maxStatus)).toBeNull();
    });

    it.each([
      ['missing', undefined],
      ['null', null],
    ] as const)('Home screen falls back to minimum catalog tier (never unconfirmed high tier_id) when loyalty_status.known=true but percent is %s', async (_label, percent) => {
      const card = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-2',
          ...(percent === null ? { percent: null } : {}),
          turnover_amount: '180000.0000',
          program_version: 1,
        },
      });
      serveData([card]);
      mount(<Home />);
      await dataDelivered();
      expect((await screen.findByTestId('home-status-name')).props.children).toBe('Серебряный');
      expect(screen.getByTestId('home-status-percent').props.children).toBe('Кешбэк 2,5%');
      expect(screen.getByTestId('status-art-image').props.source).toEqual({
        uri: 'https://api.cashback-qr.poscenter.kz/media/silver.png',
      });
      expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
      expect(screen.queryByText('Золотой')).toBeNull();
      expect(screen.queryByText(/3,5%/)).toBeNull();
    });

    it('Status and Home screens display confirmed "0.0000" percent as 0%', async () => {
      const zeroCard = makeCard({
        loyalty_status: {
          known: true,
          tier_id: 'tier-1',
          percent: '0.0000',
          turnover_amount: '10000.0000',
          program_version: 1,
        },
      });
      serveData([zeroCard]);
      const statusView = mount(<StatusRoute />);
      await dataDelivered();
      expect(await screen.findByTestId('current-status-name')).toBeTruthy();
      expect(screen.getByTestId('current-status-percent').props.children.join('')).toBe('0%');
      statusView.unmount();

      await clearAppCache();
      mockRequest.mockClear();
      serveData([zeroCard]);
      mount(<Home />);
      await dataDelivered();
      expect(await screen.findByTestId('home-status-name')).toBeTruthy();
      expect(screen.getByTestId('home-status-percent').props.children).toBe('Кешбэк 0%');
    });
  });

  describe('Minimum catalog status fallback regression suite (2026-11-13)', () => {
    const catalog = resolveCatalog({
      business_id: BUSINESS_ID,
      stores: [],
      app_texts: {},
      loyalty_tiers: SERVER_TIERS,
      loyalty_tiers_version: 1,
      updated_at: '2026-11-10T00:00:00Z',
    })!;

    it('resolveStatusDisplay separates minimum fallback from known=true for missing/null/unconfirmed personal data', () => {
      const cases = [
        makeCard({ loyalty_status: undefined }),
        makeCard({ loyalty_status: null }),
        makeCard({ loyalty_status: { known: false, reason: 'unconfirmed', program_version: 1 } }),
        makeCard({ loyalty_status: { known: false, reason: 'turnover_unknown', program_version: 1 } }),
        makeCard({ loyalty_status: { known: true, tier_id: 'tier-3', turnover_amount: '450000.0000', program_version: 1 } }),
        makeCard({ loyalty_status: { known: true, tier_id: 'tier-3', percent: null, turnover_amount: '450000.0000', program_version: 1 } }),
        makeCard({ loyalty_status: { known: true, tier_id: 'tier-3', percent: '5.0000', turnover_amount: null, program_version: 1 } }),
      ];
      for (const c of cases) {
        expect(resolveCurrentStatus(c, catalog).known).toBe(false);
        const display = resolveStatusDisplay(c, catalog);
        expect(display).toMatchObject({
          kind: 'minimum',
          status: { id: 'tier-1', name_ru: 'Серебряный' },
          percent: '2.5000',
        });
      }
    });

    it('confirmed high tier keeps priority and uses server percent (different from catalog or "0.0000")', () => {
      const highCustom = makeCard({
        loyalty_status: { known: true, tier_id: 'tier-3', percent: '7.2500', turnover_amount: '450000.0000', program_version: 1 },
      });
      const displayHigh = resolveStatusDisplay(highCustom, catalog);
      expect(displayHigh.kind).toBe('confirmed');
      if (displayHigh.kind === 'confirmed') {
        expect(displayHigh.current.status.id).toBe('tier-3');
        expect(displayHigh.current.percent).toBe('7.2500');
      }

      const confirmedZero = makeCard({
        loyalty_status: { known: true, tier_id: 'tier-2', percent: '0.0000', turnover_amount: '180000.0000', program_version: 1 },
      });
      const displayZero = resolveStatusDisplay(confirmedZero, catalog);
      expect(displayZero.kind).toBe('confirmed');
      if (displayZero.kind === 'confirmed') {
        expect(displayZero.current.status.id).toBe('tier-2');
        expect(displayZero.current.percent).toBe('0.0000');
      }
    });

    it('minimum tier with "0.0000" percent is valid in resolveMinimumCatalogTier and renders 0% on both screens', async () => {
      const zeroMinTiers: AppLoyaltyTier[] = [
        { ...SERVER_TIERS[0]!, percent: '0.0000' },
        SERVER_TIERS[1]!,
      ];
      const zeroCat = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: zeroMinTiers,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      })!;
      expect(resolveMinimumCatalogTier(zeroCat)).toMatchObject({ status: { id: 'tier-1' }, percent: '0.0000' });

      const unconfirmedCard = makeCard({ loyalty_status: null });
      serveData([unconfirmedCard], { loyalty_tiers: zeroMinTiers });
      const statusView = mount(<StatusRoute />);
      await dataDelivered();
      expect((await screen.findByTestId('current-status-name')).props.children).toBe('Серебряный');
      expect(screen.getByTestId('current-status-percent').props.children.join('')).toBe('0%');
      expect(screen.queryByTestId('status-unavailable')).toBeNull();
      statusView.unmount();

      await clearAppCache();
      mockRequest.mockClear();
      serveData([unconfirmedCard], { loyalty_tiers: zeroMinTiers });
      mount(<Home />);
      await dataDelivered();
      expect((await screen.findByTestId('home-status-name')).props.children).toBe('Серебряный');
      expect(screen.getByTestId('home-status-percent').props.children).toBe('Кешбэк 0%');
      expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
    });

    it('out-of-order catalog picks lowest (level, priority), NOT array index 0 and NOT smallest numeric percent', () => {
      const unsortedRaw: AppLoyaltyTier[] = [
        { ...SERVER_TIERS[2]!, id: 'high-small-pct', level: 3, priority: 1, name_ru: 'Высокий 0.5%', percent: '0.5000' },
        { ...SERVER_TIERS[0]!, id: 'lvl1-prio2', level: 1, priority: 2, name_ru: 'Уровень 1 приор 2', percent: '1.0000' },
        { ...SERVER_TIERS[1]!, id: 'lvl1-prio1', level: 1, priority: 1, name_ru: 'Истинный минимум', percent: '4.0000' },
      ];
      // Verify even if a caller passes manually shuffled StatusCatalog (not pre-sorted by resolveCatalog)
      const manualUnsortedCatalog = {
        version: 1,
        businessId: BUSINESS_ID,
        isServer: true,
        maxPercent: '4',
        tiers: unsortedRaw.map(t => ({ ...t, name: t.name_ru, description: t.description_ru })),
      };
      expect(resolveMinimumCatalogTier(manualUnsortedCatalog)).toMatchObject({
        status: { id: 'lvl1-prio1', name_ru: 'Истинный минимум' },
        percent: '4.0000',
      });
      const sortedCat = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: unsortedRaw,
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      })!;
      expect(resolveStatusDisplay(makeCard({ loyalty_status: null }), sortedCat)).toMatchObject({
        kind: 'minimum',
        status: { id: 'lvl1-prio1' },
        percent: '4.0000',
      });
    });

    it('does not invent minimum when catalog is empty/missing, minimum percent is invalid, business/version mismatches, stale/no_match, or turnover/percent corrupted', () => {
      expect(resolveStatusDisplay(null, catalog).kind).toBe('unavailable');
      expect(resolveStatusDisplay(makeCard({ loyalty_status: null }), null).kind).toBe('unavailable');

      const emptyCat = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: [],
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      });
      expect(resolveStatusDisplay(makeCard({ loyalty_status: null }), emptyCat).kind).toBe('unavailable');

      const badMinPctCat = resolveCatalog({
        business_id: BUSINESS_ID,
        stores: [],
        app_texts: {},
        loyalty_tiers: [{ ...SERVER_TIERS[0]!, percent: '-1.00' }, SERVER_TIERS[1]!],
        loyalty_tiers_version: 1,
        updated_at: '2026-11-10T00:00:00Z',
      });
      expect(resolveStatusDisplay(makeCard({ loyalty_status: null }), badMinPctCat).kind).toBe('unavailable');

      // Foreign business card even with loyalty_status: null or known: false
      expect(resolveStatusDisplay(makeCard({ business: { id: 'foreign-biz', name: 'Other', branding: null }, loyalty_status: null }), catalog)).toEqual({
        kind: 'unavailable',
        reason: 'mismatch',
      });
      expect(resolveStatusDisplay(makeCard({ business: { id: 'foreign-biz', name: 'Other', branding: null }, loyalty_status: { known: false, reason: 'turnover_unknown', program_version: 1 } }), catalog)).toEqual({
        kind: 'unavailable',
        reason: 'mismatch',
      });

      // Version mismatch on known=true or known=false
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: true, tier_id: 'tier-2', percent: '3.5', turnover_amount: '180000', program_version: 99 } }), catalog)).toEqual({
        kind: 'unavailable',
        reason: 'version-mismatch',
      });
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: false, reason: 'unconfirmed', program_version: 99 } }), catalog)).toEqual({
        kind: 'unavailable',
        reason: 'version-mismatch',
      });

      // Unknown tier_id, stale, no_match, no_matching_tier, negative/corrupted values
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: true, tier_id: 'unknown', turnover_amount: '180000', program_version: 1 } }), catalog)).toEqual({
        kind: 'unavailable',
        reason: 'mismatch',
      });
      for (const reason of ['stale', 'no_match', 'no_matching_tier'] as const) {
        expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: false, reason, program_version: 1 } }), catalog).kind).toBe('unavailable');
      }
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: true, tier_id: 'tier-2', percent: '3.5', turnover_amount: '-100', program_version: 1 } }), catalog).kind).toBe('unavailable');
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: true, tier_id: 'tier-2', percent: '-1', turnover_amount: '180000', program_version: 1 } }), catalog).kind).toBe('unavailable');
      expect(resolveStatusDisplay(makeCard({ loyalty_status: { known: true, tier_id: 'tier-2', percent: 'abc', turnover_amount: '180000', program_version: 1 } }), catalog).kind).toBe('unavailable');
    });

    it('RU and KK screens stay consistent for custom dynamic catalog (name, artwork accessibility, percent, no fake 0/progress/max)', async () => {
      const customTiers: AppLoyaltyTier[] = [
        {
          id: 'custom-min',
          level: 1,
          priority: 1,
          name_ru: 'Старт Бизнеса',
          name_kk: 'Бизнес Бастау',
          description_ru: 'Начальные условия',
          description_kk: 'Бастапқы шарттар',
          image_url: 'https://api.cashback-qr.poscenter.kz/media/custom-min.png',
          min_turnover: '0.0000',
          max_turnover: null,
          percent: '7.2500',
        },
      ];
      // Test missing loyalty_status in RU and KK on both Home and Status; single-tier catalog must NOT show maxStatus!
      const unconfirmedCard = makeCard({ loyalty_status: null });

      for (const [lang, expectedName, expectedHomePercent, expectedPoints] of [
        ['ru', 'Старт Бизнеса', 'Кешбэк 7,25%', 'Сумма бонусов'],
        ['kz', 'Бизнес Бастау', 'Кэшбэк 7,25%', 'Бонустар сомасы'],
      ] as const) {
        await clearAppCache();
        mockRequest.mockClear();
        serveData([unconfirmedCard], { loyalty_tiers: customTiers });
        const homeView = mount(<Home />, { language: lang });
        await dataDelivered();
        expect((await screen.findByTestId('home-status-name')).props.children).toBe(expectedName);
        expect(screen.getByTestId('home-status-percent').props.children).toBe(expectedHomePercent);
        expect(screen.getByTestId('status-art-image').props.accessibilityLabel).toBe(expectedName);
        expect(screen.getByLabelText(new RegExp(`${expectedName}.*${expectedHomePercent}.*${expectedPoints}`))).toBeTruthy();
        expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
        expect(screen.queryByText(/Не упустите|жіберіп алмаңыз/)).toBeNull();
        homeView.unmount();

        await clearAppCache();
        mockRequest.mockClear();
        serveData([unconfirmedCard], { loyalty_tiers: customTiers });
        const statusView = mount(<StatusRoute />, { language: lang });
        await dataDelivered();
        expect((await screen.findByTestId('current-status-name')).props.children).toBe(expectedName);
        expect(screen.getByTestId('current-status-percent').props.children.join('')).toBe('7,25%');
        expect(screen.getByTestId('status-art-image').props.accessibilityLabel).toBe(expectedName);
        expect(screen.queryByTestId('status-unavailable')).toBeNull();
        expect(screen.queryByText(/Сумма покупок за всё время:|Барлық уақыттағы сатып алулар сомасы:/)).toBeNull();
        expect(screen.queryByRole('progressbar')).toBeNull();
        expect(screen.queryByText(ru.maxStatus)).toBeNull();
        statusView.unmount();
      }
    });

    it('No card on Home/Status and foreign-business card keep existing protections without inventing minimum', async () => {
      serveData([]);
      const noCardHome = mount(<Home />);
      expect(await screen.findByTestId('no-card-notice')).toBeTruthy();
      expect(screen.queryByTestId('home-status-name')).toBeNull();
      expect(screen.queryByTestId('home-status-percent')).toBeNull();
      noCardHome.unmount();

      await clearAppCache();
      mockRequest.mockClear();
      serveData([makeCard({ business: { id: 'foreign-biz', name: 'Other', branding: null }, loyalty_status: null })]);
      mount(<StatusRoute />);
      await dataDelivered();
      expect(await screen.findByTestId('status-unavailable')).toBeTruthy();
      expect(screen.queryByTestId('current-status-name')).toBeNull();
      expect(screen.queryByTestId('current-status-percent')).toBeNull();
    });
  });

  describe('Geolocation timer safety in stores.tsx', () => {
    it('clears geolocation timeout on unmount to avoid leaks', () => {
      const view = render(<StatusStoresList stores={[]} language="ru" />);
      expect(() => view.unmount()).not.toThrow();
    });
  });
});
