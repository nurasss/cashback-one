import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ReactElement } from 'react';
import { Alert, type AlertButton } from 'react-native';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { clearAppCache, setCachedAppContent } from '../src/storage/appCache';
import { THEME_STORAGE_KEY } from '../src/storage/themePreference';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { Profile } from '../src/types/api';

const mockLogout = jest.fn();
const mockRequest = jest.fn();
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: mockLogout, getUserId: () => 'u1' } }),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: 'Айдар', last_name: 'Тест', email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000, gcTime: Infinity }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={query}>
      <ThemeProvider initialPreference="light"><I18nProvider initial={language}><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider></ThemeProvider>
    </QueryClientProvider>,
  );
}
const until = (description: string, condition: () => boolean) => waitFor(() => { if (!condition()) throw new Error(`not yet: ${description}`); });
async function profileShown(screen: ReturnType<typeof mount>, label: string) {
  await until('the profile request was sent', () => mockRequest.mock.calls.some(call => String(call[0]).startsWith('/me/profile')));
  await mockRequest.mock.results[0]?.value;
  await until('the logout row is shown', () => screen.queryByText(label) !== null);
}
const alertButtons = (alert: jest.SpyInstance): AlertButton[] => (alert.mock.calls[0]?.[2] ?? []) as AlertButton[];

beforeEach(async () => {
  jest.clearAllMocks();
  mockRequest.mockImplementation((path: string) => (path.startsWith('/me/profile') ? Promise.resolve(profile) : Promise.reject(new Error(`unexpected ${path}`))));
  mockLogout.mockResolvedValue(false);
  await clearAppCache();
});
afterEach(() => { jest.restoreAllMocks(); });

describe('Profile: the visible logout row', () => {
  it('is shown in Russian as «Выход из аккаунта»', async () => {
    const screen = mount(<ProfileScreen />);
    await profileShown(screen, ru.logoutAccount);
    expect(ru.logoutAccount).toBe('Выход из аккаунта');
    expect(screen.getByRole('button', { name: ru.logoutAccount })).toBeTruthy();
  });

  it('is shown in Kazakh as «Аккаунттан шығу»', async () => {
    const screen = mount(<ProfileScreen />, 'kz');
    await profileShown(screen, kz.logoutAccount);
    expect(kz.logoutAccount).toBe('Аккаунттан шығу');
    expect(screen.getByRole('button', { name: kz.logoutAccount })).toBeTruthy();
  });

  it('asks first (RU): Cancel does nothing, nobody is signed out', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<ProfileScreen />);
    await profileShown(screen, ru.logoutAccount);
    fireEvent.press(screen.getByRole('button', { name: ru.logoutAccount }));
    expect(alert).toHaveBeenCalledTimes(1);
    expect(alert.mock.calls[0]?.[0]).toBe(ru.logoutConfirm);
    const buttons = alertButtons(alert);
    expect(buttons.map(b => b.text)).toEqual([ru.cancel, ru.logout]);
    expect(buttons[0]?.style).toBe('cancel');
    expect(buttons[1]?.style).toBe('destructive');
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('asks in Kazakh too', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<ProfileScreen />, 'kz');
    await profileShown(screen, kz.logoutAccount);
    fireEvent.press(screen.getByRole('button', { name: kz.logoutAccount }));
    expect(alert.mock.calls[0]?.[0]).toBe(kz.logoutConfirm);
    expect(alertButtons(alert).map(b => b.text)).toEqual([kz.cancel, kz.logout]);
  });

  it('confirming signs out through the session exactly once, with no second message when the server revoked the token', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<ProfileScreen />);
    await profileShown(screen, ru.logoutAccount);
    fireEvent.press(screen.getByRole('button', { name: ru.logoutAccount }));
    alertButtons(alert)[1]?.onPress?.();
    await until('the session was asked to sign out', () => mockLogout.mock.calls.length === 1);
    await Promise.resolve();
    expect(alert).toHaveBeenCalledTimes(1);
  });

  it('when the server could not confirm the revocation the person is told they are signed out on this device', async () => {
    mockLogout.mockResolvedValue(true);
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const screen = mount(<ProfileScreen />);
    await profileShown(screen, ru.logoutAccount);
    fireEvent.press(screen.getByRole('button', { name: ru.logoutAccount }));
    alertButtons(alert)[1]?.onPress?.();
    await until('the second message was shown', () => alert.mock.calls.length === 2);
    expect(alert.mock.calls[1]?.slice(0, 2)).toEqual([ru.logoutAccount, ru.revokeFailed]);
  });
});

describe('Sign-out keeps the device settings', () => {
  it('clearing the cache on logout removes the cached content but not the theme preference', async () => {
    await AsyncStorage.setItem(THEME_STORAGE_KEY, 'dark');
    setCachedAppContent('u1', 'b-1', { business_id: 'b-1', stores: [], app_texts: {}, updated_at: '2026-11-11T00:00:00Z' }, null);
    await Promise.resolve();
    expect((await AsyncStorage.getAllKeys()).some(key => key.startsWith('cashback-one.cache.v1:'))).toBe(true);
    await clearAppCache(); // what the session calls before and after logout
    expect((await AsyncStorage.getAllKeys()).some(key => key.startsWith('cashback-one.cache.v1:'))).toBe(false);
    expect(await AsyncStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });
});
