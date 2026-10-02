import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { View } from 'react-native';
import { SessionProvider, useSession } from '../src/auth/provider';
import { Button, ErrorNotice, Loading, styles } from '../src/components/ui';
import { ru } from '../src/i18n/ru';
import { theme } from '../src/theme';
function Navigation() {
  const { state, session } = useSession();
  if (state.status === 'loading' || state.status === 'signing-out') return <SafeAreaView style={styles.screen}><Loading label={state.status === 'loading' ? ru.bootstrap : ru.signingOut} /></SafeAreaView>;
  if (state.status === 'error') return <SafeAreaView style={styles.screen}><View style={styles.content}><ErrorNotice error={state.error} retry={() => { void (state.cleanupRequired ? session.invalidate() : session.bootstrap()); }} /><Button label={ru.logout} secondary onPress={() => { void session.logout(); }} /></View></SafeAreaView>;
  return <Stack screenOptions={{ headerStyle: { backgroundColor: theme.colors.background }, headerTintColor: theme.colors.text, headerShadowVisible: false, contentStyle: { backgroundColor: theme.colors.background } }}>
    <Stack.Protected guard={state.status === 'anonymous'}><Stack.Screen name="login" options={{ headerShown: false }} /></Stack.Protected>
    <Stack.Protected guard={state.status === 'authenticated'}><Stack.Screen name="(wallet)" options={{ headerShown: false }} /></Stack.Protected>
  </Stack>;
}
export default function RootLayout() { return <SafeAreaProvider><SessionProvider><StatusBar style="dark" /><Navigation /></SessionProvider></SafeAreaProvider>; }
