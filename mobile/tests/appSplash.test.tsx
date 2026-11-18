import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { AccessibilityInfo, BackHandler, Linking } from 'react-native';
import * as clientConfig from '../src/config/client';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import { kz } from '../src/i18n/kz';
import { AppSplash, IMAGE_SHOW_MS, MEDIA_LOAD_TIMEOUT_MS, SPLASH_FADE_OUT_MS, resetSplashForTests } from '../src/features/splash/AppSplash';
import { cacheKey, parseSplash, readCache, resolveSplash, SPLASH_CACHE_PREFIX } from '../src/features/splash/splashConfig';
import { isSplashActive, setSplashActive } from '../src/features/splash/splashGate';
import { Context as UpdateContext, UpdateDialog, type UpdateCheck } from '../src/features/UpdateNotice';
import { ThemeProvider } from '../src/theme/ThemeProvider';

// expo-video has no native module under Jest: a tiny fake player records what the splash does to it.
const mockPlayers: { muted: boolean; volume: number; loop: boolean; played: number; listeners: Record<string, ((payload?: unknown) => void)[]> }[] = [];
jest.mock('expo-video', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return {
    useVideoPlayer: (_source: unknown, setup?: (player: unknown) => void) => {
      const React = jest.requireActual<typeof import('react')>('react');
      const ref = React.useRef<unknown>(null);
      if (!ref.current) {
        const player = {
          muted: false, volume: 1, loop: true, played: 0, listeners: {} as Record<string, ((payload?: unknown) => void)[]>,
          play() { this.played += 1; },
          addListener(name: string, cb: (payload?: unknown) => void) { (this.listeners[name] ??= []).push(cb); return { remove: () => { this.listeners[name] = (this.listeners[name] ?? []).filter(fn => fn !== cb); } }; },
        };
        setup?.(player);
        mockPlayers.push(player);
        ref.current = player;
      }
      return ref.current;
    },
    VideoView: (props: Record<string, unknown>) => <View {...props} />,
  };
});
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }) };
});

const APP_ID = 'kz.cashbackone.keremet';
const BUSINESS = 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0';
const HEX = 'a1b2c3d4e5f60718293a4b5c6d7e8f90';
const image = (over: Record<string, unknown> = {}) => ({ enabled: true, business_id: BUSINESS, media_type: 'image', media_url: `https://api.cashback-qr.poscenter.kz/media/splashes/${HEX}.webp`, width: 1080, height: 1920, duration_seconds: null, file_size: 200_000, version: 'v1', ...over });
const video = (over: Record<string, unknown> = {}) => ({ ...image(), media_type: 'video', media_url: `https://api.cashback-qr.poscenter.kz/media/splashes/${HEX}.mp4`, duration_seconds: 4.5, file_size: 3_000_000, version: 'v2', ...over });
const disabled = { enabled: false, business_id: null, media_type: null, media_url: null, width: null, height: null, duration_seconds: null, file_size: null, version: null };
const expected = { businessId: BUSINESS };

function reply(body: unknown, { status = 200, etag = '"e1"' }: { status?: number; etag?: string | null } = {}) {
  return { status, ok: status >= 200 && status < 300, json: async () => body, headers: { get: (name: string) => (name.toLowerCase() === 'etag' ? etag : null) } };
}
let fetchMock: jest.Mock;
const originalApi = process.env.EXPO_PUBLIC_API_BASE_URL;
const originalClient = process.env.EXPO_PUBLIC_CLIENT;
beforeEach(async () => {
  process.env.EXPO_PUBLIC_API_BASE_URL = 'https://api.cashback-qr.poscenter.kz';
  process.env.EXPO_PUBLIC_CLIENT = 'keremet';
  fetchMock = jest.fn();
  (global as unknown as { fetch: jest.Mock }).fetch = fetchMock;
  await AsyncStorage.clear();
  mockPlayers.length = 0;
  resetSplashForTests();
  jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(false);
});
afterEach(() => {
  jest.restoreAllMocks();
  jest.useRealTimers();
  if (originalApi === undefined) delete process.env.EXPO_PUBLIC_API_BASE_URL; else process.env.EXPO_PUBLIC_API_BASE_URL = originalApi;
  if (originalClient === undefined) delete process.env.EXPO_PUBLIC_CLIENT; else process.env.EXPO_PUBLIC_CLIENT = originalClient;
});

