import { act, render } from '@testing-library/react-native';
import * as Location from 'expo-location';
import { AppState } from 'react-native';
import { ABSENCE_REFRESH_MS, StatusStoresList, StoreLocationProvider } from '../src/features/stores';
import { I18nProvider } from '../src/i18n';
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
const store: AppStoreItem = { id: 's1', title_ru: 'Магазин 1', title_kk: 'Дүкен 1', address_ru: 'ул. Абая, 1', address_kk: 'Абай к-сі, 1', map_url: null, sort_order: 1, latitude: 43.238949, longitude: 76.889709 };
const fix = () => ({ coords: { latitude: 43.24, longitude: 76.9, altitude: 0, accuracy: 10, altitudeAccuracy: 0, heading: 0, speed: 0 }, timestamp: Date.now() });

let emit: (state: string) => void = () => undefined;
const originalAppState = AppState.currentState;
beforeEach(() => {
  jest.clearAllMocks();
  (AppState as { currentState: typeof AppState.currentState }).currentState = 'active';
  perm.mockResolvedValue(granted);
  ask.mockResolvedValue(granted);
  services.mockResolvedValue(true);
  lastKnown.mockResolvedValue(null);
  current.mockResolvedValue(fix());
  jest.spyOn(AppState, 'addEventListener').mockImplementation(((type: string, listener: (state: string) => void) => {
    if (type === 'change') emit = listener;
    return { remove: jest.fn() };
  }) as unknown as typeof AppState.addEventListener);
});
afterEach(() => {
  (AppState as { currentState: typeof AppState.currentState }).currentState = originalAppState;
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('session-level location across screen navigation', () => {
  it('opening, leaving and reopening StatusStoresList does not trigger additional location requests', async () => {
    const view = render(
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={true} sessionKey="u1" stores={[store]}>
            <StatusStoresList stores={[store]} language="ru" />
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>,
    );
    await act(async () => { await Promise.resolve(); });
    expect(current).toHaveBeenCalledTimes(1);

    // Simulate navigating away (StatusStoresList unmounted, provider remains) and returning
    await act(async () => {
      view.rerender(
        <ThemeProvider initialPreference="light">
          <I18nProvider initial="ru">
            <StoreLocationProvider authenticated={true} sessionKey="u1" stores={[store]}>
              {null}
            </StoreLocationProvider>
          </I18nProvider>
        </ThemeProvider>,
      );
    });
    await act(async () => {
      view.rerender(
        <ThemeProvider initialPreference="light">
          <I18nProvider initial="ru">
            <StoreLocationProvider authenticated={true} sessionKey="u1" stores={[store]}>
              <StatusStoresList stores={[store]} language="ru" />
            </StoreLocationProvider>
          </I18nProvider>
        </ThemeProvider>,
      );
    });
    expect(current).toHaveBeenCalledTimes(1);
  });

  it('returning to the app after >= 30 minutes triggers one automatic refresh regardless of whether stores screen is open', async () => {
    jest.useFakeTimers();
    render(
      <ThemeProvider initialPreference="light">
        <I18nProvider initial="ru">
          <StoreLocationProvider authenticated={true} sessionKey="u1" stores={[store]}>
            {null}
          </StoreLocationProvider>
        </I18nProvider>
      </ThemeProvider>,
    );
    await act(async () => { await jest.advanceTimersByTimeAsync(0); });
    expect(current).toHaveBeenCalledTimes(1);

    await act(async () => { emit('background'); });
    await act(async () => { await jest.advanceTimersByTimeAsync(ABSENCE_REFRESH_MS); emit('active'); });
    expect(current).toHaveBeenCalledTimes(2);
  });
});
