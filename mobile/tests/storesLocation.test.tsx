import fs from 'fs';
import path from 'path';
import { act, fireEvent, render } from '@testing-library/react-native';
import * as Location from 'expo-location';
import type { ReactElement } from 'react';
import { Alert, AppState, Linking } from 'react-native';
import { openMapUrl, toSafeMapUrl } from '../src/features/mapLink';
import {
  ABSENCE_REFRESH_MS,
  formatLocationUpdatedAgo,
  hasStoreCoordinates,
  locateForeground,
  StatusStoresList,
  StoreLocationProvider,
} from '../src/features/stores';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { AppStoreItem } from '../src/types/api';

jest.mock('expo-location', () => ({
  getForegroundPermissionsAsync: jest.fn(),
  requestForegroundPermissionsAsync: jest.fn(),
  hasServicesEnabledAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  getLastKnownPositionAsync: jest.fn(),
  Accuracy: { Balanced: 3 },
}));

const perm = Location.getForegroundPermissionsAsync as jest.Mock;
const ask = Location.requestForegroundPermissionsAsync as jest.Mock;
const services = Location.hasServicesEnabledAsync as jest.Mock;
const current = Location.getCurrentPositionAsync as jest.Mock;
const lastKnown = Location.getLastKnownPositionAsync as jest.Mock;

const granted = { status: 'granted', granted: true, canAskAgain: true, expires: 'never' };
const denied = (canAskAgain: boolean) => ({ status: 'denied', granted: false, canAskAgain, expires: 'never' });
const fix = (latitude: number, longitude: number, timestamp: number = Date.now()) => ({
  coords: { latitude, longitude, altitude: 0, accuracy: 10, altitudeAccuracy: 0, heading: 0, speed: 0 },
  timestamp,
});

const withCoords: AppStoreItem = { id: 's1', title_ru: 'Магазин 1', title_kk: 'Дүкен 1', address_ru: 'ул. Абая, 1', address_kk: 'Абай к-сі, 1', map_url: 'https://maps.example.com/s1', sort_order: 1, latitude: 43.238949, longitude: 76.889709 };
const withoutCoords: AppStoreItem = { id: 's2', title_ru: 'Магазин 2', title_kk: 'Дүкен 2', address_ru: 'пр. Достык, 2', address_kk: 'Достық д-лы, 2', map_url: null, sort_order: 2, latitude: null, longitude: null };

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(<ThemeProvider initialPreference="light"><I18nProvider initial={language}>{element}</I18nProvider></ThemeProvider>);
}
const text = (screen: ReturnType<typeof render>, id: string) => screen.getByTestId(id).props.children as string;

