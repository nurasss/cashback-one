import { StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { Icon } from './icons';
import { useI18n } from '../i18n';
import { fonts, theme } from '../theme';

export function NoCardNotice({ style }: { style?: ViewStyle }) {
  const { t } = useI18n();
  return (
    <View testID="no-card-notice" style={[styles.card, style]} accessible accessibilityRole="alert">
      <View style={styles.iconWrap}>
        <Icon name="card" size={20} color={theme.colors.primary} />
      </View>
      <Text style={styles.text}>{t('noCardNotice')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(17, 17, 17, 0.08)',
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
    backgroundColor: theme.colors.softPrimary,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  text: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 14,
    lineHeight: 20,
    color: theme.colors.text,
  },
});
