import { useState } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useHistory, type HistoryFilter } from '../../src/api/wallet';
import { Icon } from '../../src/components/icons';
import { Button, Chip, EmptyState, ErrorNotice, Loading, ScreenHeader, styles } from '../../src/components/ui';
import { useActiveCard } from '../../src/features/activeCard';
import { useI18n } from '../../src/i18n';
import { fonts, theme } from '../../src/theme';
import { dateText, pointsText, transactionLabel } from '../../src/utils/format';

export default function HistoryScreen() {
  const { t, language } = useI18n();
  const { card } = useActiveCard();
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const history = useHistory(card?.id, filter);
  const rows = history.data?.pages.flatMap(page => page.items) ?? [];
  const filters: [HistoryFilter, string][] = [['all', t('filterAll')], ['accrual', t('filterAccrual')], ['redemption', t('filterRedemption')]];
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('accrualHistory')} back />
    <FlatList data={rows} keyExtractor={row => row.id} contentContainerStyle={[styles.content, { paddingTop: 0, gap: 10 }]}
      refreshing={history.isRefetching && !history.isFetchingNextPage} onRefresh={() => { void history.refetch(); }}
      ListHeaderComponent={<View style={{ gap: 12, marginBottom: 6 }}>
        {card && <Text style={styles.muted}>{card.business.name}</Text>}
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{filters.map(([value, label]) =>
          <Chip key={value} label={label} selected={filter === value} onPress={() => setFilter(value)} />)}</View>
        {history.isPending && card && <Loading />}
        {history.isError && <ErrorNotice error={history.error} retry={() => { void (history.isFetchNextPageError ? history.fetchNextPage() : history.refetch()); }} />}
      </View>}
      ListEmptyComponent={history.isSuccess || !card ? <EmptyState icon="history" title={t('noHistory')} /> : null}
      renderItem={({ item }) => {
        const incoming = item.type === 'accrual';
        return <View style={local.row}>
          <View style={[local.icon, { backgroundColor: incoming ? theme.colors.softPrimary : '#EFEFF2' }]}>
            <Icon name={incoming ? 'plus' : 'minus'} size={20} color={incoming ? theme.colors.primary : theme.colors.muted} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={local.title}>{transactionLabel(item.type, language)}</Text>
            <Text style={styles.muted} numberOfLines={1}>{[item.store, dateText(item.occurred_at, language)].filter(Boolean).join(' · ')}</Text>
          </View>
          <View style={{ alignItems: 'flex-end', gap: 2 }}>
            <Text style={[local.amount, { color: incoming ? theme.colors.primary : theme.colors.text }]}>{incoming ? '+' : '−'}{pointsText(item.amount.replace('-', ''))}</Text>
            <Text style={styles.muted}>{t('balanceAfter')} {pointsText(item.balance_after)}</Text>
          </View>
        </View>;
      }}
      ListFooterComponent={history.hasNextPage ? <Button label={history.isFetchingNextPage ? t('loading') : t('more')} secondary disabled={history.isFetching}
        onPress={() => { void history.fetchNextPage(); }} /> : null} />
  </SafeAreaView>;
}

const local = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: theme.colors.surface, borderRadius: 20, padding: 16 },
  icon: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.semibold, fontSize: 16, color: theme.colors.text },
  amount: { fontFamily: fonts.bold, fontSize: 17 },
});
