import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { router } from 'expo-router';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePromotions } from '../../../src/api/app';
import { Button, EmptyState, ErrorNotice, Loading, ScreenHeader, useUiStyles } from '../../../src/components/ui';
import { FadeIn } from '../../../src/components/motion';
import { OfferCard } from '../../../src/features/home';
import { useMarkSeen } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { useTheme } from '../../../src/theme/ThemeProvider';
import type { Promotion } from '../../../src/types/api';

// The Promotions tab first shows this many cards (three rows of two); the rest sit behind "View all" on the same screen.
const PROMOTIONS_PREVIEW_COUNT = 6;

export default function PromotionsScreen() {
  const insets = useSafeAreaInsets();
  const styles = useUiStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const promotions = usePromotions();
  // Local to this mounted screen: it survives re-renders (e.g. a theme change) but not a sign-out. Logging out replaces the whole
  // navigator with the loading screen (see Navigation in app/_layout.tsx), so the next account starts collapsed.
  const [showAll, setShowAll] = useState(false);
  useMarkSeen('/me/promotions/seen', promotions.data?.has_new ?? false);
  const offers = promotions.data?.offers ?? [];
  const hasMore = offers.length > PROMOTIONS_PREVIEW_COUNT;
  const visibleOffers = hasMore && !showAll ? offers.slice(0, PROMOTIONS_PREVIEW_COUNT) : offers;

  const rows: Promotion[][] = [];
  for (let i = 0; i < visibleOffers.length; i += 2) {
    rows.push(visibleOffers.slice(i, i + 2));
  }

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('promotions')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16, paddingTop: 0 }]}
      refreshControl={<RefreshControl refreshing={promotions.isRefetching} onRefresh={() => { void promotions.refetch(); }} tintColor={colors.primary} />}>
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
      {hasMore && <Button secondary label={showAll ? t('collapse') : t('viewAll')} onPress={() => setShowAll(value => !value)} />}
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  grid: { gap: 12 },
  row: { flexDirection: 'row', gap: 12 },
  cell: { flex: 1 },
  emptyCell: { flex: 1 },
});
