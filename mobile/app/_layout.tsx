import { Montserrat_400Regular, Montserrat_500Medium, Montserrat_600SemiBold, Montserrat_700Bold, Montserrat_800ExtraBold, useFonts } from '@expo-google-fonts/montserrat';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { SafeAreaProvider, SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { SessionProvider, useSession } from '../src/auth/provider';
import { Button, ErrorNotice, Loading, useUiStyles } from '../src/components/ui';
import { I18nProvider, useI18n } from '../src/i18n';
import { DEMO_ENABLED } from '../src/demo/mockApi';
import { UpdateDialog, UpdateProvider } from '../src/features/UpdateNotice';
import { AppSplash } from '../src/features/splash/AppSplash';
import { useSplashActive } from '../src/features/splash/splashGate';
import { ThemeProvider, useTheme } from '../src/theme/ThemeProvider';

export function DemoRibbon() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return <View pointerEvents="none" testID="demo-ribbon" style={{ paddingTop: insets.top, paddingBottom: 4, backgroundColor: colors.background, alignItems: 'center' }}>
    <View style={{ backgroundColor: colors.primary, paddingHorizontal: 12, paddingVertical: 2, borderBottomLeftRadius: 8, borderBottomRightRadius: 8 }}>
      <Text style={{ color: colors.onPrimary, fontSize: 10, letterSpacing: 1, fontFamily: 'Montserrat_700Bold' }}>ДЕМО · ТЕСТОВЫЕ ДАННЫЕ</Text>
    </View>
  </View>;
}

export function DemoShell({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return <View style={{ flex: 1, backgroundColor: colors.background }}>
    <DemoRibbon />
    <View style={{ flex: 1 }}>{children}</View>
  </View>;
}

function ThemedStatusBar() {
  const { isDark } = useTheme();
  const splashActive = useSplashActive();
  return <StatusBar style={splashActive ? 'light' : (isDark ? 'light' : 'dark')} hidden={splashActive} translucent={true} backgroundColor="transparent" />;
}

function Navigation() {
  const { state, session } = useSession();
  const styles = useUiStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  if (state.status === 'loading' || state.status === 'signing-out') return <SafeAreaView style={styles.screen}><Loading label={state.status === 'loading' ? t('bootstrap') : t('signingOut')} /></SafeAreaView>;
  if (state.status === 'error') return <SafeAreaView style={styles.screen}><View style={styles.content}><ErrorNotice error={state.error} retry={() => { void (state.cleanupRequired ? session.invalidate() : session.bootstrap()); }} /><Button label={t('logout')} secondary onPress={() => { void session.logout(); }} /></View></SafeAreaView>;
  return <Stack screenOptions={{ headerShown: false, animation: 'fade', contentStyle: { backgroundColor: colors.background } }}>
    <Stack.Protected guard={state.status === 'anonymous'}><Stack.Screen name="login" /></Stack.Protected>
    <Stack.Protected guard={state.status === 'authenticated'}><Stack.Screen name="(app)" /></Stack.Protected>
  </Stack>;
}

function WebDemoFrame({ desktop, children }: { desktop: boolean; children: React.ReactNode }) {
  const { colors } = useTheme();
  return <View style={[webDemoStyles.frame, { backgroundColor: colors.background }, desktop && webDemoStyles.desktopFrame]}>{children}</View>;
}

export default function RootLayout() {
  const { width } = useWindowDimensions();
  const [fontsLoaded, fontError] = useFonts({ Montserrat_400Regular, Montserrat_500Medium, Montserrat_600SemiBold, Montserrat_700Bold, Montserrat_800ExtraBold });
  // Keep the native splash until Montserrat is ready; on a font error fall back to the system font.
  if (!fontsLoaded && !fontError) return null;
  const navigation = DEMO_ENABLED ? <DemoShell><Navigation /></DemoShell> : <Navigation />;
  const app = <UpdateProvider><ThemedStatusBar />{navigation}<UpdateDialog /><AppSplash /></UpdateProvider>;
  return <SafeAreaProvider><ThemeProvider><I18nProvider><SessionProvider>
    {Platform.OS === 'web' && DEMO_ENABLED ? <View style={webDemoStyles.backdrop}>
      <WebDemoFrame desktop={width > 430}>{app}</WebDemoFrame>
    </View> : app}
  </SessionProvider></I18nProvider></ThemeProvider></SafeAreaProvider>;
}

const webDemoStyles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', backgroundColor: '#E6E7EB' },
  frame: { flex: 1, width: '100%', maxWidth: 430 },
  desktopFrame: {
    marginVertical: 20, borderRadius: 28, borderWidth: 1, borderColor: '#D8D9DE', overflow: 'hidden',
    shadowColor: '#111111', shadowOpacity: 0.12, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 8,
  },
});
