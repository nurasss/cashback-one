import { Montserrat_400Regular, Montserrat_500Medium, Montserrat_600SemiBold, Montserrat_700Bold, Montserrat_800ExtraBold, useFonts } from '@expo-google-fonts/montserrat';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { SessionProvider, useSession } from '../src/auth/provider';
import { Button, ErrorNotice, Loading, styles } from '../src/components/ui';
import { I18nProvider, useI18n } from '../src/i18n';
import { theme } from '../src/theme';

function Navigation() {
  const { state, session } = useSession();
  const { t } = useI18n();
  if (state.status === 'loading' || state.status === 'signing-out') return <SafeAreaView style={styles.screen}><Loading label={state.status === 'loading' ? t('bootstrap') : t('signingOut')} /></SafeAreaView>;
  if (state.status === 'error') return <SafeAreaView style={styles.screen}><View style={styles.content}><ErrorNotice error={state.error} retry={() => { void (state.cleanupRequired ? session.invalidate() : session.bootstrap()); }} /><Button label={t('logout')} secondary onPress={() => { void session.logout(); }} /></View></SafeAreaView>;
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.background } }}>
    <Stack.Protected guard={state.status === 'anonymous'}><Stack.Screen name="login" /></Stack.Protected>
    <Stack.Protected guard={state.status === 'authenticated'}><Stack.Screen name="(app)" /></Stack.Protected>
  </Stack>;
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({ Montserrat_400Regular, Montserrat_500Medium, Montserrat_600SemiBold, Montserrat_700Bold, Montserrat_800ExtraBold });
  // Keep the native splash until Montserrat is ready; on a font error fall back to the system font.
  if (!fontsLoaded && !fontError) return null;
  return <SafeAreaProvider><I18nProvider><SessionProvider><StatusBar style="dark" /><Navigation /></SessionProvider></I18nProvider></SafeAreaProvider>;
}
