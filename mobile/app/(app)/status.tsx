import * as ExpoRouter from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppContent, useBadges } from '../../src/api/app';
import { getClientConfig } from '../../src/config/client';
import { FadeIn, motionEnabled, PressScale } from '../../src/components/motion';
import { Loading, NoCardNotice, ScreenHeader, useUiStyles } from '../../src/components/ui';
import { TabBar } from '../../src/components/TabBar';
import { useActiveCard } from '../../src/features/activeCard';
import { LevelsSheet } from '../../src/features/LevelsSheet';
import { StatusCoin } from '../../src/features/StatusCoin';
import { useI18n } from '../../src/i18n';
import type { ClientStatuses } from '../../clients/keremet/statuses';
import { StatusArt, StatusCatalogList } from '../../src/features/StatusArt';
import { StatusStoresList } from '../../src/features/stores';
import { useScrollToStores } from '../../src/features/useScrollToStores';
import { getCatalogLead, resolveCatalog, resolveCurrentStatus, resolveStatusDisplay, type StatusCatalog } from '../../src/features/statuses';
import { fonts, type Colors } from '../../src/theme';
import { useThemedStyles } from '../../src/theme/ThemeProvider';
import { amountText, percentText, pointsText } from '../../src/utils/format';

const getRouteParams = (
  typeof ExpoRouter.useLocalSearchParams === 'function'
    ? ExpoRouter.useLocalSearchParams
    : () => ({})
) as () => { section?: string; at?: string };

// Unified status screen: if catalog exists (server loyalty_tiers or Keremet legacy), renders CatalogStatusScreen; otherwise server levels.
export default function StatusRoute() {
  const { card } = useActiveCard();
  const appContent = useAppContent(getClientConfig().business_id ?? card?.business?.id);
  const catalog = resolveCatalog(appContent.data, getClientConfig().slug);
  return catalog ? <CatalogStatusScreen catalog={catalog} /> : <StatusScreen />;
}

