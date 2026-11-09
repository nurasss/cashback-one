import { StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { Icon } from './icons';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';

export function NoCardNotice({ style }: { style?: ViewStyle }) {
  const { t } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View testID="no-card-notice" style={[styles.card, style]} accessible accessibilityRole="alert">
      <View style={styles.iconWrap}>
        <Icon name="card" size={20} color={colors.primaryText} />
      </View>
      <Text style={styles.text}>{t('noCardNotice')}</Text>
    </View>
  );
}

const makeStyles = (c: Colors) => StyleSheet.create({
  card: {
    backgroundColor: c.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: c.cardBorder,
    paddingVertical: 14,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: c.softPrimary,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  text: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 14,
    lineHeight: 20,
    color: c.text,
  },
});
