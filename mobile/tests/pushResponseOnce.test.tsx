import { act, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Notifications from 'expo-notifications';
import { I18nProvider } from '../src/i18n';
import { PushNotificationManager, resetHandledResponseForTests } from '../src/features/push';
import { getTapTarget, notificationEpoch, resetNotificationSignals, subscribeTapTarget } from '../src/features/notificationSignals';

const mockNavigate = jest.fn();
const mockSession = { api: { request: jest.fn().mockResolvedValue(undefined) }, registerBeforeLogout: () => () => undefined, registerOnInvalidate: () => () => undefined };

jest.mock('../src/auth/provider', () => ({ useSession: () => ({ session: mockSession, state: { status: 'authenticated' } }) }));
jest.mock('../src/storage/secure', () => ({ deviceId: async () => 'installation-id' }));
jest.mock('expo-router', () => ({ router: { navigate: (...args: unknown[]) => mockNavigate(...args) } }));

const lastResponse = Notifications.getLastNotificationResponseAsync as jest.Mock;
const response = (identifier: string) => ({ notification: { request: { identifier, content: { data: { type: 'broadcast', notification_id: 'n1' } } } } });

function mount() {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}><I18nProvider initial="ru"><PushNotificationManager /></I18nProvider></QueryClientProvider>);
}

beforeEach(() => { jest.clearAllMocks(); resetHandledResponseForTests(); resetNotificationSignals(); });

it('cold start: the tap that opened the app opens the list, and a remount does not replay it', async () => {
  lastResponse.mockResolvedValue(response('tap-1'));
  const first = mount();
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/notifications'));
  first.unmount();
  mockNavigate.mockClear();
  mount();
  await waitFor(() => expect(lastResponse).toHaveBeenCalledTimes(2));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(mockNavigate).not.toHaveBeenCalled();
});

it('a different later tap (new identifier) is opened again', async () => {
  lastResponse.mockResolvedValue(response('tap-1'));
  mount();
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledTimes(1));
  lastResponse.mockResolvedValue(response('tap-2'));
  mount();
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledTimes(2));
});

it('no last response: nothing is opened', async () => {
  lastResponse.mockResolvedValue(null);
  mount();
  await waitFor(() => expect(lastResponse).toHaveBeenCalled());
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(mockNavigate).not.toHaveBeenCalled();
});

const UUID_A = '8f14e45f-ceea-467a-9575-2e8b4f1a7c11';
const UUID_B = '1679091c-5a88-4f0e-b3d2-0c6f0f2b9a42';
const tapped = (identifier: string, data: Record<string, unknown>) => ({ notification: { request: { identifier, content: { data } } } });
const addResponseListener = Notifications.addNotificationResponseReceivedListener as jest.Mock;
const addReceivedListener = Notifications.addNotificationReceivedListener as jest.Mock;
const tapLive = (response: unknown) => act(() => { (addResponseListener.mock.calls.at(-1)?.[0] as (r: unknown) => void)(response); });

describe('a tap names the notification to show, but marks nothing itself', () => {
  it('cold start tap on a broadcast: the target is the id from the payload, validated', async () => {
    lastResponse.mockResolvedValue(tapped('c1', { type: 'broadcast', notification_id: UUID_A }));
    mount();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/notifications'));
    expect(getTapTarget()).toBe(UUID_A);
    expect(mockSession.api.request).not.toHaveBeenCalledWith(expect.stringContaining('mark-read'), expect.anything());
  });

  it('foreground/background tap: the target is set, the screen opens; a second tap on another push moves the target', async () => {
    lastResponse.mockResolvedValue(null);
    mount();
    await waitFor(() => expect(addResponseListener).toHaveBeenCalled());
    tapLive(tapped('l1', { type: 'broadcast', notification_id: UUID_A }));
    expect(mockNavigate).toHaveBeenCalledWith('/notifications');
    expect(getTapTarget()).toBe(UUID_A);
    tapLive(tapped('l2', { type: 'broadcast', dataString: undefined, notification_id: UUID_B }));
    expect(getTapTarget()).toBe(UUID_B);
  });

  it('a repeated tap on the same push announces the target again', async () => {
    lastResponse.mockResolvedValue(null);
    mount();
    await waitFor(() => expect(addResponseListener).toHaveBeenCalled());
    const seen = jest.fn();
    subscribeTapTarget(seen);
    tapLive(tapped('l1', { type: 'broadcast', notification_id: UUID_A }));
    tapLive(tapped('l1', { type: 'broadcast', notification_id: UUID_A }));
    expect(seen).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['a write-off code', { type: 'redemption_code', redemption_id: UUID_A }],
    ['a broadcast with a malformed id', { type: 'broadcast', notification_id: 'not-a-uuid; DROP' }],
    ['a broadcast without an id', { type: 'broadcast' }],
    ['an unknown type that carries an id', { type: 'something', notification_id: UUID_A }],
    ['a non-string id', { type: 'broadcast', notification_id: 7 }],
  ])('%s: the screen opens, but no notification is named', async (_name, data) => {
    lastResponse.mockResolvedValue(null);
    mount();
    await waitFor(() => expect(addResponseListener).toHaveBeenCalled());
    tapLive(tapped('x1', data));
    expect(mockNavigate).toHaveBeenCalledWith('/notifications');
    expect(getTapTarget()).toBeNull();
  });

  it('a received push (app open) only invalidates and bumps the epoch: it names and marks nothing', async () => {
    lastResponse.mockResolvedValue(null);
    mount();
    await waitFor(() => expect(addReceivedListener).toHaveBeenCalled());
    const before = notificationEpoch();
    act(() => { (addReceivedListener.mock.calls.at(-1)?.[0] as () => void)(); });
    expect(notificationEpoch()).toBe(before + 1);
    expect(getTapTarget()).toBeNull();
  });

  it('leaving the authenticated session drops a pending target', async () => {
    lastResponse.mockResolvedValue(tapped('c9', { type: 'broadcast', notification_id: UUID_A }));
    const view = mount();
    await waitFor(() => expect(getTapTarget()).toBe(UUID_A));
    view.unmount();
    expect(getTapTarget()).toBeNull();
  });
});
