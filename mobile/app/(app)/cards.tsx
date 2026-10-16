import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { walletKey } from '../../src/api/wallet';
import { useSession } from '../../src/auth/provider';
import { Icon } from '../../src/components/icons';
import { FadeIn, PressScale } from '../../src/components/motion';
import { Button, ErrorNotice, Loading, ScreenHeader, styles } from '../../src/components/ui';
import { useActiveCard } from '../../src/features/activeCard';
import { useI18n } from '../../src/i18n';
import { fonts, theme } from '../../src/theme';
import type { Card } from '../../src/types/api';
import { pointsText } from '../../src/utils/format';

export default function CardsScreen() {
  const { t } = useI18n();
  const { api } = useSession();
  const query = useQueryClient();
  const { card: active, cards, select } = useActiveCard();
  const hide = useMutation({
    mutationFn: (id: string) => api.request<void>(`/me/cards/${encodeURIComponent(id)}`, { method: 'DELETE', auth: true }),
    onSuccess: async (_, id) => {
      query.setQueryData<Card[]>([...walletKey, 'cards'], previous => previous?.filter(item => item.id !== id));
      await query.invalidateQueries({ queryKey: walletKey });
    },
  });
  const confirmHide = (card: Card) => Alert.alert(t('hideTitle'), t('hideBody'), [{ text: t('cancel'), style: 'cancel' },
    { text: t('hide'), style: 'destructive', onPress: () => hide.mutate(card.id) }]);
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('myCards')} back />
    <FlatList data={cards.data ?? []} keyExtractor={item => item.id} contentContainerStyle={[styles.content, { paddingTop: 0, gap: 12 }]}
      refreshing={cards.isRefetching} onRefresh={() => { void cards.refetch(); }}
      ListHeaderComponent={<>{cards.isPending && <Loading />}{cards.isError && <ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} />}
        {hide.isError && <ErrorNotice error={hide.error} />}</>}
      renderItem={({ item, index }) => {
        const selected = item.id === active?.id;
        return <FadeIn index={Math.min(index, 6)} style={[local.card, selected && local.selected]}>
          <View style={local.cardTop}>
            <Text style={local.business} numberOfLines={1}>{item.business.name}</Text>
            {selected && <View style={local.activePill}><Icon name="check" size={14} color={theme.colors.onPrimary} strokeWidth={3} /><Text style={local.activeText}>{t('activeCard')}</Text></View>}
          </View>
          <Text style={local.balance}>{pointsText(item.balance)} <Text style={local.currency}>{t('bonusCurrency')}</Text></Text>
          <Text style={styles.muted}>{t('barcode')}: {item.barcode}{item.is_blocked ? ` · ${t('cardBlocked')}` : ''}</Text>
          <View style={local.actions}>
            {!selected && <PressScale accessibilityRole="button" onPress={() => select(item.id)} style={[local.action, local.actionPrimary]}><Text style={local.actionText}>{t('useCard')}</Text></PressScale>}
            <PressScale accessibilityRole="button" disabled={hide.isPending} onPress={() => confirmHide(item)} style={local.action}><Text style={[local.actionText, { color: theme.colors.muted }]}>{t('hide')}</Text></PressScale>
          </View>
        </FadeIn>;
      }}
      ListFooterComponent={<Button label={t('bind')} onPress={() => router.push('/bind')} />} />
  </SafeAreaView>;
}

const local = StyleSheet.create({
  card: { backgroundColor: theme.colors.surface, borderRadius: 22, padding: 18, gap: 6, borderWidth: 1.5, borderColor: 'rgba(17,17,17,0.05)' },
  selected: { borderColor: theme.colors.primary },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  business: { fontFamily: fonts.bold, fontSize: 15, color: theme.colors.text, flexShrink: 1 },
  activePill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: theme.colors.primary, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  activeText: { fontFamily: fonts.semibold, fontSize: 11, color: theme.colors.onPrimary },
  balance: { fontFamily: fonts.extrabold, fontSize: 26, color: theme.colors.text },
  currency: { fontFamily: fonts.extrabold, fontSize: 13, color: theme.colors.primary },
  actions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  action: { paddingVertical: 8, paddingHorizontal: 14, borderRadius: 999, backgroundColor: theme.colors.input },
  actionPrimary: { backgroundColor: theme.colors.softPrimary },
  actionText: { fontFamily: fonts.semibold, fontSize: 13, color: theme.colors.primary },
});
