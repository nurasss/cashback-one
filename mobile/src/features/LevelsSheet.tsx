import { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Icon } from '../components/icons';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { Tier } from '../types/api';
import { amountText, percentText } from '../utils/format';

export const MIN_CHECK = 100;

// Informational estimate only: points are accrued by the cashier in POSCENTER ONE.
export function estimatePoints(amountDigits: string, percent: string): string | null {
  const amount = Number(amountDigits);
  if (!Number.isFinite(amount) || amount < MIN_CHECK) return null;
  return (Math.floor(amount * Number(percent) ) / 100).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function LevelsSheet({ tier, onClose }: { tier: Tier; onClose: () => void }) {
  const { t: tr } = useI18n();
  const [amount, setAmount] = useState('');
  const digits = amount.replace(/\D/g, '');
  const points = useMemo(() => estimatePoints(digits, tier.percent), [digits, tier.percent]);
  const levels = tier.levels ?? [];
  return <Modal transparent animationType="slide" onRequestClose={onClose}>
    <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={tr('close')} />
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.wrap}>
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.titleRow}>
          <Text accessibilityRole="header" style={styles.title}>{tr('howToRaise')}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel={tr('close')} hitSlop={12} onPress={onClose}><Icon name="x" size={26} /></Pressable>
        </View>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 10, paddingBottom: 8 }}>
          <Text style={styles.lead}>{tr('howToLead')}</Text>
          {levels.map(level => {
            const current = level.level === tier.level;
            return <View key={level.level} style={[styles.level, current && styles.levelCurrent]} accessibilityState={{ selected: current }}>
              <View style={{ gap: 2 }}>
                <Text style={styles.levelName}>{tr('statusN', { level: level.level })}</Text>
                <Text style={styles.levelFrom}>{tr('fromAmount', { amount: amountText(level.threshold) })}</Text>
              </View>
              <Text style={[styles.levelPercent, current && { color: t.colors.primary }]}>{percentText(level.percent)}%</Text>
            </View>;
          })}
          <Text style={styles.current}>{tr('currentStatusLine', { level: tier.level, percent: percentText(tier.percent) })}</Text>
          <Text style={styles.fieldLabel}>{tr('calcLabel')}</Text>
          <TextInput accessibilityLabel={tr('calcLabel')} value={amount} onChangeText={value => setAmount(value.replace(/\D/g, '').slice(0, 9))}
            keyboardType="number-pad" placeholder="0" placeholderTextColor={t.colors.subtle} style={styles.input} />
          <View style={styles.quick}>{[5000, 15000, 40000, 120000].map(value => <Pressable key={value} accessibilityRole="button" onPress={() => setAmount(String(value))} style={styles.quickChip}>
            <Text style={styles.quickText}>{amountText(String(value))}</Text></Pressable>)}</View>
          {points ? <Text accessibilityLiveRegion="polite" style={styles.result}>{tr('calcResult', { points })}</Text>
            : <Text style={styles.hint}>{tr('calcHint')}</Text>}
          <Text style={styles.disclaimer}>{tr('calcDisclaimer')}</Text>
        </ScrollView>
      </View>
    </KeyboardAvoidingView>
  </Modal>;
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)' },
  wrap: { position: 'absolute', left: 0, right: 0, bottom: 0, maxHeight: '88%' },
  sheet: { backgroundColor: t.colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 20, paddingTop: 10, paddingBottom: 28, gap: 12 },
  handle: { alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: t.colors.border },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontFamily: fonts.extrabold, fontSize: 22, color: t.colors.text },
  lead: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 21, color: t.colors.muted },
  level: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: t.colors.input, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12 },
  levelCurrent: { backgroundColor: t.colors.softPrimary },
  levelName: { fontFamily: fonts.bold, fontSize: 16, color: t.colors.text },
  levelFrom: { fontFamily: fonts.regular, fontSize: 13, color: t.colors.muted },
  levelPercent: { fontFamily: fonts.extrabold, fontSize: 22, color: t.colors.text },
  current: { fontFamily: fonts.semibold, fontSize: 14, color: t.colors.primary, marginTop: 4 },
  fieldLabel: { fontFamily: fonts.medium, fontSize: 15, color: t.colors.text },
  input: { minHeight: 54, paddingHorizontal: 18, borderRadius: 14, backgroundColor: t.colors.input, color: t.colors.text, fontFamily: fonts.bold, fontSize: 22 },
  quick: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickChip: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 999, backgroundColor: t.colors.input },
  quickText: { fontFamily: fonts.semibold, fontSize: 14, color: t.colors.text },
  result: { fontFamily: fonts.bold, fontSize: 17, color: t.colors.primary },
  hint: { fontFamily: fonts.medium, fontSize: 13, color: t.colors.muted },
  disclaimer: { fontFamily: fonts.regular, fontSize: 12, color: t.colors.subtle },
});