describe('parseSplash: only a safe, own, in-limits splash is accepted', () => {
  it('accepts a valid image and a valid video', () => {
    expect(parseSplash(image(), expected)).toMatchObject({ mediaType: 'image', width: 1080, height: 1920, version: 'v1' });
    expect(parseSplash(video(), expected)).toMatchObject({ mediaType: 'video', durationSeconds: 4.5 });
  });
  it.each([
    ['disabled', disabled],
    ['null', null],
    ['not an object', 'x'],
    ['enabled as a string', image({ enabled: 'true' })],
    ['http media', image({ media_url: `http://api.cashback-qr.poscenter.kz/media/splashes/${HEX}.webp` })],
    ['media with a query', image({ media_url: `https://a.kz/media/splashes/${HEX}.webp?x=1` })],
    ['media with credentials', image({ media_url: `https://u:p@a.kz/media/splashes/${HEX}.webp` })],
    ['not a splash path', image({ media_url: 'https://a.kz/media/promotions/x.webp' })],
    ['javascript url', image({ media_url: 'javascript:alert(1)' })],
    ['image type with mp4 file', image({ media_url: `https://a.kz/media/splashes/${HEX}.mp4` })],
    ['video type with webp file', video({ media_url: `https://a.kz/media/splashes/${HEX}.webp` })],
    ['unknown media type', image({ media_type: 'gif' })],
    ['another business', image({ business_id: '00000000-0000-0000-0000-000000000009' })],
    ['no business', image({ business_id: null })],
    ['image above 5 MiB', image({ file_size: 5 * 1024 * 1024 + 1 })],
    ['video above 15 MiB', video({ file_size: 15 * 1024 * 1024 + 1 })],
    ['image zero file_size', image({ file_size: 0 })],
    ['image negative file_size', image({ file_size: -100 })],
    ['image non-integer file_size', image({ file_size: 50000.5 })],
    ['video longer than 5 s', video({ duration_seconds: 5.05 })],
    ['video without duration', video({ duration_seconds: null })],
    ['zero width', image({ width: 0 })],
    ['negative width', image({ width: -100 })],
    ['width exceeding 10000', image({ width: 10001 })],
    ['no version', image({ version: '' })],
  ])('rejects: %s', (_name, body) => { expect(parseSplash(body, expected)).toBeNull(); });
  it('boundaries are accepted: video exactly 5.0 s / 15 MiB, image exactly 5 MiB', () => {
    expect(parseSplash(video({ duration_seconds: 5, file_size: 15 * 1024 * 1024 }), expected)).not.toBeNull();
    expect(parseSplash(image({ file_size: 5 * 1024 * 1024 }), expected)).not.toBeNull();
  });
  it('realistic sizes > 10000 are accepted for both image and video', () => {
    expect(parseSplash(image({ file_size: 100_000 }), expected)).not.toBeNull();
    expect(parseSplash(image({ file_size: 500_000 }), expected)).not.toBeNull();
    expect(parseSplash(image({ file_size: 2_000_000 }), expected)).not.toBeNull();
    expect(parseSplash(video({ file_size: 1_000_000 }), expected)).not.toBeNull();
    expect(parseSplash(video({ file_size: 5_000_000 }), expected)).not.toBeNull();
    expect(parseSplash(video({ file_size: 10_000_000 }), expected)).not.toBeNull();
  });
  it('a client without its own business id still requires nothing more than a valid body', () => {
    expect(parseSplash(image({ business_id: BUSINESS }), { businessId: null })).not.toBeNull();
  });
});

