import { useEffect, useRef, useSyncExternalStore } from 'react';
import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNotifications } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
import { FadeIn } from '../../../src/components/motion';
import { EmptyState, ErrorNotice, Loading, NewDot, ScreenHeader, useUiStyles } from '../../../src/components/ui';
import { LinkedText } from '../../../src/components/LinkedText';
import { PushPermissionNotice } from '../../../src/features/push';
import { getTapTarget, setTapTarget, subscribeTapTarget } from '../../../src/features/notificationSignals';
import { useMarkNotificationsRead } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { fonts, type Colors } from '../../../src/theme';
import { useTheme, useThemedStyles } from '../../../src/theme/ThemeProvider';
import { dateText } from '../../../src/utils/format';
import { hasLinks } from '../../../src/utils/links';

export default function NotificationsScreen() {
  const insets = useSafeAreaInsets();
  const styles = useUiStyles();
  const local = useThemedStyles(makeLocal);
  const { colors } = useTheme();
  const { t, language } = useI18n();
  const notifications = useNotifications();
  // Only the items the list really showed are marked read (see useMarkNotificationsRead); nothing is marked just by opening the tab.
  const { onViewableItemsChanged, viewabilityConfig } = useMarkNotificationsRead(notifications.data);
  const listRef = useRef<FlatList>(null);
  // A tapped push names its notification: bring that item into view once the list has it (it is marked read once it is shown).
  const tapTarget = useSyncExternalStore(subscribeTapTarget, getTapTarget, getTapTarget);
  const items = notifications.data?.items;
  useEffect(() => {
    if (!tapTarget || !items) return;
    const index = items.findIndex(item => item.id === tapTarget);
    if (index < 0) return;
    setTapTarget(null);
    try { listRef.current?.scrollToIndex({ index, viewPosition: 0, animated: false }); } catch { /* the list is not laid out yet */ }
  }, [tapTarget, items]);
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('notifications')} />
    <FlatList ref={listRef} onViewableItemsChanged={onViewableItemsChanged} viewabilityConfig={viewabilityConfig}
      onScrollToIndexFailed={info => { listRef.current?.scrollToOffset({ offset: info.averageItemLength * info.index, animated: false }); }}
      data={notifications.data?.items ?? []} keyExtractor={item => item.id} contentContainerStyle={[styles.content, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16, paddingTop: 0, gap: 12 }]}
      refreshing={notifications.isRefetching} onRefresh={() => { void notifications.refetch(); }}
      ListHeaderComponent={<>
        <PushPermissionNotice />
        {notifications.isPending ? <Loading /> : notifications.isError ? <ErrorNotice error={notifications.error} retry={() => { void notifications.refetch(); }} /> : null}
      </>}
      ListEmptyComponent={notifications.isSuccess ? <EmptyState icon="bell" title={t('noNotifications')} /> : null}
      renderItem={({ item, index }) => {
        const isAccrual = item.kind === 'accrual';
        const isRedemption = item.kind === 'redemption';
        const iconBg = isAccrual ? colors.softSuccess : isRedemption ? colors.softError : colors.softPrimary;
        const iconColor = isAccrual ? colors.success : isRedemption ? colors.error : colors.primaryText;
        // A single accessible card would hide the links inside it from screen readers: with links, the children stay individually reachable.
        const linked = hasLinks(item.body);
        const unreadPrefix = item.is_unread ? `${t('newBadge')}. ` : '';
        return <FadeIn index={Math.min(index, 6)}><View style={local.item} accessible={!linked} accessibilityLabel={linked ? undefined : `${unreadPrefix}${item.title}. ${item.body}`}>
          <View style={[local.icon, { backgroundColor: iconBg }]}><Icon name={isAccrual ? 'plus' : isRedemption ? 'minus' : 'bell'} size={18} color={iconColor} /></View>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={local.title} accessibilityLabel={linked && item.is_unread ? `${unreadPrefix}${item.title}` : undefined}>{item.title}</Text>
            <LinkedText text={item.body} style={local.body} />
            <Text style={styles.muted}>{dateText(item.created_at, language)}</Text>
          </View>
          {item.is_unread && <NewDot />}
        </View></FadeIn>;
      }} />
  </SafeAreaView>;
}

const makeLocal = (c: Colors) => StyleSheet.create({
  item: { flexDirection: 'row', gap: 12, backgroundColor: c.surface, borderRadius: 18, padding: 16, alignItems: 'flex-start', borderWidth: 1, borderColor: c.cardBorder },
  icon: { width: 36, height: 36, borderRadius: 18, backgroundColor: c.softPrimary, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.bold, fontSize: 15, color: c.text },
  body: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 20, color: c.text },
});
