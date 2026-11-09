import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Alert, Linking, StyleSheet } from 'react-native';
import NotificationsScreen from '../app/(app)/(tabs)/notifications';
import PromotionDetail from '../app/(app)/promotion/[id]';
import { LinkedText } from '../src/components/LinkedText';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { darkColors, lightColors } from '../src/theme';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import { hasLinks, splitLinks, toSafeWebUrl } from '../src/utils/links';

const mockUseNotifications = jest.fn();
const mockUsePromotion = jest.fn();
jest.mock('../src/api/app', () => ({
  useNotifications: () => mockUseNotifications(),
  usePromotion: (id: string) => mockUsePromotion(id),
}));
jest.mock('../src/features/useMarkSeen', () => ({ useMarkSeen: jest.fn() }));
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: () => ({ id: 'promo-1' }),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const urls = (text: string) => splitLinks(text).filter(segment => segment.url).map(segment => segment.url);
// The RN jest mock of Linking keeps its call history across tests, so every spy starts from a clean slate.
function spyOpen() {
  const spy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
  spy.mockClear();
  return spy;
}
const flat = (node: { props: { style?: unknown } }) => (StyleSheet.flatten(node.props.style as never) ?? {}) as { color?: string; textDecorationLine?: string };

describe('link detection (plain text, no Markdown/HTML)', () => {
  it('leaves text without links untouched', () => {
    expect(splitLinks('Привет! Скидка 20% до пятницы.')).toEqual([{ text: 'Привет! Скидка 20% до пятницы.' }]);
    expect(splitLinks('')).toEqual([{ text: '' }]);
    expect(hasLinks('example.com без схемы')).toBe(false);
  });

  it('finds a link and keeps the text around it', () => {
    expect(splitLinks('Условия: https://example.com/akciya?a=1&b=2#top — читайте.')).toEqual([
      { text: 'Условия: ' },
      { text: 'https://example.com/akciya?a=1&b=2#top', url: 'https://example.com/akciya?a=1&b=2#top' },
      { text: ' — читайте.' },
    ]);
  });

  it('finds several links and keeps line breaks', () => {
    const text = 'Первая: http://a.kz/x\nВторая: https://b.kz/y/\n\nТретья: www.c.kz';
    expect(urls(text)).toEqual(['http://a.kz/x', 'https://b.kz/y/', 'https://www.c.kz']);
    expect(splitLinks(text).map(segment => segment.text).join('')).toBe(text);
  });

  it.each([
    ['https://a.kz/x.', 'https://a.kz/x'],
    ['https://a.kz/x,', 'https://a.kz/x'],
    ['https://a.kz/x;', 'https://a.kz/x'],
    ['https://a.kz/x:', 'https://a.kz/x'],
    ['https://a.kz/x!', 'https://a.kz/x'],
    ['https://a.kz/x?', 'https://a.kz/x'],
    ['https://a.kz/x…', 'https://a.kz/x'],
    ['https://a.kz/x."', 'https://a.kz/x'],
    ['https://a.kz/x»', 'https://a.kz/x'],
    ['(см. https://a.kz/x)', 'https://a.kz/x'],
    ['[сайт](https://a.kz/x)', 'https://a.kz/x'],
    ['https://a.kz/wiki/Foo_(bar)', 'https://a.kz/wiki/Foo_(bar)'],
    ['https://a.kz/wiki/Foo_(bar).', 'https://a.kz/wiki/Foo_(bar)'],
    ['https://a.kz/x?q=1&r=2', 'https://a.kz/x?q=1&r=2'],
  ])('sentence punctuation is not part of the link: %s', (text, expected) => {
    expect(urls(text)).toEqual([expected]);
  });

  it('supports Unicode hosts and paths', () => {
    expect(urls('Смотрите https://пример.рф/страница/акция и https://a.kz/каталог/платья.')).toEqual(['https://пример.рф/страница/акция', 'https://a.kz/каталог/платья']);
  });

  it('normalises www. to https and lower-cases the scheme, nothing else', () => {
    expect(toSafeWebUrl('www.Example.com/A')).toBe('https://www.Example.com/A');
    expect(toSafeWebUrl('HTTPS://EXAMPLE.com/Path')).toBe('https://EXAMPLE.com/Path');
    expect(toSafeWebUrl('http://example.com:8080/x')).toBe('http://example.com:8080/x');
  });

  it('does not treat www. inside a word or a longer host as a link', () => {
    expect(urls('awww.example.com')).toEqual([]);
    expect(urls('sub.www.example.com')).toEqual([]);
    expect(urls('(www.example.com)')).toEqual(['https://www.example.com']);
  });

  it.each([
    'javascript:alert(1)',
    'JAVASCRIPT:alert(document.cookie)',
    'data:text/html,<script>alert(1)</script>',
    'file:///etc/passwd',
    'intent://scan/#Intent;scheme=zxing;end',
    'tel:+77001234567',
    'mailto:a@b.kz',
    'ftp://example.com/file',
    'market://details?id=x',
    'vbscript:msgbox(1)',
  ])('never produces a link for a non-web scheme: %s', text => {
    expect(hasLinks(text)).toBe(false);
    expect(toSafeWebUrl(text)).toBeNull();
  });

  it.each([
    'https://',
    'https:///x',
    'https://user:pass@evil.example/x',
    'https://good.example@evil.example/',
    'https://localhost/x',
    'https://a..b/x',
    'https://-a.kz/',
    'https://a.kz\\@evil.example',
  ])('rejects a malformed or deceptive web URL: %s', text => {
    expect(toSafeWebUrl(text)).toBeNull();
  });

  it('a scheme-like prefix cannot smuggle a script: only the real https part is linked', () => {
    expect(urls('javascript://https://example.com/%0Aalert(1)')).toEqual(['https://example.com/%0Aalert(1)']);
  });
});

