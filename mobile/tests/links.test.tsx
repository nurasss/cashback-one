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
// 1.0.27 replaced useMarkSeen with useMarkNotificationsRead on the notifications screen; the mock must cover both.
jest.mock('../src/features/useMarkSeen', () => ({
  useMarkSeen: jest.fn(),
  useMarkNotificationsRead: () => ({ onViewableItemsChanged: jest.fn(), viewabilityConfig: {} }),
}));
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

describe('named links [label](url)', () => {
  const named = (text: string) => splitLinks(text).filter(segment => segment.url);

  it('shows only the label and keeps the URL hidden, with the text around it', () => {
    expect(splitLinks('Скидки! [Подробнее об акции](https://example.kz/akciya?a=1) — до пятницы.')).toEqual([
      { text: 'Скидки! ' },
      { text: 'Подробнее об акции', url: 'https://example.kz/akciya?a=1' },
      { text: ' — до пятницы.' },
    ]);
  });

  it('supports Kazakh and Unicode labels and Unicode URLs, and a label that alone is the whole text', () => {
    expect(splitLinks('[Толығырақ — акция туралы](https://пример.рф/страница)')).toEqual([{ text: 'Толығырақ — акция туралы', url: 'https://пример.рф/страница' }]);
  });

  it('keeps every other character and line break byte for byte', () => {
    const text = 'Строка 1\n\n[Ссылка](https://a.kz/1)\nСтрока 3 *жирный* _курсив_ [не ссылка]\n';
    const joined = splitLinks(text).map(segment => segment.text).join('');
    expect(joined).toBe(text.replace('(https://a.kz/1)', '').replace('[Ссылка]', 'Ссылка'));
    expect(named(text)).toEqual([{ text: 'Ссылка', url: 'https://a.kz/1' }]);
  });

  it('finds several named links in one paragraph, mixed with bare links', () => {
    const text = 'Смотри [акцию](https://a.kz/1), [условия](http://b.kz/2) и https://c.kz/3, а также www.d.kz.';
    expect(named(text)).toEqual([
      { text: 'акцию', url: 'https://a.kz/1' },
      { text: 'условия', url: 'http://b.kz/2' },
      { text: 'https://c.kz/3', url: 'https://c.kz/3' },
      { text: 'www.d.kz', url: 'https://www.d.kz' },
    ]);
  });

  it('normalises www. and the scheme in the hidden URL, like bare links', () => {
    expect(named('[сайт](www.Example.com/A)')[0]?.url).toBe('https://www.Example.com/A');
    expect(named('[сайт](HTTPS://EXAMPLE.com/Path)')[0]?.url).toBe('https://EXAMPLE.com/Path');
  });

  it('a URL inside the label does not create a second, nested link', () => {
    expect(splitLinks('[https://shown.kz/x](https://real.kz/y)')).toEqual([{ text: 'https://shown.kz/x', url: 'https://real.kz/y' }]);
    expect(splitLinks('[смотри www.a.kz тут](https://b.kz)')).toEqual([{ text: 'смотри www.a.kz тут', url: 'https://b.kz' }]);
  });

  it('keeps balanced parentheses inside the URL and ends at the matching one', () => {
    expect(named('Читать: [статья](https://a.kz/wiki/Foo_(bar)).')).toEqual([{ text: 'статья', url: 'https://a.kz/wiki/Foo_(bar)' }]);
    expect(splitLinks('([статья](https://a.kz/x))')).toEqual([{ text: '(' }, { text: 'статья', url: 'https://a.kz/x' }, { text: ')' }]);
  });

  it('allows a long label (up to 300 chars) and rejects a longer one as plain text', () => {
    const ok = 'а'.repeat(300);
    expect(named(`[${ok}](https://a.kz)`)).toHaveLength(1);
    const tooLong = `[${ok}а](https://a.kz)`;
    expect(named(tooLong).map(segment => segment.text)).toEqual(['https://a.kz']);
  });

  it.each([
    '[текст](javascript:alert(1))',
    '[текст](JAVASCRIPT:alert(1))',
    '[текст](data:text/html,<script>alert(1)</script>)',
    '[текст](file:///etc/passwd)',
    '[текст](intent://scan/#Intent;scheme=zxing;end)',
    '[текст](tel:+77001234567)',
    '[текст](mailto:a@b.kz)',
    '[текст](ftp://a.kz/f)',
    '[текст](market://details?id=x)',
    '[текст](vbscript:msgbox(1))',
    '[текст](//evil.example/x)',
    '[текст](/relative/path)',
    '[текст](a.kz)',
    '[текст](https://user:pass@evil.example/)',
    '[текст](https://localhost/x)',
  ])('never links a forbidden or malformed target, the markup stays visible as text: %s', text => {
    expect(hasLinks(text)).toBe(false);
    expect(splitLinks(text)).toEqual([{ text }]);
  });

  it.each([
    ['[текст](https://a.kz', 'unfinished: no closing parenthesis'],
    ['[текст](', 'unfinished: empty URL'],
    ['[текст]', 'no URL part'],
    ['[текст] (https://a.kz)', 'space between ] and ('],
    ['[](https://a.kz)', 'empty label'],
    ['[   ](https://a.kz)', 'blank label'],
    ['[a\nb](https://a.kz)', 'label with a line break'],
    ['[текст]( https://a.kz )', 'space inside the parentheses'],
    ['[текст](https://a.kz/x y)', 'space inside the URL'],
    ['[текст](https://a.kz/<x>)', 'angle brackets in the URL'],
    ['[a\u202eb](https://a.kz)', 'bidi override in the label'],
    ['[a\u0007b](https://a.kz)', 'control character in the label'],
  ])('invalid markup is shown as text, no label link is made and nothing is lost: %s (%s)', (text) => {
    const result = splitLinks(text);
    expect(result.map(segment => segment.text).join('')).toBe(text);
    // Only a literal bare http(s) URL inside the broken markup may still be a link, exactly as before; never a hidden-URL link.
    for (const segment of result) {
      if (segment.url) expect(segment.text).toMatch(/^https?:\/\//);
    }
  });

  it('a stray bracket before a valid link does not hide it', () => {
    expect(named('[a [b](https://a.kz)')).toEqual([{ text: 'b', url: 'https://a.kz' }]);
    expect(splitLinks('[ [Ссылка](https://a.kz) ]')).toEqual([{ text: '[ ' }, { text: 'Ссылка', url: 'https://a.kz' }, { text: ' ]' }]);
  });

  it('unfinished markup before a later valid one leaves both correct', () => {
    expect(splitLinks('[нет] а вот [да](https://a.kz/ok)')).toEqual([{ text: '[нет] а вот ' }, { text: 'да', url: 'https://a.kz/ok' }]);
  });

  // Correctness on large and hostile input: never throws, never loses or reorders text, never makes a link that is not a real http(s) URL.
  const HOSTILE: [string, string][] = [
    ['"[" x50000', '['.repeat(50_000)],
    ['"[a](" x20000', '[a]('.repeat(20_000)],
    ['"[" + 100k letters, unfinished', `[${'a'.repeat(100_000)}`],
    ['"[x](" + "(" x50000', `[x](${'('.repeat(50_000)}`],
    ['named link with a 100k URL', `[x](https://a.kz/${'a'.repeat(100_000)})`],
    ['"www." x20000', 'www.'.repeat(20_000)],
    ['"[x](" x5000 + real URL', `${'[x]('.repeat(5_000)}https://a.kz)`],
    ['"[a](www." x20000', '[a](www.'.repeat(20_000)],
    ['"[a](https://( " x20000 with spaces', '[a](https://( '.repeat(20_000)],
    ['promotion limit (4000): "[a](" x1000', '[a]('.repeat(1_000)],
    ['notification limit (2000): "[" x2000', '['.repeat(2_000)],
  ];

  it.each(HOSTILE)('large or hostile input is parsed correctly: %s', (_name, input) => {
    const result = splitLinks(input);
    for (const segment of result) {
      if (segment.url) expect(segment.url).toMatch(/^https?:\/\/\S+$/);
    }
    // A hidden-URL link replaces `[label](url)` by `label`; every other character must survive in order.
    const named = result.filter(segment => segment.url !== undefined && !/^(?:https?:\/\/|www\.)/i.test(segment.text));
    if (named.length === 0) expect(result.map(segment => segment.text).join('')).toBe(input);
  });

  it('an over-long hidden URL (> 2048 chars) does not become a named link; the text is kept intact', () => {
    const long = `[текст](https://a.kz/${'a'.repeat(2100)})`;
    const result = splitLinks(long);
    expect(result.map(segment => segment.text).join('')).toBe(long);
    // No link carries the label: a plain URL inside the broken markup may stay clickable by the old rules.
    expect(result.filter(segment => segment.url !== undefined && segment.text === 'текст')).toEqual([]);
    const ok = splitLinks(`[текст](https://a.kz/${'a'.repeat(2000)})`);
    expect(ok).toEqual([{ text: 'текст', url: `https://a.kz/${'a'.repeat(2000)}` }]);
  });

  it('a hidden URL is only started by http://, https:// or www. (checked before any long scan)', () => {
    expect(splitLinks('[a](ftp://x.kz)')).toEqual([{ text: '[a](ftp://x.kz)' }]);
    expect(splitLinks('[a](((((((((((')).toEqual([{ text: '[a](((((((((((' }]);
    expect(splitLinks('[a](WWW.x.kz)')).toEqual([{ text: 'a', url: 'https://WWW.x.kz' }]);
  });
});

// Parsing cost is measured by `scripts/bench-links.js` (a report, not a pass/fail Jest check). Jest only checks correctness above.

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

describe('named links in components', () => {
  afterEach(() => { jest.restoreAllMocks(); });

  it('LinkedText shows only the label, hides the URL, and opens the hidden URL on tap (never on render)', async () => {
    const open = spyOpen();
    mount(<LinkedText text={'Скидки до 30%. [Подробнее об акции](https://example.kz/akciya?a=1&b=2) — до пятницы.'} />);
    expect(open).not.toHaveBeenCalled();
    const link = screen.getByRole('link');
    expect(link.props.children).toBe('Подробнее об акции');
    expect(screen.queryByText(/example\.kz/)).toBeNull();
    expect(screen.queryByText(/\]\(/)).toBeNull();
    await act(async () => { fireEvent.press(link); });
    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith('https://example.kz/akciya?a=1&b=2');
  });

  it('several named links and a bare link in one paragraph each open their own URL', async () => {
    const open = spyOpen();
    mount(<LinkedText text={'[Акция](https://a.kz/1), [Условия](http://b.kz/2) и www.c.kz'} />);
    const links = screen.getAllByRole('link');
    expect(links.map(link => link.props.children)).toEqual(['Акция', 'Условия', 'www.c.kz']);
    for (const link of links) await act(async () => { fireEvent.press(link); });
    expect(open.mock.calls.map(call => call[0])).toEqual(['https://a.kz/1', 'http://b.kz/2', 'https://www.c.kz']);
  });

  it('a URL inside the label is only text: one link, opening the hidden URL', async () => {
    const open = spyOpen();
    mount(<LinkedText text="[https://shown.kz/x](https://real.kz/y)" />);
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(1);
    await act(async () => { fireEvent.press(links[0]!); });
    expect(open).toHaveBeenCalledWith('https://real.kz/y');
  });

  it('unfinished markup keeps its text; only the literal bare https://a.kz stays a link and it opens only that address', async () => {
    const open = spyOpen();
    const text = '[Нажми](javascript:alert(1)) и [ещё](https://a.kz';
    mount(<LinkedText text={text} />);
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0]!.props.children).toBe('https://a.kz');
    // "Нажми" and "ещё" are not links: they stay inside the plain text around the single link.
    expect(screen.queryByRole('link', { name: 'Нажми' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'ещё' })).toBeNull();
    expect(screen.getByText(/\[Нажми\]\(javascript:alert\(1\)\) и \[ещё\]\(/, { exact: false })).toBeTruthy();
    expect(open).not.toHaveBeenCalled();
    await act(async () => { fireEvent.press(links[0]!); });
    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith('https://a.kz');
  });

  it('a forbidden scheme without any plain URL: no links at all, nothing is opened', () => {
    const open = spyOpen();
    mount(<LinkedText text="[Нажми](javascript:alert(1)) и [ещё](data:text/html,hi) и [файл](file:///etc/passwd)" />);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.getByText('[Нажми](javascript:alert(1)) и [ещё](data:text/html,hi) и [файл](file:///etc/passwd)')).toBeTruthy();
    expect(open).not.toHaveBeenCalled();
  });

  it.each([['ru', ru.linkOpenFailed], ['kz', kz.linkOpenFailed]] as const)('an open error of a named link shows the %s message and does not crash', async (language, message) => {
    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('No Activity found'));
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mount(<LinkedText text="[Подробнее](https://a.kz)" />, { language });
    await act(async () => { fireEvent.press(screen.getByRole('link')); });
    expect(alert).toHaveBeenCalledTimes(1);
    expect(alert.mock.calls[0]![1]).toBe(message);
  });

  it.each([['light', lightColors], ['dark', darkColors]] as const)('a named link is underlined, uses the readable accent and a link role (%s)', (theme, colors) => {
    mount(<LinkedText text="[Подробнее об акции](https://a.kz/x)" />, { theme });
    const link = screen.getByRole('link');
    expect(link.props.accessibilityRole).toBe('link');
    const style = flat(link);
    expect(style.textDecorationLine).toBe('underline');
    expect(style.color).toBe(colors.primaryText);
  });

  it('a long label wraps inside the same Text: it is one nested Text, no truncation props', () => {
    const label = 'Очень длинная подпись ссылки '.repeat(8).trim();
    mount(<LinkedText text={`[${label}](https://a.kz)`} />);
    const link = screen.getByRole('link');
    expect(link.props.children).toBe(label);
    expect(link.props.numberOfLines).toBeUndefined();
  });

  it('notification: the card is not one accessible element; the named link is reachable and opens the hidden URL', async () => {
    const open = spyOpen();
    setNotifications([notification({ body: 'Новая акция! [Подробнее об акции](https://a.kz/promo)' })]);
    mount(<NotificationsScreen />);
    const link = screen.getByRole('link');
    expect(link.props.children).toBe('Подробнее об акции');
    expect(screen.queryByText(/a\.kz/)).toBeNull();
    expect(screen.getByLabelText(`${ru.newBadge}. Акция`)).toBeTruthy();
    expect(open).not.toHaveBeenCalled();
    await act(async () => { fireEvent.press(link); });
    expect(open).toHaveBeenCalledWith('https://a.kz/promo');
  });

  it('notification with forbidden markup stays one accessible card with the old label', () => {
    setNotifications([notification({ body: '[Нажми](javascript:alert(1))' })]);
    mount(<NotificationsScreen />);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.getByLabelText(`${ru.newBadge}. Акция. [Нажми](javascript:alert(1))`)).toBeTruthy();
  });

  it('promotion description: a named link opens the hidden URL in both themes', async () => {
    for (const theme of ['light', 'dark'] as const) {
      const open = spyOpen();
      mockUsePromotion.mockReturnValue({ data: { id: 'promo-1', business_id: null, kind: 'offer', title: 'Акция', subtitle: 'Подзаголовок', badge: null, body: 'Условия.\n[Подробнее об акции](https://a.kz/terms)', image_url: null, starts_at: null, ends_at: null, is_new: false }, isPending: false, isError: false, error: null, refetch: jest.fn() });
      const view = mount(<PromotionDetail />, { theme });
      const link = screen.getByRole('link');
      expect(link.props.children).toBe('Подробнее об акции');
      expect(flat(link).color).toBe((theme === 'dark' ? darkColors : lightColors).primaryText);
      await act(async () => { fireEvent.press(link); });
      expect(open).toHaveBeenCalledWith('https://a.kz/terms');
      view.unmount();
    }
  });
});
