import { useKeyboardLift } from '../components/useKeyboardLift';
import { useRef, useMemo, useState } from 'react';
import { Keyboard, Animated, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '../components/icons';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import type { ClientStatuses } from '../../clients/keremet/statuses';
import type { Tier } from '../types/api';
import { StatusCatalogList } from './StatusArt';
import type { CurrentStatus } from './statuses';
import { amountText, percentText } from '../utils/format';

function useSafeInsets() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, bottom: 0, left: 0, right: 0 };
  }
}

export const MIN_CHECK = 100;

// Informational estimate only: points are accrued by the cashier in POSCENTER ONE.
export function estimatePoints(amountDigits: string, percent: string): string | null {
  const amount = Number(amountDigits);
  if (!Number.isFinite(amount) || amount < MIN_CHECK) return null;
  return (Math.floor(amount * Number(percent) ) / 100).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// `catalog` (Keremet) replaces the server's numbered levels with the named statuses; the sheet then also works without a card or a known
// status. Without `catalog` the sheet is exactly the shared one: it needs `tier`.
export function LevelsSheet({ tier, onClose, catalog, current }: { tier?: Tier | null; onClose: () => void; catalog?: ClientStatuses | null; current?: CurrentStatus | null }) {
  const { t: tr } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const { colors, isDark } = useTheme();
  const insets = useSafeInsets();
  const [amount, setAmount] = useState('');
  const lift = useKeyboardLift();
  const scroll = useRef<ScrollView>(null);
  const inputY = useRef(0);
  const inputFocused = useRef(false);
  const digits = amount.replace(/\D/g, '');
  // In catalog mode the estimate uses the percent of the confirmed current status only; an unknown status gives no estimate.
  const percent = catalog ? (current?.known ? String(current.status.percent) : null) : tier?.percent ?? null;
  const points = useMemo(() => (percent === null ? null : estimatePoints(digits, percent)), [digits, percent]);
  const levels = tier?.levels ?? [];

  const handleRequestClose = () => {
    if (lift.keyboardVisible.current) {
      Keyboard.dismiss();
      return;
    }
    onClose();
  };

  return <Modal transparent animationType="slide" onRequestClose={handleRequestClose} statusBarTranslucent>
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={tr('close')} />
      <Animated.View ref={lift.ref} collapsable={false} onLayout={lift.onLayout} pointerEvents="box-none" style={[styles.wrap, lift.style]}>
        <View style={[styles.sheet, { maxHeight: lift.maxHeight ?? '88%', paddingBottom: Math.max(28, insets.bottom + 16) }]}>
          <View style={styles.handle} />
          <View style={styles.titleRow}>
            <Text accessibilityRole="header" style={styles.title}>{tr('howToRaise')}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={tr('close')} hitSlop={12} onPress={onClose}><Icon name="x" size={26} /></Pressable>
          </View>
          <ScrollView ref={scroll} onLayout={() => { if (inputFocused.current) scroll.current?.scrollTo({ y: inputY.current, animated: false }); }} style={{ flexShrink: 1 }} keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 10, paddingBottom: 8 }}>
            <Text style={styles.lead}>{catalog ? tr('statusLead') : tr('howToLead')}</Text>
            {catalog ? <StatusCatalogList catalog={catalog} current={current} /> : levels.map(level => {
              const isCurrent = level.level === tier?.level;
              return <View key={level.level} style={[styles.level, isCurrent && styles.levelCurrent]} accessibilityState={{ selected: isCurrent }}>
                <View style={{ gap: 2 }}>
                  <Text style={styles.levelName}>{tr('statusN', { level: level.level })}</Text>
                  <Text style={styles.levelFrom}>{tr('fromAmount', { amount: amountText(level.threshold) })}</Text>
                </View>
                <Text style={[styles.levelPercent, isCurrent && { color: colors.primaryText }]}>{percentText(level.percent)}%</Text>
              </View>;
            })}
            {catalog
              ? <Text style={styles.current}>{current?.known ? tr('statusCurrentNamed', { name: current.status.name, percent: String(current.status.percent) }) : tr('statusUnavailable')}</Text>
              : tier && <Text style={styles.current}>{tr('currentStatusLine', { level: tier.level, percent: percentText(tier.percent) })}</Text>}
            {percent !== null && <>
            <Text style={styles.fieldLabel}>{tr('calcLabel')}</Text>
            <TextInput onLayout={event => { inputY.current = event.nativeEvent.layout.y; }} onFocus={() => { inputFocused.current = true; scroll.current?.scrollTo({ y: inputY.current, animated: true }); }} onBlur={() => { inputFocused.current = false; }} accessibilityLabel={tr('calcLabel')} value={amount} onChangeText={value => setAmount(value.replace(/\D/g, '').slice(0, 9))}
              keyboardType="number-pad" placeholder="0" placeholderTextColor={colors.placeholder} keyboardAppearance={isDark ? 'dark' : 'light'} style={styles.input} />
            <View style={styles.quick}>{[5000, 15000, 40000, 120000].map(value => <Pressable key={value} accessibilityRole="button" onPress={() => setAmount(String(value))} style={styles.quickChip}>
              <Text style={styles.quickText}>{amountText(String(value))}</Text></Pressable>)}</View>
            {points ? <Text accessibilityLiveRegion="polite" style={styles.result}>{tr('calcResult', { points })}</Text>
              : <Text style={styles.hint}>{tr('calcHint')}</Text>}
            <Text style={styles.disclaimer}>{tr('calcDisclaimer')}</Text>
            </>}
          </ScrollView>
        </View>
      </Animated.View>
    </View>
  </Modal>;
}

const makeStyles = (c: Colors) => StyleSheet.create({
  modalOverlay: { flex: 1, justifyContent: 'flex-end' },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: c.overlay },
  wrap: { flex: 1, width: '100%', justifyContent: 'flex-end' },
  sheet: { flexShrink: 1, maxHeight: '88%', backgroundColor: c.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 20, paddingTop: 10, gap: 12 },
  handle: { alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: c.border },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontFamily: fonts.extrabold, fontSize: 22, color: c.text },
  lead: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 21, color: c.muted },
  level: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: c.input, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12 },
  levelCurrent: { backgroundColor: c.softPrimary },
  levelName: { fontFamily: fonts.bold, fontSize: 16, color: c.text },
  levelFrom: { fontFamily: fonts.regular, fontSize: 13, color: c.muted },
  levelPercent: { fontFamily: fonts.extrabold, fontSize: 22, color: c.text },
  current: { fontFamily: fonts.semibold, fontSize: 14, color: c.primaryText, marginTop: 4 },
  fieldLabel: { fontFamily: fonts.medium, fontSize: 15, color: c.text },
  input: { minHeight: 54, paddingHorizontal: 18, borderRadius: 14, backgroundColor: c.input, color: c.text, fontFamily: fonts.bold, fontSize: 22 },
  quick: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickChip: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 999, backgroundColor: c.input },
  quickText: { fontFamily: fonts.semibold, fontSize: 14, color: c.text },
  result: { fontFamily: fonts.bold, fontSize: 17, color: c.primaryText },
  hint: { fontFamily: fonts.medium, fontSize: 13, color: c.muted },
  disclaimer: { fontFamily: fonts.regular, fontSize: 12, color: c.muted },
});
