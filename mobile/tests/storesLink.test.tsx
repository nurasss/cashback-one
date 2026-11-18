import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { ScrollView, View } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import StatusRoute from '../app/(app)/status';
import * as clientConfig from '../src/config/client';
import { ActiveCardProvider } from '../src/features/activeCard';
import { useScrollToStores } from '../src/features/useScrollToStores';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import { kz } from '../src/i18n/kz';
import { clearAppCache } from '../src/storage/appCache';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { AppContent, Card, Profile } from '../src/types/api';

const mockPush = jest.fn();
let mockParams: Record<string, string> = {};
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
  useLocalSearchParams: () => mockParams,
}));
const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'test-user' } }),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View: RnView } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: RnView, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));

// The jest ScrollView mock keeps scrollTo as one shared jest.fn on the prototype.
const scrollTo = (ScrollView as unknown as { prototype: { scrollTo: jest.Mock } }).prototype.scrollTo;
const layoutEvent = (y: number, height: number) => ({ nativeEvent: { layout: { x: 0, y, width: 390, height } } });

const card: Card = { id: 'c1', barcode: '0123456789012', balance: '1250.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b-1', name: 'Shop', branding: null }, tier: null };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const stores = [
  { id: 's1', title_ru: 'Магазин 1', title_kk: 'Дүкен 1', address_ru: 'ул. Абая, 1', address_kk: 'Абай к-сі, 1', map_url: 'https://maps.example.com/s1', sort_order: 1 },
];
const content = (withStores = stores): AppContent => ({ business_id: 'b-1', stores: withStores, app_texts: {}, updated_at: '2026-11-11T00:00:00Z' });

function serve(app: AppContent, cards: Card[]) {
  mockRequest.mockImplementation((path: string) => {
    if (path.startsWith('/me/cards')) return Promise.resolve(cards);
    if (path.startsWith('/me/profile')) return Promise.resolve(profile);
    if (path.startsWith('/me/promotions')) return Promise.resolve({ banners: [], offers: [], has_new: false });
    if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
    if (path.startsWith('/me/app-content')) return Promise.resolve(app);
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}
function Providers({ query, language = 'ru', children }: { query: QueryClient; language?: 'ru' | 'kz'; children: ReactElement }) {
  return (
    <QueryClientProvider client={query}>
      <ThemeProvider initialPreference="light"><I18nProvider initial={language}><ActiveCardProvider>{children}</ActiveCardProvider></I18nProvider></ThemeProvider>
    </QueryClientProvider>
  );
}
const newQuery = () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000, gcTime: Infinity }, mutations: { retry: false } } });
function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(<Providers query={newQuery()} language={language}>{element}</Providers>);
}
const until = (description: string, condition: () => boolean) => waitFor(() => { if (!condition()) throw new Error(`not yet: ${description}`); });
// The load chain (cards -> business -> app-content -> screen) is waited for in steps, each with its own window, as in the other screen tests:
// the first render of a screen in a file is slow, and one wait for the whole chain can run out of time under load.
const requestIndexes = (prefix: string) => mockRequest.mock.calls.flatMap((call, index) => (String(call[0]).startsWith(prefix) ? [index] : []));
async function responseDelivered(prefix: string) {
  await until(`${prefix} request was sent`, () => requestIndexes(prefix).length >= 1);
  const result = mockRequest.mock.results[requestIndexes(prefix)[0] ?? -1];
  if (!result) throw new Error(`${prefix} request has no recorded result`);
  return result.value;
}
async function dataDelivered() {
  await responseDelivered('/me/cards');
  await responseDelivered('/me/app-content');
}

beforeEach(async () => {
  jest.clearAllMocks();
  mockParams = {};
  scrollTo.mockClear();
  await clearAppCache();
});
afterEach(() => { jest.restoreAllMocks(); });

describe('useScrollToStores (the scroll offset logic)', () => {
  function Harness({ section, at }: { section?: string; at?: string }) {
    const { scrollRef, onStoresLayout } = useScrollToStores(section, at);
    return <ScrollView ref={scrollRef}><View testID="anchor" onLayout={onStoresLayout} /></ScrollView>;
  }

  it('scrolls to the stores section (a little above it) once its layout is known', () => {
    const screen = render(<Harness section="stores" at="1" />);
    expect(scrollTo).not.toHaveBeenCalled(); // nothing is laid out yet
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 300));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ y: 688, animated: true });
  });

  it('waits while the stores list is still empty (height 0), then scrolls when it arrives', () => {
    const screen = render(<Harness section="stores" at="1" />);
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 0));
    expect(scrollTo).not.toHaveBeenCalled();
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 280));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ y: 688, animated: true });
  });

  it('does not scroll again for the same request, even when the layout changes', () => {
    const screen = render(<Harness section="stores" at="1" />);
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 300));
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 300));
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(710, 340));
    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('scrolls again when an already open screen is opened once more (a new token)', () => {
    const screen = render(<Harness section="stores" at="1" />);
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 300));
    screen.rerender(<Harness section="stores" at="2" />);
    expect(scrollTo).toHaveBeenCalledTimes(2);
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 688, animated: true });
  });

  it('never scrolls for another or a missing section', () => {
    const screen = render(<Harness section="other" at="1" />);
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(700, 300));
    screen.rerender(<Harness />);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('does not scroll above the top of the page', () => {
    const screen = render(<Harness section="stores" at="1" />);
    fireEvent(screen.getByTestId('anchor'), 'layout', layoutEvent(4, 300));
    expect(scrollTo).toHaveBeenCalledWith({ y: 0, animated: true });
  });
});

