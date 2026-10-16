import { FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNotifications } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
import { FadeIn } from '../../../src/components/motion';
import { EmptyState, ErrorNotice, Loading, NewDot, ScreenHeader, styles } from '../../../src/components/ui';
import { useMarkSeen } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import { dateText } from '../../../src/utils/format';

export default function NotificationsScreen() {
  const { t, language } = useI18n();
  const notifications = useNotifications();
  useMarkSeen('/me/notifications/read', (notifications.data?.unread_count ?? 0) > 0);
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('notifications')} />
    <FlatList data={notifications.data?.items ?? []} keyExtractor={item => item.id} contentContainerStyle={[styles.content, { paddingTop: 0, gap: 12 }]}
      refreshing={notifications.isRefetching} onRefresh={() => { void notifications.refetch(); }}
      ListHeaderComponent={notifications.isPending ? <Loading /> : notifications.isError ? <ErrorNotice error={notifications.error} retry={() => { void notifications.refetch(); }} /> : null}
      ListEmptyComponent={notifications.isSuccess ? <EmptyState icon="bell" title={t('noNotifications')} /> : null}
      renderItem={({ item, index }) => <FadeIn index={Math.min(index, 6)}><View style={local.item} accessible accessibilityLabel={`${item.is_unread ? t('newBadge') + '. ' : ''}${item.title}. ${item.body}`}>
        <View style={local.icon}><Icon name={item.kind === 'accrual' ? 'plus' : item.kind === 'redemption' ? 'minus' : 'bell'} size={18} color={theme.colors.primary} /></View>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={local.title}>{item.title}</Text>
          <Text style={local.body}>{item.body}</Text>
          <Text style={styles.muted}>{dateText(item.created_at, language)}</Text>
        </View>
        {item.is_unread && <NewDot />}
      </View></FadeIn>} />
  </SafeAreaView>;
}

const local = StyleSheet.create({
  item: { flexDirection: 'row', gap: 12, backgroundColor: theme.colors.surface, borderRadius: 18, padding: 16, alignItems: 'flex-start', borderWidth: 1, borderColor: 'rgba(17,17,17,0.05)' },
  icon: { width: 36, height: 36, borderRadius: 18, backgroundColor: theme.colors.softPrimary, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.bold, fontSize: 15, color: theme.colors.text },
  body: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 20, color: theme.colors.text },
});