describe('resolveSplash: ETag, cache policy and two clients', () => {
  it('first online launch asks the server without If-None-Match, stores the answer and returns it', async () => {
    fetchMock.mockResolvedValue(reply(image()));
    const result = await resolveSplash(APP_ID, expected);
    expect(result).toMatchObject({ firstCheck: true, splash: { version: 'v1' } });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(`https://api.cashback-qr.poscenter.kz/public/app-splash?app_id=${APP_ID}`);
    expect(init.headers['If-None-Match']).toBeUndefined();
    expect((await readCache(APP_ID))?.etag).toBe('"e1"');
    expect(Object.keys(await AsyncStorage.getAllKeys().then(keys => Object.fromEntries(keys.map(k => [k, 1]))))).toEqual([`${SPLASH_CACHE_PREFIX}${APP_ID}`]);
  });
  it('sends If-None-Match and keeps the stored splash on 304', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockResolvedValueOnce(reply(null, { status: 304 }));
    const result = await resolveSplash(APP_ID, expected);
    expect(fetchMock.mock.calls[1]![1].headers['If-None-Match']).toBe('"e1"');
    expect(result).toMatchObject({ firstCheck: false, splash: { version: 'v1' } });
  });
  it('a changed media (new version) replaces the stored one', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockResolvedValueOnce(reply(video(), { etag: '"e2"' }));
    expect((await resolveSplash(APP_ID, expected)).splash?.version).toBe('v2');
    expect((await readCache(APP_ID))?.splash?.mediaType).toBe('video');
  });
  it('disabled after an enabled one removes the stored splash and starts normally', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockResolvedValueOnce(reply(disabled, { etag: null }));
    expect((await resolveSplash(APP_ID, expected)).splash).toBeNull();
    expect((await readCache(APP_ID))?.splash).toBeNull();
    // Offline afterwards: the old splash must not come back.
    fetchMock.mockRejectedValueOnce(new Error('offline'));
    expect((await resolveSplash(APP_ID, expected)).splash).toBeNull();
  });
  it('an invalid (unsafe) answer is treated as disabled and clears the stored splash', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockResolvedValueOnce(reply(image({ media_url: 'http://evil.example/media/splashes/x.webp' })));
    expect((await resolveSplash(APP_ID, expected)).splash).toBeNull();
    expect((await readCache(APP_ID))?.splash).toBeNull();
  });
  it('offline with a stored splash shows the last confirmed splash of this client; offline without one is an ordinary launch', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockRejectedValueOnce(new Error('offline'));
    expect((await resolveSplash(APP_ID, expected)).splash?.version).toBe('v1');
    await AsyncStorage.clear();
    fetchMock.mockRejectedValueOnce(new Error('offline'));
    expect(await resolveSplash(APP_ID, expected)).toEqual({ splash: null, firstCheck: true });
  });
  it('an HTTP error status is not a splash and not a crash', async () => {
    fetchMock.mockResolvedValueOnce(reply({}, { status: 500 }));
    expect((await resolveSplash(APP_ID, expected)).splash).toBeNull();
  });
  it('a hanging request is cut at the time budget', async () => {
    fetchMock.mockImplementation((_url: string, init: { signal: AbortSignal }) => new Promise((_resolve, reject) => { init.signal.addEventListener('abort', () => reject(new Error('aborted'))); }));
    const started = Date.now();
    expect((await resolveSplash(APP_ID, expected, 30)).splash).toBeNull();
    expect(Date.now() - started).toBeLessThan(1500);
  });
  it('two clients never share a cache entry or a request', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockRejectedValueOnce(new Error('offline'));
    expect((await resolveSplash('kz.cashbackone.mobile', { businessId: null })).splash).toBeNull();
    expect(fetchMock.mock.calls[1]![0]).toContain('app_id=kz.cashbackone.mobile');
    expect(await readCache('kz.cashbackone.mobile')).toMatchObject({ appId: 'kz.cashbackone.mobile', splash: null });
    expect((await readCache(APP_ID))?.splash?.version).toBe('v1');
    expect(cacheKey(APP_ID)).not.toBe(cacheKey('kz.cashbackone.mobile'));
  });
});

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(<ThemeProvider initialPreference="light"><I18nProvider initial={language}>{element}</I18nProvider></ThemeProvider>);
}
const flush = async () => { await act(async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); }); };
const advance = async (ms: number) => { await act(async () => { jest.advanceTimersByTime(ms); }); await flush(); };
const fakeTimers = () => jest.useFakeTimers({ doNotFake: ['nextTick', 'setImmediate', 'queueMicrotask'] });