function mount(element: ReactElement, { language = 'ru', theme = 'light' }: { language?: 'ru' | 'kz'; theme?: 'light' | 'dark' } = {}) {
  return render(<ThemeProvider initialPreference={theme}><I18nProvider initial={language}>{element}</I18nProvider></ThemeProvider>);
}

describe('LinkedText', () => {
  afterEach(() => { jest.restoreAllMocks(); });

  it('renders text without links as a plain Text (no link roles)', () => {
    mount(<LinkedText text="Обычный текст" />);
    expect(screen.getByText('Обычный текст')).toBeTruthy();
    expect(screen.queryAllByRole('link')).toHaveLength(0);
  });

  it('opens each link only on tap, in the external browser, with the normalised URL, and never on render', async () => {
    const open = spyOpen();
    mount(<LinkedText text={'Сайт: www.a.kz, магазин (https://b.kz/shop).'} />);
    expect(open).not.toHaveBeenCalled();
    const links = screen.getAllByRole('link');
    expect(links.map(link => link.props.children)).toEqual(['www.a.kz', 'https://b.kz/shop']);
    await act(async () => { fireEvent.press(links[0]!); });
    expect(open).toHaveBeenLastCalledWith('https://www.a.kz');
    await act(async () => { fireEvent.press(links[1]!); });
    expect(open).toHaveBeenLastCalledWith('https://b.kz/shop');
    expect(open).toHaveBeenCalledTimes(2);
  });

  it('shows a clear RU message and does not crash when the link cannot be opened', async () => {
    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('No Activity found'));
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mount(<LinkedText text="https://a.kz" />);
    await act(async () => { fireEvent.press(screen.getByRole('link')); });
    expect(alert).toHaveBeenCalledTimes(1);
    expect(alert.mock.calls[0]![1]).toBe(ru.linkOpenFailed);
  });

  it('the failure message exists in Kazakh', async () => {
    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('no browser'));
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mount(<LinkedText text="https://a.kz" />, { language: 'kz' });
    await act(async () => { fireEvent.press(screen.getByRole('link')); });
    expect(alert.mock.calls[0]![1]).toBe(kz.linkOpenFailed);
  });

  it.each([['light', lightColors], ['dark', darkColors]] as const)('links are underlined and use the readable accent (%s)', (theme, colors) => {
    mount(<LinkedText text="Смотри https://a.kz/x" />, { theme });
    const style = flat(screen.getByRole('link'));
    expect(style.textDecorationLine).toBe('underline');
    expect(style.color).toBe(colors.primaryText);
  });

  it('never sends a non-web scheme to the system, even if one is pasted', async () => {
    const open = spyOpen();
    mount(<LinkedText text="javascript:alert(1) file:///x data:text/plain,hi" />);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(open).not.toHaveBeenCalled();
  });
});

