import { Stack } from 'expo-router';
import { useEffect, type ReactNode } from 'react';
import { useAppContent, useProfile } from '../../src/api/app';
import { useSession } from '../../src/auth/provider';
import { getClientConfig } from '../../src/config/client';
import { ActiveCardProvider, useActiveCard } from '../../src/features/activeCard';
import { StoreLocationProvider } from '../../src/features/stores';
import { useI18n } from '../../src/i18n';
import { useTheme } from '../../src/theme/ThemeProvider';

function LanguageSync() {
  const profile = useProfile();
  const { setLanguage } = useI18n();
  const language = profile.data?.language;
  useEffect(() => { if (language === 'ru' || language === 'kz') setLanguage(language); }, [language, setLanguage]);
  return null;
}

function AppStoreLocationProvider({ children }: { children: ReactNode }) {
  const { session, state } = useSession();
  const { card } = useActiveCard();
  const appContent = useAppContent(getClientConfig().business_id ?? card?.business?.id);
  const authenticated = state.status === 'authenticated';
  const sessionKey = authenticated ? (session.getUserId?.() ?? 'authenticated') : state.status;
  return (
    <StoreLocationProvider
      authenticated={authenticated}
      sessionKey={sessionKey}
      stores={appContent.data?.stores}
    >
      {children}
    </StoreLocationProvider>
  );
}

export default function AppLayout() {
  const { colors } = useTheme();
  return <ActiveCardProvider>
    <AppStoreLocationProvider>
      <LanguageSync />
      <Stack screenOptions={{ headerShown: false, animation: 'ios_from_right', gestureEnabled: true, contentStyle: { backgroundColor: colors.background } }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="status" />
        <Stack.Screen name="history" />
        <Stack.Screen name="cards" />
        <Stack.Screen name="promotion/[id]" />
        <Stack.Screen name="settings" />
      </Stack>
    </AppStoreLocationProvider>
  </ActiveCardProvider>;
}
