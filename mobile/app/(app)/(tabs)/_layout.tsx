import { Tabs } from 'expo-router';
import { useBadges } from '../../../src/api/app';
import { TabBar, type TabRoute } from '../../../src/components/TabBar';
import { theme } from '../../../src/theme';

export default function TabsLayout() {
  const badges = useBadges();
  return <Tabs screenOptions={{ headerShown: false, animation: 'shift', sceneStyle: { backgroundColor: theme.colors.background } }}
    tabBar={({ state, navigation }) => <TabBar active={state.routes[state.index]?.name as TabRoute}
      onSelect={route => navigation.navigate(route)}
      badges={{ promotions: badges.data?.promotions_new ?? false, notifications: badges.data?.notifications_unread ?? 0 }} />}>
    <Tabs.Screen name="index" />
    <Tabs.Screen name="promotions" />
    <Tabs.Screen name="qr" />
    <Tabs.Screen name="notifications" />
    <Tabs.Screen name="profile" />
  </Tabs>;
}
