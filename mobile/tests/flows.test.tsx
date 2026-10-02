import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert } from 'react-native';
import Bind from '../app/(wallet)/bind';
import CardDetail from '../app/(wallet)/cards/[id]';
import Login from '../app/login';
import { ApiError } from '../src/api/errors';
import { ru } from '../src/i18n/ru';
import type { Card } from '../src/types/api';
const mockRequest = jest.fn();
const mockAccept = jest.fn().mockResolvedValue(undefined);
const mockReplace = jest.fn();
const mockApi = { request: mockRequest };
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: mockApi, session: { accept: mockAccept } }) }));
jest.mock('../src/storage/secure', () => ({ deviceId: async () => 'installation-id' }));
jest.mock('expo-router', () => ({ router: { replace: (...args: unknown[]) => mockReplace(...args) }, useLocalSearchParams: () => ({ id: 'card-id' }) }));
jest.mock('react-native-qrcode-svg', () => function MockQr() { return null; });
const card: Card = { id: 'card-id', barcode: '0123456789012', balance: '15.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b', name: 'Shop', branding: null } };
function client() { return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } }); }
beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });
it('SMS requests phone/device, verifies exact six-digit code and accepts real token DTO', async () => {
  const tokens = { access_token: 'a', refresh_token: 'r', expires_in: 900, token_type: 'bearer' };
  mockRequest.mockResolvedValueOnce({ status: 'sent', expires_in: 300 }).mockResolvedValueOnce(tokens);
  const screen = render(<Login />); fireEvent.press(screen.getByRole('button', { name: ru.sms }));
  fireEvent.changeText(screen.getByLabelText(ru.phone), '+7 701 123 45 67'); fireEvent.press(screen.getByRole('button', { name: ru.requestSms }));
  await waitFor(() => expect(screen.getByLabelText(ru.otp)).toBeTruthy());
  expect(mockRequest).toHaveBeenNthCalledWith(1, '/auth/sms/request', { method: 'POST', body: { phone: '+7 701 123 45 67', device_id: 'installation-id' } });
  fireEvent.changeText(screen.getByLabelText(ru.otp), '012345'); fireEvent.press(screen.getByRole('button', { name: ru.verify }));
  await waitFor(() => expect(mockAccept).toHaveBeenCalledWith(tokens));
  expect(mockRequest).toHaveBeenNthCalledWith(2, '/auth/sms/verify', { method: 'POST', body: { phone: '+7 701 123 45 67', device_id: 'installation-id', code: '012345' } });
  screen.unmount();
});
it('WhatsApp challenge request has only device_id and displays backend challenge instructions', async () => {
  mockRequest.mockResolvedValueOnce({ challenge_id: 'c', code: 'ABCDEFGH', login_url: 'https://wa.me/70000000000?text=ABCDEFGH', expires_in: 180, expires_at: new Date(Date.now() + 180000).toISOString() });
  const screen = render(<Login />); fireEvent.press(screen.getByRole('button', { name: ru.whatsapp }));
  await waitFor(() => expect(screen.getByText('ABCDEFGH')).toBeTruthy());
  expect(mockRequest).toHaveBeenCalledWith('/auth/challenge', { method: 'POST', body: { device_id: 'installation-id' } }); expect(screen.getByText(ru.waInstruction)).toBeTruthy(); screen.unmount();
});
it('ambiguous bind offers backend businesses and resubmits with selected business_id', async () => {
  const query = client(); query.setQueryData(['wallet', 'cards'], []);
  mockRequest.mockRejectedValueOnce(new ApiError('BUSINESS_SELECTION_REQUIRED', 409, [{ id: 'b', name: 'Shop' }])).mockResolvedValueOnce(card);
  const screen = render(<QueryClientProvider client={query}><Bind /></QueryClientProvider>);
  fireEvent.changeText(screen.getByLabelText(ru.barcode), card.barcode); fireEvent.press(screen.getByRole('button', { name: ru.bind }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Shop' })).toBeTruthy()); fireEvent.press(screen.getByRole('button', { name: 'Shop' }));
  await waitFor(() => expect(mockReplace).toHaveBeenCalled());
  expect(mockRequest).toHaveBeenNthCalledWith(2, '/me/cards/bind', { method: 'POST', auth: true, body: { barcode: card.barcode, business_id: 'b' } });
  expect(query.getQueryData(['wallet', 'cards'])).toEqual([card]); screen.unmount(); query.clear();
});
it('history loads only next backend cursor, and confirmed hide updates cache after server success', async () => {
  const query = client(); query.setQueryData(['wallet', 'cards'], [card]);
  let confirm: (() => void) | undefined; let deleted: (() => void) | undefined;
  jest.spyOn(Alert, 'alert').mockImplementation((_title, _message, buttons) => { confirm = () => buttons?.[1]?.onPress?.(); });
  mockRequest.mockImplementation((path: string, options: { method?: string }) => {
    if (options.method === 'DELETE') return new Promise<void>(resolve => { deleted = resolve; });
    if (path.includes('cursor=')) return Promise.resolve({ items: [], has_more: false, next_cursor: null });
    if (path.includes('transactions')) return Promise.resolve({ items: [], has_more: true, next_cursor: 'opaque+/=' });
    return Promise.resolve(card);
  });
  const screen = render(<QueryClientProvider client={query}><CardDetail /></QueryClientProvider>);
  await waitFor(() => expect(screen.getByRole('button', { name: ru.more })).toBeTruthy()); fireEvent.press(screen.getByRole('button', { name: ru.more }));
  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('/me/cards/card-id/transactions?limit=20&cursor=opaque%2B%2F%3D', expect.objectContaining({ auth: true })));
  fireEvent.press(screen.getByRole('button', { name: ru.hide }));
  expect(mockRequest.mock.calls.some(call => call[1]?.method === 'DELETE')).toBe(false);
  await act(async () => { confirm?.(); }); expect(query.getQueryData(['wallet', 'cards'])).toEqual([card]);
  await act(async () => { deleted?.(); }); await waitFor(() => expect(query.getQueryData(['wallet', 'cards'])).toEqual([]));
  expect(mockReplace).toHaveBeenCalledWith('/'); screen.unmount(); query.clear(); jest.restoreAllMocks();
});
