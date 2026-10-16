import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import { Icon, type IconName } from './icons';
import { PressScale } from './motion';
import { NewDot } from './ui';

export type TabRoute = 'index' | 'promotions' | 'qr' | 'notifications' | 'profile';
const tabs: { route: TabRoute; icon: IconName; label: 'tabHome' | 'tabPromotions' | 'tabQr' | 'tabNotifications' | 'tabProfile' }[] = [
  { route: 'index', icon: 'home', label: 'tabHome' },
  { route: 'promotions', icon: 'gift', label: 'tabPromotions' },
  { route: 'qr', icon: 'qr', label: 'tabQr' },
  { route: 'notifications', icon: 'message', label: 'tabNotifications' },
  { route: 'profile', icon: 'user', label: 'tabProfile' },
];

export function TabBar({ active, onSelect, badges }: {
  active: TabRoute; onSelect: (route: TabRoute) => void; badges: { promotions: boolean; notifications: number };
}) {
  const { t: tr } = useI18n();
  const insets = useSafeAreaInsets();
  return <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 12) }]}>
    {tabs.map(tab => {
      const selected = tab.route === active;
      const label = tr(tab.label);
      if (tab.route === 'qr') {
        return <View key={tab.route} style={styles.centerSlot}>
          <PressScale accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected }} onPress={() => onSelect('qr')} scale={0.9}
            style={styles.qrButton}>
            <Icon name="qr" size={24} color={t.colors.onPrimary} />
          </PressScale>
        </View>;
      }
      const hasNew = (tab.route === 'promotions' && badges.promotions) || (tab.route === 'notifications' && badges.notifications > 0);
      const color = selected ? t.colors.primary : t.colors.subtle;
      return <Pressable key={tab.route} accessibilityRole="tab" accessibilityState={{ selected }}
        accessibilityLabel={hasNew ? `${label}. ${tr('newBadge')}` : label} onPress={() => onSelect(tab.route)} style={styles.item}>
        <View>
          <Icon name={tab.icon} size={24} color={color} strokeWidth={1.8} filled={selected && tab.route === 'index'} />
          {hasNew && <NewDot style={styles.dot} />}
        </View>
        <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} style={[styles.label, { color: selected ? t.colors.primary : t.colors.muted }]}>{label}</Text>
      </Pressable>;
    })}
  </View>;
}

const styles = StyleSheet.create({
  bar: {
    position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', alignItems: 'flex-end', paddingTop: 10,
    backgroundColor: t.colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28,
    shadowColor: t.colors.shadow, shadowOpacity: 0.06, shadowRadius: 16, shadowOffset: { width: 0, height: -4 }, elevation: 12,
  },
  item: { flex: 1, alignItems: 'center', gap: 6, minHeight: 56, justifyContent: 'flex-end', paddingHorizontal: 2 },
  label: { fontFamily: fonts.medium, fontSize: 11, letterSpacing: -0.2 },
  centerSlot: { flex: 1, alignItems: 'center' },
  qrButton: {
    width: 52, height: 52, borderRadius: 26, marginTop: -26, marginBottom: 8, backgroundColor: t.colors.primary, alignItems: 'center', justifyContent: 'center',
    shadowColor: t.colors.primary, shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 8,
  },
  dot: { position: 'absolute', top: -2, right: -4 },
});