const notification = (overrides: Record<string, unknown> = {}) => ({
  id: 'n1', kind: 'broadcast', title: 'Акция', body: 'Подробности: https://a.kz/promo.', created_at: '2026-11-09T10:00:00Z', is_unread: true, ...overrides,
});
function setNotifications(items: unknown[]) {
  mockUseNotifications.mockReturnValue({ data: { items, unread_count: items.length }, isPending: false, isError: false, isSuccess: true, isRefetching: false, refetch: jest.fn() });
}

describe('notification texts', () => {
  afterEach(() => { jest.restoreAllMocks(); });

  it('a notification with a link keeps its children reachable for screen readers and opens the link on tap', async () => {
    const open = spyOpen();
    setNotifications([notification()]);
    mount(<NotificationsScreen />);
    const link = screen.getByRole('link');
    expect(link.props.children).toBe('https://a.kz/promo');
    // The card must not be one accessible element that swallows the link.
    expect(screen.queryByLabelText(/Подробности/)).toBeNull();
    // Unread state is still announced, on the title.
    expect(screen.getByLabelText(`${ru.newBadge}. Акция`)).toBeTruthy();
    await act(async () => { fireEvent.press(link); });
    expect(open).toHaveBeenCalledWith('https://a.kz/promo');
  });

  it('a notification without a link is unchanged: one accessible card with the old label', () => {
    setNotifications([notification({ body: 'Без ссылок, просто текст.' })]);
    mount(<NotificationsScreen />);
    expect(screen.getByLabelText(`${ru.newBadge}. Акция. Без ссылок, просто текст.`)).toBeTruthy();
    expect(screen.queryAllByRole('link')).toHaveLength(0);
  });

  it('keeps text, line breaks and several links of the body', () => {
    const body = 'Строка 1 https://a.kz/1\nСтрока 2: www.b.kz/2!\nКонец';
    setNotifications([notification({ body })]);
    mount(<NotificationsScreen />);
    expect(screen.getAllByRole('link').map(link => link.props.children)).toEqual(['https://a.kz/1', 'www.b.kz/2']);
    expect(screen.getByText(/Строка 1/, { exact: false })).toBeTruthy();
  });

  it('opening the notifications screen never opens a link by itself', () => {
    const open = spyOpen();
    setNotifications([notification()]);
    mount(<NotificationsScreen />);
    expect(open).not.toHaveBeenCalled();
  });
});

describe('promotion description', () => {
  afterEach(() => { jest.restoreAllMocks(); });
  const promotion = (body: string | null) => ({ data: { id: 'promo-1', business_id: null, kind: 'offer', title: 'Акция', subtitle: 'Подзаголовок', badge: null, body, image_url: null, starts_at: null, ends_at: null, is_new: false }, isPending: false, isError: false, error: null, refetch: jest.fn() });

  it('links in the description are tappable and open externally', async () => {
    const open = spyOpen();
    mockUsePromotion.mockReturnValue(promotion('Условия акции — https://a.kz/terms, подробнее в магазине.'));
    mount(<PromotionDetail />, { theme: 'dark' });
    const link = screen.getByRole('link');
    expect(link.props.children).toBe('https://a.kz/terms');
    expect(flat(link).color).toBe(darkColors.primaryText);
    await act(async () => { fireEvent.press(link); });
    expect(open).toHaveBeenCalledWith('https://a.kz/terms');
  });

  it('a description without links looks as before', () => {
    mockUsePromotion.mockReturnValue(promotion('Просто описание.'));
    mount(<PromotionDetail />);
    expect(screen.getByText('Просто описание.')).toBeTruthy();
    expect(screen.queryAllByRole('link')).toHaveLength(0);
  });
});
