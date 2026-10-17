import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Linking, Platform } from 'react-native';
import QrScreen from '../app/(app)/(tabs)/qr';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { ru, errorMessages } from '../src/i18n/ru';
import type { Card } from '../src/types/api';
import { ApiError } from '../src/api/errors';
import { requestWalletLink } from '../src/api/app';

const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { logout: jest.fn() } }),
}));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: (effect: () => void) => effect(),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) {
    return React.createElement(Text, { testID: 'qr-payload' }, value);
  };
});

const testCard: Card = {
  id: 'card-123',
  barcode: '2000000000012',
  balance: '500.0000',
  is_blocked: false,
  updated_at: '2026-10-01T00:00:00Z',
  bound_at: '2026-10-01T00:00:00Z',
  bind_method: 'phone_auto',
  business: { id: 'biz-1', name: 'Test Market', branding: null },
};

function mountScreen(element: ReactElement) {
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  const screen = render(
    <QueryClientProvider client={query}>
      <I18nProvider>
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  return { screen, query };
}

function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    if (routes[path] !== undefined) return Promise.resolve(routes[path]);
    const match = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
});

it('hides Add to Wallet button when wallet availability is false', async () => {
  serve({
    '/me/cards/card-123/qr': { token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 },
    '/me/cards': [testCard],
    '/me/wallet': { apple: false, google: false },
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByText(ru.showToCashier)).toBeTruthy());

  expect(screen.queryByLabelText(ru.addToAppleWallet)).toBeNull();
  expect(screen.queryByLabelText(ru.addToGoogleWallet)).toBeNull();
  screen.unmount();
});

it('shows Add to Apple Wallet button on iOS when apple=true and opens URL on press', async () => {
  Platform.OS = 'ios';
  const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
  const passUrl = 'https://api.cashback-qr.poscenter.kz/wallet/apple/W1TEST.pkpass';

  mockRequest.mockImplementation((path: string, options?: { body?: { platform: string } }) => {
    if (path === '/me/cards') return Promise.resolve([testCard]);
    if (path.startsWith('/me/cards/card-123/qr')) {
      return Promise.resolve({ token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
    }
    if (path === '/me/wallet') return Promise.resolve({ apple: true, google: false });
    if (path === '/me/cards/card-123/wallet' && options?.body?.platform === 'apple') {
      return Promise.resolve({ url: passUrl, expires_at: '2026-10-17T01:30:00Z' });
    }
    return Promise.reject(new Error(`unexpected ${path}`));
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByLabelText(ru.addToAppleWallet)).toBeTruthy());

  fireEvent.press(screen.getByLabelText(ru.addToAppleWallet));

  await waitFor(() => {
    expect(mockRequest).toHaveBeenCalledWith(
      '/me/cards/card-123/wallet',
      expect.objectContaining({ method: 'POST', auth: true, body: { platform: 'apple' } }),
    );
  });
  await waitFor(() => expect(openUrlSpy).toHaveBeenCalledWith(passUrl));

  openUrlSpy.mockRestore();
  screen.unmount();
});

it('shows Add to Google Wallet button on Android when google=true and opens URL on press', async () => {
  Platform.OS = 'android';
  const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
  const saveUrl = 'https://pay.google.com/gp/v/save/eyJhbGciOiJSUzI1NiJ9.test';

  mockRequest.mockImplementation((path: string, options?: { body?: { platform: string } }) => {
    if (path === '/me/cards') return Promise.resolve([testCard]);
    if (path.startsWith('/me/cards/card-123/qr')) {
      return Promise.resolve({ token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
    }
    if (path === '/me/wallet') return Promise.resolve({ apple: false, google: true });
    if (path === '/me/cards/card-123/wallet' && options?.body?.platform === 'google') {
      return Promise.resolve({ url: saveUrl, expires_at: null });
    }
    return Promise.reject(new Error(`unexpected ${path}`));
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByLabelText(ru.addToGoogleWallet)).toBeTruthy());

  fireEvent.press(screen.getByLabelText(ru.addToGoogleWallet));

  await waitFor(() => {
    expect(mockRequest).toHaveBeenCalledWith(
      '/me/cards/card-123/wallet',
      expect.objectContaining({ method: 'POST', auth: true, body: { platform: 'google' } }),
    );
  });
  await waitFor(() => expect(openUrlSpy).toHaveBeenCalledWith(saveUrl));

  openUrlSpy.mockRestore();
  Platform.OS = 'ios';
  screen.unmount();
});

it('does not show wallet button on web even if wallet is available', async () => {
  Platform.OS = 'web';
  serve({
    '/me/cards/card-123/qr': { token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 },
    '/me/cards': [testCard],
    '/me/wallet': { apple: true, google: true },
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByText(ru.showToCashier)).toBeTruthy());

  expect(screen.queryByLabelText(ru.addToAppleWallet)).toBeNull();
  expect(screen.queryByLabelText(ru.addToGoogleWallet)).toBeNull();

  Platform.OS = 'ios';
  screen.unmount();
});

it('displays ErrorNotice when requestWalletLink rejects without crashing', async () => {
  Platform.OS = 'android';
  mockRequest.mockImplementation((path: string) => {
    if (path === '/me/cards') return Promise.resolve([testCard]);
    if (path.startsWith('/me/cards/card-123/qr')) {
      return Promise.resolve({ token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
    }
    if (path === '/me/wallet') return Promise.resolve({ apple: false, google: true });
    if (path === '/me/cards/card-123/wallet') {
      return Promise.reject(new ApiError('WALLET_UNAVAILABLE', 503));
    }
    return Promise.reject(new Error(`unexpected ${path}`));
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByLabelText(ru.addToGoogleWallet)).toBeTruthy());

  fireEvent.press(screen.getByLabelText(ru.addToGoogleWallet));

  await waitFor(() => {
    expect(screen.getByText(errorMessages.WALLET_UNAVAILABLE!)).toBeTruthy();
  });

  Platform.OS = 'ios';
  screen.unmount();
});

it('requestWalletLink correctly invokes api.request', async () => {
  const dummyApi = { request: jest.fn().mockResolvedValue({ url: 'https://test.link' }) };
  const res = await requestWalletLink(dummyApi, 'card-999', 'apple');
  expect(res.url).toBe('https://test.link');
  expect(dummyApi.request).toHaveBeenCalledWith(
    '/me/cards/card-999/wallet',
    expect.objectContaining({ method: 'POST', auth: true, body: { platform: 'apple' } }),
  );
});

it('does not request /me/wallet when platform is web', async () => {
  Platform.OS = 'web';
  mockRequest.mockClear();
  mockRequest.mockImplementation((path: string) => {
    if (path === '/me/cards') return Promise.resolve([testCard]);
    if (path.startsWith('/me/cards/card-123/qr')) {
      return Promise.resolve({ token: 'C1TESTTOKEN', expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
    }
    return Promise.resolve({});
  });

  const { screen } = mountScreen(<QrScreen />);
  await waitFor(() => expect(screen.getByText(ru.showToCashier)).toBeTruthy());
  expect(mockRequest).not.toHaveBeenCalledWith('/me/wallet', expect.anything());

  Platform.OS = 'ios';
  screen.unmount();
});
