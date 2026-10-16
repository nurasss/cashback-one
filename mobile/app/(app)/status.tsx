import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useBadges } from '../../src/api/app';
import { FadeIn, motionEnabled, PressScale } from '../../src/components/motion';
import { EmptyState, Loading, ScreenHeader, styles } from '../../src/components/ui';
import { TabBar } from '../../src/components/TabBar';
import { useActiveCard } from '../../src/features/activeCard';
import { LevelsSheet } from '../../src/features/LevelsSheet';
import { StatusCoin } from '../../src/features/StatusCoin';
import { useI18n } from '../../src/i18n';
import { fonts, theme } from '../../src/theme';
import { amountText, pointsText } from '../../src/utils/format';

export default function StatusScreen() {
  const { t } = useI18n();
  const { card, cards } = useActiveCard();
  const badges = useBadges();
  const tier = card?.tier;
  const [sheetOpen, setSheetOpen] = useState(false);
  const progress = tier?.next_threshold && tier.spend_total !== undefined
    ? Math.min(1, Math.max(0, Number(tier.spend_total ?? 0) / Number(tier.next_threshold))) : tier && !tier.next_level ? 1 : 0;
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('myStatus')} back />
    <ScrollView contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0, gap: 16 }]}>
      {cards.isPending ? <Loading /> : !card ? <EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')} /> : <>
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
      </>}
    </ScrollView>
    <TabBar active="index" onSelect={route => router.navigate(route === 'index' ? '/' : `/${route}`)}
      badges={{ promotions: badges.data?.promotions_new ?? false, notifications: badges.data?.notifications_unread ?? 0 }} />
    {sheetOpen && tier && <LevelsSheet tier={tier} onClose={() => setSheetOpen(false)} />}
  </SafeAreaView>;
}

function ProgressBar({ progress }: { progress: number }) {
  const fill = useRef(new Animated.Value(motionEnabled ? 0 : progress)).current;
  useEffect(() => {
    if (motionEnabled) Animated.timing(fill, { toValue: progress, duration: 900, delay: 200, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start();
    else fill.setValue(progress);
  }, [fill, progress]);
  return <View style={local.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}>
    <Animated.View style={[local.fill, { width: fill.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
  </View>;
}

const local = StyleSheet.create({
  balance: { fontFamily: fonts.extrabold, fontSize: 30, color: theme.colors.text },
  card: { backgroundColor: theme.colors.surface, borderRadius: 22, padding: 20, gap: 10, borderWidth: 1, borderColor: 'rgba(17,17,17,0.05)' },
  caption: { fontFamily: fonts.semibold, fontSize: 11, color: theme.colors.muted, textTransform: 'uppercase', letterSpacing: 0.8 },
  level: { fontFamily: fonts.extrabold, fontSize: 26, color: theme.colors.text, marginTop: -4 },
  track: { height: 6, borderRadius: 3, backgroundColor: '#ECECF0', overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: theme.colors.primary },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  progressText: { fontFamily: fonts.medium, fontSize: 13, color: theme.colors.muted },
  cta: { marginTop: 6, minHeight: 44, borderRadius: 12, backgroundColor: theme.colors.softPrimary, alignItems: 'center', justifyContent: 'center' },
  ctaText: { fontFamily: fonts.semibold, fontSize: 14, color: theme.colors.primary },
});
