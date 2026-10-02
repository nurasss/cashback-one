import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { Alert, FlatList, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useCard, useHistory, walletKey } from '../../../src/api/wallet';
import { useSession } from '../../../src/auth/provider';
import { Button, ErrorNotice, Loading, styles } from '../../../src/components/ui';
import { CardQr } from '../../../src/features/CardQr';
import type { Card } from '../../../src/types/api';
import { ru } from '../../../src/i18n/ru';
import { theme as t } from '../../../src/theme';
import { dateText, decimalText, transactionLabel } from '../../../src/utils/format';
export default function CardDetail() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = params.id;
  const card = useCard(id);
  const history = useHistory(id);
  const { api } = useSession();
  const query = useQueryClient();
  const hide = useMutation({ mutationFn: () => api.request<void>(`/me/cards/${encodeURIComponent(id)}`, { method: 'DELETE', auth: true }),
    onSuccess: async () => {
      query.setQueryData<Card[]>([...walletKey, 'cards'], previous => previous?.filter(item => item.id !== id));
      query.removeQueries({ queryKey: [...walletKey, 'card', id] });
      query.removeQueries({ queryKey: [...walletKey, 'history', id] });
      await query.invalidateQueries({ queryKey: [...walletKey, 'cards'] });
      router.replace('/');
    } });
  const refresh = () => { void card.refetch(); void history.refetch(); };
  if (card.isPending) return <Loading />;
  if (!card.data) return <View style={styles.content}><ErrorNotice error={card.error} retry={() => { void card.refetch(); }} /></View>;
  const current = card.data;
  const header = <View style={styles.gap}>
    {card.isError && <><ErrorNotice error={card.error} retry={() => { void card.refetch(); }} /><Text style={styles.muted}>{ru.stale}</Text></>}
    <View style={styles.panel}><Text style={styles.title}>{current.business.name}</Text><Text style={styles.muted}>{ru.bonuses}</Text><Text style={{ color: t.colors.text, fontSize: t.font.balance, fontWeight: '700' }}>{decimalText(current.balance)}</Text>
      <Text style={styles.body}>{current.is_blocked ? ru.blocked : ru.active}</Text><Text style={styles.muted}>{ru.updated}: {dateText(current.updated_at)}</Text><Text style={styles.muted}>{ru.lastLoaded}: {dateText(card.dataUpdatedAt)}</Text>
    </View><CardQr barcode={current.barcode} />
    <Button label={ru.hide} secondary disabled={hide.isPending || card.isError} onPress={() => Alert.alert(ru.hideTitle, ru.hideBody, [{ text: ru.cancel, style: 'cancel' }, { text: ru.hide, style: 'destructive', onPress: () => hide.mutate() }])} />
    {hide.isError && <ErrorNotice error={hide.error} />}
    <Text style={styles.title}>{ru.history}</Text>
    {history.dataUpdatedAt > 0 && <Text style={styles.muted}>{ru.lastLoaded}: {dateText(history.dataUpdatedAt)}</Text>}
    {history.isPending && <Loading />}
    {history.isError && <><ErrorNotice error={history.error} retry={() => { if (history.isFetchNextPageError) { void history.fetchNextPage(); } else { void history.refetch(); } }} />{history.data && <Text style={styles.muted}>{ru.stale}</Text>}</>}
  </View>;
  const rows = history.data?.pages.flatMap(page => page.items) ?? [];
  return <SafeAreaView edges={['bottom']} style={styles.screen}><FlatList data={rows} keyExtractor={row => row.id} contentContainerStyle={styles.content} ListHeaderComponent={header}
    refreshing={card.isRefetching || (history.isRefetching && !history.isFetchingNextPage)} onRefresh={refresh}
    ListEmptyComponent={history.isSuccess ? <Text style={styles.muted}>{ru.noHistory}</Text> : null}
    renderItem={({ item }) => <View style={styles.panel}><Text style={[styles.label, { color: item.type === 'accrual' ? t.colors.success : item.type === 'redemption' ? t.colors.error : t.colors.text }]}>{transactionLabel(item.type)}</Text>
      <Text style={styles.title}>{decimalText(item.amount)}</Text><Text style={styles.muted}>{dateText(item.occurred_at)}</Text>
      <Text style={styles.body}>{ru.balanceAfter}: {decimalText(item.balance_after)}</Text>{item.store && <Text style={styles.muted}>{item.store}</Text>}{item.receipt_ref && <Text style={styles.muted}>{item.receipt_ref}</Text>}
    </View>}
    ListFooterComponent={history.hasNextPage ? <Button label={history.isFetchingNextPage ? ru.loading : ru.more} secondary disabled={history.isFetching} onPress={() => { void history.fetchNextPage(); }} /> : null} />
  </SafeAreaView>;
}