describe('AppSplash on a cold start', () => {
  it('disabled: an ordinary launch right after the check, nothing is shown', async () => {
    fetchMock.mockResolvedValue(reply(disabled, { etag: null }));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(isSplashActive()).toBe(false);
  });

  it('image: shown with a skip button at once, covers 2 s from the moment it is ready, covers screen', async () => {
    fakeTimers();
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />);
    await flush();
    expect(isSplashActive()).toBe(true);
    const skip = screen.getByTestId('splash-skip');
    expect(skip.props.accessibilityRole).toBe('button');
    expect(ru.splashSkip).toBe('Пропустить заставку');
    expect(skip.props.accessibilityLabel).toBe('Пропустить заставку');
    expect(screen.getByText('Пропустить заставку')).toBeTruthy();
    const media = screen.getByTestId('splash-image');
    expect(media.props.contentFit).toBe('cover');
    expect(media.props.accessibilityIgnoresInvertColors).toBe(true);
    // Before the image is ready, time passing (less than the budget) keeps the splash.
    await advance(MEDIA_LOAD_TIMEOUT_MS - 200);
    expect(screen.queryByTestId('splash-stage')).not.toBeNull();
    fireEvent(media, 'load');
    await advance(IMAGE_SHOW_MS - 100);
    expect(screen.queryByTestId('splash-stage')).not.toBeNull();
    await advance(100 + SPLASH_FADE_OUT_MS);
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(isSplashActive()).toBe(false);
  });

  it('image that does not load within the budget, or fails: ordinary launch, no frozen screen', async () => {
    fakeTimers();
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />);
    await flush();
    await advance(MEDIA_LOAD_TIMEOUT_MS + 50);
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    resetSplashForTests();
    jest.useRealTimers();
    fetchMock.mockResolvedValue(reply(image({ version: 'v3' }), { etag: '"e3"' }));
    screen.unmount();
    mount(<AppSplash />);
    await flush();
    fireEvent(screen.getByTestId('splash-image'), 'error');
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('skip ends the splash immediately', async () => {
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />);
    await flush();
    fireEvent.press(screen.getByTestId('splash-skip'));
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(isSplashActive()).toBe(false);
  });

  it('the Kazakh label is used for the skip button', async () => {
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />, 'kz');
    await flush();
    expect(kz.splashSkip).toBe('Заставканы өткізу');
    expect(screen.getByTestId('splash-skip').props.accessibilityLabel).toBe('Заставканы өткізу');
    expect(screen.getByText('Заставканы өткізу')).toBeTruthy();
  });

  it('video: muted, not looping, played; ends at the end of the file', async () => {
    fakeTimers();
    fetchMock.mockResolvedValue(reply(video()));
    mount(<AppSplash />);
    await flush();
    expect(screen.getByTestId('splash-video').props.contentFit).toBe('cover');
    expect(screen.getByTestId('splash-video').props.nativeControls).toBe(false);
    const player = mockPlayers[0]!;
    expect(player.muted).toBe(true);
    expect(player.volume).toBe(0);
    expect(player.loop).toBe(false);
    expect(player.played).toBeGreaterThan(0);
    await act(async () => { player.listeners.statusChange?.forEach(cb => cb({ status: 'readyToPlay' })); });
    await advance(1500);
    expect(screen.queryByTestId('splash-stage')).not.toBeNull();
    await act(async () => { player.listeners.playToEnd?.forEach(cb => cb()); });
    await advance(SPLASH_FADE_OUT_MS);
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('video: a player error ends it; a video that never gets ready ends within the budget; a long one is cut at 5 s', async () => {
    fakeTimers();
    fetchMock.mockResolvedValue(reply(video()));
    mount(<AppSplash />);
    await flush();
    await act(async () => { mockPlayers[0]!.listeners.statusChange?.forEach(cb => cb({ status: 'error' })); });
    expect(screen.queryByTestId('splash-stage')).toBeNull();

    resetSplashForTests(); screen.unmount();
    mount(<AppSplash />);
    await flush();
    await advance(MEDIA_LOAD_TIMEOUT_MS + 50);
    expect(screen.queryByTestId('splash-stage')).toBeNull();

    resetSplashForTests(); screen.unmount();
    mount(<AppSplash />);
    await flush();
    await act(async () => { mockPlayers[mockPlayers.length - 1]!.listeners.statusChange?.forEach(cb => cb({ status: 'readyToPlay' })); });
    await advance(4900);
    expect(screen.queryByTestId('splash-stage')).not.toBeNull();
    await advance(100 + SPLASH_FADE_OUT_MS);
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('reduced motion: a video is skipped at once in favour of the ordinary launch; an image is still shown', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
    fetchMock.mockResolvedValue(reply(video()));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    resetSplashForTests(); screen.unmount();
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-image')).not.toBeNull();
  });

  it('only one show per cold start: a second mount (tab change, foreground, link) does not show it again and does not call the server', async () => {
    fetchMock.mockResolvedValue(reply(image()));
    const first = mount(<AppSplash />);
    await flush();
    fireEvent.press(screen.getByTestId('splash-skip'));
    first.unmount();
    fetchMock.mockClear();
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('first launch offline (no cache): an ordinary launch within the time budget, not a hang', async () => {
    fetchMock.mockImplementation((_url: string, init: { signal: AbortSignal }) => new Promise((_resolve, reject) => { init.signal.addEventListener('abort', () => reject(new Error('aborted'))); }));
    fakeTimers();
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-checking')).not.toBeNull(); // neutral cover while checking
    await advance(2100);
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('offline with a cached splash: the last confirmed one is shown', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockRejectedValue(new Error('offline'));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-image')).not.toBeNull();
  });

  it('a cache that says "disabled" never delays the launch: the app opens at once, the check runs in the background', async () => {
    fetchMock.mockResolvedValueOnce(reply(disabled, { etag: null }));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockReset();
    fetchMock.mockImplementation(() => new Promise(() => {})); // a server that never answers
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1); // the background refresh for the next start
  });

  it('a stored splash that the server has turned off is not shown on this start', async () => {
    fetchMock.mockResolvedValueOnce(reply(image()));
    await resolveSplash(APP_ID, expected);
    fetchMock.mockResolvedValue(reply(disabled, { etag: null }));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('two clients: the request carries this client\'s own app id and business', async () => {
    jest.spyOn(clientConfig, 'getClientConfig').mockReturnValue({ ...clientConfig.getClientConfig(), android_app_id: 'kz.cashbackone.other', business_id: null });
    fetchMock.mockResolvedValue(reply(image({ business_id: 'whatever' })));
    mount(<AppSplash />);
    await flush();
    expect(fetchMock.mock.calls[0]![0]).toContain('app_id=kz.cashbackone.other');
    expect(await readCache('kz.cashbackone.other')).not.toBeNull();
    expect(await readCache(APP_ID)).toBeNull();
  });

  it('a media file of another business is never shown by the Keremet client', async () => {
    fetchMock.mockResolvedValue(reply(image({ business_id: '00000000-0000-0000-0000-000000000009' })));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('an incoming link or the Back button ends the splash so that the target screen is reachable at once', async () => {
    let urlHandler: (() => void) | undefined;
    jest.spyOn(Linking, 'addEventListener').mockImplementation(((_name: string, handler: () => void) => { urlHandler = handler; return { remove: jest.fn() }; }) as never);
    fetchMock.mockResolvedValue(reply(image()));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-stage')).not.toBeNull();
    await act(async () => { urlHandler?.(); });
    expect(screen.queryByTestId('splash-stage')).toBeNull();

    resetSplashForTests(); screen.unmount();
    let backHandler: (() => boolean) | undefined;
    jest.spyOn(BackHandler, 'addEventListener').mockImplementation(((_name: string, handler: () => boolean) => { backHandler = handler; return { remove: jest.fn() }; }) as never);
    mount(<AppSplash />);
    await flush();
    await act(async () => { expect(backHandler?.()).toBe(true); });
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });
});

describe('Safe checking phase budget, watchdog and late resolution protection', () => {
  it('watchdog terminates checking phase at 2000 ms if fetch or storage hangs, removing overlay', async () => {
    fakeTimers();
    fetchMock.mockImplementation(() => new Promise(() => {})); // Never resolves
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-checking')).not.toBeNull();

    await advance(2000);
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('late resolution after watchdog does not show splash over the app', async () => {
    fakeTimers();
    let resolveServer!: (val: unknown) => void;
    fetchMock.mockImplementation(() => new Promise(r => { resolveServer = r; }));
    mount(<AppSplash />);
    await flush();
    expect(screen.queryByTestId('splash-checking')).not.toBeNull();

    // Trigger watchdog
    await advance(2000);
    expect(screen.queryByTestId('splash-checking')).toBeNull();

    // Now server answers late with enabled image
    await act(async () => {
      resolveServer(reply(image()));
    });
    await flush();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
    expect(screen.queryByTestId('splash-image')).toBeNull();
  });

  it('skip button on checking overlay immediately ends checking without waiting for timeout', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {})); // Hanging fetch
    mount(<AppSplash />);
    expect(screen.queryByTestId('splash-checking')).not.toBeNull();
    const skipBtn = screen.getByTestId('splash-skip');
    expect(skipBtn).toBeTruthy();

    fireEvent.press(skipBtn);
    expect(screen.queryByTestId('splash-checking')).toBeNull();
    expect(screen.queryByTestId('splash-stage')).toBeNull();
  });

  it('corrupted cached splash is validated and cleared from cache read', async () => {
    const corruptedEntry = {
      appId: APP_ID,
      etag: '"e1"',
      checkedAt: Date.now(),
      splash: {
        mediaType: 'image',
        mediaUrl: 'http://insecure-domain.com/media/splashes/test.webp', // Insecure HTTP
        width: 1080,
        height: 1920,
        durationSeconds: null,
        fileSize: 200_000,
        version: 'v1',
        businessId: BUSINESS,
      },
    };
    await AsyncStorage.setItem(cacheKey(APP_ID), JSON.stringify(corruptedEntry));
    const entry = await readCache(APP_ID, expected);
    expect(entry?.splash).toBeNull();
  });
});

describe('UpdateDialog order', () => {
  const required: UpdateCheck = {
    supported: true, status: 'available', availableVersion: '1.0.20', checkNow: async () => 'available',
    info: { latest_version: '1.0.20', latest_version_code: 21, min_version_code: 21, download_url: 'https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.20.apk' },
    decision: 'required', visible: true, openDownload: async () => {}, dismissOptional: () => {},
  };
  const dialog = () => <UpdateContext.Provider value={required}><UpdateDialog /></UpdateContext.Provider>;

  it('is not shown above the splash and appears after it (a required update is kept, not lost)', async () => {
    setSplashActive(true);
    mount(dialog());
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
    await act(async () => { setSplashActive(false); });
    expect(screen.queryByText(ru.updateTitle)).not.toBeNull();
  });
});
