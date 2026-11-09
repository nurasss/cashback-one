import { Image, StyleSheet, Text, View } from 'react-native';
import type { ClientStatus, ClientStatuses } from '../../clients/keremet/statuses';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useThemedStyles } from '../theme/ThemeProvider';
import { amountText } from '../utils/format';
import { statusCondition, type CurrentStatus } from './statuses';

// The owner's character artwork is shown as delivered (light rounded tile, transparent corners) in both themes: never inverted or tinted.
export function StatusArt({ status, size }: { status: ClientStatus; size: number }) {
  return <Image testID={`status-art-${status.key}`} source={status.image} resizeMode="contain" accessibilityIgnoresInvertColors
    accessible accessibilityRole="image" accessibilityLabel={status.name} style={{ width: size, height: size }} />;
}

export function useConditionText() {
  const { t } = useI18n();
  return (levels: readonly ClientStatus[], level: ClientStatus): string => {
    const condition = statusCondition(levels, level);
    return t(condition.key, { amount: amountText(String(condition.to ?? condition.from)), from: amountText(String(condition.from)), to: amountText(String(condition.to ?? 0)) });
  };
}

// The three statuses with picture, name, condition and percent. Informational: it needs no card and shows no personal data.
export function StatusCatalogList({ catalog, current }: { catalog: ClientStatuses; current?: CurrentStatus | null }) {
  const { t } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const condition = useConditionText();
  return <View style={styles.list} testID="status-catalog">
    {catalog.levels.map(level => {
      const isCurrent = current?.known === true && current.status.level === level.level;
      return <View key={level.level} testID={`status-row-${level.key}`} style={[styles.row, isCurrent && styles.rowCurrent]} accessibilityState={{ selected: isCurrent }}>
        <StatusArt status={level} size={64} />
        <View style={styles.texts}>
          <Text style={styles.name}>{level.name}</Text>
          <Text style={styles.condition}>{condition(catalog.levels, level)}</Text>
        </View>
        <Text style={[styles.percent, isCurrent && styles.percentCurrent]}>{level.percent}%</Text>
      </View>;
    })}
    <Text style={styles.note}>{t('statusPeriodNote')}</Text>
  </View>;
}

const makeStyles = (c: Colors) => StyleSheet.create({
  list: { gap: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.input, borderRadius: 16, padding: 10, borderWidth: 1.5, borderColor: 'transparent' },
  rowCurrent: { backgroundColor: c.softPrimary, borderColor: c.primary },
  texts: { flex: 1, gap: 2 },
  name: { fontFamily: fonts.bold, fontSize: 16, color: c.text, lineHeight: 21 },
  condition: { fontFamily: fonts.regular, fontSize: 13, color: c.muted, lineHeight: 18 },
  percent: { fontFamily: fonts.extrabold, fontSize: 22, color: c.text },
  percentCurrent: { color: c.primaryText },
  note: { fontFamily: fonts.medium, fontSize: 12, color: c.muted, textAlign: 'center', marginTop: 2 },
});
