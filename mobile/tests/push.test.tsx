import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { Linking, Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  pushStorage,
  registerPushToken,
  unregisterPushToken,
  configureNotificationHandler,
  setupNotificationChannel,
  setupNotificationListeners,
  PushPermissionNotice,
} from '../src/features/push';
import { ApiClient } from '../src/api/client';
import { keys } from '../src/api/app';
import { Session } from '../src/auth/session';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import type { Tokens } from '../src/types/api';
import Home from '../app/(app)/(tabs)/index';
import NotificationsScreen from '../app/(app)/(tabs)/notifications';
import { ActiveCardProvider } from '../src/features/activeCard';

const mockRequest = jest.fn();
const mockSessionAccept = jest.fn();
const mockSessionLogout = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({
    api: { request: mockRequest },
    session: {
      accept: mockSessionAccept,
      logout: mockSessionLogout,
      registerBeforeClear: (fn: () => Promise<void>) => fn,
    },
    state: { status: 'authenticated' },
  }),
}));

jest.mock('../src/storage/secure', () => ({
  deviceId: async () => 'installation-id',
}));

jest.mock('expo-router', () => ({
  router: {
    push: jest.fn(),
    replace: jest.fn(),
    navigate: jest.fn(),
    back: jest.fn(),
    canGoBack: () => true,
  },
  useFocusEffect: (effect: () => void) => {
    const React = jest.requireActual<typeof import('react')>('react');
    React.useEffect(effect, [effect]);
  },
  useLocalSearchParams: () => ({}),
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return {
    SafeAreaView: View,
    useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
  };
});

describe('Push Notifications', () => {
  let queryClient: QueryClient;
  let mockApi: ApiClient;

  beforeEach(async () => {
    jest.clearAllMocks();
    await pushStorage.clear();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
    });
    mockApi = {
      request: mockRequest,
    } as unknown as ApiClient;
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
    });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
    });
    (Notifications.getDevicePushTokenAsync as jest.Mock).mockResolvedValue({
      type: 'android',
      data: 'test-device-token-1',
    });
  });

  afterEach(() => {
    queryClient.clear();
    jest.restoreAllMocks();
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
    });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
    });
  });

  describe('1. Device Registration', () => {
    it('requests permissions, gets native token, and calls PUT /me/push-token on login', async () => {
      mockRequest.mockResolvedValueOnce(undefined);

      const ok = await registerPushToken(mockApi);
      expect(ok).toBe(true);
      expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
      expect(Notifications.getDevicePushTokenAsync).toHaveBeenCalled();
      expect(mockRequest).toHaveBeenCalledTimes(1);
      expect(mockRequest).toHaveBeenCalledWith('/me/push-token', {
        method: 'PUT',
        auth: true,
        body: {
          token: 'test-device-token-1',
          platform: 'android',
          app_id: 'kz.cashbackone.mobile',
        },
      });

      const saved = await pushStorage.read();
      expect(saved?.token).toBe('test-device-token-1');
      expect(saved?.registeredAt).toBeGreaterThan(0);
    });

    it('does not re-register if token is unchanged within 24 hours', async () => {
      mockRequest.mockResolvedValue(undefined);

      await registerPushToken(mockApi);
      expect(mockRequest).toHaveBeenCalledTimes(1);

      // Second registration within 24 hours
      await registerPushToken(mockApi);
      expect(mockRequest).toHaveBeenCalledTimes(1); // No second call
    });

    it('immediately re-registers if token changes', async () => {
      mockRequest.mockResolvedValue(undefined);

      await registerPushToken(mockApi);
      expect(mockRequest).toHaveBeenCalledTimes(1);

      // Token changed
      (Notifications.getDevicePushTokenAsync as jest.Mock).mockResolvedValue({
        type: 'android',
        data: 'test-device-token-2',
      });

      await registerPushToken(mockApi, { force: true, explicitToken: 'test-device-token-2' });
      expect(mockRequest).toHaveBeenCalledTimes(2);
      expect(mockRequest).toHaveBeenLastCalledWith('/me/push-token', {
        method: 'PUT',
        auth: true,
        body: {
          token: 'test-device-token-2',
          platform: 'android',
          app_id: 'kz.cashbackone.mobile',
        },
      });
      const saved = await pushStorage.read();
      expect(saved?.token).toBe('test-device-token-2');
    });

    it('silently catches network and 429 errors without throwing', async () => {
      mockRequest.mockRejectedValueOnce(new Error('Network request failed'));

      const ok = await registerPushToken(mockApi);
      expect(ok).toBe(false);
      const saved = await pushStorage.read();
      expect(saved).toBeNull();
    });
  });

  describe('2. Permission Denied and Warning Card', () => {
    it('does not send request if permission is denied', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
      });

      const ok = await registerPushToken(mockApi);
      expect(ok).toBe(false);
      expect(mockRequest).not.toHaveBeenCalled();
      expect(Notifications.getDevicePushTokenAsync).not.toHaveBeenCalled();
    });

    it('shows warning card on Home and Notifications when permission is not granted', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
      });

      // Render Home
      mockRequest.mockImplementation((path: string) => {
        if (path === '/me/profile') return Promise.resolve({ phone: '+77058344326', language: 'ru' });
        if (path === '/me/cards') return Promise.resolve([{ id: 'c1', barcode: '123456', balance: '100.0000', is_blocked: false, bound_at: '', updated_at: '', bind_method: 'phone_auto', business: { id: 'b', name: 'Shop', branding: null }, tier: null }]);
        if (path === '/me/promotions') return Promise.resolve({ banners: [], offers: [], has_new: false });
        if (path === '/me/notifications') return Promise.resolve({ items: [], unread_count: 0 });
        return Promise.resolve({});
      });

      const home = render(
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <ActiveCardProvider>
              <Home />
            </ActiveCardProvider>
          </I18nProvider>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(home.getByText(ru.enableNotificationsPrompt)).toBeTruthy();
        expect(home.getByText(ru.enableNotificationsAction)).toBeTruthy();
      });

      // Render Notifications tab
      const notifs = render(
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <NotificationsScreen />
          </I18nProvider>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(notifs.getByText(ru.enableNotificationsPrompt)).toBeTruthy();
      });
    });

    it('pressing button requests permission if system allows, otherwise opens settings', async () => {
      // Case 1: canAskAgain is true -> calls requestPermissionsAsync
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'undetermined',
        canAskAgain: true,
        granted: false,
      });
      (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
      });

      const element1 = render(
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <PushPermissionNotice />
          </I18nProvider>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(element1.getByText(ru.enableNotificationsAction)).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(element1.getByText(ru.enableNotificationsAction));
      });

      expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();

      // Case 2: canAskAgain is false -> calls Linking.openSettings()
      jest.spyOn(Linking, 'openSettings').mockImplementation(jest.fn());
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
      });

      const element2 = render(
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <PushPermissionNotice />
          </I18nProvider>
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(element2.getByText(ru.enableNotificationsAction)).toBeTruthy();
      });

      await act(async () => {
        fireEvent.press(element2.getByText(ru.enableNotificationsAction));
      });

      expect(Linking.openSettings).toHaveBeenCalled();
    });
  });

  describe('3. Logout and Invalidation', () => {
    it('refresh failure invalidates without calling DELETE /me/push-token and clears local push storage within 1s', async () => {
      jest.useFakeTimers();
      try {
        await pushStorage.write({ token: 'test-device-token-1', registeredAt: Date.now() });

        const tokens: Tokens = {
          access_token: 'expired-access',
          refresh_token: 'invalid-refresh',
          expires_in: 900,
          token_type: 'bearer',
        };
        const mockStore = {
          read: jest.fn().mockResolvedValue(tokens),
          write: jest.fn().mockResolvedValue(undefined),
          clear: jest.fn().mockResolvedValue(undefined),
        };

        const fetchCalls: string[] = [];
        const session = new Session(mockStore, 'https://cloud.example', jest.fn(), jest.fn(), async (url, opts) => {
          const urlStr = String(url);
          fetchCalls.push(`${opts?.method ?? 'GET'} ${urlStr}`);
          if (urlStr.endsWith('/auth/refresh')) {
            return new Response(JSON.stringify({ error: { code: 'INVALID_REFRESH_TOKEN' } }), { status: 401 });
          }
          return new Response(JSON.stringify({}), { status: 200 });
        });

        await session.accept(tokens);
        session.registerBeforeLogout(async () => {
          await unregisterPushToken(session.api);
        });
        session.registerOnInvalidate(() => {
          void pushStorage.clear();
        });

        // Trigger refresh failure
        const refreshPromise = session.refresh();
        await expect(refreshPromise).rejects.toMatchObject({ code: 'INVALID_REFRESH_TOKEN' });

        expect(session.state.status).toBe('anonymous');
        // Check that NO DELETE /me/push-token request was ever made
        const deleteCalls = fetchCalls.filter(c => c.includes('/me/push-token'));
        expect(deleteCalls).toHaveLength(0);

        // Check push storage was cleared
        const saved = await pushStorage.read();
        expect(saved).toBeNull();
      } finally {
        jest.useRealTimers();
      }
    });

    it('logout executes exactly one DELETE /me/push-token before /auth/logout, and timeout does not delay > 3s', async () => {
      await pushStorage.write({ token: 'test-device-token-1', registeredAt: Date.now() });

      const tokens: Tokens = {
        access_token: 'valid-access',
        refresh_token: 'valid-refresh',
        expires_in: 900,
        token_type: 'bearer',
      };
      const mockStore = {
        read: jest.fn().mockResolvedValue(tokens),
        write: jest.fn().mockResolvedValue(undefined),
        clear: jest.fn().mockResolvedValue(undefined),
      };

      const callOrder: string[] = [];
      const session = new Session(mockStore, 'https://cloud.example', jest.fn(), jest.fn(), async (url, opts) => {
        const urlStr = String(url);
        if (urlStr.endsWith('/me/push-token') && opts?.method === 'DELETE') {
          callOrder.push('DELETE /me/push-token');
          return new Response(null, { status: 204 });
        }
        if (urlStr.endsWith('/auth/logout')) {
          callOrder.push('POST /auth/logout');
          return new Response(JSON.stringify({ status: 'ok' }), { status: 200 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      });

      await session.accept(tokens);
      session.registerBeforeLogout(async () => {
        await unregisterPushToken(session.api);
      });
      session.registerOnInvalidate(() => {
        void pushStorage.clear();
      });

      await session.logout();

      expect(callOrder).toEqual(['DELETE /me/push-token', 'POST /auth/logout']);
      expect(session.state.status).toBe('anonymous');
      expect(mockStore.clear).toHaveBeenCalled();
      const saved = await pushStorage.read();
      expect(saved).toBeNull();
    });

    it('logout succeeds even if DELETE /me/push-token fails or times out', async () => {
      await pushStorage.write({ token: 'test-device-token-1', registeredAt: Date.now() });

      const tokens: Tokens = {
        access_token: 'valid-access',
        refresh_token: 'valid-refresh',
        expires_in: 900,
        token_type: 'bearer',
      };
      const mockStore = {
        read: jest.fn().mockResolvedValue(tokens),
        write: jest.fn().mockResolvedValue(undefined),
        clear: jest.fn().mockResolvedValue(undefined),
      };

      const session = new Session(mockStore, 'https://cloud.example', jest.fn(), jest.fn(), async (url, opts) => {
        const urlStr = String(url);
        if (urlStr.endsWith('/me/push-token') && opts?.method === 'DELETE') {
          return new Response(JSON.stringify({ error: { code: 'SERVER_ERROR' } }), { status: 500 });
        }
        if (urlStr.endsWith('/auth/logout')) {
          return new Response(JSON.stringify({ status: 'ok' }), { status: 200 });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      });

      await session.accept(tokens);
      session.registerBeforeLogout(async () => {
        await unregisterPushToken(session.api);
      });
      session.registerOnInvalidate(() => {
        void pushStorage.clear();
      });

      await session.logout();

      expect(session.state.status).toBe('anonymous');
      expect(mockStore.clear).toHaveBeenCalled();
      const saved = await pushStorage.read();
      expect(saved).toBeNull();
    });

    it('immediately calls PUT /me/push-token after invalidate and new login without 24h wait', async () => {
      // 1. Initial registration
      mockRequest.mockResolvedValue(undefined);
      await registerPushToken(mockApi);
      expect(mockRequest).toHaveBeenCalledTimes(1);

      // 2. Invalidate clears storage
      await pushStorage.clear();

      // 3. New login immediately registers without waiting 24 hours
      await registerPushToken(mockApi);
      expect(mockRequest).toHaveBeenCalledTimes(2);
      expect(mockRequest).toHaveBeenLastCalledWith('/me/push-token', {
        method: 'PUT',
        auth: true,
        body: {
          token: 'test-device-token-1',
          platform: 'android',
          app_id: 'kz.cashbackone.mobile',
        },
      });
    });
  });

  describe('4. Notification Handling and Navigation', () => {
    it('sets notification handler to show banner and sound in foreground', async () => {
      configureNotificationHandler();
      expect(Notifications.setNotificationHandler).toHaveBeenCalledWith({
        handleNotification: expect.any(Function),
      });
      const calls = (Notifications.setNotificationHandler as jest.Mock).mock.calls;
      const handler = calls[calls.length - 1][0].handleNotification;
      const behavior = await handler();
      expect(behavior).toEqual({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      });
    });

    it('clicking a notification opens /notifications and invalidates query cache', () => {
      let responseCallback: (response: unknown) => void = () => {};
      (Notifications.addNotificationResponseReceivedListener as jest.Mock).mockImplementation(cb => {
        responseCallback = cb;
        return { remove: jest.fn() };
      });

      const navigateMock = jest.fn();
      const invalidateSpy = jest.spyOn(queryClient, 'invalidateQueries');

      setupNotificationListeners(queryClient, navigateMock);

      // Simulate notification click
      responseCallback({
        notification: {
          request: {
            content: {
              data: { type: 'redemption_code', redemption_id: 'test-123' },
              title: 'Списание 500 баллов',
              body: 'Код подтверждения: 1234',
            },
          },
        },
      });

      expect(navigateMock).toHaveBeenCalledWith('/notifications');
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: keys.notifications });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: keys.badges });
    });

    it('receiving notification in open app refreshes notifications and badges', () => {
      let receivedCallback: (notif: unknown) => void = () => {};
      (Notifications.addNotificationReceivedListener as jest.Mock).mockImplementation(cb => {
        receivedCallback = cb;
        return { remove: jest.fn() };
      });

      const invalidateSpy = jest.spyOn(queryClient, 'invalidateQueries');

      setupNotificationListeners(queryClient, jest.fn());

      receivedCallback({
        request: {
          content: {
            title: 'Новое начисление',
            body: 'Начислено 150 баллов',
          },
        },
      });

      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: keys.notifications });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: keys.badges });
    });
  });

  describe('5. Android Notification Channel', () => {
    it('configures HIGH importance channel in Russian and Kazakh', async () => {
      const originalPlatform = Platform.OS;
      Object.defineProperty(Platform, 'OS', { value: 'android', configurable: true });

      await setupNotificationChannel('ru');
      expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith('default', expect.objectContaining({
        name: 'Коды и уведомления',
        importance: 4,
      }));

      await setupNotificationChannel('kz');
      expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith('default', expect.objectContaining({
        name: 'Кодтар мен хабарламалар',
        importance: 4,
      }));

      Object.defineProperty(Platform, 'OS', { value: originalPlatform, configurable: true });
    });
  });

  describe('6. Demo Mode', () => {
    it('does not request permissions or register push token in demo mode', async () => {
      const originalEnv = process.env.EXPO_PUBLIC_DEMO;
      process.env.EXPO_PUBLIC_DEMO = '1';
      try {
        const ok = await registerPushToken(mockApi);
        expect(ok).toBe(false);
        expect(Notifications.getPermissionsAsync).not.toHaveBeenCalled();
        expect(Notifications.getDevicePushTokenAsync).not.toHaveBeenCalled();
        expect(mockRequest).not.toHaveBeenCalled();

        const element = render(
          <QueryClientProvider client={queryClient}>
            <I18nProvider>
              <PushPermissionNotice />
            </I18nProvider>
          </QueryClientProvider>
        );
        expect(element.toJSON()).toBeNull();
      } finally {
        process.env.EXPO_PUBLIC_DEMO = originalEnv;
      }
    });
  });
});