function CatalogStatusScreen({ catalog }: { catalog: StatusCatalog | ClientStatuses }) {
  const { section, at } = getRouteParams();
  const { scrollRef, onStoresLayout } = useScrollToStores(section, at);
  const { t } = useI18n();
  const styles = useUiStyles();
  const local = useThemedStyles(makeLocal);
  const { card, cards } = useActiveCard();
  const badges = useBadges();
  const appContent = useAppContent(getClientConfig().business_id ?? card?.business?.id);
  const [sheetOpen, setSheetOpen] = useState(false);
  const { language } = useI18n();
  const langKey = language === 'kz' ? 'kk' : 'ru';
  const balanceDelayNote = appContent.data?.app_texts?.balance_delay_note?.[langKey]?.trim() || t('balanceDelayNote');
  // Current status only from confirmed server data; display falls back to the business minimum tier when personal status is missing/unconfirmed.
  const current = card ? resolveCurrentStatus(card, catalog, appContent.data) : null;
  const display = card ? resolveStatusDisplay(card, catalog, appContent.data) : null;
  const hasTiers = 'tiers' in catalog ? catalog.tiers.length > 0 : catalog.levels.length > 0;
  const shownStatus = display?.kind === 'confirmed'
    ? display.current.status
    : display?.kind === 'minimum'
      ? display.status
      : null;
  const shownPercent = display?.kind === 'confirmed'
    ? display.current.percent
    : display?.kind === 'minimum'
      ? display.percent
      : null;

  const currentName = shownStatus
    ? ((langKey === 'kk' ? shownStatus.name_kk : shownStatus.name_ru) || shownStatus.name)
    : '';
  const currentDesc = shownStatus
    ? ((langKey === 'kk' ? shownStatus.description_kk : shownStatus.description_ru) || shownStatus.description)
    : null;
  const confirmed = display?.kind === 'confirmed' ? display.current : null;
  const turnoverText = confirmed
    ? amountText(confirmed.spendDecimal ?? String(confirmed.spend))
    : '0';
  // Lifetime turnover: statuses never depend on a rolling window or months.
  const currentSpendLine = t('statusSpendLineLifetime', { amount: turnoverText });
  const remainingText = confirmed
    ? (confirmed.remainingDecimal !== undefined && confirmed.remainingDecimal !== null
        ? amountText(confirmed.remainingDecimal)
        : amountText(String(confirmed.remaining ?? 0)))
    : '0';
  const nextName = confirmed && confirmed.next
    ? ((langKey === 'kk' ? confirmed.next.name_kk : confirmed.next.name_ru) || confirmed.next.name)
    : '';

  return <SafeAreaView edges={['top', 'bottom']} style={styles.screen}>
    <ScreenHeader title={t('myStatus')} back />
    <ScrollView ref={scrollRef} contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0, gap: 16 }]}>
      {cards.isPending ? <Loading /> : <>
        {!card && <NoCardNotice />}
        {card && <>
          <FadeIn style={{ alignItems: 'center', marginTop: 24, gap: 4 }}>
            {shownStatus ? <StatusArt status={shownStatus} size={190} /> : null}
            <Text style={[local.caption, { marginTop: shownStatus ? 8 : 24 }]}>{t('pointsSum')}</Text>
            <Text style={local.balance} accessibilityLabel={`${t('pointsSum')}: ${pointsText(card.balance)}`}>{pointsText(card.balance)}</Text>
          </FadeIn>
          <FadeIn index={1} style={local.card}>
            <Text style={local.caption}>{t('yourStatus')}</Text>
            {shownStatus && shownPercent !== null ? <>
              <View style={local.statusHeaderRow}>
                <Text testID="current-status-name" style={[local.level, { flex: 1, marginTop: 0 }]}>{currentName}</Text>
                <View style={local.percentPill}>
                  <Text testID="current-status-percent" style={local.percentPillText}>{percentText(shownPercent)}%</Text>
                </View>
              </View>
              {currentDesc ? <Text testID="current-status-description" style={styles.muted}>{currentDesc}</Text> : null}
              {confirmed ? <>
                <Text style={styles.muted}>{currentSpendLine}</Text>
                {confirmed.next ? (
                  confirmed.progress !== null ? <>
                    <ProgressBar progress={confirmed.progress} />
                    <View style={local.row}>
                      <Text style={local.progressText}>{t('moreToSpend', { amount: remainingText })}</Text>
                      <Text style={[local.progressText, { flexShrink: 1, textAlign: 'right' }]}>{t('untilStatus', { level: nextName })}</Text>
                    </View>
                  </> : null
                ) : <Text style={local.progressText}>{t('maxStatus')}</Text>}
              </> : null}
            </> : <Text testID="status-unavailable" style={local.unavailable}>{t('statusUnavailable')}</Text>}
            {hasTiers && (
              <PressScale accessibilityRole="button" onPress={() => setSheetOpen(true)} scale={0.97} style={local.cta}>
                <Text style={local.ctaText}>{t('howToRaise')}</Text>
              </PressScale>
            )}
          </FadeIn>
        </>}
        {!card && hasTiers && <FadeIn index={1} style={local.card}>
          <Text accessibilityRole="header" style={local.catalogTitle}>{t('statusCatalogTitle')}</Text>
          <Text style={styles.muted}>{getCatalogLead(catalog, t)}</Text>
          <StatusCatalogList catalog={catalog} language={language} />
        </FadeIn>}
        {card && <FadeIn index={2}>
          <View style={local.balanceNote} accessible accessibilityRole="text"><Text style={local.balanceNoteText}>{balanceDelayNote}</Text></View>
        </FadeIn>}
        <View testID="stores-section" onLayout={onStoresLayout}>
          <FadeIn index={card ? 3 : 2}>
            <StatusStoresList stores={appContent.data?.stores} language={language} />
          </FadeIn>
        </View>
      </>}
    </ScrollView>
    <TabBar active="index" onSelect={route => ExpoRouter.router.navigate(route === 'index' ? '/' : `/${route}`)}
      badges={{ promotions: badges.data?.promotions_new ?? false, notifications: badges.data?.notifications_unread ?? 0 }} />
    {sheetOpen && <LevelsSheet tier={card?.tier} catalog={catalog} current={current} onClose={() => setSheetOpen(false)} />}
  </SafeAreaView>;
}

