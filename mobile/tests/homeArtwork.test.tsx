import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Linking } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import { ActiveCardProvider } from '../src/features/activeCard';
import { getCarouselAutoplaySlot, getCarouselLogicalIndex, getLoopSlides } from '../src/features/home';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import type { AppContent, Card, Profile, Promotion } from '../src/types/api';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));

const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'test-user' } }),
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const tier = { level: 1, name: 'Base', percent: '3', max_percent: '12', spend_total: '150000.0000', next_level: 2, next_threshold: '500000.0000', remaining: '350000.0000' };
const card: Card = { id: 'card-1', barcode: '0123456789012', balance: '1250.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b-1', name: 'Supermarket', branding: null }, tier };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: 'Иван', last_name: 'Иванов', email: null, gender: null, city: 'Алматы', address: null, birth_date: null, iin: null, company: null };
const serverBanner1: Promotion = { id: 'banner-server-1', business_id: null, kind: 'banner', title: 'Большой розыгрыш', subtitle: 'Участвуйте во всех супермаркетах сети', badge: null, body: 'Подробные условия акции', image_url: 'https://example.com/banner1.png', starts_at: null, ends_at: null, is_new: true };
const serverBanner2: Promotion = { id: 'banner-server-2', business_id: null, kind: 'banner', title: 'Кешбэк 15%', subtitle: 'На свежие фрукты', badge: null, body: 'Условия кешбэка', image_url: 'https://example.com/banner2.png', starts_at: null, ends_at: null, is_new: false };
const serverOffer1: Promotion = { id: 'offer-server-1', business_id: null, kind: 'offer', title: 'Скидки на выпечку', subtitle: null, badge: 'Выпечка', body: 'Свежая выпечка со скидкой', image_url: 'https://example.com/offer1.png', starts_at: null, ends_at: null, is_new: true };
const serverOffer2: Promotion = { id: 'offer-server-2', business_id: null, kind: 'offer', title: 'Молочные продукты', subtitle: null, badge: 'Молоко', body: 'Молоко со скидкой', image_url: 'https://example.com/offer2.png', starts_at: null, ends_at: null, is_new: false };

const sampleAppContent: AppContent = {
  business_id: 'b-1',
  stores: [
    { id: 's2', title_ru: 'Филиал 2', title_kk: '2-бөлімше', address_ru: 'ул. Абая, 20', address_kk: 'Абай к-сі, 20', map_url: null, sort_order: 2 },
    { id: 's1', title_ru: 'Филиал 1', title_kk: '1-бөлімше', address_ru: 'пр. Республики, 5', address_kk: 'Республика д-лы, 5', map_url: 'https://maps.example.com/s1', sort_order: 1 },
  ],
  app_texts: {
    home_store_note_lead: {
      ru: 'Баллы действуют в магазинах: ',
      kk: 'Ұпайлар мына дүкендерде жарамды: ',
    },
    balance_delay_note: {
      ru: 'Баллы начисляются после смены',
      kk: 'Ұпайлар ауысымнан кейін есептеледі',
    },
  },
  updated_at: '2026-11-04T12:00:00Z',
};

function mountWith(element: ReactElement, initialLanguage: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  const screen = render(
    <QueryClientProvider client={query}>
      <I18nProvider initial={initialLanguage}>
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
  return { screen, query };
}

function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}

