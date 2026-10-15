import { FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNotifications } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
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
      renderItem={({ item }) => <View style={local.item} accessible accessibilityLabel={`${item.is_unread ? t('newBadge') + '. ' : ''}${item.title}. ${item.body}`}>
        <View style={local.icon}><Icon name={item.kind === 'accrual' ? 'plus' : item.kind === 'redemption' ? 'minus' : 'bell'} size={20} color={theme.colors.primary} /></View>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={local.title}>{item.title}</Text>
          <Text style={styles.body}>{item.body}</Text>
          <Text style={styles.muted}>{dateText(item.created_at, language)}</Text>
        </View>
        {item.is_unread && <NewDot />}
      </View>} />
  </SafeAreaView>;
}

const local = StyleSheet.create({
  item: { flexDirection: 'row', gap: 14, backgroundColor: theme.colors.surface, borderRadius: 22, padding: 18, alignItems: 'flex-start' },
  icon: { width: 42, height: 42, borderRadius: 21, backgroundColor: theme.colors.softPrimary, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.bold, fontSize: 17, color: theme.colors.text },
});
