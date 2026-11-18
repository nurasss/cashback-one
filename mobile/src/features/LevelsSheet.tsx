import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '../components/icons';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import type { ClientStatuses } from '../../clients/keremet/statuses';
import type { Tier } from '../types/api';
import { StatusCatalogList } from './StatusArt';
import { getCatalogLead, type CurrentStatus, type StatusCatalog } from './statuses';
import { amountText, percentText } from '../utils/format';

function useSafeInsets() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, bottom: 0, left: 0, right: 0 };
  }
}

// `catalog` (Keremet) replaces the server's numbered levels with the named statuses; the sheet then also works without a card or a known
// status. Without `catalog` the sheet is exactly the shared one: it needs `tier`.
export function LevelsSheet({ tier, onClose, catalog, current }: { tier?: Tier | null; onClose: () => void; catalog?: StatusCatalog | ClientStatuses | null; current?: CurrentStatus | null }) {
  const { t: tr, language } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const { colors } = useTheme();
  const insets = useSafeInsets();
  const levels = tier?.levels ?? [];

  return <Modal transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={tr('close')} />
      <View pointerEvents="box-none" style={styles.wrap}>
        <View style={[styles.sheet, { paddingBottom: Math.max(28, insets.bottom + 16) }]}>
          <View style={styles.handle} />
          <View style={styles.titleRow}>
            <Text accessibilityRole="header" style={styles.title}>{tr('howToRaise')}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={tr('close')} hitSlop={12} onPress={onClose}><Icon name="x" size={26} /></Pressable>
          </View>
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ gap: 10, paddingBottom: 8 }}>
            <Text style={styles.lead}>{getCatalogLead(catalog, tr)}</Text>
            {catalog ? <StatusCatalogList catalog={catalog} current={current} language={language} /> : levels.map(level => {
              const isCurrent = level.level === tier?.level;
              return <View key={level.level} style={[styles.level, isCurrent && styles.levelCurrent]} accessibilityState={{ selected: isCurrent }}>
                <View style={{ gap: 2 }}>
                  <Text style={styles.levelName}>{tr('statusN', { level: level.level })}</Text>
                  <Text style={styles.levelFrom}>{tr('fromAmount', { amount: amountText(level.threshold) })}</Text>
                </View>
                <Text style={[styles.levelPercent, isCurrent && { color: colors.primaryText }]}>{percentText(level.percent)}%</Text>
              </View>;
            })}
          </ScrollView>
        </View>
      </View>
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
});