describe('Home screen server content and artwork', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('hides the banner carousel when there are no banners', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [serverOffer1], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText('+7 705 834 43 26')).toBeTruthy());
    expect(screen.queryByTestId('banner-carousel')).toBeNull();
    screen.unmount();
  });

  it('renders server banners in the carousel and tapping opens /promotion/[id]', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [serverBanner1, serverBanner2], offers: [], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
    fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 200 } } });

    await waitFor(() => expect(screen.getAllByText('Большой', { exact: false }).length).toBeGreaterThan(0));
    fireEvent.press(screen.getAllByLabelText(new RegExp(serverBanner1.title, 'i'))[0]!);
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: serverBanner1.id } });
    screen.unmount();
  });

  it('hides the hot offers section when there are no offers', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [serverBanner1], offers: [], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText('+7 705 834 43 26')).toBeTruthy());
    expect(screen.queryByText(ru.hotOffers)).toBeNull();
    expect(screen.queryByTestId('server-offers-grid')).toBeNull();
    screen.unmount();
  });

  it('renders server offers grid and tapping opens /promotion/[id]', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [serverOffer1, serverOffer2], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.hotOffers)).toBeTruthy());
    expect(screen.getByTestId('server-offers-grid')).toBeTruthy();

    expect(screen.getByText(serverOffer1.title)).toBeTruthy();
    expect(screen.getByText(serverOffer2.title)).toBeTruthy();

    fireEvent.press(screen.getByText(serverOffer1.title));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: serverOffer1.id } });

    fireEvent.press(screen.getByText(ru.all));
    expect(mockPush).toHaveBeenCalledWith('/promotions');
    screen.unmount();
  });

  it('renders stores sorted by sort_order with map_url clickable and non-map plain', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('store-block')).toBeTruthy());

    expect(screen.getByText(sampleAppContent.app_texts.home_store_note_lead!.ru!, { exact: false })).toBeTruthy();
    // Sorted by sort_order: s1 (order 1: пр. Республики, 5) before s2 (order 2: ул. Абая, 20)
    const linkS1 = screen.getByTestId('store-link-s1');
    const textS2 = screen.getByTestId('store-text-s2');

    expect(linkS1).toBeTruthy();
    expect(textS2).toBeTruthy();

    fireEvent.press(linkS1);
    expect(openUrlSpy).toHaveBeenCalledWith('https://maps.example.com/s1');
    openUrlSpy.mockRestore();
    screen.unmount();
  });

  it('uses default lead text when server home_store_note_lead is null or empty', async () => {
    const noLeadAppContent: AppContent = {
      ...sampleAppContent,
      app_texts: { home_store_note_lead: null, balance_delay_note: null },
    };
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
      '/me/app-content': noLeadAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('store-block')).toBeTruthy());
    expect(screen.getByText(ru.storeNoteDefaultLead, { exact: false })).toBeTruthy();
    screen.unmount();
  });

  it('renders store lead and addresses in Kazakh when locale is kz', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': { ...profile, language: 'kz' },
      '/me/promotions': { banners: [], offers: [], has_new: false },
      '/me/app-content': sampleAppContent,
    });

    const { screen } = mountWith(<Home />, 'kz');
    await waitFor(() => expect(screen.getByTestId('store-block')).toBeTruthy());
    expect(screen.getByText(sampleAppContent.app_texts.home_store_note_lead!.kk!, { exact: false })).toBeTruthy();
    expect(screen.getByText('Республика д-лы, 5')).toBeTruthy();
    expect(screen.getByText('Абай к-сі, 20')).toBeTruthy();
    screen.unmount();
  });

  it('hides store block when stores array is empty', async () => {
    const emptyStoresAppContent: AppContent = {
      ...sampleAppContent,
      stores: [],
    };
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
      '/me/app-content': emptyStoresAppContent,
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText('+7 705 834 43 26')).toBeTruthy());
    expect(screen.queryByTestId('store-block')).toBeNull();
    screen.unmount();
  });

  it('carousel helper functions loop correctly', () => {
    expect(getLoopSlides([])).toEqual([]);
    expect(getLoopSlides(['a'])).toEqual(['a']);
    expect(getLoopSlides(['a', 'b', 'c'])).toEqual(['c', 'a', 'b', 'c', 'a']);

    expect(getCarouselAutoplaySlot(0, 3)).toBe(2);
    expect(getCarouselAutoplaySlot(1, 1)).toBe(0);

    expect(getCarouselLogicalIndex(0, 3)).toBe(2);
    expect(getCarouselLogicalIndex(1, 3)).toBe(0);
    expect(getCarouselLogicalIndex(2, 3)).toBe(1);
    expect(getCarouselLogicalIndex(3, 3)).toBe(2);
    expect(getCarouselLogicalIndex(4, 3)).toBe(0);
  });
});
