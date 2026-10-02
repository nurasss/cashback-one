import { Stack } from 'expo-router';
import { ru } from '../../src/i18n/ru';
import { theme } from '../../src/theme';
export default function WalletLayout() {
  return <Stack screenOptions={{ headerStyle: { backgroundColor: theme.colors.background }, headerTintColor: theme.colors.text, headerShadowVisible: false }}>
    <Stack.Screen name="index" options={{ title: ru.wallet }} />
    <Stack.Screen name="bind" options={{ title: ru.bind }} />
    <Stack.Screen name="cards/[id]" options={{ title: ru.showQr }} />
  </Stack>;
}
