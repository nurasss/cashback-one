import { useCallback, useEffect, useState } from 'react';
import { AppState, Linking, Platform, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { ApiClient } from '../api/client';
import { keys } from '../api/app';
import { useSession } from '../auth/provider';
import { DEMO_ENABLED } from '../demo/mockApi';
import { getClientConfig } from '../config/client';
import { useI18n, type Language } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import { Button } from '../components/ui';
import { Icon } from '../components/icons';
import { bumpNotificationEpoch, isNotificationId, resetNotificationSignals, setTapTarget } from './notificationSignals';
import { pushPayload } from './notificationTray';

const PUSH_STORAGE_KEY = 'cashback-one.push-registration.v1';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export interface PushRegistrationState {
  token: string;
  registeredAt: number;
}

let memoryStorage: PushRegistrationState | null = null;

export const pushStorage = {
  async read(): Promise<PushRegistrationState | null> {
    if (Platform.OS === 'web') return memoryStorage;
    try {
      const raw = await SecureStore.getItemAsync(PUSH_STORAGE_KEY);
      if (!raw) return memoryStorage;
      return JSON.parse(raw) as PushRegistrationState;
    } catch {
      return memoryStorage;
    }
  },
  async write(state: PushRegistrationState): Promise<void> {
    memoryStorage = state;
    if (Platform.OS === 'web') return;
    try {
      await SecureStore.setItemAsync(PUSH_STORAGE_KEY, JSON.stringify(state));
    } catch {
      // In-memory fallback
    }
  },
  async clear(): Promise<void> {
    memoryStorage = null;
    if (Platform.OS === 'web') return;
    try {
      await SecureStore.deleteItemAsync(PUSH_STORAGE_KEY);
    } catch {
      // In-memory fallback
    }
  },
};

export function isDemoMode(): boolean {
  return DEMO_ENABLED || process.env.EXPO_PUBLIC_DEMO === '1';
}

export function getPushAppId(): string {
  const client = getClientConfig();
  return (
    client.android_app_id ||
    Constants.expoConfig?.android?.package ||
    (Constants as { applicationId?: string }).applicationId ||
    'kz.cashbackone.mobile'
  );
}

export function configureNotificationHandler(): void {
  try {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
  } catch {
    // Ignore in unsupported environments
  }
}

// Configure handler immediately on module load
configureNotificationHandler();

export async function setupNotificationChannel(language: Language = 'ru'): Promise<void> {
  if (Platform.OS !== 'android') return;
  const name = language === 'kz' ? 'Кодтар мен хабарламалар' : 'Коды и уведомления';
  try {
    await Notifications.setNotificationChannelAsync('default', {
      name,
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      sound: 'default',
      enableVibrate: true,
      showBadge: true,
    });
  } catch {
    // Ignore in unsupported environments or mocks
  }
}

export async function registerPushToken(
  api: ApiClient,
  options?: { force?: boolean; explicitToken?: string }
): Promise<boolean> {
  if (isDemoMode() || Platform.OS === 'web') return false;

  try {
    const perm = await Notifications.getPermissionsAsync();
    let status = perm.status;
    if (status !== 'granted' && perm.canAskAgain) {
      const requested = await Notifications.requestPermissionsAsync();
      status = requested.status;
    }
    if (status !== 'granted') {
      return false;
    }

    const rawToken =
      options?.explicitToken ??
      (await Notifications.getDevicePushTokenAsync()).data;
    const token = typeof rawToken === 'string' ? rawToken.trim() : '';
    if (!token) return false;

    const saved = await pushStorage.read();
    const isSameToken = saved?.token === token;
    const isWithin24Hours = !!(saved && Date.now() - saved.registeredAt < ONE_DAY_MS);

    if (!options?.force && isSameToken && isWithin24Hours) {
      return true;
    }

    const appId = getPushAppId();

    await api.request<void>('/me/push-token', {
      method: 'PUT',
      auth: true,
      body: {
        token,
        platform: 'android',
        app_id: appId,
      },
    });

    await pushStorage.write({ token, registeredAt: Date.now() });
    return true;
  } catch {
    // Suppress network errors and 429 from customer. Do not log the token.
    return false;
  }
}

export async function unregisterPushToken(api: ApiClient): Promise<void> {
  if (isDemoMode() || Platform.OS === 'web') return;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const saved = await pushStorage.read();
    if (!saved?.token) return;
    const controller = new AbortController();
    const timeoutPromise = new Promise<void>(resolve => {
      timer = setTimeout(() => {
        controller.abort();
        resolve();
      }, 3000);
    });

    const requestPromise = api.request<void>('/me/push-token', {
      method: 'DELETE',
      auth: true,
      body: { token: saved.token },
      signal: controller.signal,
    });

    await Promise.race([requestPromise, timeoutPromise]).catch(() => {});
  } catch {
    // Ignore server error / timeout during logout or invalidation
  } finally {
    if (timer) clearTimeout(timer);
    await pushStorage.clear();
  }
}

// A response (tap) is opened once: the "last response" the system keeps after a cold start must not be replayed every time
// the session object changes or this manager remounts.
let handledResponseId: string | null = null;
function responseId(response: unknown): string | null {
  const id = (response as { notification?: { request?: { identifier?: unknown } } } | null)?.notification?.request?.identifier;
  return typeof id === 'string' && id ? id : null;
}
/** @internal for tests */
export function resetHandledResponseForTests(): void { handledResponseId = null; }