const originalAppState = AppState.currentState;
beforeEach(() => {
  jest.clearAllMocks();
  (AppState as { currentState: typeof AppState.currentState }).currentState = 'active';
  perm.mockResolvedValue(granted);
  ask.mockResolvedValue(granted);
  services.mockResolvedValue(true);
  lastKnown.mockResolvedValue(null);
});
afterEach(() => {
  (AppState as { currentState: typeof AppState.currentState }).currentState = originalAppState;
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('hasStoreCoordinates', () => {
  it.each([
    [{ latitude: 43.2, longitude: 76.9 }, true],
    [{ latitude: 0, longitude: 0 }, true],
    [{ latitude: null, longitude: null }, false],
    [{}, false],
    [{ latitude: 43.2 }, false],
    [{ latitude: Number.NaN, longitude: 76.9 }, false],
    [{ latitude: 91, longitude: 76.9 }, false],
    [{ latitude: 43.2, longitude: 181 }, false],
    [{ latitude: '43.2' as unknown as number, longitude: 76.9 }, false],
  ])('%j -> %s', (store, expected) => {
    expect(hasStoreCoordinates(store)).toBe(expected);
  });
});

describe('locateForeground: every outcome is reported', () => {
  it('returns the position when permission and the fix are fine', async () => {
    current.mockResolvedValue(fix(43.24, 76.9));
    await expect(locateForeground()).resolves.toEqual({ ok: true, coords: { latitude: 43.24, longitude: 76.9 }, timestamp: expect.any(Number) });
    expect(ask).not.toHaveBeenCalled(); // already granted: no second prompt
  });

  it('asks for permission when it is not granted yet', async () => {
    perm.mockResolvedValue({ ...granted, status: 'undetermined', granted: false });
    current.mockResolvedValue(fix(43.24, 76.9));
    await expect(locateForeground()).resolves.toMatchObject({ ok: true });
    expect(ask).toHaveBeenCalledTimes(1);
  });

  it.each([[true], [false]])('reports a denied permission (canAskAgain=%s) and never reads the position', async canAskAgain => {
    perm.mockResolvedValue(denied(canAskAgain));
    ask.mockResolvedValue(denied(canAskAgain));
    await expect(locateForeground()).resolves.toEqual({ ok: false, failure: 'denied', canAskAgain });
    expect(current).not.toHaveBeenCalled();
  });

  it('reports a permission request that itself fails as denied', async () => {
    perm.mockResolvedValue(denied(true));
    ask.mockRejectedValue(new Error('boom'));
    await expect(locateForeground()).resolves.toMatchObject({ ok: false, failure: 'denied' });
  });

  it('reports switched-off location services without waiting for a fix', async () => {
    services.mockResolvedValue(false);
    await expect(locateForeground()).resolves.toEqual({ ok: false, failure: 'services-off' });
    expect(current).not.toHaveBeenCalled();
  });

  it('maps the Android "settings unsatisfied" error to services-off and skips the last known fix', async () => {
    current.mockRejectedValue(Object.assign(new Error('Location settings are not satisfied.'), { code: 'ERR_LOCATION_SETTINGS_UNSATISFIED' }));
    lastKnown.mockResolvedValue(fix(43, 76));
    await expect(locateForeground()).resolves.toEqual({ ok: false, failure: 'services-off' });
    expect(lastKnown).not.toHaveBeenCalled();
  });

  it('times out after the limit, with no last known fix: a timeout is reported', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(new Promise(() => undefined));
    const outcome = locateForeground(10000);
    await jest.advanceTimersByTimeAsync(10000);
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'timeout' });
  });

  it('times out but uses a recent last known fix when there is one, preserving its real timestamp', async () => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-11-17T12:00:00Z'));
    const realFixTime = Date.now() - 4 * 60 * 1000;
    current.mockReturnValue(new Promise(() => undefined));
    lastKnown.mockResolvedValue(fix(43.3, 76.95, realFixTime));
    const outcome = locateForeground(10000);
    await jest.advanceTimersByTimeAsync(10000);
    await expect(outcome).resolves.toEqual({ ok: true, coords: { latitude: 43.3, longitude: 76.95 }, timestamp: realFixTime });
    expect(lastKnown).toHaveBeenCalledWith({ maxAge: 300000 });
  });

  it('reports a generic error for a failing fix', async () => {
    current.mockRejectedValue(new Error('GPS failure'));
    await expect(locateForeground()).resolves.toEqual({ ok: false, failure: 'error' });
  });

  it.each([
    ['NaN latitude', fix(Number.NaN, 76.9)],
    ['latitude out of range', fix(120, 76.9)],
    ['missing coords', {}],
    ['undefined position', undefined],
  ])('does not accept an unusable fix (%s) as a position', async (_name, position) => {
    current.mockResolvedValue(position);
    await expect(locateForeground()).resolves.toMatchObject({ ok: false, failure: 'error' });
  });
});

describe('locateForeground: no step can keep the wait open forever', () => {
  const never = () => new Promise<never>(() => undefined);
  // Tracks whether the outcome promise has settled, so "still waiting" can be asserted without awaiting it.
  const track = <T,>(promise: Promise<T>) => {
    const state = { settled: false };
    void promise.then(() => { state.settled = true; }, () => { state.settled = true; });
    return state;
  };

  it('fresh position never arrives and the last known one never arrives either: it ends with a timeout, within a bounded time', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(never());
    lastKnown.mockReturnValue(never());
    const outcome = locateForeground(10000, 2000);
    const state = track(outcome);
    await jest.advanceTimersByTimeAsync(10000);
    expect(state.settled).toBe(false); // the fresh fix timed out, the fallback is now being awaited, but only for a limited time
    expect(lastKnown).toHaveBeenCalledWith({ maxAge: 300000 });
    await jest.advanceTimersByTimeAsync(1999);
    expect(state.settled).toBe(false);
    await jest.advanceTimersByTimeAsync(1);
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'timeout' });
    expect(jest.getTimerCount()).toBe(0); // no timer is left running
  });

  it('keeps the original reason when the fresh fix failed with an error and the fallback hangs', async () => {
    jest.useFakeTimers();
    current.mockRejectedValue(new Error('GPS failure'));
    lastKnown.mockReturnValue(never());
    const outcome = locateForeground(10000, 2000);
    await jest.advanceTimersByTimeAsync(2000);
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'error' });
  });

  it('still uses a last known fix that arrives within the limit', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(never());
    // mockImplementation: the delay starts when the fallback is called (after the fresh fix timed out), not when the mock is set up.
    lastKnown.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve(fix(43.31, 76.96)), 1500)));
    const outcome = locateForeground(10000, 2000);
    await jest.advanceTimersByTimeAsync(10000 + 1500);
    await expect(outcome).resolves.toEqual({ ok: true, coords: { latitude: 43.31, longitude: 76.96 }, timestamp: expect.any(Number) });
  });

  it('ignores a last known fix that arrives after the limit', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(never());
    // mockImplementation: the 3000 ms delay starts when the fallback is called, so it really is later than the 2000 ms limit.
    lastKnown.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve(fix(43.31, 76.96)), 3000)));
    const outcome = locateForeground(10000, 2000);
    await jest.advanceTimersByTimeAsync(10000 + 2000);
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'timeout' });
    await jest.advanceTimersByTimeAsync(5000); // the late fix arrives now ...
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'timeout' }); // ... and does not change the finished outcome
    expect(jest.getTimerCount()).toBe(0);
  });

  it('keeps the timeout reason when the fallback read itself fails', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(never());
    lastKnown.mockRejectedValue(new Error('provider unavailable'));
    const outcome = locateForeground(10000, 2000);
    await jest.advanceTimersByTimeAsync(10000);
    await expect(outcome).resolves.toEqual({ ok: false, failure: 'timeout' });
  });

  it('a services check that never answers does not stop the attempt (the position request has its own limit)', async () => {
    jest.useFakeTimers();
    services.mockReturnValue(never());
    current.mockResolvedValue(fix(43.24, 76.9));
    const outcome = locateForeground(10000, 2000);
    await jest.advanceTimersByTimeAsync(3000);
    await expect(outcome).resolves.toEqual({ ok: true, coords: { latitude: 43.24, longitude: 76.9 }, timestamp: expect.any(Number) });
  });

  it('switched-off services are still reported, and the fallback is not consulted', async () => {
    services.mockResolvedValue(false);
    await expect(locateForeground(10000, 2000)).resolves.toEqual({ ok: false, failure: 'services-off' });
    expect(lastKnown).not.toHaveBeenCalled();
  });

  it('the system permission dialog is not bounded by these limits: it can stay open for a minute', async () => {
    jest.useFakeTimers();
    perm.mockResolvedValue({ ...granted, status: 'undetermined', granted: false });
    let answer: (value: unknown) => void = () => undefined;
    ask.mockReturnValue(new Promise(resolve => { answer = resolve; }));
    current.mockResolvedValue(fix(43.24, 76.9));
    const outcome = locateForeground(10000, 2000);
    const state = track(outcome);
    await jest.advanceTimersByTimeAsync(60000);
    expect(state.settled).toBe(false); // still waiting for the person, no failure invented
    expect(current).not.toHaveBeenCalled();
    answer(granted);
    await jest.advanceTimersByTimeAsync(0);
    await expect(outcome).resolves.toEqual({ ok: true, coords: { latitude: 43.24, longitude: 76.9 }, timestamp: expect.any(Number) });
  });
});

