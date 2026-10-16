import { router } from 'expo-router';
import { RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePromotions } from '../../../src/api/app';
import { EmptyState, ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { FadeIn } from '../../../src/components/motion';
import { OfferCard } from '../../../src/features/home';
import { useMarkSeen } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { theme } from '../../../src/theme';

export default function PromotionsScreen() {
  const { t } = useI18n();
  const promotions = usePromotions();
  useMarkSeen('/me/promotions/seen', promotions.data?.has_new ?? false);
  const offers = promotions.data?.offers ?? [];
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('promotions')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 0 }]}
      refreshControl={<RefreshControl refreshing={promotions.isRefetching} onRefresh={() => { void promotions.refetch(); }} tintColor={theme.colors.primary} />}>
      {promotions.isPending ? <Loading /> : promotions.isError ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
        offers.length === 0 ? <EmptyState icon="gift" title={t('noPromotions')} /> :
        <View style={{ gap: 12 }}>{offers.map((offer, index) => <FadeIn key={offer.id} index={index}><OfferCard offer={offer} index={index} wide
          onPress={() => router.push({ pathname: '/promotion/[id]', params: { id: offer.id } })} /></FadeIn>)}</View>}
    </ScrollView>
  </SafeAreaView>;
}
