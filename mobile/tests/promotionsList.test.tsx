import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { RefreshControl, Text } from 'react-native';
import PromotionsScreen from '../app/(app)/(tabs)/promotions';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { ThemeProvider, useTheme } from '../src/theme/ThemeProvider';
import type { Promotion } from '../src/types/api';

const mockPush = jest.fn();
const mockUsePromotions = jest.fn();
const mockRefetch = jest.fn();
jest.mock('expo-router', () => ({ router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), back: jest.fn(), canGoBack: () => true } }));
jest.mock('../src/api/app', () => ({ usePromotions: (...args: unknown[]) => mockUsePromotions(...args) }));
jest.mock('../src/features/useMarkSeen', () => ({ useMarkSeen: jest.fn() }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const offers = (count: number): Promotion[] => Array.from({ length: count }, (_, i) => ({
  id: `o${i + 1}`, business_id: null, kind: 'offer', title: `Акция ${i + 1}`, subtitle: null, badge: null, body: `Описание ${i + 1}`,
  image_url: null, starts_at: null, ends_at: null, is_new: false,
}));
function serve(count: number, overrides: Record<string, unknown> = {}) {
  mockUsePromotions.mockReturnValue({ data: { banners: [], offers: offers(count), has_new: false }, isPending: false, isError: false, error: null, isRefetching: false, refetch: mockRefetch, ...overrides });
}
function mount(element: ReactElement = <PromotionsScreen />, language: 'ru' | 'kz' = 'ru', theme: 'light' | 'dark' = 'light') {
  return render(<ThemeProvider initialPreference={theme}><I18nProvider initial={language}>{element}</I18nProvider></ThemeProvider>);
}
const titles = () => screen.queryAllByText(/^Акция \d+$/).map(node => node.props.children as string);
const sequence = (n: number) => Array.from({ length: n }, (_, i) => `Акция ${i + 1}`);

beforeEach(() => { mockPush.mockReset(); mockRefetch.mockReset(); mockUsePromotions.mockReset(); });

describe('Promotions tab: first six cards', () => {
  it.each([0, 1, 2, 5, 6])('shows %i card(s) and no "View all" button', count => {
    serve(count);
    mount();
    expect(titles()).toEqual(sequence(count));
    expect(screen.queryByText(ru.viewAll)).toBeNull();
    expect(screen.queryByText(ru.collapse)).toBeNull();
  });

  it('shows the empty state for no promotions', () => {
    serve(0);
    mount();
    expect(screen.getByText(ru.noPromotions)).toBeTruthy();
  });

  it.each([7, 8, 13])('with %i promotions shows the first six in server order (three rows) and a "View all" button', count => {
    serve(count);
    mount();
    expect(titles()).toEqual(sequence(6));
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
    expect(screen.getByTestId('server-promotion-cards').children).toHaveLength(3);
  });

  it('"View all" shows every available promotion on the same screen, in order; "Collapse" returns to six', () => {
    serve(13);
    mount();
    fireEvent.press(screen.getByText(ru.viewAll));
    expect(titles()).toEqual(sequence(13));
    expect(screen.queryByText(ru.viewAll)).toBeNull();
    expect(screen.getByTestId('server-promotion-cards').children).toHaveLength(7);
    expect(mockPush).not.toHaveBeenCalled();
    fireEvent.press(screen.getByText(ru.collapse));
    expect(titles()).toEqual(sequence(6));
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
  });

  it('opens the description of a card from the collapsed list and from the expanded one', () => {
    serve(8);
    mount();
    fireEvent.press(screen.getByLabelText('Акция 2'));
    expect(mockPush).toHaveBeenLastCalledWith({ pathname: '/promotion/[id]', params: { id: 'o2' } });
    fireEvent.press(screen.getByText(ru.viewAll));
    fireEvent.press(screen.getByLabelText('Акция 8'));
    expect(mockPush).toHaveBeenLastCalledWith({ pathname: '/promotion/[id]', params: { id: 'o8' } });
  });

  it('does not limit the request: the hook is used without arguments and receives the whole list', () => {
    serve(30);
    mount();
    fireEvent.press(screen.getByText(ru.viewAll));
    expect(titles()).toEqual(sequence(30));
    expect(mockUsePromotions.mock.calls.every(call => call.length === 0)).toBe(true);
  });

  it('pull-to-refresh still refetches', () => {
    serve(9);
    const view = mount();
    act(() => { view.UNSAFE_getByType(RefreshControl).props.onRefresh(); });
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('keeps loading and error states, and cached offers during a failed refresh', () => {
    mockUsePromotions.mockReturnValue({ data: undefined, isPending: true, isError: false, error: null, isRefetching: false, refetch: mockRefetch });
    const loading = mount();
    expect(screen.queryByText(ru.viewAll)).toBeNull();
    expect(screen.getByText(ru.loading)).toBeTruthy();
    loading.unmount();
    serve(9, { isError: true, error: new Error('offline') });
    mount();
    expect(titles()).toEqual(sequence(6));
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
  });

  it('the new list length updates the button after a refresh (7 -> 6 hides it, 6 -> 8 shows it)', () => {
    serve(7);
    const view = mount();
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
    serve(6);
    view.rerender(<ThemeProvider initialPreference="light"><I18nProvider initial="ru"><PromotionsScreen /></I18nProvider></ThemeProvider>);
    expect(screen.queryByText(ru.viewAll)).toBeNull();
    serve(8);
    view.rerender(<ThemeProvider initialPreference="light"><I18nProvider initial="ru"><PromotionsScreen /></I18nProvider></ThemeProvider>);
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
    expect(titles()).toEqual(sequence(6));
  });

  it('the expanded mode survives a theme change (no remount)', () => {
    serve(9);
    function Switch() { const { setPreference } = useTheme(); return <Text testID="to-dark" onPress={() => setPreference('dark')}>dark</Text>; }
    mount(<><Switch /><PromotionsScreen /></>);
    fireEvent.press(screen.getByText(ru.viewAll));
    expect(titles()).toEqual(sequence(9));
    fireEvent.press(screen.getByTestId('to-dark'));
    expect(titles()).toEqual(sequence(9));
    expect(screen.getByText(ru.collapse)).toBeTruthy();
  });

  it('the expanded mode is not carried over to the next session of the screen (sign-out unmounts it)', () => {
    serve(9);
    const first = mount();
    fireEvent.press(screen.getByText(ru.viewAll));
    expect(titles()).toEqual(sequence(9));
    first.unmount();
    serve(9);
    mount();
    expect(titles()).toEqual(sequence(6));
    expect(screen.getByText(ru.viewAll)).toBeTruthy();
  });

  it('the buttons exist in Kazakh', () => {
    serve(8);
    mount(<PromotionsScreen />, 'kz');
    fireEvent.press(screen.getByText(kz.viewAll));
    expect(screen.getByText(kz.collapse)).toBeTruthy();
  });
});
