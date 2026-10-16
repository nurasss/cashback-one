import { Stack } from 'expo-router';
import { useEffect } from 'react';
import { useProfile } from '../../src/api/app';
import { ActiveCardProvider } from '../../src/features/activeCard';
import { useI18n } from '../../src/i18n';
import { theme } from '../../src/theme';

function LanguageSync() {
  const profile = useProfile();
  const { setLanguage } = useI18n();
  const language = profile.data?.language;
  useEffect(() => { if (language === 'ru' || language === 'kz') setLanguage(language); }, [language, setLanguage]);
  return null;
}

export default function AppLayout() {
  return <ActiveCardProvider>
    <LanguageSync />
    <Stack screenOptions={{ headerShown: false, animation: 'ios_from_right', gestureEnabled: true, contentStyle: { backgroundColor: theme.colors.background } }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="status" />
      <Stack.Screen name="history" />
      <Stack.Screen name="cards" />
      <Stack.Screen name="bind" />
      <Stack.Screen name="promotion/[id]" />
    </Stack>
  </ActiveCardProvider>;
}
