import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useProfile, usePromotions } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
import { FadeIn } from '../../../src/components/motion';
import { Button, EmptyState, ErrorNotice, Loading, styles } from '../../../src/components/ui';
import { useActiveCard } from '../../../src/features/activeCard';
import { BalanceHeader, BannerCarousel, OfferCard, StatusCard } from '../../../src/features/home';
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
      <FadeIn style={local.topSheet}>
        <BalanceHeader phone={phoneText(profile.data?.phone)} balance={card?.balance ?? '0'} />
        <BannerCarousel banners={promotions.data?.banners ?? []} open={openPromotion} />
      </FadeIn>

      <FadeIn index={1} style={local.section}>
        {cards.isPending ? <Loading /> : cards.isError && !cards.data ? <ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} /> :
          card ? <>
            <StatusCard tier={card.tier} balance={card.balance} onPress={() => router.push('/status')} />
            {card.tier && Number(card.tier.max_percent) > 0 && <View style={local.promoLine}>
              <Icon name="crown" size={18} color={theme.colors.primary} />
              <Text style={local.promoLineText}>{t('dontMiss', { percent: percentText(card.tier.max_percent) })}</Text>
            </View>}
          </> : <View style={styles.sheet}><EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')}>
            <Button label={t('bind')} onPress={() => router.push('/bind')} style={{ alignSelf: 'stretch' }} />
          </EmptyState></View>}
      </FadeIn>

      <FadeIn index={2} style={local.offersSheet}>
        <View style={local.offersHeader}>
          <Text style={local.offersTitle}>{t('hotOffers')}</Text>
          <Pressable accessibilityRole="button" hitSlop={10} onPress={() => router.push('/promotions')} style={local.allLink}>
            <Text style={local.allText}>{t('all')}</Text><Icon name="chevronRight" size={16} color={theme.colors.primary} />
          </Pressable>
        </View>
        {promotions.isPending ? <Loading /> : promotions.isError ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
          offers.length === 0 ? <Text style={[styles.muted, { paddingHorizontal: 24 }]}>{t('noOffers')}</Text> :
          <View style={local.grid}>{[offers.slice(0, 2), offers.slice(2, 4)].map((row, r) => row.length > 0 && <View key={r} style={local.gridRow}>
            {row.map((offer, i) => <OfferCard key={offer.id} fill offer={offer} index={r * 2 + i} onPress={() => openPromotion(offer.id)} />)}
          </View>)}</View>}
      </FadeIn>
    </View>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  page: { flex: 1, paddingBottom: 96 },
  topSheet: { backgroundColor: theme.colors.surface, borderBottomLeftRadius: 28, borderBottomRightRadius: 28, paddingBottom: 14 },
  section: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14, gap: 10 },
  promoLine: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  promoLineText: { fontFamily: fonts.semibold, fontSize: 13, color: theme.colors.primary },
  offersSheet: { flex: 1, minHeight: 0, backgroundColor: theme.colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingTop: 18, paddingBottom: 14, gap: 12 },
  offersHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20 },
  offersTitle: { fontFamily: fonts.bold, fontSize: 18, color: theme.colors.text },
  allLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  allText: { fontFamily: fonts.semibold, fontSize: 14, color: theme.colors.primary },
  grid: { flex: 1, minHeight: 0, gap: 12, paddingHorizontal: 20 },
  gridRow: { flex: 1, minHeight: 0, flexDirection: 'row', gap: 12 },
});