describe('StatusStoresList: location states on screen', () => {
  it('says why there are no distances when no store has coordinates, and does not ask for location at all', () => {
    const screen = mount(<StatusStoresList stores={[withoutCoords]} language="ru" />);
    expect(screen.queryByTestId('show-distances-button')).toBeNull();
    expect(screen.getByTestId('stores-coords-missing-note').props.children).toBe(ru.storesCoordsNotSet);
    expect(text(screen, 'store-distance-s2')).toContain(ru.storeCoordsMissing);
    expect(perm).not.toHaveBeenCalled();
    expect(ask).not.toHaveBeenCalled();
  });

  it('the same states in Kazakh', () => {
    const screen = mount(<StatusStoresList stores={[withoutCoords]} language="kz" />, 'kz');
    expect(screen.getByTestId('stores-coords-missing-note').props.children).toBe(kz.storesCoordsNotSet);
    expect(text(screen, 'store-distance-s2')).toContain(kz.storeCoordsMissing);
  });

  // The screen asks for the position by itself when it opens: tests mount inside act() so that attempt is settled.
  async function open(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
    const screen = mount(element, language);
    await act(async () => { await Promise.resolve(); });
    return screen;
  }

  it('shows distances by itself when the screen opens, without any tap, never an invented 0', async () => {
    current.mockResolvedValue(fix(43.238949, 76.899709));
    const screen = await open(<StatusStoresList stores={[withCoords, withoutCoords]} language="ru" />);
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    expect(text(screen, 'store-distance-s1')).not.toContain('0 км');
    expect(text(screen, 'store-distance-s2')).toContain(ru.storeCoordsMissing);
    expect(screen.queryByTestId('location-failure-note')).toBeNull();
    expect(screen.queryByTestId('location-denied-note')).toBeNull();
    expect(current).toHaveBeenCalledTimes(1);
    expect(screen.getByText(ru.updateDistances)).toBeTruthy();
  });

  it('shows "determining" while the automatic request runs, then the distance', async () => {
    let finish: (value: unknown) => void = () => undefined;
    current.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(text(screen, 'store-distance-s1')).toContain(ru.distanceLocating);
    expect(screen.getByLabelText(ru.locatingDistances)).toBeTruthy();
    await act(async () => { finish(fix(43.238949, 76.899709)); });
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
  });

  it('the first open asks the system permission once (undetermined), then reads the position', async () => {
    perm.mockResolvedValue({ status: 'undetermined', granted: false, canAskAgain: true, expires: 'never' });
    ask.mockResolvedValue(granted);
    current.mockResolvedValue(fix(43.238949, 76.899709));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(ask).toHaveBeenCalledTimes(1);
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
  });

  it('a permission refused earlier is not asked again automatically: a clear note and a retry button instead', async () => {
    perm.mockResolvedValue(denied(true));
    ask.mockResolvedValue(granted);
    current.mockResolvedValue(fix(43.238949, 76.899709));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(ask).not.toHaveBeenCalled();
    expect(current).not.toHaveBeenCalled();
    expect(screen.getByText(ru.locationPermissionDenied)).toBeTruthy();
    expect(screen.getByText(ru.retryDistances)).toBeTruthy();
    // The person asks again through the button: now the system dialog may appear and the distance shows up.
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой/);
  });

  it('ends the loading and explains a denied permission (RU/KK), with a settings hint when it cannot be asked again', async () => {
    perm.mockResolvedValue(denied(false));
    ask.mockResolvedValue(denied(false));
    const ruScreen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(ruScreen.getByText(ru.locationPermissionDenied)).toBeTruthy();
    expect(ruScreen.getByText(ru.locationPermissionSettingsHint)).toBeTruthy();
    expect(ruScreen.getByText(ru.retryDistances)).toBeTruthy(); // the spinner is gone, the button is back
    expect(text(ruScreen, 'store-distance-s1')).toContain(ru.distanceUnavailable);
    const kzScreen = await open(<StatusStoresList stores={[withCoords]} language="kz" />, 'kz');
    expect(kzScreen.getByText(kz.locationPermissionDenied)).toBeTruthy();
    expect(kzScreen.getByText(kz.retryDistances)).toBeTruthy();
    expect(ask).not.toHaveBeenCalled();
  });

  it('explains switched-off location services', async () => {
    services.mockResolvedValue(false);
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(screen.getByTestId('location-failure-note').props.children).toBe(ru.locationServicesOff);
    expect(screen.getByText(ru.retryDistances)).toBeTruthy();
  });

  it('explains a GPS error', async () => {
    current.mockRejectedValue(new Error('GPS failure'));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="kz" />, 'kz');
    expect(screen.getByTestId('location-failure-note').props.children).toBe(kz.locationError);
  });

  it('after the timeout the loading ends and the reason is shown (not a silent spinner)', async () => {
    jest.useFakeTimers();
    current.mockReturnValue(new Promise(() => undefined));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(screen.getByLabelText(ru.locatingDistances)).toBeTruthy(); // spinner while waiting
    await act(async () => { await jest.advanceTimersByTimeAsync(10000); });
    expect(screen.getByTestId('location-failure-note').props.children).toBe(ru.locationTimeout);
    expect(screen.getByText(ru.retryDistances)).toBeTruthy();
    expect(screen.queryByLabelText(ru.locatingDistances)).toBeNull();
    expect(current).toHaveBeenCalledTimes(1); // no automatic second attempt
  });

  it('fresh and last known position both hang: the spinner ends, the reason is shown, and the person can try again', async () => {
    jest.useFakeTimers();
    current.mockReturnValueOnce(new Promise(() => undefined)).mockResolvedValueOnce(fix(43.238949, 76.899709));
    lastKnown.mockReturnValue(new Promise(() => undefined));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(screen.getByLabelText(ru.locatingDistances)).toBeTruthy(); // spinner while waiting
    await act(async () => { await jest.advanceTimersByTimeAsync(10000); });
    expect(screen.getByLabelText(ru.locatingDistances)).toBeTruthy(); // the fallback is still being awaited, for a limited time
    await act(async () => { await jest.advanceTimersByTimeAsync(2000); });
    expect(screen.queryByLabelText(ru.locatingDistances)).toBeNull(); // spinner gone
    expect(screen.getByTestId('location-failure-note').props.children).toBe(ru.locationTimeout);
    expect(text(screen, 'store-distance-s1')).toContain(ru.distanceUnavailable);
    expect(screen.getByText(ru.retryDistances)).toBeTruthy(); // the button is back
    // Retry works: the next attempt gets a position, the message is gone and the distance appears.
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(screen.queryByTestId('location-failure-note')).toBeNull();
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    expect(screen.getByText(ru.updateDistances)).toBeTruthy();
  });

  it('a retry clears the previous failure, and a later success shows distances', async () => {
    current.mockRejectedValueOnce(new Error('GPS failure')).mockResolvedValueOnce(fix(43.238949, 76.899709));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    expect(screen.getByTestId('location-failure-note')).toBeTruthy();
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(screen.queryByTestId('location-failure-note')).toBeNull();
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    expect(screen.getByText(ru.updateDistances)).toBeTruthy();
  });

  it('ignores a tap while the automatic request is running (one permission/position request)', async () => {
    let finish: (value: unknown) => void = () => undefined;
    current.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(current).toHaveBeenCalledTimes(1);
    await act(async () => { finish(fix(43.238949, 76.899709)); });
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой/);
    expect(current).toHaveBeenCalledTimes(1);
  });

  it('leaving the screen while locating causes no update and no unhandled error', async () => {
    let finish: (value: unknown) => void = () => undefined;
    current.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const errors = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    screen.unmount();
    await act(async () => { finish(fix(43.238949, 76.899709)); });
    expect(errors).not.toHaveBeenCalled();
  });

  it('a store at latitude 0 / longitude 0 is valid: the automatic request runs and the distance is real', async () => {
    current.mockResolvedValue(fix(0, 0));
    const screen = await open(<StatusStoresList stores={[{ ...withCoords, latitude: 0, longitude: 0 }]} language="ru" />);
    expect(text(screen, 'store-distance-s1')).toContain('0 м');
    expect(current).toHaveBeenCalledTimes(1);
  });

  it('a caller that controls userCoords gets no automatic request', async () => {
    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" userCoords={{ latitude: 43.238949, longitude: 76.899709 }} />);
    expect(perm).not.toHaveBeenCalled();
    expect(current).not.toHaveBeenCalled();
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
  });

  it('a store list without coordinates anywhere makes no request on open', async () => {
    await open(<StatusStoresList stores={[withoutCoords]} language="ru" />);
    expect(perm).not.toHaveBeenCalled();
    expect(current).not.toHaveBeenCalled();
  });

  describe('coming back to the app', () => {
    let emit: (state: string) => void = () => undefined;
    let removed = 0;
    beforeEach(() => {
      removed = 0;
      jest.spyOn(AppState, 'addEventListener').mockImplementation(((type: string, listener: (state: string) => void) => {
        if (type === 'change') emit = listener;
        return { remove: () => { removed += 1; } };
      }) as unknown as typeof AppState.addEventListener);
    });

    it('absent 29 minutes: no automatic request; absent 30 minutes: one automatic attempt, and removes listener on unmount', async () => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date('2026-11-17T10:00:00Z'));
      current.mockResolvedValue(fix(43.238949, 76.899709));
      const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
      expect(current).toHaveBeenCalledTimes(1);

      // Leave app and return after 29 minutes -> no automatic request
      await act(async () => { emit('background'); });
      await act(async () => { await jest.advanceTimersByTimeAsync(29 * 60 * 1000); emit('active'); });
      expect(current).toHaveBeenCalledTimes(1);

      // Leave app and return after 30 minutes -> one automatic attempt
      await act(async () => { emit('background'); });
      await act(async () => { await jest.advanceTimersByTimeAsync(ABSENCE_REFRESH_MS); emit('active'); });
      expect(current).toHaveBeenCalledTimes(2);

      screen.unmount();
      expect(removed).toBeGreaterThan(0);
    });

    it('does not start a second request while one is running, and ignores background/inactive without 30 min absence', async () => {
      current.mockReturnValue(new Promise(() => undefined));
      jest.useFakeTimers();
      await open(<StatusStoresList stores={[withCoords]} language="ru" />);
      await act(async () => { emit('active'); emit('background'); emit('inactive'); emit('active'); });
      expect(current).toHaveBeenCalledTimes(1);
    });

    it('a permission the person denied in the system dialog is not asked again on return after 30 minutes, and no loop follows', async () => {
      jest.useFakeTimers();
      perm.mockResolvedValue(denied(true));
      const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
      await act(async () => { emit('background'); await jest.advanceTimersByTimeAsync(ABSENCE_REFRESH_MS); emit('active'); });
      await act(async () => { emit('background'); await jest.advanceTimersByTimeAsync(ABSENCE_REFRESH_MS); emit('active'); });
      expect(ask).not.toHaveBeenCalled();
      expect(current).not.toHaveBeenCalled();
      expect(screen.getByText(ru.locationPermissionDenied)).toBeTruthy();
    });

    it('returning from the system permission dialog does not count as an app absence or trigger a second attempt', async () => {
      jest.useFakeTimers();
      perm.mockResolvedValue({ status: 'undetermined', granted: false, canAskAgain: true, expires: 'never' });
      let resolveAsk: (v: unknown) => void = () => undefined;
      ask.mockReturnValue(new Promise(resolve => { resolveAsk = resolve; }));
      current.mockResolvedValue(fix(43.238949, 76.899709));

      await open(<StatusStoresList stores={[withCoords]} language="ru" />);
      expect(ask).toHaveBeenCalledTimes(1);

      // System dialog causes inactive/background -> active transitions even if user lingers 31 min
      await act(async () => { emit('inactive'); emit('background'); });
      await act(async () => { await jest.advanceTimersByTimeAsync(31 * 60 * 1000); });
      await act(async () => { resolveAsk(granted); emit('active'); await Promise.resolve(); });
      expect(current).toHaveBeenCalledTimes(1);
      expect(ask).toHaveBeenCalledTimes(1);
    });
  });

  it('picks up coordinates the shop adds later (updated app-content) without restarting the screen', () => {
    const screen = mount(<StatusStoresList stores={[{ ...withCoords, latitude: null, longitude: null }]} language="ru" />);
    expect(screen.queryByTestId('show-distances-button')).toBeNull();
    screen.rerender(<ThemeProvider initialPreference="light"><I18nProvider initial="ru"><StatusStoresList stores={[withCoords]} language="ru" /></I18nProvider></ThemeProvider>);
    expect(screen.getByTestId('show-distances-button')).toBeTruthy();
    expect(screen.queryByTestId('stores-coords-missing-note')).toBeNull();
  });

  it('keeps the phone position on the phone: no network call and no background location', async () => {
    current.mockResolvedValue(fix(43.238949, 76.899709));
    const fetchSpy = jest.fn();
    const original = global.fetch;
    global.fetch = fetchSpy as unknown as typeof fetch;
    try {
      mount(<StatusStoresList stores={[withCoords]} language="ru" />);
      await act(async () => { await Promise.resolve(); });
      expect(current).toHaveBeenCalledTimes(1);
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      global.fetch = original;
    }
    // Only the foreground APIs exist in the mocked module: a background/watch call would have thrown. The build config says the same.
    const app = JSON.parse(fs.readFileSync(path.join(__dirname, '../app.json'), 'utf8')) as { expo: { plugins: unknown[] } };
    const plugin = app.expo.plugins.find(item => Array.isArray(item) && item[0] === 'expo-location') as [string, Record<string, unknown>];
    expect(plugin[1].isAndroidBackgroundLocationEnabled).toBe(false);
    expect(plugin[1].isAndroidForegroundServiceEnabled).toBe(false);
  });

  it('shows staleness label for fresh and last-known positions, preserves saved distance on error, and hides on revoked permission', async () => {
    jest.useFakeTimers();
    const now = new Date('2026-11-17T12:00:00Z').getTime();
    jest.setSystemTime(now);
    const fourMinAgo = now - 4 * 60 * 1000;
    current.mockReturnValueOnce(new Promise(() => undefined)).mockRejectedValueOnce(new Error('GPS failure'));
    lastKnown.mockResolvedValueOnce(fix(43.238949, 76.899709, fourMinAgo));

    const screen = await open(<StatusStoresList stores={[withCoords]} language="ru" />);
    await act(async () => { await jest.advanceTimersByTimeAsync(10000); });
    expect(screen.getByTestId('location-updated-at').props.children).toBe('Обновлено 4 минуты назад');
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);

    // Manual refresh fails with GPS error -> saved distance & honest staleness remain alongside failure note
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(screen.getByTestId('location-failure-note').props.children).toBe(ru.locationError);
    expect(text(screen, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    expect(screen.getByTestId('location-updated-at').props.children).toBe('Обновлено 4 минуты назад');

    // Manual refresh sees revoked permission -> coordinates and distances are hidden
    perm.mockResolvedValueOnce(denied(false));
    ask.mockResolvedValueOnce(denied(false));
    await act(async () => { fireEvent.press(screen.getByTestId('show-distances-button')); });
    expect(screen.getByTestId('location-denied-note')).toBeTruthy();
    expect(text(screen, 'store-distance-s1')).toContain(ru.distanceUnavailable);
    expect(screen.queryByTestId('location-updated-at')).toBeNull();
  });
});

