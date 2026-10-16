import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, EmptyState, Loading, ScreenHeader, styles } from '../../src/components/ui';
import { useActiveCard } from '../../src/features/activeCard';
import { LevelsSheet } from '../../src/features/LevelsSheet';
import { StatusCoin } from '../../src/features/StatusCoin';
import { useI18n } from '../../src/i18n';
import { fonts, theme } from '../../src/theme';
import { amountText, percentText, pointsText } from '../../src/utils/format';

export default function StatusScreen() {
  const { t } = useI18n();
  const { card, cards } = useActiveCard();
  const tier = card?.tier;
  const [sheetOpen, setSheetOpen] = useState(false);
  const progress = tier?.next_threshold && tier.spend_total !== undefined
    ? Math.min(1, Math.max(0, Number(tier.spend_total ?? 0) / Number(tier.next_threshold))) : tier && !tier.next_level ? 1 : 0;
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('myStatus')} back />
    <ScrollView contentContainerStyle={[styles.content, { alignItems: 'stretch', paddingTop: 0 }]}>
      {cards.isPending ? <Loading /> : !card ? <EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')} /> : <>
        <View style={{ alignItems: 'center', marginTop: -10 }}>
          <StatusCoin level={tier?.level ?? '—'} />
          <Text style={local.balance} accessibilityLabel={`${t('pointsSum')}: ${pointsText(card.balance)}`}>{pointsText(card.balance)}</Text>
        </View>
        <View style={local.card}>
          <Text style={local.caption}>{t('yourStatus')}</Text>
          <Text style={local.level}>{tier ? tier.level : '—'}</Text>
          {tier ? <>
            <View style={local.track} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}>
              <View style={[local.fill, { width: `${progress * 100}%` }]} />
            </View>
            {tier.next_level ? <View style={local.row}>
              <Text style={local.progressText}>{t('moreToSpend', { amount: amountText(tier.remaining) })}</Text>
              <Text style={local.progressText}>{t('untilStatus', { level: tier.next_level })}</Text>
            </View> : <Text style={local.progressText}>{t('maxStatus')}</Text>}
            <Text style={styles.muted}>{t('cashbackPercent', { percent: percentText(tier.percent) })}</Text>
          </> : <Text style={styles.muted}>{t('statusesSoon')}</Text>}
          {tier?.levels && tier.levels.length > 0 && <Button label={t('howToRaise')} secondary onPress={() => setSheetOpen(true)} style={{ marginTop: 8 }} />}
          <Button label={t('accrualHistory')} secondary onPress={() => router.push('/history')} style={{ marginTop: 0 }} />
        </View>
      </>}
    </ScrollView>
    {sheetOpen && tier && <LevelsSheet tier={tier} onClose={() => setSheetOpen(false)} />}
  </SafeAreaView>;
}

const local = StyleSheet.create({
  balance: { fontFamily: fonts.bold, fontSize: 44, color: theme.colors.text, marginTop: -30 },
  card: { backgroundColor: theme.colors.surface, borderRadius: 28, padding: 24, gap: 12 },
  caption: { fontFamily: fonts.regular, fontSize: 16, color: theme.colors.text },
  level: { fontFamily: fonts.bold, fontSize: 40, color: theme.colors.text },
  track: { height: 8, borderRadius: 4, backgroundColor: '#ECECF0', overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: theme.colors.primary },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  progressText: { fontFamily: fonts.regular, fontSize: 17, color: theme.colors.text },
});
