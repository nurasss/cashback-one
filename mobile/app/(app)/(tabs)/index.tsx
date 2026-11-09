import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { router } from 'expo-router';
import { Alert, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAppContent, useProfile, usePromotions } from '../../../src/api/app';
import { getClientConfig } from '../../../src/config/client';
import { Icon } from '../../../src/components/icons';
import { FadeIn } from '../../../src/components/motion';
import { Button, ErrorNotice, Loading, NoCardNotice, useUiStyles } from '../../../src/components/ui';
import { useActiveCard } from '../../../src/features/activeCard';
import { BalanceHeader, BannerCarousel, ServerOffersGrid, StatusCard, StoreBlock } from '../../../src/features/home';
import { PushPermissionNotice } from '../../../src/features/push';
import { getClientStatuses, maxStatusPercent, resolveCurrentStatus } from '../../../src/features/statuses';
import { useI18n } from '../../../src/i18n';
import { errorMessages } from '../../../src/i18n/ru';
import { fonts, type Colors } from '../../../src/theme';
import { useTheme, useThemedStyles } from '../../../src/theme/ThemeProvider';
import { percentText, phoneText } from '../../../src/utils/format';

export default function Home() {
  const insets = useSafeAreaInsets();
  const styles = useUiStyles();
  const local = useThemedStyles(makeLocal);
  const { colors } = useTheme();
  const { t, language } = useI18n();
  const { card, cards } = useActiveCard();
  const profile = useProfile();
  const promotions = usePromotions();
  const appContent = useAppContent(getClientConfig().business_id ?? card?.business?.id);
  const openPromotion = (id: string) => router.push({ pathname: '/promotion/[id]', params: { id } });
  const openPromotions = () => router.push('/promotions');
  const openStoreMap = (url: string) => {
    Linking.openURL(url).catch(() => {
      Alert.alert(t('app'), errorMessages.UNKNOWN_ERROR);
    });
  };

  const isRefreshing = promotions.isRefetching || cards.isRefetching || profile.isRefetching || appContent.isRefetching;
  const onRefresh = () => {
    void Promise.all([
      promotions.refetch(),
      cards.refetch(),
      profile.refetch(),
      appContent.refetch(),
    ]);
  };

  // Keremet's named statuses; other clients keep the server's tier.
  const statuses = getClientStatuses();
  const currentStatus = statuses && card ? resolveCurrentStatus(card.tier, statuses) : null;
  const banners = promotions.data?.banners ?? [];
  const offers = promotions.data?.offers ?? [];

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScrollView
      style={local.scrollView}
      contentContainerStyle={[local.pageContent, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16 }]}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing}
          onRefresh={onRefresh}
          tintColor={colors.primary}
        />
      }
    >
      <FadeIn style={local.topSheet}>
        <BalanceHeader phone={phoneText(profile.data?.phone)} balance={card?.balance ?? '0'} />
        {banners.length > 0 && <BannerCarousel banners={banners} open={openPromotion} />}
      </FadeIn>

      <FadeIn index={1} style={local.section}>
        {cards.isPending ? <Loading /> : cards.isError && !cards.data ? <ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} /> : <>
          {card ? <>
            <StatusCard tier={card.tier} balance={card.balance} onPress={() => router.push('/status')} statuses={statuses && currentStatus ? { catalog: statuses, current: currentStatus } : undefined} />
            {(statuses ? currentStatus?.known === true : !!card.tier && Number(card.tier.max_percent) > 0) && <View style={local.promoLine}>
              <Icon name="crown" size={18} color={colors.primaryText} />
              <Text style={local.promoLineText}>{t('dontMiss', { percent: statuses ? String(maxStatusPercent(statuses)) : percentText(card.tier?.max_percent) })}</Text>
            </View>}
          </> : <>
            <NoCardNotice />
            {/* Anyone can read the status conditions; a current status and a balance only exist with a card. */}
            {statuses && <Button secondary label={t('statusCatalogTitle')} onPress={() => router.push('/status')} />}
          </>}
          <StoreBlock appContent={appContent.data} language={language} onOpenMap={openStoreMap} />
          <PushPermissionNotice />
        </>}
      </FadeIn>

      {offers.length > 0 && <FadeIn index={2} style={local.offersSheet}>
        <View style={local.offersHeader}>
          <Text style={local.offersTitle}>{t('hotOffers')}</Text>
          <Pressable accessibilityRole="button" hitSlop={10} onPress={openPromotions} style={local.allLink}>
            <Text style={local.allText}>{t('all')}</Text><Icon name="chevronRight" size={16} color={colors.primaryText} />
          </Pressable>
        </View>
        <ServerOffersGrid offers={offers} onOpen={openPromotion} />
      </FadeIn>}
    </ScrollView>
  </SafeAreaView>;
}

const makeLocal = (c: Colors) => StyleSheet.create({
  scrollView: { flex: 1 },
  pageContent: { flexGrow: 1 },
  topSheet: { backgroundColor: c.surface, borderBottomLeftRadius: 28, borderBottomRightRadius: 28, paddingBottom: 14 },
  section: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14, gap: 10 },
  promoLine: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  promoLineText: { fontFamily: fonts.semibold, fontSize: 13, color: c.primaryText },
  offersSheet: { backgroundColor: c.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingTop: 18, paddingBottom: 24, gap: 12 },
  offersHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20 },
  offersTitle: { fontFamily: fonts.bold, fontSize: 18, color: c.text },
  allLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  allText: { fontFamily: fonts.semibold, fontSize: 14, color: c.primaryText },
});
