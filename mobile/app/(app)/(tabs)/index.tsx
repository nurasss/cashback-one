import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useProfile, usePromotions } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
import { FadeIn } from '../../../src/components/motion';
import { Button, EmptyState, ErrorNotice, Loading, styles } from '../../../src/components/ui';
import { useActiveCard } from '../../../src/features/activeCard';
import { BannerCarousel, HomeHeader, OfferCard, WalletCard } from '../../../src/features/home';
import { useI18n } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import { percentText, phoneText } from '../../../src/utils/format';

export default function Home() {
  const { t } = useI18n();
  const { card, cards } = useActiveCard();
  const profile = useProfile();
  const promotions = usePromotions();
  const offers = promotions.data?.offers ?? [];
  const openPromotion = (id: string) => router.push({ pathname: '/promotion/[id]', params: { id } });

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <View style={local.page}>
      <FadeIn><HomeHeader name={profile.data?.first_name} phone={phoneText(profile.data?.phone)} /></FadeIn>

      <FadeIn index={1} style={local.wallet}>
        {cards.isPending ? <Loading /> : cards.isError && !cards.data ? <View style={local.inset}><ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} /></View> :
          card ? <>
            <WalletCard tier={card.tier} balance={card.balance} onPress={() => router.push('/status')} />
            {card.tier && Number(card.tier.max_percent) > Number(card.tier.percent) && <View style={local.promoLine}>
              <Icon name="crown" size={16} color={theme.colors.primary} />
              <Text style={local.promoLineText}>{t('dontMiss', { percent: percentText(card.tier.max_percent) })}</Text>
            </View>}
          </> : <View style={[styles.sheet, local.inset]}><EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')}>
            <Button label={t('bind')} onPress={() => router.push('/bind')} style={{ alignSelf: 'stretch' }} />
          </EmptyState></View>}
      </FadeIn>

      <FadeIn index={2}><BannerCarousel banners={promotions.data?.banners ?? []} open={openPromotion} /></FadeIn>

      <FadeIn index={3} style={local.offers}>
        <View style={local.offersHeader}>
          <Text style={local.offersTitle}>{t('hotOffers')}</Text>
          <Pressable accessibilityRole="button" hitSlop={10} onPress={() => router.push('/promotions')} style={local.allLink}>
            <Text style={local.allText}>{t('all')}</Text><Icon name="chevronRight" size={16} color={theme.colors.primary} />
          </Pressable>
        </View>
        {promotions.isPending ? <Loading /> : promotions.isError ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
          offers.length === 0 ? <Text style={styles.muted}>{t('noOffers')}</Text> :
          <View style={local.grid}>{[offers.slice(0, 2), offers.slice(2, 4)].map((row, r) => row.length > 0 && <View key={r} style={local.gridRow}>
            {row.map(offer => <OfferCard key={offer.id} fill offer={offer} onPress={() => openPromotion(offer.id)} />)}
          </View>)}</View>}
      </FadeIn>
    </View>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  page: { flex: 1, paddingBottom: 92, gap: 16 },
  wallet: { gap: 10 },
  inset: { marginHorizontal: 20 },
  promoLine: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  promoLineText: { fontFamily: fonts.medium, fontSize: 13, color: theme.colors.muted },
  offers: { flex: 1, minHeight: 0, paddingHorizontal: 20, gap: 10 },
  offersHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  offersTitle: { fontFamily: fonts.bold, fontSize: 18, color: theme.colors.text },
  allLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  allText: { fontFamily: fonts.semibold, fontSize: 14, color: theme.colors.primary },
  grid: { flex: 1, minHeight: 0, gap: 10 },
  gridRow: { flex: 1, minHeight: 0, flexDirection: 'row', gap: 10 },
});
