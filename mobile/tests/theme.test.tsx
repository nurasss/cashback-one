import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Appearance, StyleSheet, Text, View } from 'react-native';
import type { ReactElement } from 'react';
import SettingsScreen from '../app/(app)/settings';
import { Button, EmptyState, ErrorNotice, NoCardNotice } from '../src/components/ui';
import { TabBar } from '../src/components/TabBar';
import { DynamicQr, QR_QUIET_ZONE } from '../src/features/DynamicQr';
import { FieldSheet } from '../src/features/profile';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { ApiError } from '../src/api/errors';
import { clearAppCache } from '../src/storage/appCache';
import { parseThemePreference, THEME_STORAGE_KEY } from '../src/storage/themePreference';
import { darkColors, lightColors, mixWithWhite } from '../src/theme';
import { ThemeProvider, useTheme } from '../src/theme/ThemeProvider';

jest.mock('react-native-safe-area-context', () => {
  const { View: RNView } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: RNView, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('expo-router', () => ({ router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true } }));
const mockQrProps = jest.fn();
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text: RNText } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr(props: { value: string }) {
    mockQrProps(props);
    return React.createElement(RNText, { testID: 'qr-payload' }, props.value);
  };
});

const colorScheme = jest.requireMock<{ default: jest.Mock }>('react-native/Libraries/Utilities/useColorScheme').default;
type FlatStyle = { color?: string; backgroundColor?: string; width?: number };
const flat = (node: { props: { style?: unknown } }): FlatStyle => (StyleSheet.flatten(node.props.style as never) ?? {}) as FlatStyle;

