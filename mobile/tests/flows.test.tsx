import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import Home from '../app/(app)/(tabs)/index';
import NotificationsScreen from '../app/(app)/(tabs)/notifications';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import QrScreen from '../app/(app)/(tabs)/qr';
import HistoryScreen from '../app/(app)/history';
import StatusScreen from '../app/(app)/status';
import Login from '../app/login';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import type { Card, Profile } from '../src/types/api';

const mockRequest = jest.fn();
const mockAccept = jest.fn().mockResolvedValue(undefined);
const mockPush = jest.fn();
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: { request: mockRequest }, session: { accept: mockAccept, logout: jest.fn() } }) }));
jest.mock('../src/storage/secure', () => ({ deviceId: async () => 'installation-id' }));
jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return {
    router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
    useLocalSearchParams: () => ({ id: 'promo' }),
    useFocusEffect: (effect: () => void) => React.useEffect(effect, [effect]),
  };
});
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) { return React.createElement(Text, { testID: 'qr-payload' }, value); };
});

const tier = { level: 1, name: 'Base', percent: '3', max_percent: '12', spend_total: '150000.0000', next_level: 2, next_threshold: '500000.0000', remaining: '350000.0000' };
const card: Card = { id: 'card-id', barcode: '0123456789012', balance: '0.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b', name: 'Shop', branding: null }, tier };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const offer = { id: 'o1', business_id: null, kind: 'offer', title: 'Покупайте выгодно', subtitle: null, badge: 'Скидка на хиты', body: null, image_url: null, starts_at: null, ends_at: null, is_new: true };
const banner = { ...offer, id: 'b1', kind: 'banner', title: 'Выиграй авто', badge: null };

function mountWith(element: ReactElement) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  const screen = render(<QueryClientProvider client={query}><I18nProvider><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider></QueryClientProvider>);
  return { screen, query };
}
function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}
beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });

it('logs in with a one-time WhatsApp code', async () => {
  const tokens = { access_token: 'a', refresh_token: 'r', expires_in: 900, token_type: 'bearer' };
  mockRequest.mockResolvedValueOnce({ status: 'sent', expires_in: 300 }).mockResolvedValueOnce(tokens);
  const { screen } = mountWith(<Login />);
  fireEvent.changeText(screen.getByLabelText(ru.phone), '+7 705 834 43 26');
  fireEvent.press(screen.getByRole('button', { name: ru.requestCode }));
  await waitFor(() => expect(screen.getByLabelText(ru.code)).toBeTruthy());
  expect(mockRequest).toHaveBeenNthCalledWith(1, '/auth/whatsapp/request', { method: 'POST', body: { phone: '+7 705 834 43 26', device_id: 'installation-id' } });
  expect(screen.getByText('+7 705 834 43 26')).toBeTruthy();
  fireEvent.changeText(screen.getByLabelText(ru.code), '01-23 45');
  fireEvent.press(screen.getByRole('button', { name: ru.verify }));
  await waitFor(() => expect(mockAccept).toHaveBeenCalledWith(tokens));
  expect(mockRequest).toHaveBeenNthCalledWith(2, '/auth/whatsapp/verify', { method: 'POST', body: { phone: '+7 705 834 43 26', device_id: 'installation-id', code: '012345' } });
  screen.unmount();
});

it('home shows phone, balance, status, max cashback and hot offers', async () => {
  serve({ '/me/cards': [card], '/me/profile': profile, '/me/promotions': { banners: [banner], offers: [offer], has_new: true } });
  const { screen } = mountWith(<Home />);
  await waitFor(() => expect(screen.getByText('+7 705 834 43 26')).toBeTruthy());
  await waitFor(() => expect(screen.getByText(ru.hotOffers)).toBeTruthy());
  expect(screen.getByText('Не упустите до 12% баллов')).toBeTruthy();
  expect(screen.getAllByText('0,00').length).toBeGreaterThanOrEqual(2);
  await waitFor(() => expect(screen.getByLabelText('Выиграй авто')).toBeTruthy());
  fireEvent.press(screen.getByLabelText('Скидка на хиты. Покупайте выгодно'));
  expect(mockPush).toHaveBeenCalledWith({ pathname: '/promotion/[id]', params: { id: 'o1' } });
  fireEvent.press(screen.getByLabelText(/Ваш статус 1/));
  expect(mockPush).toHaveBeenCalledWith('/status');
  screen.unmount();
});

