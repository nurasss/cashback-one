import { router } from 'expo-router';
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
import { getClientStatuses, resolveCurrentStatus } from '../../src/features/statuses';
import { fonts, type Colors } from '../../src/theme';
import { useThemedStyles } from '../../src/theme/ThemeProvider';
import { amountText, pointsText } from '../../src/utils/format';

// Keremet (and any client with named statuses) gets its own screen; every other client keeps the server-driven one below.
export default function StatusRoute() {
  const catalog = getClientStatuses();
  return catalog ? <CatalogStatusScreen catalog={catalog} /> : <StatusScreen />;
}

function CatalogStatusScreen({ catalog }: { catalog: ClientStatuses }) {
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
  // Current status only from confirmed server data; with no card there is no status and no balance, only the conditions.
  const current = card ? resolveCurrentStatus(card.tier, catalog) : null;
  return <SafeAreaView edges={['top', 'bottom']} style={styles.screen}>
    <ScreenHeader title={t('myStatus')} back />
    <ScrollView contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0, gap: 16 }]}>
      {cards.isPending ? <Loading /> : <>
        {!card && <NoCardNotice />}
        {card && <>
          <FadeIn style={{ alignItems: 'center', marginTop: 24, gap: 4 }}>
            {current?.known ? <StatusArt status={current.status} size={190} /> : null}
            <Text style={[local.caption, { marginTop: current?.known ? 8 : 24 }]}>{t('pointsSum')}</Text>
            <Text style={local.balance} accessibilityLabel={`${t('pointsSum')}: ${pointsText(card.balance)}`}>{pointsText(card.balance)}</Text>
          </FadeIn>
          <FadeIn index={1} style={local.card}>
            <Text style={local.caption}>{t('yourStatus')}</Text>
            {current?.known ? <>
              <Text testID="current-status-name" style={local.level}>{current.status.name}</Text>
              <Text style={styles.muted}>{t('statusSpendLine', { amount: amountText(String(current.spend)) })}</Text>
              <ProgressBar progress={current.progress} />
              {current.next ? <View style={local.row}>
                <Text style={local.progressText}>{t('moreToSpend', { amount: amountText(String(current.remaining ?? 0)) })}</Text>
                <Text style={[local.progressText, { flexShrink: 1, textAlign: 'right' }]}>{t('untilStatus', { level: current.next.name })}</Text>
              </View> : <Text style={local.progressText}>{t('maxStatus')}</Text>}
            </> : <Text testID="status-unavailable" style={local.unavailable}>{t('statusUnavailable')}</Text>}
            <PressScale accessibilityRole="button" onPress={() => setSheetOpen(true)} scale={0.97} style={local.cta}><Text style={local.ctaText}>{t('howToRaise')}</Text></PressScale>
          </FadeIn>
        </>}
        {!card && <FadeIn index={1} style={local.card}>
          <Text accessibilityRole="header" style={local.catalogTitle}>{t('statusCatalogTitle')}</Text>
          <Text style={styles.muted}>{t('statusLead')}</Text>
          <StatusCatalogList catalog={catalog} />
        </FadeIn>}
        {card && <FadeIn index={2}>
          <View style={local.balanceNote} accessible accessibilityRole="text"><Text style={local.balanceNoteText}>{balanceDelayNote}</Text></View>
        </FadeIn>}
      </>}
    </ScrollView>
    <TabBar active="index" onSelect={route => router.navigate(route === 'index' ? '/' : `/${route}`)}
      badges={{ promotions: badges.data?.promotions_new ?? false, notifications: badges.data?.notifications_unread ?? 0 }} />
    {sheetOpen && <LevelsSheet tier={card?.tier} catalog={catalog} current={current} onClose={() => setSheetOpen(false)} />}
  </SafeAreaView>;
}

function StatusScreen() {
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
    <ScrollView contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0, gap: 16 }]}>
      {cards.isPending ? <Loading /> : !card ? <NoCardNotice /> : <>
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
    </ScrollView>
    <TabBar active="index" onSelect={route => router.navigate(route === 'index' ? '/' : `/${route}`)}
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
