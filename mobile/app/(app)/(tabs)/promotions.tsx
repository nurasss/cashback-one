import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { router } from 'expo-router';
import { Image, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePromotions } from '../../../src/api/app';
import { ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { FadeIn, PressScale } from '../../../src/components/motion';
import { OfferCard } from '../../../src/features/home';
import { PROMOTION_CARDS } from '../../../src/features/promotionsArtwork';
import { useMarkSeen } from '../../../src/features/useMarkSeen';
import { useI18n } from '../../../src/i18n';
import { theme } from '../../../src/theme';

export default function PromotionsScreen() {
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const promotions = usePromotions();
  useMarkSeen('/me/promotions/seen', promotions.data?.has_new ?? false);
  const offers = promotions.data?.offers ?? [];
  const openArtwork = (id: string) => router.push({ pathname: '/promotion/[id]', params: { id } });
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('promotions')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16, paddingTop: 0 }]}
      refreshControl={<RefreshControl refreshing={promotions.isRefetching} onRefresh={() => { void promotions.refetch(); }} tintColor={theme.colors.primary} />}>
      <View testID="promotion-artwork-cards" style={local.cards}>
        {PROMOTION_CARDS.map(card => <PressScale key={card.id} testID={`promotion-card-${card.id}`} accessibilityRole="button"
          accessibilityLabel={t(card.titleKey)} onPress={() => openArtwork(card.id)} style={local.artworkCard}>
          <Image testID={`promotion-image-${card.id}`} source={card.image} style={local.artworkImage} resizeMode="contain" accessibilityIgnoresInvertColors />
        </PressScale>)}
      </View>
      {promotions.isPending ? <Loading /> : promotions.isError ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
        offers.length > 0 ? <View testID="server-promotion-cards" style={local.cards}>{offers.map((offer, index) => <FadeIn key={offer.id} index={index}>
          <OfferCard offer={offer} index={index} wide onPress={() => router.push({ pathname: '/promotion/[id]', params: { id: offer.id } })} />
        </FadeIn>)}</View> : null}
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  cards: { gap: 12 },
  artworkCard: { width: '100%', aspectRatio: 2000 / 1085, borderRadius: 20, overflow: 'hidden', backgroundColor: 'transparent' },
  artworkImage: { width: '100%', height: '100%' },
});