describe('formatLocationUpdatedAgo', () => {
  it('formats RU and KK staleness labels accurately', () => {
    const now = new Date('2026-11-17T12:00:00Z').getTime();
    const tRu = (k: keyof typeof ru, p?: Record<string, string | number>) =>
      p ? ru[k].replace(/\{(\w+)\}/g, (_, n: string) => String(p[n] ?? '')) : ru[k];
    const tKz = (k: keyof typeof kz, p?: Record<string, string | number>) =>
      p ? kz[k].replace(/\{(\w+)\}/g, (_, n: string) => String(p[n] ?? '')) : kz[k];

    expect(formatLocationUpdatedAgo(now - 20_000, now, tRu)).toBe('Обновлено только что');
    expect(formatLocationUpdatedAgo(now - 60_000, now, tRu)).toBe('Обновлено 1 минуту назад');
    expect(formatLocationUpdatedAgo(now - 2 * 60_000, now, tRu)).toBe('Обновлено 2 минуты назад');
    expect(formatLocationUpdatedAgo(now - 15 * 60_000, now, tRu)).toBe('Обновлено 15 минут назад');
    expect(formatLocationUpdatedAgo(now - 60 * 60_000, now, tRu)).toBe('Обновлено 1 час назад');

    expect(formatLocationUpdatedAgo(now - 20_000, now, tKz)).toBe('Жаңа ғана жаңартылды');
    expect(formatLocationUpdatedAgo(now - 15 * 60_000, now, tKz)).toBe('15 минут бұрын жаңартылды');
    expect(formatLocationUpdatedAgo(now - 2 * 60 * 60_000, now, tKz)).toBe('2 сағат бұрын жаңартылды');
  });
});

