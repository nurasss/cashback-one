import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import Home from '../app/(app)/(tabs)/index';
import QrScreen from '../app/(app)/(tabs)/qr';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Card, Profile } from '../src/types/api';

const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }) }));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) { return React.createElement(Text, { testID: 'qr-payload' }, value); };
});

const card: Card = { id: 'card-id', barcode: '0123456789012', balance: '0.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b', name: 'Shop', branding: null }, tier: null };
const second: Card = { ...card, id: 'card-2', barcode: '000123456', business: { id: 'b2', name: 'Market', branding: null } };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const token = 'C1' + 'QRSTUVWX'.repeat(6);

function mountWith(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><I18nProvider initial={language}><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider></QueryClientProvider>);
}
function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}
const qrReply = () => ({ token, expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });

describe('QR screen', () => {
  it('shows the dynamic QR without a barcode and never puts the card number into it', async () => {
    serve({ '/me/cards/card-id/qr': qrReply(), '/me/cards': [card] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload').props.children).toBe(token));
    expect(screen.queryByRole('button', { name: 'QR-код' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Штрихкод' })).toBeNull();
    screen.unmount();
  });

  it('requests the QR of the card chosen by the customer', async () => {
    serve({ '/me/cards/card-id/qr': qrReply(), '/me/cards/card-2/qr': qrReply(), '/me/cards': [card, second] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload')).toBeTruthy());
    fireEvent.press(screen.getByRole('button', { name: 'Market' }));
    await waitFor(() => expect(mockRequest.mock.calls.some(call => String(call[0]).startsWith('/me/cards/card-2/qr'))).toBe(true));
    await waitFor(() => expect(screen.getByTestId('qr-payload')).toBeTruthy());
    screen.unmount();
  });

  it('blocked card: no QR request', async () => {
    serve({ '/me/cards': [{ ...card, is_blocked: true }] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.cardBlocked)).toBeTruthy());
    expect(mockRequest.mock.calls.some(call => String(call[0]).endsWith('/qr'))).toBe(false);
    screen.unmount();
  });

  it('no card: no code', async () => {
    serve({ '/me/cards': [] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.noCardTitle)).toBeTruthy());
    expect(screen.queryByTestId('qr-payload')).toBeNull();
    screen.unmount();
  });
});

describe('Balance delay note on the home screen', () => {
  const approved = 'Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.';
  const home = { '/me/cards': [card], '/me/profile': profile, '/me/promotions': { banners: [], offers: [], has_new: false } };

  it('shows the approved Russian text', async () => {
    serve(home);
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(approved)).toBeTruthy());
    expect(ru.balanceDelayNote).toBe(approved);
    screen.unmount();
  });

  it('shows the Kazakh equivalent when the language is Kazakh', async () => {
    serve({ ...home, '/me/profile': { ...profile, language: 'kz' } });
    const screen = mountWith(<Home />, 'kz');
    await waitFor(() => expect(screen.getByText(kz.balanceDelayNote)).toBeTruthy());
    expect(screen.queryByText(approved)).toBeNull();
    screen.unmount();
  });

  it('states the twice-a-day schedule, matching the site, without hours or shifts', () => {
    expect(kz.balanceDelayNote).toBe('Баланс бірден жаңартылмайды. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі.');
    for (const text of [ru.balanceDelayNote, kz.balanceDelayNote]) {
      expect(text).not.toMatch(/24|48|час|сағат|смен/i);
    }
    expect(kz.balanceDelayNote).not.toBe(ru.balanceDelayNote);
  });

  it('is hidden when there is no card to update', async () => {
    serve({ ...home, '/me/cards': [] });
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.noCardTitle)).toBeTruthy());
    expect(screen.queryByText(approved)).toBeNull();
    screen.unmount();
  });
});
