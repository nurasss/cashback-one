import { fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { StyleSheet } from 'react-native';
import PromotionDetail from '../app/(app)/promotion/[id]';
import PromotionsScreen from '../app/(app)/(tabs)/promotions';
import { ApiError } from '../src/api/errors';
import { PROMOTION_CARDS } from '../src/features/promotionsArtwork';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Promotion, Promotions } from '../src/types/api';

const mockPush = jest.fn();
const mockParams = jest.fn();
const mockUsePromotions = jest.fn();
const mockUsePromotion = jest.fn();

jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
  useLocalSearchParams: () => mockParams(),
}));

jest.mock('../src/api/app', () => ({
  usePromotions: () => mockUsePromotions(),
  usePromotion: (id: string) => mockUsePromotion(id),
}));

jest.mock('../src/features/useMarkSeen', () => ({ useMarkSeen: jest.fn() }));

jest.mock('react-native-safe-area-context', () => {
  const { View: NativeView } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: NativeView, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const serverOffer: Promotion = {
  id: 'server-offer-1', business_id: null, kind: 'offer', title: 'Серверная акция', subtitle: 'Подзаголовок сервера',
  badge: 'Предложение', body: 'Описание серверной акции', image_url: 'https://example.test/server-offer.png',
  starts_at: null, ends_at: null, is_new: false,
};

function setPromotions(state: Partial<{
  data: Promotions;
  isPending: boolean;
  isError: boolean;
  error: unknown;
}> = {}) {
  mockUsePromotions.mockReturnValue({
    data: state.data,
    isPending: state.isPending ?? false,
    isError: state.isError ?? false,
    error: state.error,
    isRefetching: false,
    refetch: jest.fn(),
  });
}

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(<I18nProvider initial={language}>{element}</I18nProvider>);
}

describe('promotions artwork', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setPromotions({ data: { banners: [], offers: [], has_new: false } });
    mockParams.mockReturnValue({ id: '' });
    mockUsePromotion.mockReturnValue({ data: undefined, error: undefined, isError: false, isPending: true, refetch: jest.fn() });
  });

  it('always shows the four own promotion cards in the required order when the API has no offers', () => {
    setPromotions({ data: { banners: [], offers: [], has_new: false } });
    mount(<PromotionsScreen />);

    expect(screen.getAllByTestId(/^promotion-card-art-/).map(card => card.props.testID)).toEqual([
      'promotion-card-art-hits-discount',
      'promotion-card-art-card-bonus',
      'promotion-card-art-weekly-promo',
      'promotion-card-art-fresh-products',
    ]);
    expect(screen.queryByText(ru.noPromotions)).toBeNull();
    const image = screen.getByTestId('promotion-image-art-hits-discount');
    expect(image.props.resizeMode).toBe('contain');
    // A required asset brings its own pixel height, so the ratio has to live on the wrapper.
    expect(image.props.style).toEqual({ width: '100%', height: '100%' });
    expect(StyleSheet.flatten(screen.getByTestId('promotion-card-art-hits-discount').props.style)).toEqual(
      expect.objectContaining({ aspectRatio: 2000 / 1085 }),
    );
  });

  it.each([
    ['loading', { isPending: true }],
    ['error', { isError: true, error: new Error('offline') }],
  ])('keeps own cards visible while server promotions are in %s state', (_state, overrides) => {
    setPromotions(overrides);
    mount(<PromotionsScreen />);
    expect(screen.getAllByTestId(/^promotion-card-art-/)).toHaveLength(4);
  });

  it('places server offers below own cards when the API returns offers', () => {
    setPromotions({ data: { banners: [], offers: [serverOffer], has_new: false } });
    mount(<PromotionsScreen />);

    expect(screen.getAllByTestId(/^(promotion-artwork|server-promotion)-cards$/).map(node => node.props.testID)).toEqual([
      'promotion-artwork-cards',
      'server-promotion-cards',
    ]);
    expect(screen.getByLabelText('Предложение. Серверная акция')).toBeTruthy();
  });

  it('opens an own card detail route and does not query the server for own detail cards', () => {
    setPromotions({ data: { banners: [], offers: [], has_new: false } });
    mount(<PromotionsScreen />);
    fireEvent.press(screen.getByTestId('promotion-card-art-hits-discount'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: 'art-hits-discount' } });

    mockParams.mockReturnValue({ id: 'art-hits-discount' });
    mount(<PromotionDetail />);
    expect(mockUsePromotion).not.toHaveBeenCalled();
    expect(screen.getByText(ru.offerHitsDiscount)).toBeTruthy();
    expect(screen.getByText(ru.offerHitsDiscountBody)).toBeTruthy();
    expect(screen.getByTestId('promotion-detail-image')).toBeTruthy();
  });

  it('shows a friendly empty state for an unknown ID without crashing', () => {
    mockParams.mockReturnValue({ id: 'unknown-id' });
    mockUsePromotion.mockReturnValue({
      data: undefined,
      error: new ApiError('PROMOTION_NOT_FOUND', 404),
      isError: true,
      isPending: false,
      refetch: jest.fn(),
    });
    mount(<PromotionDetail />);
    expect(screen.getByText(ru.promotionNotFound)).toBeTruthy();
  });

  it('still renders a server promotion using the existing detail fields', () => {
    mockParams.mockReturnValue({ id: serverOffer.id });
    mockUsePromotion.mockReturnValue({ data: serverOffer, error: undefined, isError: false, isPending: false, refetch: jest.fn() });
    mount(<PromotionDetail />);

    expect(mockUsePromotion).toHaveBeenCalledWith(serverOffer.id);
    expect(screen.getByText(serverOffer.title)).toBeTruthy();
    expect(screen.getByText(serverOffer.subtitle!)).toBeTruthy();
    expect(screen.getByText(serverOffer.body!)).toBeTruthy();
  });

  it('keeps RU and KK translations in parity and uses the requested copy', () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(kz).sort());
    expect(ru.bannerCoffeeMachine).toBe('Выиграй кофемашину и годовой запас кофе');
    expect(ru.bannerStickers).toBe('Стикеры в подарок к заказам от 10 000 ₸');
    expect(kz.bannerCoffeeMachine).toBe('Кофемашина және бір жылдық кофе қорын ұтып алыңыз');
    expect(kz.bannerStickers).toBe('10 000 ₸ бастап тапсырыстарға сыйлыққа стикерлер');
    expect(ru.offerHitsDiscountBody).toBe('По всем вопросам применения скидок / баллов обращайтесь в магазин.');
    const kazakhBody = 'Жеңілдіктерді / балдарды қолдану туралы барлық сұрақтар бойынша дүкенге хабарласыңыз.';
    for (const card of PROMOTION_CARDS) {
      expect(ru[card.bodyKey]).toBe(ru.offerHitsDiscountBody);
      expect(kz[card.bodyKey]).toBe(kazakhBody);
    }
    expect(PROMOTION_CARDS.map(card => card.titleKey)).toEqual([
      'offerHitsDiscount', 'offerCardBonus', 'offerWeeklyPromo', 'offerFreshProducts',
    ]);
  });
});
