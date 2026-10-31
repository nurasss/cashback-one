import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Image, Text } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import { ActiveCardProvider } from '../src/features/activeCard';
import { getCarouselAutoplaySlot, getCarouselLogicalIndex, getLoopSlides, PermanentOffersGrid } from '../src/features/home';
import { LOCAL_BANNERS, PERMANENT_OFFERS } from '../src/features/promotionsArtwork';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Card, Profile, Promotion } from '../src/types/api';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));

const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const tier = { level: 1, name: 'Base', percent: '3', max_percent: '12', spend_total: '150000.0000', next_level: 2, next_threshold: '500000.0000', remaining: '350000.0000' };
const card: Card = { id: 'card-1', barcode: '0123456789012', balance: '1250.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b-1', name: 'Supermarket', branding: null }, tier };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: 'Иван', last_name: 'Иванов', email: null, gender: null, city: 'Алматы', address: null, birth_date: null, iin: null, company: null };
const serverBanner: Promotion = { id: 'banner-server-1', business_id: null, kind: 'banner', title: 'Большой розыгрыш', subtitle: 'Участвуйте во всех супермаркетах сети', badge: null, body: 'Подробные условия акции', image_url: 'https://example.com/banner.png', starts_at: null, ends_at: null, is_new: true };

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

describe('Home artwork and permanent promotions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders exactly four permanent offer cards in the grid in correct order', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('permanent-offers-grid')).toBeTruthy());

    // Exactly four cards present by their unique testIDs
    const cardHits = screen.getByTestId('permanent-card-hits-discount');
    const cardWeekly = screen.getByTestId('permanent-card-weekly-promo');
    const cardBonus = screen.getByTestId('permanent-card-card-bonus');
    const cardFresh = screen.getByTestId('permanent-card-fresh-products');

    expect(cardHits.props.accessibilityLabel).toBe(ru.offerHitsDiscount);
    expect(cardWeekly.props.accessibilityLabel).toBe(ru.offerWeeklyPromo);
    expect(cardBonus.props.accessibilityLabel).toBe(ru.offerCardBonus);
    expect(cardFresh.props.accessibilityLabel).toBe(ru.offerFreshProducts);

    screen.unmount();
  });

  it('permanent offer cards remain visible while promotions API is loading or in error state', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.startsWith('/me/cards')) return Promise.resolve([card]);
      if (path.startsWith('/me/profile')) return Promise.resolve(profile);
      if (path.startsWith('/me/promotions')) return Promise.reject(new Error('Network error'));
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.hotOffers)).toBeTruthy());

    // Grid remains intact with all four cards
    expect(screen.getByTestId('permanent-card-hits-discount')).toBeTruthy();
    expect(screen.getByTestId('permanent-card-weekly-promo')).toBeTruthy();
    expect(screen.getByTestId('permanent-card-card-bonus')).toBeTruthy();
    expect(screen.getByTestId('permanent-card-fresh-products')).toBeTruthy();

    // No error notice is shown in the offers section
    expect(screen.queryByText(ru.noOffers)).toBeNull();
    screen.unmount();
  });

  it('permanent cards have the correct order, keys, and navigate to /promotions', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
    });

    expect(PERMANENT_OFFERS).toHaveLength(4);
    expect(PERMANENT_OFFERS[0]!.id).toBe('hits-discount');
    expect(PERMANENT_OFFERS[0]!.labelKey).toBe('offerHitsDiscount');
    expect(PERMANENT_OFFERS[1]!.id).toBe('weekly-promo');
    expect(PERMANENT_OFFERS[1]!.labelKey).toBe('offerWeeklyPromo');
    expect(PERMANENT_OFFERS[2]!.id).toBe('card-bonus');
    expect(PERMANENT_OFFERS[2]!.labelKey).toBe('offerCardBonus');
    expect(PERMANENT_OFFERS[3]!.id).toBe('fresh-products');
    expect(PERMANENT_OFFERS[3]!.labelKey).toBe('offerFreshProducts');

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.hotOffers)).toBeTruthy());

    // Press each card and verify navigation to /promotions
    fireEvent.press(screen.getByLabelText(ru.offerHitsDiscount));
    expect(mockPush).toHaveBeenLastCalledWith('/promotions');

    fireEvent.press(screen.getByLabelText(ru.offerWeeklyPromo));
    expect(mockPush).toHaveBeenLastCalledWith('/promotions');

    fireEvent.press(screen.getByLabelText(ru.offerCardBonus));
    expect(mockPush).toHaveBeenLastCalledWith('/promotions');

    fireEvent.press(screen.getByLabelText(ru.offerFreshProducts));
    expect(mockPush).toHaveBeenLastCalledWith('/promotions');

    // Button "Все" also navigates to /promotions
    fireEvent.press(screen.getByRole('button', { name: ru.all }));
    expect(mockPush).toHaveBeenLastCalledWith('/promotions');
    screen.unmount();
  });

  it('renders the three local banners in order when API banners is empty', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
    fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 180 } } });

    // The loop has a last-slide clone, three local slides, and a first-slide clone.
    expect(screen.getByTestId('banner-slide-0').props.accessibilityLabel).toBe(ru.bannerStickers);
    expect(screen.getByTestId('banner-slide-1').props.accessibilityLabel).toBe(ru.bannerCarPrize);
    expect(screen.getByTestId('banner-slide-2').props.accessibilityLabel).toBe(ru.bannerCoffeeMachine);
    expect(screen.getByTestId('banner-slide-3').props.accessibilityLabel).toBe(ru.bannerStickers);
    expect(screen.getByTestId('banner-slide-4').props.accessibilityLabel).toBe(ru.bannerCarPrize);
    expect(screen.queryByTestId('banner-slide-5')).toBeNull();
    expect(screen.getByTestId('banner-dot-0', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-1', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-2', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.queryByTestId('banner-dot-3', { includeHiddenElements: true })).toBeNull();
    expect(LOCAL_BANNERS.map(banner => banner.aspectRatio)).toEqual([675 / 294, 2000 / 862, 2000 / 860]);
    for (const slot of [1, 2, 3]) {
      expect(screen.getByTestId(`banner-slide-${slot}`).findByType(Image).props.resizeMode).toBe('contain');
    }

    // Clicking the local banner opens /promotions
    fireEvent.press(screen.getByTestId('banner-slide-1'));
    expect(mockPush).toHaveBeenCalledWith('/promotions');
    screen.unmount();
  });

  it('renders N+1 logical slides and dots when N server banners are provided, preserving order and accounting for loop clones', async () => {
    const bannerA: Promotion = {
      ...serverBanner,
      id: 'banner-a',
      title: 'Акция А',
      subtitle: 'Первая серверная акция',
    };
    const bannerB: Promotion = {
      ...serverBanner,
      id: 'banner-b',
      title: 'Акция Б',
      subtitle: 'Вторая серверная акция',
    };

    // Three local banners are followed by the two server banners.
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [bannerA, bannerB], offers: [], has_new: false },
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByTestId('banner-carousel')).toBeTruthy());
    fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 180 } } });

    await waitFor(() => expect(screen.getAllByLabelText(/Акция А/).length).toBeGreaterThan(0));

    // Five logical slides plus two loop clones.
    const slots = Array.from({ length: 7 }, (_, index) => screen.getByTestId(`banner-slide-${index}`));
    expect(screen.queryByTestId('banner-slide-7')).toBeNull();

    // Slot 0 is the clone of the final server slide.
    expect(slots[0]!.props.accessibilityLabel).toContain('Акция Б');
    expect(slots[1]!.props.accessibilityLabel).toBe(ru.bannerCarPrize);
    expect(slots[2]!.props.accessibilityLabel).toBe(ru.bannerCoffeeMachine);
    expect(slots[3]!.props.accessibilityLabel).toBe(ru.bannerStickers);
    expect(slots[4]!.props.accessibilityLabel).toContain('Акция А');
    expect(slots[5]!.props.accessibilityLabel).toContain('Акция Б');
    expect(slots[6]!.props.accessibilityLabel).toBe(ru.bannerCarPrize);

    // Check click on logical Local banner -> /promotions
    fireEvent.press(slots[1]!);
    expect(mockPush).toHaveBeenCalledWith('/promotions');

    // Check click on logical bannerA -> /promotion/banner-a
    fireEvent.press(slots[4]!);
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: 'banner-a' } });

    // Check click on logical bannerB -> /promotion/banner-b
    fireEvent.press(slots[5]!);
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: 'banner-b' } });

    // Exactly five dots, one per logical slide.
    expect(screen.getByTestId('banner-dot-0', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-1', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-2', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-3', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.getByTestId('banner-dot-4', { includeHiddenElements: true })).toBeTruthy();
    expect(screen.queryByTestId('banner-dot-5', { includeHiddenElements: true })).toBeNull();

    screen.unmount();
  });

  it('local items do not trigger an API call with dummy IDs', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': profile,
      '/me/promotions': { banners: [], offers: [], has_new: false },
    });

    const { screen } = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.hotOffers)).toBeTruthy());

    // Clicking local items
    fireEvent.press(screen.getByLabelText(ru.offerHitsDiscount));
    fireEvent.press(screen.getByLabelText(ru.offerWeeklyPromo));

    // Verify all mockRequest calls were to expected standard endpoints
    for (const call of mockRequest.mock.calls) {
      const path = String(call[0]);
      for (const banner of LOCAL_BANNERS) expect(path).not.toMatch(new RegExp(banner.id));
      expect(path).not.toMatch(/hits-discount|weekly-promo|card-bonus|fresh-products/);
    }
    screen.unmount();
  });

  it('ready artwork images do not have duplicate overlay text labels', () => {
    const onOpen = jest.fn();
    const screen = render(
      <I18nProvider initial="ru">
        <PermanentOffersGrid onOpenAll={onOpen} />
      </I18nProvider>
    );

    const grid = screen.getByTestId('permanent-offers-grid');
    // The grid should not contain duplicate overlay Text components inside the cards
    const textNodes = grid.findAllByType(Text);
    expect(textNodes).toHaveLength(0);
  });

  it('supports Kazakh accessibility labels when language is kz', async () => {
    serve({
      '/me/cards': [card],
      '/me/profile': { ...profile, language: 'kz' },
      '/me/promotions': { banners: [], offers: [], has_new: false },
    });

    const { screen } = mountWith(<Home />, 'kz');
    await waitFor(() => expect(screen.getByText(kz.hotOffers)).toBeTruthy());

    expect(screen.getByLabelText(kz.offerHitsDiscount)).toBeTruthy();
    expect(screen.getByLabelText(kz.offerWeeklyPromo)).toBeTruthy();
    expect(screen.getByLabelText(kz.offerCardBonus)).toBeTruthy();
    expect(screen.getByLabelText(kz.offerFreshProducts)).toBeTruthy();

    fireEvent(screen.getByTestId('banner-carousel'), 'layout', { nativeEvent: { layout: { width: 390, height: 180 } } });
    expect(screen.getAllByLabelText(kz.bannerCarPrize).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(kz.bannerCoffeeMachine).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(kz.bannerStickers).length).toBeGreaterThan(0);
    screen.unmount();
  });

  it('keeps carousel looping and autoplay targets valid with any slide count', () => {
    expect(getLoopSlides(['only'])).toEqual(['only']);
    for (const count of [3, 5, 8]) {
      const slides = Array.from({ length: count }, (_, index) => index);
      const loopSlides = getLoopSlides(slides);
      expect(loopSlides).toHaveLength(count + 2);
      expect(loopSlides[0]).toBe(count - 1);
      expect(loopSlides[count + 1]).toBe(0);
      expect(getCarouselAutoplaySlot(0, count)).toBe(2);
      expect(getCarouselLogicalIndex(getCarouselAutoplaySlot(count - 1, count), count)).toBe(0);
      expect(getCarouselLogicalIndex(0, count)).toBe(count - 1);
      expect(getCarouselLogicalIndex(count, count)).toBe(count - 1);
    }
  });
});
