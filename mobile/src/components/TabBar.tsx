import { Platform, Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import { Icon, type IconName } from './icons';
import { PressScale } from './motion';
import { NewDot } from './ui';

// Panel height excluding the system bottom inset: top padding + items + bottom padding.
// The QR item is a 48px button plus a label, taller than the 24px icons of the other tabs.
export const TAB_BAR_HEIGHT = 10 + 68 + 16;

export type TabRoute = 'index' | 'promotions' | 'qr' | 'notifications' | 'profile';
export const tabs: { route: TabRoute; icon: IconName; label: 'tabHome' | 'tabPromotions' | 'tabQr' | 'tabNotifications' | 'tabProfile' }[] = [
  { route: 'index', icon: 'home', label: 'tabHome' },
  { route: 'promotions', icon: 'gift', label: 'tabPromotions' },
  { route: 'qr', icon: 'qr', label: 'tabQr' },
  { route: 'notifications', icon: 'bell', label: 'tabNotifications' },
  { route: 'profile', icon: 'user', label: 'tabProfile' },
];

export function TabBar({ active, onSelect, badges }: {
  active: TabRoute; onSelect: (route: TabRoute) => void; badges: { promotions: boolean; notifications: number };
}) {
  const { t: tr } = useI18n();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const styles = useThemedStyles(makeStyles);
  const { colors } = useTheme();
  const narrow = width > 0 && width < 360;
  const labelStyle = (text: string) => {
    if (narrow) return [styles.label, styles.labelNarrow, Platform.OS === 'web' && text.length > 12 ? { fontSize: 7.5 } : null];
    if (Platform.OS === 'web' && text.length > 12) return [styles.label, { fontSize: 8.8, letterSpacing: -0.35 }];
    return styles.label;
  };
  return <View style={[styles.bar, { paddingBottom: insets.bottom + 16 }]}>
    {tabs.map(tab => {
      const selected = tab.route === active;
      const label = tr(tab.label);
      if (tab.route === 'qr') {
        return <View key={tab.route} style={styles.item}>
          <PressScale accessibilityRole="tab" accessibilityLabel={label} accessibilityState={{ selected }} onPress={() => onSelect('qr')} scale={0.9}
            style={[styles.qrButton, selected && styles.qrButtonSelected]}>
            <Icon name="qr" size={26} color={colors.onPrimary} />
          </PressScale>
          <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}
            style={[labelStyle(label), { color: selected ? colors.primaryText : colors.muted }]}>{label}</Text>
        </View>;
      }
      const hasNew = (tab.route === 'promotions' && badges.promotions) || (tab.route === 'notifications' && badges.notifications > 0);
      const color = selected ? colors.primaryText : colors.subtle;
      return <Pressable key={tab.route} accessibilityRole="tab" accessibilityState={{ selected }}
        accessibilityLabel={hasNew ? `${label}. ${tr('newBadge')}` : label} onPress={() => onSelect(tab.route)} style={styles.item}>
        <View>
          <Icon name={tab.icon} size={24} color={color} strokeWidth={1.8} filled={selected && tab.route === 'index'} />
          {hasNew && <NewDot style={styles.dot} />}
        </View>
        <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75} style={[labelStyle(label), { color: selected ? colors.primaryText : colors.muted }]}>{label}</Text>
      </Pressable>;
    })}
  </View>;
}

export const makeStyles = (c: Colors) => StyleSheet.create({
  bar: {
    position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', alignItems: 'flex-end', paddingTop: 10,
    backgroundColor: c.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28,
    shadowColor: c.shadow, shadowOpacity: 0.06, shadowRadius: 16, shadowOffset: { width: 0, height: -4 }, elevation: 12,
  },
  item: { flex: 1, alignItems: 'center', gap: 6, minHeight: 56, justifyContent: 'flex-end', paddingHorizontal: 1 },
  label: { fontFamily: fonts.medium, fontSize: 10, letterSpacing: -0.3 },
  labelNarrow: { fontSize: 8.5, letterSpacing: -0.4 },
  // Flush with the other tabs: no negative margin, aligned to the bottom edge like the icon+label rows.
  qrButton: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center',
  },
  qrButtonSelected: { borderWidth: 2, borderColor: c.surface },
  dot: { position: 'absolute', top: -2, right: -4 },
});
