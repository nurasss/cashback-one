import { router } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps, type ViewStyle } from 'react-native';
import { ApiError } from '../api/errors';
import { errorMessages } from '../i18n/ru';
import { useI18n } from '../i18n';
import { fonts, theme as t, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import { Icon, type IconName } from './icons';
import { PressScale } from './motion';

export function Button({ label, onPress, disabled, secondary = false, destructive = false, style }: {
  label: string; onPress: () => void; disabled?: boolean; secondary?: boolean; destructive?: boolean; style?: ViewStyle;
}) {
  const styles = useUiStyles();
  const isDisabled = !!disabled;
  return <PressScale accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} scale={0.97}
    style={[styles.button, secondary && styles.secondary, destructive && styles.destructive,
      isDisabled && (secondary ? styles.secondaryDisabled : styles.disabled), style]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryText, destructive && !secondary && styles.destructiveText,
      isDisabled && (secondary ? styles.secondaryDisabledText : styles.disabledText)]}>{label}</Text>
  </PressScale>;
}

export function Input({ label, hint, error, ...props }: TextInputProps & { label: string; hint?: string; error?: string }) {
  const styles = useUiStyles();
  const { colors, isDark } = useTheme();
  return <View style={styles.gap}>
    <Text style={styles.fieldLabel}>{label}</Text>
    <TextInput {...props} accessibilityLabel={label} style={[styles.input, error ? styles.inputError : null]} placeholderTextColor={colors.placeholder} keyboardAppearance={isDark ? 'dark' : 'light'} />
    {error ? <Text style={styles.errorSmall}>{error}</Text> : hint ? <Text style={styles.muted}>{hint}</Text> : null}
  </View>;
}

export function ScreenHeader({ title, back = false, onBack, right }: { title: string; back?: boolean; onBack?: () => void; right?: React.ReactNode }) {
  const { t: tr } = useI18n();
  const styles = useUiStyles();
  return <View style={styles.header}>
    {back && <Pressable accessibilityRole="button" accessibilityLabel={tr('back')} hitSlop={12} style={styles.backButton}
      onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))}>
      <Icon name="arrowLeft" size={24} strokeWidth={2} />
    </Pressable>}
    <Text accessibilityRole="header" style={[styles.headerTitle, { flex: 1 }, right ? { fontSize: 18 } : null]} numberOfLines={1}>{title}</Text>
    {right}
  </View>;
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t: tr } = useI18n();
  const styles = useUiStyles();
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const message = errorMessages[code] ?? (error instanceof ApiError && error.status >= 500 ? errorMessages.SERVER_UNAVAILABLE : errorMessages.UNKNOWN_ERROR);
  return <View style={styles.error}>
    <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={styles.errorText}>{message}</Text>
    {retry && <Button label={tr('retry')} onPress={retry} secondary />}
  </View>;
}

export function Loading({ label }: { label?: string }) {
  const { t: tr } = useI18n();
  const styles = useUiStyles();
  const { colors } = useTheme();
  return <View style={styles.loading}><ActivityIndicator color={colors.primaryText} /><Text style={styles.muted}>{label ?? tr('loading')}</Text></View>;
}

export function EmptyState({ icon, title, body, children }: { icon: IconName; title: string; body?: string; children?: React.ReactNode }) {
  const styles = useUiStyles();
  const { colors } = useTheme();
  return <View style={styles.empty}>
    <View style={styles.emptyIcon}><Icon name={icon} size={30} color={colors.primaryText} /></View>
    <Text style={[styles.title, { textAlign: 'center' }]}>{title}</Text>
    {body && <Text style={[styles.body, { textAlign: 'center', color: colors.muted }]}>{body}</Text>}
    {children}
  </View>;
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const styles = useUiStyles();
  return <Pressable accessibilityRole="button" accessibilityState={{ selected }} onPress={onPress} style={[styles.chip, selected && styles.chipSelected]}>
    <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
  </Pressable>;
}

export function NewDot({ style }: { style?: ViewStyle }) {
  const styles = useUiStyles();
  return <View accessibilityElementsHidden importantForAccessibility="no" style={[styles.dot, style]} />;
}

export { NoCardNotice } from './NoCardNotice';

export function useUiStyles() {
  return useThemedStyles(makeUiStyles);
}

export const makeUiStyles = (c: Colors) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.background },
  content: { padding: 20, gap: 20, paddingBottom: 140 },
  gap: { gap: t.spacing.sm }, row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: t.spacing.md },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12, minHeight: 56 },
  backButton: { width: 28, height: 40, justifyContent: 'center' },
  headerTitle: { fontFamily: fonts.bold, fontSize: 20, color: c.text },
  title: { fontFamily: fonts.bold, fontSize: 18, color: c.text }, hero: { fontFamily: fonts.bold, fontSize: t.font.hero, color: c.text },
  body: { fontFamily: fonts.regular, fontSize: 15, color: c.text, lineHeight: 22 },
  muted: { fontFamily: fonts.regular, fontSize: t.font.small, color: c.muted, lineHeight: 20 },
  label: { fontFamily: fonts.semibold, fontSize: t.font.body, color: c.text },
  fieldLabel: { fontFamily: fonts.semibold, fontSize: 11, color: c.muted, textTransform: 'uppercase', letterSpacing: 0.8 },
  input: { minHeight: 48, paddingHorizontal: 16, borderRadius: 12, backgroundColor: c.input, color: c.text, fontFamily: fonts.medium, fontSize: 16 },
  inputError: { borderWidth: 1, borderColor: c.error },
  errorSmall: { fontFamily: fonts.medium, fontSize: t.font.small, color: c.error },
  button: { minHeight: 46, paddingHorizontal: t.spacing.lg, borderRadius: 12, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center' },
  pressed: { backgroundColor: c.primaryPressed },
  buttonText: { fontFamily: fonts.semibold, fontSize: 15, color: c.onPrimary, textAlign: 'center' },
  secondary: { backgroundColor: c.tint }, secondaryText: { color: c.primaryText },
  disabled: { backgroundColor: c.disabledBackground, borderWidth: 1, borderColor: c.disabledBorder },
  disabledText: { color: c.disabledText },
  secondaryDisabled: { backgroundColor: c.secondaryDisabledBackground, borderWidth: 1, borderColor: c.secondaryDisabledBorder },
  secondaryDisabledText: { color: c.secondaryDisabledText },
  destructive: { backgroundColor: c.destructive }, destructiveText: { color: c.onDestructive }, dim: { opacity: 0.6 },
  panel: { padding: 20, borderRadius: 22, backgroundColor: c.surface, gap: t.spacing.md, borderWidth: 1, borderColor: c.cardBorder },
  sheet: { backgroundColor: c.surface, borderRadius: 32, paddingVertical: t.spacing.lg },
  loading: { padding: t.spacing.xl, alignItems: 'center', gap: t.spacing.md },
  error: { padding: t.spacing.md, gap: t.spacing.md, backgroundColor: c.softError, borderRadius: t.radius.sm },
  errorText: { fontFamily: fonts.medium, color: c.error, fontSize: t.font.body },
  empty: { alignItems: 'center', gap: t.spacing.md, padding: t.spacing.xl },
  emptyIcon: { width: 56, height: 56, borderRadius: 28, backgroundColor: c.softPrimary, alignItems: 'center', justifyContent: 'center' },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: t.radius.pill, backgroundColor: c.surface },
  chipSelected: { backgroundColor: c.primary },
  chipText: { fontFamily: fonts.medium, fontSize: 13, color: c.text }, chipTextSelected: { color: c.onPrimary },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: c.primary, borderWidth: 2, borderColor: c.surface },
});