function StatusScreen() {
  const { section, at } = getRouteParams();
  const { scrollRef, onStoresLayout } = useScrollToStores(section, at);
  const { t, language } = useI18n();
  const styles = useUiStyles();
  const local = useThemedStyles(makeLocal);
  const { card, cards } = useActiveCard();
  const badges = useBadges();
  const appContent = useAppContent(getClientConfig().business_id ?? card?.business?.id);
  const tier = card?.tier;
  const [sheetOpen, setSheetOpen] = useState(false);
  const langKey = language === 'kz' ? 'kk' : 'ru';
  const balanceDelayNote = appContent.data?.app_texts?.balance_delay_note?.[langKey]?.trim() || t('balanceDelayNote');
  const progress = tier?.next_threshold && tier.spend_total !== undefined
    ? Math.min(1, Math.max(0, Number(tier.spend_total ?? 0) / Number(tier.next_threshold))) : tier && !tier.next_level ? 1 : 0;

  return <SafeAreaView edges={['top', 'bottom']} style={styles.screen}>
    <ScreenHeader title={t('myStatus')} back />
    <ScrollView ref={scrollRef} contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0, gap: 16 }]}>
      {cards.isPending ? <Loading /> : <>
        {!card && <NoCardNotice />}
        {card && <>
          <FadeIn style={{ alignItems: 'center', marginTop: 40, gap: 4 }}>
            <StatusCoin level={tier?.level ?? '—'} size={190} />
            <Text style={local.caption}>{t('pointsSum')}</Text>
            <Text style={local.balance} accessibilityLabel={`${t('pointsSum')}: ${pointsText(card.balance)}`}>{pointsText(card.balance)}</Text>
          </FadeIn>
          <FadeIn index={1} style={local.card}>
            <Text style={local.caption}>{t('yourStatus')}</Text>
            <Text style={local.level}>{tier ? tier.level : '—'}</Text>
            {tier ? <>
              <ProgressBar progress={progress} />
              {tier.next_level ? <View style={local.row}>
                <Text style={local.progressText}>{t('moreToSpend', { amount: amountText(tier.remaining) })}</Text>
                <Text style={local.progressText}>{t('untilStatus', { level: tier.next_level })}</Text>
              </View> : <Text style={local.progressText}>{t('maxStatus')}</Text>}
            </> : <Text style={styles.muted}>{t('statusesSoon')}</Text>}
            {tier?.levels && tier.levels.length > 0 && <PressScale accessibilityRole="button" onPress={() => setSheetOpen(true)} scale={0.97}
              style={local.cta}><Text style={local.ctaText}>{t('howToRaise')}</Text></PressScale>}
          </FadeIn>
          <FadeIn index={2}>
            <View style={local.balanceNote} accessible accessibilityRole="text">
              <Text style={local.balanceNoteText}>{balanceDelayNote}</Text>
            </View>
          </FadeIn>
        </>}
        <View testID="stores-section" onLayout={onStoresLayout}>
          <FadeIn index={card ? 3 : 1}>
            <StatusStoresList stores={appContent.data?.stores} language={language} />
          </FadeIn>
        </View>
      </>}
    </ScrollView>
    <TabBar active="index" onSelect={route => ExpoRouter.router.navigate(route === 'index' ? '/' : `/${route}`)}
      badges={{ promotions: badges.data?.promotions_new ?? false, notifications: badges.data?.notifications_unread ?? 0 }} />
    {sheetOpen && tier && <LevelsSheet tier={tier} onClose={() => setSheetOpen(false)} />}
  </SafeAreaView>;
}

function ProgressBar({ progress }: { progress: number }) {
  const local = useThemedStyles(makeLocal);
  const fill = useRef(new Animated.Value(motionEnabled ? 0 : progress)).current;
  useEffect(() => {
    if (motionEnabled) Animated.timing(fill, { toValue: progress, duration: 900, delay: 200, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start();
    else fill.setValue(progress);
  }, [fill, progress]);
  return <View style={local.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}>
    <Animated.View style={[local.fill, { width: fill.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
  </View>;
}

const makeLocal = (c: Colors) => StyleSheet.create({
  balance: { fontFamily: fonts.extrabold, fontSize: 30, color: c.text },
  card: { backgroundColor: c.surface, borderRadius: 22, padding: 20, gap: 10, borderWidth: 1, borderColor: c.cardBorder },
  statusHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: -4 },
  percentPill: { backgroundColor: c.softPrimary, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5 },
  percentPillText: { fontFamily: fonts.extrabold, fontSize: 18, color: c.primaryText },
  unavailable: { fontFamily: fonts.semibold, fontSize: 15, lineHeight: 21, color: c.muted },
  catalogTitle: { fontFamily: fonts.bold, fontSize: 18, color: c.text },
  caption: { fontFamily: fonts.semibold, fontSize: 11, color: c.muted, textTransform: 'uppercase', letterSpacing: 0.8 },
  level: { fontFamily: fonts.extrabold, fontSize: 26, color: c.text, marginTop: -4 },
  track: { height: 6, borderRadius: 3, backgroundColor: c.track, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: c.primary },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  progressText: { fontFamily: fonts.medium, fontSize: 13, color: c.muted },
  cta: { marginTop: 6, minHeight: 44, borderRadius: 12, backgroundColor: c.softPrimary, alignItems: 'center', justifyContent: 'center' },
  ctaText: { fontFamily: fonts.semibold, fontSize: 14, color: c.primaryText },
  balanceNote: { backgroundColor: c.softPrimary, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10 },
  balanceNoteText: { fontFamily: fonts.medium, fontSize: 13, lineHeight: 18, color: c.text },
});
