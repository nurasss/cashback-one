import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import fs from 'fs';
import path from 'path';
import { Pressable, ScrollView, Text } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import * as clientConfig from '../src/config/client';
import { ActiveCardProvider } from '../src/features/activeCard';
import { HomeTextBlock, homeTextFor } from '../src/features/home';
import { I18nProvider, useI18n } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { clearAppCache, setCachedAppContent } from '../src/storage/appCache';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { AppContent, Card, Profile } from '../src/types/api';

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
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));

const card: Card = { id: 'card-1', barcode: '0123456789012', balance: '1250.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b-1', name: 'Supermarket', branding: null }, tier: null };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: 'Иван', last_name: 'Иванов', email: null, gender: null, city: 'Алматы', address: null, birth_date: null, iin: null, company: null };
const stores = [
  { id: 's2', title_ru: 'Филиал 2', title_kk: '2-бөлімше', address_ru: 'ул. Абая, 20', address_kk: 'Абай к-сі, 20', map_url: null, sort_order: 2 },
  { id: 's1', title_ru: 'Филиал 1', title_kk: '1-бөлімше', address_ru: 'пр. Республики, 5', address_kk: 'Республика д-лы, 5', map_url: 'https://maps.example.com/s1', sort_order: 1 },
  { id: 's3', title_ru: 'Филиал 3', title_kk: '3-бөлімше', address_ru: 'мкр. Самал, 7', address_kk: 'Самал ш/а, 7', map_url: null, sort_order: 3 },
];
const content = (texts: AppContent['app_texts'], withStores = stores): AppContent => ({ business_id: 'b-1', stores: withStores, app_texts: texts, updated_at: '2026-11-09T10:00:00Z' });

const HOME_RU = 'Добро пожаловать в Keremet!\nБонусы начисляются после покупки.\n\nЖдём вас каждый день.';
const HOME_KK = 'Keremet-ке қош келдіңіз!\nБонустар сатып алудан кейін есептеледі.';