describe('the status screen scrolls to the stores', () => {
  it('with a card', async () => {
    mockParams = { section: 'stores', at: '100' };
    serve(content(), [card]);
    const screen = mount(<StatusRoute />);
    await dataDelivered();
    await until('the store item is shown', () => screen.queryByTestId('status-store-item-s1') !== null);
    fireEvent(screen.getByTestId('stores-section'), 'layout', layoutEvent(640, 210));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ y: 628, animated: true });
  });

  it('without a card (a client app that knows its business)', async () => {
    jest.spyOn(clientConfig, 'getClientConfig').mockReturnValue({ ...clientConfig.getClientConfig(), business_id: 'b-1' });
    mockParams = { section: 'stores', at: '100' };
    serve(content(), []);
    const screen = mount(<StatusRoute />);
    await dataDelivered();
    await until('the store item is shown', () => screen.queryByTestId('status-store-item-s1') !== null);
    fireEvent(screen.getByTestId('stores-section'), 'layout', layoutEvent(560, 210));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ y: 548, animated: true });
  });

  it('opened once more while already mounted: a new token scrolls again, the same one does not', async () => {
    mockParams = { section: 'stores', at: '100' };
    serve(content(), [card]);
    const query = newQuery();
    const screen = render(<Providers query={query}><StatusRoute /></Providers>);
    await dataDelivered();
    await until('the store item is shown', () => screen.queryByTestId('status-store-item-s1') !== null);
    fireEvent(screen.getByTestId('stores-section'), 'layout', layoutEvent(640, 210));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    screen.rerender(<Providers query={query}><StatusRoute /></Providers>); // same request: no second scroll
    expect(scrollTo).toHaveBeenCalledTimes(1);
    mockParams = { section: 'stores', at: '101' }; // the same screen is opened once more
    screen.rerender(<Providers query={query}><StatusRoute /></Providers>);
    expect(scrollTo).toHaveBeenCalledTimes(2);
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 628, animated: true });
  });

  it('does not scroll without the section parameter, and not when there are no stores', async () => {
    serve(content(), [card]);
    const plain = mount(<StatusRoute />);
    await dataDelivered();
    await until('the store item is shown', () => plain.queryByTestId('status-store-item-s1') !== null);
    fireEvent(plain.getByTestId('stores-section'), 'layout', layoutEvent(640, 210));
    expect(scrollTo).not.toHaveBeenCalled();
    plain.unmount();

    mockParams = { section: 'stores', at: '1' };
    serve(content([]), [card]);
    const empty = mount(<StatusRoute />);
    await dataDelivered();
    await until('the screen is shown', () => empty.queryByTestId('stores-section') !== null);
    fireEvent(empty.getByTestId('stores-section'), 'layout', layoutEvent(640, 0));
    expect(scrollTo).not.toHaveBeenCalled();
  });
});

describe('the Home link opens the stores section', () => {
  const press = (screen: ReturnType<typeof mount>) => fireEvent.press(screen.getByTestId('where-to-spend-link'));

  it.each([['ru', ru.whereToSpendBonuses], ['kz', kz.whereToSpendBonuses]] as const)('with a card (%s): one navigation with a fresh token per tap', async (language, label) => {
    serve(content(), [card]);
    const screen = mount(<Home />, language);
    await dataDelivered();
    await until('the link is shown', () => screen.queryByTestId('where-to-spend-link') !== null);
    expect(screen.getByText(label)).toBeTruthy();
    const now = jest.spyOn(Date, 'now');
    now.mockReturnValue(10_000);
    press(screen);
    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenLastCalledWith({ pathname: '/status', params: { section: 'stores', at: '10000' } });
    now.mockReturnValue(10_300); // a quick second tap: ignored (no second copy of the screen)
    press(screen);
    expect(mockPush).toHaveBeenCalledTimes(1);
    now.mockReturnValue(12_000); // a later tap works again, with a new token
    press(screen);
    expect(mockPush).toHaveBeenCalledTimes(2);
    expect(mockPush).toHaveBeenLastCalledWith({ pathname: '/status', params: { section: 'stores', at: '12000' } });
  });

  it('without a card: the same link and the same navigation', async () => {
    jest.spyOn(clientConfig, 'getClientConfig').mockReturnValue({ ...clientConfig.getClientConfig(), business_id: 'b-1' });
    serve(content(), []);
    const screen = mount(<Home />);
    await dataDelivered();
    await until('the link is shown', () => screen.queryByTestId('where-to-spend-link') !== null);
    expect(screen.getByText(ru.noCardNotice, { exact: false })).toBeTruthy();
    press(screen);
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/status', params: { section: 'stores', at: expect.any(String) } });
  });

  it('still shows no address plate on Home', async () => {
    serve(content(), [card]);
    const screen = mount(<Home />);
    await dataDelivered();
    await until('the link is shown', () => screen.queryByTestId('where-to-spend-link') !== null);
    expect(screen.queryByTestId('store-block')).toBeNull();
    expect(screen.queryByText('ул. Абая, 1', { exact: false })).toBeNull();
  });
});