describe('StoreLocationProvider: session-level lifecycle', () => {
  it('requests once on startup after session is ready, including late store loading, and screen transitions do not re-request', async () => {
    current.mockResolvedValue(fix(43.238949, 76.899709));
    const tree = (authenticated: boolean, sessionKey: string, stores: AppStoreItem[] | undefined, showList: boolean) => (
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={authenticated} sessionKey={sessionKey} stores={stores}>
            {showList ? <StatusStoresList stores={stores} language="ru" /> : null}
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>
    );

    // 1. Session not ready yet -> no request
    const view = render(tree(false, 'loading', [withCoords], false));
    await act(async () => { await Promise.resolve(); });
    expect(current).not.toHaveBeenCalled();

    // 2. Session ready, stores not loaded yet -> no request
    await act(async () => { view.rerender(tree(true, 'user-1', undefined, false)); });
    expect(current).not.toHaveBeenCalled();

    // 3. Stores load later with valid coords -> one automatic request
    await act(async () => { view.rerender(tree(true, 'user-1', [withCoords], false)); });
    expect(current).toHaveBeenCalledTimes(1);

    // 4. Opening and closing StatusStoresList (navigating between screens) -> no new requests, distances are already ready
    await act(async () => { view.rerender(tree(true, 'user-1', [withCoords], true)); });
    expect(current).toHaveBeenCalledTimes(1);
    expect(text(view, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    expect(view.getByTestId('location-updated-at').props.children).toBe('Обновлено только что');

    await act(async () => { view.rerender(tree(true, 'user-1', [withCoords], false)); });
    await act(async () => { view.rerender(tree(true, 'user-1', [withCoords], true)); });
    expect(current).toHaveBeenCalledTimes(1);
  });

  it('clears coordinates on session change and discards late async response from previous session', async () => {
    let finishOldRequest: (v: unknown) => void = () => undefined;
    current
      .mockReturnValueOnce(new Promise(resolve => { finishOldRequest = resolve; }))
      .mockResolvedValueOnce(fix(51.1694, 71.4491));

    const tree = (sessionKey: string, stores: AppStoreItem[]) => (
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={true} sessionKey={sessionKey} stores={stores}>
            <StatusStoresList stores={stores} language="ru" />
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>
    );

    const view = render(tree('user-1', [withCoords]));
    await act(async () => { await Promise.resolve(); });
    expect(current).toHaveBeenCalledTimes(1);

    // Switch session while user-1's request is still pending; user-2 has no stores with coords yet
    await act(async () => { view.rerender(tree('user-2', [withoutCoords])); });
    expect(text(view, 'store-distance-s2')).toContain(ru.storeCoordsMissing);

    // Old async response for user-1 arrives now -> must be ignored and never enter user-2's session
    await act(async () => { finishOldRequest(fix(43.238949, 76.899709)); });
    await act(async () => { view.rerender(tree('user-2', [withCoords])); });
    // user-2 had its own automatic attempt with user-2's coords (51.1694, 71.4491, far from Almaty)
    expect(current).toHaveBeenCalledTimes(2);
    expect(text(view, 'store-distance-s1')).toContain('км');
  });

  it('sessionKey A -> B with authenticated=true and stores with coords in both: B gets its own attempt and A late response is ignored', async () => {
    let finishA: (v: unknown) => void = () => undefined;
    let finishB: (v: unknown) => void = () => undefined;
    current
      .mockReturnValueOnce(new Promise(resolve => { finishA = resolve; }))
      .mockReturnValueOnce(new Promise(resolve => { finishB = resolve; }));

    const tree = (sessionKey: string) => (
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={true} sessionKey={sessionKey} stores={[withCoords]}>
            <StatusStoresList stores={[withCoords]} language="ru" />
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>
    );

    const view = render(tree('session-A'));
    await act(async () => { await Promise.resolve(); });
    expect(current).toHaveBeenCalledTimes(1);

    // Switch directly to session-B while both sessions are authenticated and have stores with coords
    await act(async () => { view.rerender(tree('session-B')); });
    expect(current).toHaveBeenCalledTimes(2);
    expect(text(view, 'store-distance-s1')).toContain(ru.distanceLocating);

    // Late response from session-A arrives -> must be ignored
    await act(async () => { finishA(fix(43.238949, 76.899709)); });
    expect(text(view, 'store-distance-s1')).toContain(ru.distanceLocating);

    // Session-B's own response arrives (51.1694, 71.4491 -> far from Almaty, shown in км)
    await act(async () => { finishB(fix(51.1694, 71.4491)); });
    expect(text(view, 'store-distance-s1')).toContain('км');
  });

  it('defers initial automatic attempt when stores load in background and runs it once on active even after < 30 min', async () => {
    jest.useFakeTimers();
    let emit: (state: string) => void = () => undefined;
    jest.spyOn(AppState, 'addEventListener').mockImplementation(((type: string, listener: (state: string) => void) => {
      if (type === 'change') emit = listener;
      return { remove: jest.fn() };
    }) as unknown as typeof AppState.addEventListener);

    current.mockResolvedValue(fix(43.238949, 76.899709));
    const tree = (stores: AppStoreItem[] | undefined) => (
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={true} sessionKey="user-bg-stores" stores={stores}>
            <StatusStoresList stores={stores} language="ru" />
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>
    );

    const view = render(tree(undefined));
    await act(async () => { await Promise.resolve(); });
    expect(current).not.toHaveBeenCalled();

    // App goes to background, then stores load while in background -> still no request
    await act(async () => { emit('background'); });
    await act(async () => { view.rerender(tree([withCoords])); });
    expect(current).not.toHaveBeenCalled();

    // Return to active after only 5 minutes (< 30 min) -> deferred initial attempt runs once
    await act(async () => { await jest.advanceTimersByTimeAsync(5 * 60 * 1000); emit('active'); });
    expect(current).toHaveBeenCalledTimes(1);
    expect(text(view, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
  });

  it('defers initial automatic attempt when new session becomes ready in background until app becomes active', async () => {
    jest.useFakeTimers();
    let emit: (state: string) => void = () => undefined;
    jest.spyOn(AppState, 'addEventListener').mockImplementation(((type: string, listener: (state: string) => void) => {
      if (type === 'change') emit = listener;
      return { remove: jest.fn() };
    }) as unknown as typeof AppState.addEventListener);

    const prevState = AppState.currentState;
    (AppState as { currentState: string }).currentState = 'background';
    try {
      current.mockResolvedValue(fix(43.238949, 76.899709));
      const tree = (authenticated: boolean) => (
        <ThemeProvider initialPreference="light">
          <I18nProvider initial="ru">
            <StoreLocationProvider authenticated={authenticated} sessionKey="user-bg-session" stores={[withCoords]}>
              <StatusStoresList stores={[withCoords]} language="ru" />
            </StoreLocationProvider>
          </I18nProvider>
        </ThemeProvider>
      );

      const view = render(tree(false));
      await act(async () => { await Promise.resolve(); });
      await act(async () => { view.rerender(tree(true)); });
      expect(current).not.toHaveBeenCalled();

      await act(async () => { await jest.advanceTimersByTimeAsync(2 * 60 * 1000); emit('active'); });
      expect(current).toHaveBeenCalledTimes(1);
      expect(text(view, 'store-distance-s1')).toMatch(/По прямой: \d+ м/);
    } finally {
      (AppState as { currentState: string }).currentState = prevState;
    }
  });
});

describe('Map links', () => {
  it.each([
    ['https://maps.example.com/s1', 'https://maps.example.com/s1'],
    ['  https://2gis.kz/almaty/geo/1  ', 'https://2gis.kz/almaty/geo/1'],
    ['HTTPS://maps.example.com/x', 'https://maps.example.com/x'],
  ])('accepts a plain https link: %s', (raw, expected) => {
    expect(toSafeMapUrl(raw)).toBe(expected);
  });

  it.each([
    ['http://maps.example.com/s1'],
    ['geo:43.2,76.9'],
    ['javascript:alert(1)'],
    ['intent://scan#Intent;end'],
    ['maps.example.com/no-scheme'],
    ['https://'],
    ['https://user@evil.example.com/'],
    [''],
    [null],
    [undefined],
  ])('rejects an unusable link: %s', raw => {
    expect(toSafeMapUrl(raw as string | null | undefined)).toBeNull();
  });

  it('opens a valid link through the phone (browser or maps app)', async () => {
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    await expect(openMapUrl('https://maps.example.com/s1')).resolves.toBe(true);
    expect(open).toHaveBeenCalledWith('https://maps.example.com/s1');
  });

  it('reports false, instead of throwing, when nothing can open the link', async () => {
    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('No Activity found'));
    await expect(openMapUrl('https://maps.example.com/s1')).resolves.toBe(false);
  });

  it('does not even try to open an unsafe link', async () => {
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    await expect(openMapUrl('javascript:alert(1)')).resolves.toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it('a store tap opens its link; a failure is shown to the user, not swallowed', async () => {
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<StatusStoresList stores={[withCoords]} language="ru" />);
    await act(async () => { fireEvent.press(screen.getByTestId('status-store-item-s1')); });
    expect(open).toHaveBeenCalledWith('https://maps.example.com/s1');
    expect(alert).not.toHaveBeenCalled();

    open.mockRejectedValue(new Error('No Activity found'));
    await act(async () => { fireEvent.press(screen.getByTestId('status-store-item-s1')); });
    expect(alert).toHaveBeenCalledWith(ru.app, ru.mapOpenFailed);
  });

  it('a store with an unsafe map_url is not opened and the user is told', async () => {
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<StatusStoresList stores={[{ ...withCoords, map_url: 'javascript:alert(1)' }]} language="ru" />);
    await act(async () => { fireEvent.press(screen.getByTestId('status-store-item-s1')); });
    expect(open).not.toHaveBeenCalled();
    expect(alert).toHaveBeenCalledWith(ru.app, ru.mapOpenFailed);
  });
});