// A tap names a notification only when the payload is a broadcast with a well-formed id; write-off codes and anything else
// just open the screen. The tap does not mark anything read: the item is marked after it was really shown (useMarkNotificationsRead).
function announceTap(response: unknown): void {
  const payload = pushPayload((response as { notification?: Parameters<typeof pushPayload>[0] } | null)?.notification);
  if (payload.type === 'broadcast' && isNotificationId(payload.notification_id)) setTapTarget(payload.notification_id);
}

export function setupNotificationListeners(
  queryClient: QueryClient,
  navigate: (route: string) => void
): () => void {
  const receivedSub = Notifications.addNotificationReceivedListener(() => {
    bumpNotificationEpoch();
    void queryClient.invalidateQueries({ queryKey: keys.notifications });
    void queryClient.invalidateQueries({ queryKey: keys.badges });
  });

  const responseSub = Notifications.addNotificationResponseReceivedListener(response => {
    handledResponseId = responseId(response) ?? handledResponseId;
    bumpNotificationEpoch();
    announceTap(response);
    void queryClient.invalidateQueries({ queryKey: keys.notifications });
    void queryClient.invalidateQueries({ queryKey: keys.badges });
    navigate('/notifications');
  });

  return () => {
    receivedSub.remove();
    responseSub.remove();
  };
}

export function PushNotificationManager() {
  const { session, state } = useSession();
  const queryClient = useQueryClient();
  const { language } = useI18n();

  useEffect(() => {
    void setupNotificationChannel(language);
  }, [language]);

  useEffect(() => {
    if (isDemoMode()) return;
    const cleanupListeners = setupNotificationListeners(queryClient, route => {
      try {
        router.navigate(route as '/notifications');
      } catch {
        // Navigation not ready yet
      }
    });

    void Notifications.getLastNotificationResponseAsync().then(response => {
      const id = responseId(response);
      if (response && !(id && id === handledResponseId)) {
        handledResponseId = id ?? handledResponseId;
        bumpNotificationEpoch();
        announceTap(response);
        void queryClient.invalidateQueries({ queryKey: keys.notifications });
        void queryClient.invalidateQueries({ queryKey: keys.badges });
        try {
          router.navigate('/notifications');
        } catch {
          // Navigation not ready yet
        }
      }
    }).catch(() => {});

    const tokenSub = Notifications.addPushTokenListener(deviceToken => {
      const token = typeof deviceToken?.data === 'string' ? deviceToken.data : undefined;
      if (token && session) {
        void registerPushToken(session.api, { force: true, explicitToken: token });
      }
    });

    return () => {
      cleanupListeners();
      tokenSub.remove();
    };
  }, [queryClient, session]);

  useEffect(() => {
    if (isDemoMode() || state.status !== 'authenticated') return;

    const unregisterLogout = session.registerBeforeLogout(async () => {
      await unregisterPushToken(session.api);
    });

    const unregisterInvalidate = session.registerOnInvalidate(() => {
      void pushStorage.clear();
    });

    void registerPushToken(session.api);

    return () => {
      unregisterLogout();
      unregisterInvalidate();
      resetNotificationSignals();
    };
  }, [session, state.status]);

  return null;
}

export function PushPermissionNotice({ style }: { style?: ViewStyle }) {
  const { t } = useI18n();
  const noticeStyles = useThemedStyles(makeNoticeStyles);
  const { colors } = useTheme();
  const { session } = useSession();
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  const checkPermission = useCallback(async () => {
    if (isDemoMode() || Platform.OS === 'web') {
      setHasPermission(true);
      return;
    }
    try {
      const perm = await Notifications.getPermissionsAsync();
      const granted = perm.status === 'granted';
      setHasPermission(granted);
      if (granted && session) {
        void registerPushToken(session.api);
      }
    } catch {
      setHasPermission(true);
    }
  }, [session]);

  useEffect(() => {
    void checkPermission();
    const sub = AppState.addEventListener('change', state => {
      if (state === 'active') {
        void checkPermission();
      }
    });
    return () => sub.remove();
  }, [checkPermission]);

  if (isDemoMode() || hasPermission !== false) {
    return null;
  }

  const handleAction = async () => {
    try {
      const current = await Notifications.getPermissionsAsync();
      if (current.status !== 'granted' && current.canAskAgain) {
        const req = await Notifications.requestPermissionsAsync();
        const granted = req.status === 'granted';
        setHasPermission(granted);
        if (granted && session) {
          void registerPushToken(session.api, { force: true });
          return;
        }
        if (!req.canAskAgain) {
          void Linking.openSettings();
        }
        return;
      }
      void Linking.openSettings();
    } catch {
      void Linking.openSettings();
    }
  };

  return (
    <View style={[noticeStyles.card, style]} accessible accessibilityRole="alert">
      <View style={noticeStyles.header}>
        <View style={noticeStyles.iconWrap}>
          <Icon name="bell" size={20} color={colors.primaryText} />
        </View>
        <Text style={noticeStyles.text}>{t('enableNotificationsPrompt')}</Text>
      </View>
      <Button
        label={t('enableNotificationsAction')}
        onPress={handleAction}
        style={noticeStyles.button}
      />
    </View>
  );
}

const makeNoticeStyles = (c: Colors) => StyleSheet.create({
  card: {
    backgroundColor: c.surface,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: c.primary,
    padding: 16,
    gap: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: c.softPrimary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: c.text,
  },
  button: {
    alignSelf: 'stretch',
  },
});