it('status screen shows progress to the next level and opens accrual history', async () => {
  serve({ '/me/cards': [card] });
  const { screen } = mountWith(<StatusScreen />);
  await waitFor(() => expect(screen.getByText('ещё 350 000 ₸')).toBeTruthy());
  expect(screen.getByText('до статуса 2')).toBeTruthy();
  fireEvent.press(screen.getByRole('button', { name: ru.accrualHistory }));
  expect(mockPush).toHaveBeenCalledWith('/history');
  screen.unmount();
});

it('QR screen renders the dynamic token for the active card', async () => {
  const token = 'C1' + 'QRSTUVWX'.repeat(6);
  serve({ '/me/cards/card-id/qr': { token, expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 }, '/me/cards': [card] });
  const { screen } = mountWith(<QrScreen />);
  await waitFor(() => expect(screen.getByTestId('qr-payload').props.children).toBe(token));
  expect(mockRequest).toHaveBeenCalledWith('/me/cards/card-id/qr', expect.objectContaining({ auth: true }));
  screen.unmount();
});

it('accrual history filters by type through the backend', async () => {
  serve({ '/me/cards/card-id/transactions': { items: [{ id: 't', external_id: 'e', type: 'accrual', amount: '1500.0000', balance_after: '1500.0000', occurred_at: '2026-10-01T00:00:00Z', receipt_ref: null, store: 'Shop 1' }], has_more: false, next_cursor: null }, '/me/cards': [card] });
  const { screen } = mountWith(<HistoryScreen />);
  await waitFor(() => expect(screen.getByText('+1 500,00')).toBeTruthy());
  fireEvent.press(screen.getByRole('button', { name: ru.filterAccrual }));
  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('/me/cards/card-id/transactions?limit=20&type=accrual', expect.anything()));
  screen.unmount();
});

it('notifications are marked read when the tab opens and badges refresh', async () => {
  serve({ '/me/notifications/read': undefined, '/me/notifications': { items: [{ id: 'n', kind: 'accrual', title: 'Начислено 1 500 баллов', body: 'Shop', created_at: '2026-10-01T00:00:00Z', is_unread: true }], unread_count: 1 } });
  const { screen, query } = mountWith(<NotificationsScreen />);
  const invalidate = jest.spyOn(query, 'invalidateQueries');
  await waitFor(() => expect(screen.getByText('Начислено 1 500 баллов')).toBeTruthy());
  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('/me/notifications/read', { method: 'POST', auth: true }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['app', 'badges'] }));
  screen.unmount();
});

it('profile saves only changed fields in API format and switches language', async () => {
  serve({ '/me/profile': profile });
  const { screen } = mountWith(<ProfileScreen />);
  await waitFor(() => expect(screen.getByLabelText(ru.firstName)).toBeTruthy());
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  fireEvent.press(screen.getByLabelText(ru.birthDate));
  const dateInput = () => screen.getAllByLabelText(ru.birthDate).at(-1)!;
  fireEvent.changeText(dateInput(), '31.02.1990');
  fireEvent.press(screen.getByRole('button', { name: ru.done }));
  expect(screen.getByText(ru.invalidDate)).toBeTruthy();
  fireEvent.changeText(dateInput(), '01.02.1990');
  fireEvent.press(screen.getByRole('button', { name: ru.done }));
  fireEvent.press(screen.getByLabelText(ru.gender));
  fireEvent.press(screen.getByRole('radio', { name: ru.female }));

  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Айгерим', birth_date: '1990-02-01', gender: 'female' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(mockRequest).toHaveBeenCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { first_name: 'Айгерим', gender: 'female', birth_date: '1990-02-01' } });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());

  mockRequest.mockResolvedValueOnce({ ...profile, language: 'kz' });
  await act(async () => { fireEvent.press(screen.getByRole('radio', { name: ru.langKz })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { language: 'kz' } });
  await waitFor(() => expect(screen.getByText('Менің профилім')).toBeTruthy());
  screen.unmount();
});