function luminance(hex: string): number {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

function Harness({ children, language = 'ru', initial }: { children: ReactElement; language?: 'ru' | 'kz'; initial?: 'light' | 'dark' | 'system' }) {
  return <ThemeProvider initialPreference={initial}><I18nProvider initial={language}>{children}</I18nProvider></ThemeProvider>;
}

beforeEach(async () => {
  jest.restoreAllMocks();
  mockQrProps.mockClear();
  colorScheme.mockReturnValue('light');
  await AsyncStorage.clear();
});

describe('theme preference storage', () => {
  it('defaults to light for absent or damaged values', () => {
    expect(parseThemePreference(null)).toBe('light');
    expect(parseThemePreference(undefined)).toBe('light');
    expect(parseThemePreference('')).toBe('light');
    expect(parseThemePreference('{"x":1}')).toBe('light');
    expect(parseThemePreference('DARK')).toBe('light');
    expect(parseThemePreference(42)).toBe('light');
    expect(parseThemePreference('light')).toBe('light');
    expect(parseThemePreference('dark')).toBe('dark');
    expect(parseThemePreference('system')).toBe('system');
  });

  function Probe() {
    const { scheme, preference } = useTheme();
    return <Text testID="probe">{`${preference}/${scheme}`}</Text>;
  }

  it('existing users without a stored choice get the light theme', async () => {
    render(<Harness><Probe /></Harness>);
    await waitFor(() => expect(screen.getByTestId('probe').props.children).toBe('light/light'));
  });

  it('restores the stored choice on launch', async () => {
    await AsyncStorage.setItem(THEME_STORAGE_KEY, 'dark');
    render(<Harness><Probe /></Harness>);
    await waitFor(() => expect(screen.getByTestId('probe').props.children).toBe('dark/dark'));
  });

  it('a damaged stored value falls back to light', async () => {
    await AsyncStorage.setItem(THEME_STORAGE_KEY, '{broken');
    render(<Harness><Probe /></Harness>);
    await waitFor(() => expect(screen.getByTestId('probe').props.children).toBe('light/light'));
  });

  it('a read error falls back to light and does not crash', async () => {
    jest.spyOn(AsyncStorage, 'getItem').mockRejectedValueOnce(new Error('storage down'));
    render(<Harness><Probe /></Harness>);
    await waitFor(() => expect(screen.getByTestId('probe').props.children).toBe('light/light'));
  });

  it('a write error does not crash and the choice still applies in this session', async () => {
    jest.spyOn(AsyncStorage, 'setItem').mockRejectedValueOnce(new Error('disk full'));
    function Switch() { const { setPreference } = useTheme(); return <Text testID="go" onPress={() => setPreference('dark')}>go</Text>; }
    render(<Harness><View><Probe /><Switch /></View></Harness>);
    await waitFor(() => expect(screen.getByTestId('probe')).toBeTruthy());
    fireEvent.press(screen.getByTestId('go'));
    await waitFor(() => expect(screen.getByTestId('probe').props.children).toBe('dark/dark'));
  });

  it('does not block the first frame forever when storage never answers', async () => {
    jest.useFakeTimers();
    try {
      jest.spyOn(AsyncStorage, 'getItem').mockReturnValueOnce(new Promise(() => {}));
      render(<Harness><Probe /></Harness>);
      expect(screen.queryByTestId('probe')).toBeNull();
      await act(async () => { jest.advanceTimersByTime(2000); });
      expect(screen.getByTestId('probe').props.children).toBe('light/light');
    } finally { jest.useRealTimers(); }
  });

  it('the choice survives logout / cache invalidation: it is not part of the app cache', async () => {
    await AsyncStorage.setItem(THEME_STORAGE_KEY, 'dark');
    await AsyncStorage.setItem('cashback-one.cache.v1:user:u:promotions', '{}');
    await clearAppCache();
    expect(await AsyncStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(await AsyncStorage.getItem('cashback-one.cache.v1:user:u:promotions')).toBeNull();
  });
});

describe('late storage read after the loading timeout', () => {
  function Probe() {
    const { scheme, preference, setPreference } = useTheme();
    return <View>
      <Text testID="probe">{`${preference}/${scheme}`}</Text>
      <Text testID="pick-light" onPress={() => setPreference('light')}>l</Text>
      <Text testID="pick-dark" onPress={() => setPreference('dark')}>d</Text>
      <Text testID="pick-system" onPress={() => setPreference('system')}>s</Text>
    </View>;
  }

  function deferredRead() {
    let resolve!: (value: string | null) => void;
    const promise = new Promise<string | null>(res => { resolve = res; });
    jest.spyOn(AsyncStorage, 'getItem').mockReturnValueOnce(promise);
    return resolve;
  }

  async function openAfterTimeout() {
    const resolveRead = deferredRead();
    const view = render(<Harness><Probe /></Harness>);
    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(screen.getByTestId('probe').props.children).toBe('light/light');
    return { resolveRead, view };
  }

  beforeEach(() => { jest.useFakeTimers(); });
  afterEach(() => { jest.useRealTimers(); });

  it('an explicit "light" is not overwritten by an old stored "dark" that arrives later', async () => {
    const { resolveRead } = await openAfterTimeout();
    fireEvent.press(screen.getByTestId('pick-light'));
    await act(async () => { resolveRead('dark'); });
    expect(screen.getByTestId('probe').props.children).toBe('light/light');
    await act(async () => { jest.advanceTimersByTime(50); });
    expect(screen.getByTestId('probe').props.children).toBe('light/light');
    expect(await AsyncStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('dark chosen and then light chosen: the later explicit choice wins over the late stored dark', async () => {
    const { resolveRead } = await openAfterTimeout();
    fireEvent.press(screen.getByTestId('pick-dark'));
    fireEvent.press(screen.getByTestId('pick-light'));
    await act(async () => { resolveRead('dark'); });
    expect(screen.getByTestId('probe').props.children).toBe('light/light');
  });

  it('an explicit "dark" is not overwritten by a late stored "light"', async () => {
    const { resolveRead } = await openAfterTimeout();
    fireEvent.press(screen.getByTestId('pick-dark'));
    await act(async () => { resolveRead('light'); });
    expect(screen.getByTestId('probe').props.children).toBe('dark/dark');
  });

  it('an explicit "system" is not overwritten by a late stored "dark"', async () => {
    colorScheme.mockReturnValue('light');
    const { resolveRead } = await openAfterTimeout();
    fireEvent.press(screen.getByTestId('pick-system'));
    await act(async () => { resolveRead('dark'); });
    expect(screen.getByTestId('probe').props.children).toBe('system/light');
  });

  it('without any explicit choice the late stored value still applies', async () => {
    const { resolveRead } = await openAfterTimeout();
    await act(async () => { resolveRead('dark'); });
    expect(screen.getByTestId('probe').props.children).toBe('dark/dark');
  });

  it('a read that finishes after unmount changes nothing and does not touch the state or the storage', async () => {
    const setItem = jest.spyOn(AsyncStorage, 'setItem');
    setItem.mockClear(); // the AsyncStorage mock keeps calls from earlier tests
    const errors = jest.spyOn(console, 'error').mockImplementation(() => {});
    const { resolveRead, view } = await openAfterTimeout();
    view.unmount();
    await act(async () => { resolveRead('dark'); });
    expect(setItem).not.toHaveBeenCalled();
    expect(errors).not.toHaveBeenCalled();
  });
});

describe('Settings screen', () => {
  it('already open screen switches theme immediately, persists the choice and syncs native surfaces', async () => {
    const setScheme = jest.spyOn(Appearance, 'setColorScheme').mockImplementation(() => {});
    render(<Harness initial="light"><SettingsScreen /></Harness>);
    const title = screen.getByText(ru.themeTitle);
    expect(flat(title).color).toBe(lightColors.text);

    fireEvent.press(screen.getByRole('radio', { name: ru.themeDark }));
    expect(flat(screen.getByText(ru.themeTitle)).color).toBe(darkColors.text);
    expect(screen.getByRole('radio', { name: ru.themeDark }).props.accessibilityState.selected).toBe(true);
    expect(screen.getByRole('radio', { name: ru.themeLight }).props.accessibilityState.selected).toBe(false);
    await waitFor(() => expect(AsyncStorage.getItem(THEME_STORAGE_KEY)).resolves.toBe('dark'));
    expect(setScheme).toHaveBeenLastCalledWith('dark');

    fireEvent.press(screen.getByRole('radio', { name: ru.themeLight }));
    expect(flat(screen.getByText(ru.themeTitle)).color).toBe(lightColors.text);
    expect(setScheme).toHaveBeenLastCalledWith('light');
  });

  it('offers the three options in Russian and Kazakh', () => {
    const view = render(<Harness language="kz" initial="light"><SettingsScreen /></Harness>);
    expect(screen.getByText(kz.themeTitle)).toBeTruthy();
    for (const label of [kz.themeLight, kz.themeDark, kz.themeSystem]) expect(screen.getByRole('radio', { name: label })).toBeTruthy();
    view.unmount();
    render(<Harness initial="light"><SettingsScreen /></Harness>);
    for (const label of [ru.themeLight, ru.themeDark, ru.themeSystem]) expect(screen.getByRole('radio', { name: label })).toBeTruthy();
  });

  it('"As on device" follows the system theme live and passes `unspecified` to the native layer', async () => {
    const setScheme = jest.spyOn(Appearance, 'setColorScheme').mockImplementation(() => {});
    colorScheme.mockReturnValue('light');
    const view = render(<Harness initial="system"><SettingsScreen /></Harness>);
    expect(flat(screen.getByText(ru.themeTitle)).color).toBe(lightColors.text);
    expect(setScheme).toHaveBeenLastCalledWith('unspecified');

    colorScheme.mockReturnValue('dark');
    view.rerender(<Harness initial="system"><SettingsScreen /></Harness>);
    await waitFor(() => expect(flat(screen.getByText(ru.themeTitle)).color).toBe(darkColors.text));

    colorScheme.mockReturnValue('light');
    view.rerender(<Harness initial="system"><SettingsScreen /></Harness>);
    await waitFor(() => expect(flat(screen.getByText(ru.themeTitle)).color).toBe(lightColors.text));
  });

  it('an explicit light/dark choice ignores the system theme', () => {
    colorScheme.mockReturnValue('dark');
    render(<Harness initial="light"><SettingsScreen /></Harness>);
    expect(flat(screen.getByText(ru.themeTitle)).color).toBe(lightColors.text);
  });
});

describe('open modal and shared components follow the theme', () => {
  it('a bottom sheet that is already open recolours when the theme changes', () => {
    function Switch() { const { setPreference } = useTheme(); return <Text testID="go" onPress={() => setPreference('dark')}>go</Text>; }
    render(<Harness initial="light"><View><Switch /><FieldSheet title="Город" initial="" onDone={jest.fn()} onClose={jest.fn()} /></View></Harness>);
    expect(flat(screen.getByText('Город')).color).toBe(lightColors.text);
    fireEvent.press(screen.getByTestId('go'));
    expect(flat(screen.getByText('Город')).color).toBe(darkColors.text);
  });

  it('no-card notice, empty and error states are readable on dark surfaces', () => {
    render(<Harness initial="dark"><View><NoCardNotice /><EmptyState icon="gift" title="Пусто" /><ErrorNotice error={new ApiError('NETWORK_ERROR')} /></View></Harness>);
    const notice = screen.getByTestId('no-card-notice');
    expect(flat(notice).backgroundColor).toBe(darkColors.surface);
    expect(flat(screen.getByText(ru.noCardNotice)).color).toBe(darkColors.text);
    expect(flat(screen.getByText('Пусто')).color).toBe(darkColors.text);
    const [, errorText] = screen.getAllByRole('alert');
    expect(flat(errorText!).color).toBe(darkColors.error);
  });

  it('tab bar uses the dark surface and a lightened brand accent for the selected tab', () => {
    render(<Harness initial="dark"><TabBar active="profile" onSelect={jest.fn()} badges={{ promotions: false, notifications: 0 }} /></Harness>);
    expect(flat(screen.getByText(ru.tabProfile)).color).toBe(darkColors.primaryText);
    expect(flat(screen.getByText(ru.tabHome)).color).toBe(darkColors.muted);
  });
});

describe('destructive button', () => {
  it.each([['light', lightColors], ['dark', darkColors]] as const)('uses its own fill and label colours (%s)', (name, colors) => {
    render(<Harness initial={name}><Button destructive label="Удалить" onPress={jest.fn()} /></Harness>);
    const button = screen.getByRole('button', { name: 'Удалить' });
    expect(flat(button).backgroundColor).toBe(colors.destructive);
    expect(flat(screen.getByText('Удалить')).color).toBe(colors.onDestructive);
    expect(contrast(colors.onDestructive, colors.destructive)).toBeGreaterThanOrEqual(4.5);
  });

  it('the light look is unchanged (same red fill and white label as before)', () => {
    expect(lightColors.destructive).toBe(lightColors.error);
    expect(lightColors.onDestructive).toBe(lightColors.onPrimary);
  });
});

describe('QR code stays scannable in every theme', () => {
  it.each(['light', 'dark'] as const)('is black on an opaque white field with a quiet zone (%s)', initial => {
    render(<Harness initial={initial}><DynamicQr value="0001234" blocked={false} /></Harness>);
    const frame = screen.getByTestId('qr-code');
    expect(flat(frame).backgroundColor).toBe('#FFFFFF');
    const props = mockQrProps.mock.calls.at(-1)![0] as { value: string; color: string; backgroundColor: string; size: number };
    expect(props.value).toBe('0001234');
    expect(props.color).toBe('#000000');
    expect(props.backgroundColor).toBe('#FFFFFF');
    expect(flat(frame).width! - props.size).toBe(QR_QUIET_ZONE * 2);
    expect(contrast(props.color, props.backgroundColor)).toBeGreaterThanOrEqual(21);
  });
});

describe('palettes', () => {
  // Third value: minimum contrast in the dark palette; fourth (optional): minimum for the unchanged light palette.
  const pairs: [string, (c: typeof lightColors) => [string, string], number, number?][] = [
    ['text on background', c => [c.text, c.background], 7],
    ['text on surface', c => [c.text, c.surface], 7],
    ['muted on surface', c => [c.muted, c.surface], 4.5],
    ['muted on background', c => [c.muted, c.background], 4.5],
    ['placeholder on input', c => [c.placeholder, c.input], 4.5],
    ['text on input', c => [c.text, c.input], 7],
    ['inactive tab icon on surface', c => [c.subtle, c.surface], 3, 1.5],
    ['brand text on surface', c => [c.primaryText, c.surface], 4.5, 3.9],
    ['brand text on soft brand', c => [c.primaryText, c.softPrimary], 3],
    ['brand text on tint', c => [c.primaryText, c.tint], 4.5, 3.5],
    ['success (accrual) on surface', c => [c.success, c.surface], 4.5, 4.3],
    ['success on soft success', c => [c.success, c.softSuccess], 3],
    ['error (redemption) on surface', c => [c.error, c.surface], 4.5],
    ['error on soft error', c => [c.error, c.softError], 3],
    ['error on error notice', c => [c.error, c.softError], 3],
    ['disabled text on disabled button', c => [c.disabledText, c.disabledBackground], 4.5],
    ['secondary disabled text', c => [c.secondaryDisabledText, c.secondaryDisabledBackground], 4.5],
    ['text on destructive button', c => [c.onDestructive, c.destructive], 4.5],
  ];
  it.each([['light', lightColors], ['dark', darkColors]] as const)('%s palette keeps text readable', (_name, colors) => {
    for (const [label, pick, darkMin, lightMin] of pairs) {
      const [fg, bg] = pick(colors);
      const min = colors === darkColors ? darkMin : lightMin ?? darkMin;
      expect({ label, ratio: contrast(fg, bg) >= min }).toEqual({ label, ratio: true });
    }
  });

  it('accrual and redemption colours are distinguishable from each other in both themes', () => {
    for (const c of [lightColors, darkColors]) {
      expect(c.success).not.toBe(c.error);
      expect(c.softSuccess).not.toBe(c.softError);
    }
  });

  it.each(['#EE1D3E', '#FA2247', '#2563EB'])('brand accent %s is lightened to stay legible as text on the dark surface', primary => {
    expect(contrast(mixWithWhite(primary, 0.25), darkColors.surface)).toBeGreaterThanOrEqual(4.5);
    expect(mixWithWhite(primary, 0)).toBe(primary.toUpperCase());
  });

  it('the brand fill colour is the same in both themes (client identity is kept)', () => {
    expect(darkColors.primary).toBe(lightColors.primary);
    expect(darkColors.onPrimary).toBe(lightColors.onPrimary);
  });
});
