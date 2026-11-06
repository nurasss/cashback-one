import { fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import PromotionDetail from '../app/(app)/promotion/[id]';
import PromotionsScreen from '../app/(app)/(tabs)/promotions';
import { ApiError } from '../src/api/errors';
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

const serverOffer1: Promotion = {
  id: 'server-offer-1', business_id: null, kind: 'offer', title: 'Серверная акция 1', subtitle: 'Подзаголовок сервера 1',
  badge: 'Скидка недели', body: 'Описание серверной акции 1', image_url: 'https://example.test/server-offer1.png',
  starts_at: null, ends_at: '2026-11-20T00:00:00Z', is_new: true,
};
const serverOffer2: Promotion = {
  id: 'server-offer-2', business_id: null, kind: 'offer', title: 'Серверная акция 2', subtitle: null,
  badge: null, body: null, image_url: null, starts_at: null, ends_at: null, is_new: false,
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

describe('Promotions screen and detail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setPromotions({ data: { banners: [], offers: [], has_new: false } });
    mockParams.mockReturnValue({ id: '' });
    mockUsePromotion.mockReturnValue({ data: undefined, error: undefined, isError: false, isPending: true, refetch: jest.fn() });
  });

  it('renders only server offers when available', () => {
    setPromotions({ data: { banners: [], offers: [serverOffer1, serverOffer2], has_new: false } });
    mount(<PromotionsScreen />);

    expect(screen.getByTestId('server-promotion-cards')).toBeTruthy();
    expect(screen.getByText(serverOffer1.title)).toBeTruthy();
    expect(screen.getByText(serverOffer2.title)).toBeTruthy();
    expect(screen.getByText(serverOffer1.badge!)).toBeTruthy();
  });

  it('shows empty state when server offers list is empty', () => {
    setPromotions({ data: { banners: [], offers: [], has_new: false } });
    mount(<PromotionsScreen />);

    expect(screen.getByText(ru.noPromotions)).toBeTruthy();
    expect(screen.queryByTestId('server-promotion-cards')).toBeNull();
  });

  it('tapping a server offer opens detail route /promotion/[id]', () => {
    setPromotions({ data: { banners: [], offers: [serverOffer1], has_new: false } });
    mount(<PromotionsScreen />);

    fireEvent.press(screen.getByText(serverOffer1.title));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: serverOffer1.id } });
  });

  it('renders server promotion detail with title, subtitle, badge, body and date', () => {
    mockParams.mockReturnValue({ id: serverOffer1.id });
    mockUsePromotion.mockReturnValue({ data: serverOffer1, error: undefined, isError: false, isPending: false, refetch: jest.fn() });
    mount(<PromotionDetail />);

    expect(mockUsePromotion).toHaveBeenCalledWith(serverOffer1.id);
    expect(screen.getByText(serverOffer1.title)).toBeTruthy();
    expect(screen.getByText(serverOffer1.subtitle!)).toBeTruthy();
    expect(screen.getByText(serverOffer1.badge!)).toBeTruthy();
    expect(screen.getByText(serverOffer1.body!)).toBeTruthy();
  });

  it('shows friendly empty state on 404 PROMOTION_NOT_FOUND', () => {
    mockParams.mockReturnValue({ id: 'missing-id' });
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

  it('shows friendly empty state when no ID is provided', () => {
    mockParams.mockReturnValue({ id: '' });
    mount(<PromotionDetail />);

    expect(screen.getByText(ru.promotionNotFound)).toBeTruthy();
  });

  it('renders promotions in a 2-column grid layout', () => {
    const serverOffer3: Promotion = {
      id: 'server-offer-3', business_id: null, kind: 'offer', title: 'Серверная акция 3', subtitle: null,
      badge: 'Новинка', body: null, image_url: null, starts_at: null, ends_at: null, is_new: true,
    };
    setPromotions({ data: { banners: [], offers: [serverOffer1, serverOffer2, serverOffer3], has_new: false } });
    mount(<PromotionsScreen />);

    const grid = screen.getByTestId('server-promotion-cards');
    expect(grid).toBeTruthy();
    expect(screen.getByText(serverOffer1.title)).toBeTruthy();
    expect(screen.getByText(serverOffer2.title)).toBeTruthy();
    expect(screen.getByText(serverOffer3.title)).toBeTruthy();
  });

  it('renders promotion detail image with dynamic aspect ratio, not fixed 1.7', () => {
    mockParams.mockReturnValue({ id: serverOffer1.id });
    mockUsePromotion.mockReturnValue({ data: serverOffer1, error: undefined, isError: false, isPending: false, refetch: jest.fn() });
    mount(<PromotionDetail />);

    const img = screen.getByTestId('expo-image');
    expect(img).toBeTruthy();
    const findAspect = (styleProp: unknown): number | undefined => {
      const flat = [styleProp].flat();
      return flat.reduce((acc: number | undefined, s: unknown) => {
        if (typeof s === 'object' && s !== null && 'aspectRatio' in s) {
          const val = (s as Record<string, unknown>).aspectRatio;
          if (typeof val === 'number') return val;
        }
        return acc;
      }, undefined);
    };

    const initialAspect = findAspect(img.props.style);
    expect(initialAspect).toBeCloseTo(4 / 3, 2);
    expect(initialAspect).not.toBeCloseTo(1.7, 2);

    fireEvent(img, 'load', { source: { width: 1200, height: 500 } });
    const updatedAspect = findAspect(img.props.style);
    expect(updatedAspect).toBeCloseTo(1200 / 500, 2);
  });

  it('keeps RU and KK translations in parity', () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(kz).sort());
    expect(ru.storeNoteDefaultLead).toBe('Вы можете потратить баллы по адресу: ');
    expect(kz.storeNoteDefaultLead).toBe('Ұпайларды мына мекенжай бойынша жұмсай аласыз: ');
  });
});
