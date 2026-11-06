import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { router } from 'expo-router';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePromotions } from '../../../src/api/app';
import { EmptyState, ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { FadeIn } from '../../../src/components/motion';
import { OfferCard } from '../../../src/features/home';
import { useMarkSeen } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { theme } from '../../../src/theme';
import type { Promotion } from '../../../src/types/api';

export default function PromotionsScreen() {
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const promotions = usePromotions();
  useMarkSeen('/me/promotions/seen', promotions.data?.has_new ?? false);
  const offers = promotions.data?.offers ?? [];

  const rows: Promotion[][] = [];
  for (let i = 0; i < offers.length; i += 2) {
    rows.push(offers.slice(i, i + 2));
  }

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('promotions')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16, paddingTop: 0 }]}
      refreshControl={<RefreshControl refreshing={promotions.isRefetching} onRefresh={() => { void promotions.refetch(); }} tintColor={theme.colors.primary} />}>
      {promotions.isPending && offers.length === 0 ? <Loading /> : promotions.isError && offers.length === 0 ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
        offers.length > 0 ? (
          <View testID="server-promotion-cards" style={local.grid}>
            {rows.map((row, r) => (
              <View key={r} style={local.row}>
                {row.map((offer, idx) => {
                  const globalIdx = r * 2 + idx;
                  return (
                    <FadeIn key={offer.id} index={globalIdx} style={local.cell}>
                      <OfferCard
                        offer={offer}
                        index={globalIdx}
                        fill
                        onPress={() => router.push({ pathname: '/promotion/[id]', params: { id: offer.id } })}
                      />
                    </FadeIn>
                  );
                })}
                {row.length === 1 && <View style={local.emptyCell} />}
              </View>
            ))}
          </View>
        ) : <EmptyState icon="gift" title={t('noPromotions')} />}
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  grid: { gap: 12 },
  row: { flexDirection: 'row', gap: 12 },
  cell: { flex: 1 },
  emptyCell: { flex: 1 },
});
