import { router } from 'expo-router';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useProfile, usePromotions } from '../../../src/api/app';
import { Icon } from '../../../src/components/icons';
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
  const refreshing = cards.isRefetching || promotions.isRefetching;
  const refresh = () => { void cards.refetch(); void promotions.refetch(); void profile.refetch(); };
  const offers = promotions.data?.offers ?? [];
  const openPromotion = (id: string) => router.push({ pathname: '/promotion/[id]', params: { id } });

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScrollView contentContainerStyle={{ paddingBottom: 140 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.colors.primary} />}>
      <View style={local.topSheet}>
        <BalanceHeader phone={phoneText(profile.data?.phone)} balance={card?.balance ?? '0'} />
        <BannerCarousel banners={promotions.data?.banners ?? []} open={openPromotion} />
      </View>

      <View style={local.section}>
        {cards.isPending ? <Loading /> : cards.isError && !cards.data ? <ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} /> :
          card ? <>
            <StatusCard tier={card.tier} balance={card.balance} onPress={() => router.push('/status')} />
            {card.tier && Number(card.tier.max_percent) > 0 && <View style={local.promoLine}>
              <Icon name="crown" size={24} color={theme.colors.primary} />
              <Text style={local.promoLineText}>{t('dontMiss', { percent: percentText(card.tier.max_percent) })}</Text>
            </View>}
          </> : <View style={styles.sheet}><EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')}>
            <Button label={t('bind')} onPress={() => router.push('/bind')} style={{ alignSelf: 'stretch' }} />
          </EmptyState></View>}
      </View>

      <View style={local.offersSheet}>
        <View style={local.offersHeader}>
          <Text style={local.offersTitle}>{t('hotOffers')}</Text>
          <Pressable accessibilityRole="button" hitSlop={10} onPress={() => router.push('/promotions')} style={local.allLink}>
            <Text style={local.allText}>{t('all')}</Text><Icon name="chevronRight" size={22} color={theme.colors.primary} />
          </Pressable>
        </View>
        {promotions.isPending ? <Loading /> : promotions.isError ? <ErrorNotice error={promotions.error} retry={() => { void promotions.refetch(); }} /> :
          offers.length === 0 ? <Text style={[styles.muted, { paddingHorizontal: 24 }]}>{t('noOffers')}</Text> :
          <View style={local.grid}>{offers.slice(0, 4).map((offer, index) => <OfferCard key={offer.id} offer={offer} index={index} onPress={() => openPromotion(offer.id)} />)}</View>}
      </View>
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  topSheet: { backgroundColor: theme.colors.surface, borderBottomLeftRadius: 32, borderBottomRightRadius: 32 },
  section: { padding: 24, gap: 18 },
  promoLine: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  promoLineText: { fontFamily: fonts.semibold, fontSize: 18, color: theme.colors.primary },
  offersSheet: { backgroundColor: theme.colors.surface, borderRadius: 32, paddingTop: 26, paddingBottom: 24, gap: 20 },
  offersHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24 },
  offersTitle: { fontFamily: fonts.bold, fontSize: 22, color: theme.colors.text },
  allLink: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  allText: { fontFamily: fonts.semibold, fontSize: 18, color: theme.colors.primary },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, paddingHorizontal: 24 },
});
