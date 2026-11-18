import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { AppState, Linking, Platform } from 'react-native';
import type { ReactElement } from 'react';
import SettingsScreen from '../app/(app)/settings';
import { getClientConfig } from '../src/config/client';
import {
  getCurrentVersionCode,
  getUpdateSource,
  loadVersionInfo,
  parseVersionInfo,
  VERSION_INFO_URL,
  type UpdateSource,
} from '../src/features/appUpdate';
import { UpdateDialog, UpdateProvider } from '../src/features/UpdateNotice';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { ThemeProvider } from '../src/theme/ThemeProvider';

interface Globals { __mockExpoConfig?: { android?: { versionCode?: number }; version?: string } | null; __mockNativeBuild?: string | null }
const g = globalThis as unknown as Globals;

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    get expoConfig() {
      const v = globalThis as unknown as Globals;
      return v.__mockExpoConfig !== undefined ? v.__mockExpoConfig : { version: '1.0.16', android: { versionCode: 10 } };
    },
  },
}));
jest.mock('expo-application', () => ({
  get nativeBuildVersion() { return (globalThis as unknown as Globals).__mockNativeBuild ?? null; },
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('expo-router', () => ({ router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true } }));

const BASE = 'https://cashback-qr.poscenter.kz/app/';
const generalManifest = (code: number, version = '1.0.16', min = 1) => ({
  latest_version: version, latest_version_code: code, min_version_code: min, download_url: `${BASE}cashback-one-${version}.apk`,
});
const keremetManifest = (code: number, version = '1.0.16', min = 1) => ({
  latest_version: version, latest_version_code: code, min_version_code: min, download_url: `${BASE}keremet-cashback-${version}.apk`,
});
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as never;

const originalClient = process.env.EXPO_PUBLIC_CLIENT;
const originalPlatform = Platform.OS;
function useClient(slug: string | undefined) {
  if (slug === undefined) delete process.env.EXPO_PUBLIC_CLIENT; else process.env.EXPO_PUBLIC_CLIENT = slug;
}

beforeEach(() => {
  g.__mockExpoConfig = undefined;
  g.__mockNativeBuild = null;
  Platform.OS = 'android';
  jest.spyOn(AppState, 'addEventListener').mockImplementation(() => ({ remove: jest.fn() }) as never);
});
afterEach(() => {
  useClient(originalClient);
  Platform.OS = originalPlatform;
  g.__mockExpoConfig = undefined;
  g.__mockNativeBuild = null;
  jest.restoreAllMocks();
});

describe('update source per client', () => {
  it('Cashback One keeps the shared manifest and its own APK name', () => {
    useClient('cashbackone');
    expect(getUpdateSource()).toEqual({ slug: 'cashbackone', manifestUrl: `${BASE}version.json`, apkName: 'cashback-one' });
    expect(getUpdateSource()!.manifestUrl).toBe(VERSION_INFO_URL);
    useClient(undefined);
    expect(getUpdateSource()!.manifestUrl).toBe(VERSION_INFO_URL);
  });

  it('Keremet reads its own manifest and APK name', () => {
    useClient('keremet');
    expect(getUpdateSource()).toEqual({ slug: 'keremet', manifestUrl: `${BASE}keremet-version.json`, apkName: 'keremet-cashback' });
  });

  it('a new client without explicit fields derives both from its slug, never from the shared manifest', () => {
    useClient('example');
    expect(getUpdateSource()).toEqual({ slug: 'example', manifestUrl: `${BASE}example-version.json`, apkName: 'example' });
  });

  it('an explicit update_manifest in the client config wins', () => {
    expect(getUpdateSource({ ...getClientConfig('keremet'), update_manifest: 'shop-version.json' })!.manifestUrl).toBe(`${BASE}shop-version.json`);
  });

  it('an invalid config (path-like manifest or bad apk name) disables checks instead of guessing', () => {
    expect(getUpdateSource({ ...getClientConfig('keremet'), update_manifest: '../version.json' })).toBeNull();
    expect(getUpdateSource({ ...getClientConfig('keremet'), update_manifest: 'a/b.json' })).toBeNull();
    expect(getUpdateSource({ ...getClientConfig('keremet'), apk_name: 'Keremet_X' })).toBeNull();
    useClient('unknown-client');
    expect(getUpdateSource()).toBeNull();
  });
});

describe('download URL is bound to the client APK', () => {
  const general = (): UpdateSource => ({ slug: 'cashbackone', manifestUrl: `${BASE}version.json`, apkName: 'cashback-one' });
  const keremet = (): UpdateSource => ({ slug: 'keremet', manifestUrl: `${BASE}keremet-version.json`, apkName: 'keremet-cashback' });

  it('each client accepts only its own APK', () => {
    expect(parseVersionInfo(generalManifest(17), general())).not.toBeNull();
    expect(parseVersionInfo(keremetManifest(17), keremet())).not.toBeNull();
    expect(parseVersionInfo(keremetManifest(17), general())).toBeNull();
    expect(parseVersionInfo(generalManifest(17), keremet())).toBeNull();
  });

  it('rejects lookalike names, other origins, schemes, paths and test builds', () => {
    const bad = [
      `${BASE}keremet-cashback-1.0.16.apk.exe`,
      `${BASE}keremet-cashback-1.0.16-test.apk`,
      `${BASE}x-keremet-cashback-1.0.16.apk`,
      `${BASE}sub/keremet-cashback-1.0.16.apk`,
      `${BASE}../keremet-cashback-1.0.16.apk`,
      'http://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.16.apk',
      'https://cashback-qr.poscenter.kz.evil.example/app/keremet-cashback-1.0.16.apk',
      'https://evil.example/app/keremet-cashback-1.0.16.apk',
      'https://user@cashback-qr.poscenter.kz/app/keremet-cashback-1.0.16.apk',
      `${BASE}keremet-cashback-1.0.16.apk?x=1`,
    ];
    for (const download_url of bad) expect({ download_url, accepted: parseVersionInfo({ ...keremetManifest(17), download_url }, keremet()) !== null }).toEqual({ download_url, accepted: false });
  });

  it('keeps the old manifest format: the same four fields, nothing else required', () => {
    expect(parseVersionInfo({ latest_version: '1.0.10', latest_version_code: 11, min_version_code: 1, download_url: `${BASE}cashback-one-1.0.10.apk` }, general()))
      .toEqual({ latest_version: '1.0.10', latest_version_code: 11, min_version_code: 1, download_url: `${BASE}cashback-one-1.0.10.apk` });
  });
});

describe('loadVersionInfo', () => {
  it('Keremet requests only its manifest and never falls back to the shared one on failure', async () => {
    useClient('keremet');
    const fetcher = jest.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
    expect(await loadVersionInfo(fetcher as never)).toEqual({ ok: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0]![0]).toBe(`${BASE}keremet-version.json`);
  });

  it('Keremet does not accept the shared manifest content even if served at its own URL', async () => {
    useClient('keremet');
    expect(await loadVersionInfo(jest.fn().mockResolvedValue(ok(generalManifest(99))) as never)).toEqual({ ok: false });
  });

  it('Cashback One requests the shared manifest', async () => {
    useClient('cashbackone');
    const fetcher = jest.fn().mockResolvedValue(ok(generalManifest(11, '1.0.10')));
    const result = await loadVersionInfo(fetcher as never);
    expect(result.ok).toBe(true);
    expect(fetcher.mock.calls[0]![0]).toBe(VERSION_INFO_URL);
  });

  it('tells an error apart from a valid answer (network error, HTML, invalid manifest)', async () => {
    useClient('cashbackone');
    expect(await loadVersionInfo(jest.fn().mockRejectedValue(new Error('offline')) as never)).toEqual({ ok: false });
    expect(await loadVersionInfo(jest.fn().mockResolvedValue({ ok: true, json: async () => { throw new SyntaxError('html'); } }) as never)).toEqual({ ok: false });
    expect(await loadVersionInfo(jest.fn().mockResolvedValue(ok({ nope: true })) as never)).toEqual({ ok: false });
  });
});

describe('getCurrentVersionCode source', () => {
  it('prefers the installed package versionCode over the app.json value', () => {
    g.__mockExpoConfig = { android: { versionCode: 10 } };
    g.__mockNativeBuild = '17';
    expect(getCurrentVersionCode()).toBe(17);
  });

  it('falls back to the embedded config when the native value is missing or not a number', () => {
    g.__mockExpoConfig = { android: { versionCode: 10 } };
    g.__mockNativeBuild = null;
    expect(getCurrentVersionCode()).toBe(10);
    g.__mockNativeBuild = 'mock';
    expect(getCurrentVersionCode()).toBe(10);
    g.__mockNativeBuild = '0';
    expect(getCurrentVersionCode()).toBe(10);
  });

  it('is null when neither source has a valid code', () => {
    g.__mockExpoConfig = null;
    expect(getCurrentVersionCode()).toBeNull();
  });
});

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(<ThemeProvider initialPreference="light"><I18nProvider initial={language}>{element}</I18nProvider></ThemeProvider>);
}
const app = (language: 'ru' | 'kz' = 'ru') => mount(<UpdateProvider><SettingsScreen /><UpdateDialog /></UpdateProvider>, language);
const press = async () => { await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.checkUpdates })); }); };