function serve(app: unknown, { cards = [card] }: { cards?: Card[] } = {}) {
  mockRequest.mockImplementation((path: string) => {
    if (path.startsWith('/me/cards')) return Promise.resolve(cards);
    if (path.startsWith('/me/profile')) return Promise.resolve(profile);
    if (path.startsWith('/me/promotions')) return Promise.resolve({ banners: [], offers: [], has_new: false });
    if (path.startsWith('/me/badges')) return Promise.resolve({ promotions_new: false, notifications_unread: 0 });
    if (path.startsWith('/me/app-content')) return Promise.resolve(app);
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}
function mount(element: ReactElement, { language = 'ru', theme = 'light' }: { language?: 'ru' | 'kz'; theme?: 'light' | 'dark' } = {}) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={query}>
      <ThemeProvider initialPreference={theme}>
        <I18nProvider initial={language}><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

// Waiting helpers. Each waits for one step with a boolean condition and a short message, so a timeout never serialises a ReactTestInstance
// (the default 1000 ms window of every waitFor is unchanged). The steps are sequential: card ready -> app-content received -> block shown.
async function until(description: string, condition: () => boolean) {
  await waitFor(() => {
    if (!condition()) throw new Error(`not yet: ${description}`);
  });
}
const BALANCE_LABEL = /1\D{0,3}250/; // the balance header's accessibility label for the 1250 balance, in any language
const appContentCallIndexes = () => mockRequest.mock.calls.flatMap((call, index) => (String(call[0]).startsWith('/me/app-content') ? [index] : []));
// Waits until the n-th app-content request was sent and its response was delivered; returns that response.
async function appContentReceived(n: number): Promise<AppContent> {
  await until(`app-content request #${n} was sent`, () => appContentCallIndexes().length >= n);
  const result = mockRequest.mock.results[appContentCallIndexes()[n - 1] ?? -1];
  if (!result) throw new Error(`app-content request #${n} has no recorded result`);
  return (await result.value) as AppContent;
}
// Step 1 and 2 for a screen with a card; a client app without a card (it has no balance) waits for the no-card notice instead.
async function homeLoaded(screen: ReturnType<typeof render>, { withCard = true }: { withCard?: boolean } = {}) {
  if (withCard) await until('the card balance is shown', () => screen.queryAllByLabelText(BALANCE_LABEL).length > 0);
  else await until('the no-card notice is shown', () => screen.queryByText(ru.noCardNotice, { exact: false }) !== null);
  await appContentReceived(1);
}

describe('homeTextFor (language choice)', () => {
  it('prefers the selected language and falls back to the other one', () => {
    const app = content({ home_text: { ru: 'Русский', kk: 'Қазақша' } });
    expect(homeTextFor(app, 'ru')).toBe('Русский');
    expect(homeTextFor(app, 'kz')).toBe('Қазақша');
    expect(homeTextFor(content({ home_text: { ru: 'Только русский', kk: null } }), 'kz')).toBe('Только русский');
    expect(homeTextFor(content({ home_text: { ru: '', kk: 'Тек қазақша' } }), 'ru')).toBe('Тек қазақша');
    expect(homeTextFor(content({ home_text: { ru: '   \n ', kk: 'Тек қазақша' } }), 'ru')).toBe('Тек қазақша');
  });

  it.each([
    ['field is absent (older server)', content({})],
    ['home_text is null', content({ home_text: null })],
    ['home_text is empty object', content({ home_text: {} })],
    ['both languages empty', content({ home_text: { ru: '', kk: '' } })],
    ['both languages null', content({ home_text: { ru: null, kk: null } })],
    ['both languages whitespace', content({ home_text: { ru: ' \n\t', kk: '  ' } })],
  ])('returns null when %s', (_name, app) => {
    expect(homeTextFor(app, 'ru')).toBeNull();
    expect(homeTextFor(app, 'kz')).toBeNull();
  });

  it('returns null without content and never uses the legacy lead', () => {
    expect(homeTextFor(null, 'ru')).toBeNull();
    expect(homeTextFor(undefined, 'kz')).toBeNull();
    expect(homeTextFor(content({ home_store_note_lead: { ru: 'Старая фраза: ', kk: 'Ескі: ' } }), 'ru')).toBeNull();
  });

  it('returns the text untouched: line breaks, spaces and the full length (2000 chars)', () => {
    const long = `${'Строка текста для проверки длины. '.repeat(70)}\nКонец`.slice(0, 2000);
    expect(long.length).toBe(2000);
    expect(homeTextFor(content({ home_text: { ru: long, kk: null } }), 'ru')).toBe(long);
    expect(homeTextFor(content({ home_text: { ru: HOME_RU, kk: null } }), 'ru')).toBe(HOME_RU);
  });
});

describe('Home: the pink home_text block is not shown (owner decision 2026-11-10)', () => {
  afterEach(() => { jest.restoreAllMocks(); });
  beforeEach(async () => {
    jest.clearAllMocks();
    await clearAppCache();
  });

  // The stores are known and loaded once the "where can I spend" link is shown (it needs the stores list from app-content).
  const storeBlockShown = (screen: ReturnType<typeof render>) => until('the stores link is shown', () => screen.queryByTestId('where-to-spend-link') !== null);

  it('does not render the text block or the address plate in Russian, while the link stays', async () => {
    serve(content({ home_text: { ru: HOME_RU, kk: HOME_KK }, home_store_note_lead: { ru: 'Старая фраза: ', kk: 'Ескі: ' } }));
    const screen = mount(<Home />);
    await homeLoaded(screen);
    await storeBlockShown(screen);
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText(/Добро пожаловать/)).toBeNull();
    expect(screen.queryByText(/Старая фраза/)).toBeNull();
    // The address plate is gone from the home screen too (the addresses live in the stores section); the link stays.
    expect(screen.queryByTestId('store-block')).toBeNull();
    for (const address of ['пр. Республики, 5', 'ул. Абая, 20', 'мкр. Самал, 7']) expect(screen.queryByText(address, { exact: false })).toBeNull();
    expect(screen.getByTestId('where-to-spend-link')).toBeTruthy();
    expect(screen.getByText(ru.whereToSpendBonuses)).toBeTruthy();
  });

  it('does not render the text block or the address plate in Kazakh either', async () => {
    serve(content({ home_text: { ru: HOME_RU, kk: HOME_KK } }));
    const screen = mount(<Home />, { language: 'kz' });
    await homeLoaded(screen);
    await storeBlockShown(screen);
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText(/қош келдіңіз/)).toBeNull();
    expect(screen.queryByText(/Добро пожаловать/)).toBeNull();
    expect(screen.queryByTestId('store-block')).toBeNull();
    for (const address of ['Республика д-лы, 5', 'Абай к-сі, 20', 'Самал ш/а, 7']) expect(screen.queryByText(address, { exact: false })).toBeNull();
    expect(screen.getByText(kz.whereToSpendBonuses)).toBeTruthy();
  });

  it('keeps it hidden after switching the language on the open screen', async () => {
    serve(content({ home_text: { ru: HOME_RU, kk: HOME_KK } }));
    function Switcher() {
      const { setLanguage } = useI18n();
      return <Pressable testID="switch-language" onPress={() => setLanguage('kz')}><Text>kk</Text></Pressable>;
    }
    const screen = mount(<><Switcher /><Home /></>);
    await homeLoaded(screen);
    await storeBlockShown(screen);
    expect(screen.queryByText(/Добро пожаловать/)).toBeNull();
    await act(async () => { fireEvent.press(screen.getByTestId('switch-language')); });
    await until('the Kazakh link text is shown', () => screen.queryByText(kz.whereToSpendBonuses) !== null);
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText(/қош келдіңіз/)).toBeNull();
    expect(screen.queryByText(/Добро пожаловать/)).toBeNull();
  });

  it('shows nothing extra for a client app without a card, next to the no-card notice', async () => {
    jest.spyOn(clientConfig, 'getClientConfig').mockReturnValue({ ...clientConfig.getClientConfig(), business_id: 'b-1' });
    serve(content({ home_text: { ru: HOME_RU, kk: HOME_KK } }, []), { cards: [] });
    const screen = mount(<Home />);
    await homeLoaded(screen, { withCard: false });
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText(/Добро пожаловать/)).toBeNull();
    expect(screen.getByText(ru.noCardNotice, { exact: false })).toBeTruthy();
  });

  it('without a card (client app) the stores link stays and opens the stores section, with no address plate', async () => {
    jest.spyOn(clientConfig, 'getClientConfig').mockReturnValue({ ...clientConfig.getClientConfig(), business_id: 'b-1' });
    serve(content({ home_text: { ru: HOME_RU, kk: HOME_KK } }), { cards: [] });
    const screen = mount(<Home />);
    await homeLoaded(screen, { withCard: false });
    await storeBlockShown(screen);
    expect(screen.queryByTestId('store-block')).toBeNull();
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText('пр. Республики, 5', { exact: false })).toBeNull();
    fireEvent.press(screen.getByTestId('where-to-spend-link'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/status', params: { section: 'stores', at: expect.any(String) } });
  });

  it('with a card the stores link opens the stores section; with no stores there is no link and no plate', async () => {
    serve(content({}));
    const screen = mount(<Home />);
    await homeLoaded(screen);
    await storeBlockShown(screen);
    fireEvent.press(screen.getByTestId('where-to-spend-link'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/status', params: { section: 'stores', at: expect.any(String) } });
    screen.unmount();

    jest.clearAllMocks();
    await clearAppCache();
    serve(content({}, []));
    const noStores = mount(<Home />);
    await homeLoaded(noStores);
    expect(noStores.queryByTestId('where-to-spend-link')).toBeNull();
    expect(noStores.queryByTestId('store-block')).toBeNull();
  });

  it('keeps hiding it after a refresh that brings a changed text, and still reads an old cached entry safely', async () => {
    setCachedAppContent('test-user', 'b-1', content({ home_store_note_lead: { ru: 'Старая фраза: ', kk: null } }), null, Date.now() - 3_600_000);
    serve(content({ home_text: { ru: 'Первый текст', kk: null } }));
    const screen = mount(<Home />);
    await homeLoaded(screen);
    await storeBlockShown(screen);
    expect(screen.queryByText('Первый текст')).toBeNull();
    serve(content({ home_text: { ru: 'Новый текст', kk: null } }));
    const refreshControl = screen.UNSAFE_getByType(ScrollView).props.refreshControl;
    await act(async () => { refreshControl.props.onRefresh(); });
    // The refresh sends a new app-content request and its response carries the new text: the server data still arrives intact.
    expect(homeTextFor(await appContentReceived(2), 'ru')).toBe('Новый текст');
    expect(screen.queryByTestId('home-text-block')).toBeNull();
    expect(screen.queryByText('Новый текст')).toBeNull();
    expect(screen.queryByText(/Старая фраза/)).toBeNull();
  });

  it('the stand-alone component is kept for a possible return, but the home screen does not use it', () => {
    const shown = mount(<HomeTextBlock appContent={content({ home_text: { ru: HOME_RU, kk: null } })} language="ru" />);
    expect(shown.getByTestId('home-text-block')).toBeTruthy();
    shown.unmount();
    const home = fs.readFileSync(path.join(__dirname, '../app/(app)/(tabs)/index.tsx'), 'utf8');
    expect(home).not.toMatch(/<HomeTextBlock\b/);
  });
});