describe('manual update check in Settings', () => {
  beforeEach(() => { useClient('keremet'); g.__mockExpoConfig = { version: '1.0.16', android: { versionCode: 17 } }; });

  it('shows the app version next to the check button', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    app();
    expect(screen.getByTestId('settings-version').props.children).toBe('Версия 1.0.16');
    expect(screen.getByRole('button', { name: ru.checkUpdates })).toBeTruthy();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });

  it('reports "up to date" only after a successful request that finds the same version', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    app();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId('update-status')).toBeNull();
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateUpToDate));
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls.every(call => call[0] === `${BASE}keremet-version.json`)).toBe(true);
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
  });

  it('treats an older server version as up to date too', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(16, '1.0.15')));
    app();
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateUpToDate));
  });

  it('announces a newer version and shows the dialog with the download link', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(18, '1.0.17')));
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    app();
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateAvailable.replace('{version}', '1.0.17')));
    const updateButton = await screen.findByText(ru.updateNow);
    await act(async () => { fireEvent.press(updateButton); });
    expect(open).toHaveBeenCalledWith(`${BASE}keremet-cashback-1.0.17.apk`);
    await waitFor(() => expect(screen.queryByText(ru.updateTitle)).toBeNull());
  });

  it.each([
    ['network error', () => Promise.reject(new Error('offline'))],
    ['HTTP 500', () => Promise.resolve({ ok: false, status: 500, json: async () => ({}) })],
    ['invalid JSON', () => Promise.resolve({ ok: true, status: 200, json: async () => { throw new SyntaxError('bad'); } })],
    ['foreign APK in manifest', () => Promise.resolve(ok(generalManifest(99)))],
  ])('shows an error, never "up to date", on %s', async (_label, respond) => {
    jest.spyOn(global, 'fetch').mockImplementation(respond as never);
    app();
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateCheckFailed));
    expect(screen.queryByText(ru.updateUpToDate)).toBeNull();
  });

  it('a later successful check replaces the earlier error', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('offline')).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(ok(keremetManifest(17)));
    app();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateCheckFailed));
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateUpToDate));
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });

  it('is not limited by the six-hour automatic interval', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    app();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateUpToDate));
    await press();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(3));
  });

  it('shows an optional update again after "Later" when the user checks manually', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(18, '1.0.17')));
    app();
    fireEvent.press(await screen.findByText(ru.updateLater));
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
    await press();
    expect(await screen.findByText(ru.updateTitle)).toBeTruthy();
  });

  it('the required mode is still decided by min_version_code (mock only; production is never switched on here)', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(20, '1.0.20', 18)));
    app();
    expect(await screen.findByText(ru.updateRequiredBody)).toBeTruthy();
    expect(screen.queryByText(ru.updateLater)).toBeNull();
  });

  it('texts exist in Kazakh', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    app('kz');
    await act(async () => { fireEvent.press(screen.getByRole('button', { name: kz.checkUpdates })); });
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(kz.updateUpToDate));
  });

  it('hides the check on web and iOS and in demo, where updates are not supported', () => {
    Platform.OS = 'ios';
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    app();
    expect(screen.queryByRole('button', { name: ru.checkUpdates })).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('works without the provider too (standalone Settings), with no automatic dialog', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(ok(keremetManifest(17)));
    mount(<SettingsScreen />);
    expect(fetchSpy).not.toHaveBeenCalled();
    await press();
    await waitFor(() => expect(screen.getByTestId('update-status').props.children).toBe(ru.updateUpToDate));
  });
});

describe('dialog in the dark theme', () => {
  it('uses dark surface, text and overlay colours', async () => {
    useClient('cashbackone');
    g.__mockExpoConfig = { version: '1.0.9', android: { versionCode: 10 } };
    jest.spyOn(global, 'fetch').mockResolvedValue(ok(generalManifest(11, '1.0.10')));
    render(<ThemeProvider initialPreference="dark"><I18nProvider initial="ru"><UpdateProvider><UpdateDialog /></UpdateProvider></I18nProvider></ThemeProvider>);
    const title = await screen.findByText(ru.updateTitle);
    const { StyleSheet } = jest.requireActual<typeof import('react-native')>('react-native');
    const { darkColors } = jest.requireActual<typeof import('../src/theme')>('../src/theme');
    expect(StyleSheet.flatten(title.props.style).color).toBe(darkColors.text);
    expect(StyleSheet.flatten(screen.getByText(ru.updateBody).props.style).color).toBe(darkColors.muted);
  });
});
