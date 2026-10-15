import { router } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps, type ViewStyle } from 'react-native';
import { ApiError } from '../api/errors';
import { errorMessages } from '../i18n/ru';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import { Icon, type IconName } from './icons';

export function Button({ label, onPress, disabled, secondary = false, destructive = false, style }: {
  label: string; onPress: () => void; disabled?: boolean; secondary?: boolean; destructive?: boolean; style?: ViewStyle;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [styles.button, secondary && styles.secondary, destructive && styles.destructive, pressed && !secondary && styles.pressed, (disabled || pressed) && styles.dim, style]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryText]}>{label}</Text>
  </Pressable>;
}

export function Input({ label, hint, error, ...props }: TextInputProps & { label: string; hint?: string; error?: string }) {
  return <View style={styles.gap}>
    <Text style={styles.fieldLabel}>{label}</Text>
    <TextInput {...props} accessibilityLabel={label} style={[styles.input, error ? styles.inputError : null]} placeholderTextColor={t.colors.subtle} />
    {error ? <Text style={styles.errorSmall}>{error}</Text> : hint ? <Text style={styles.muted}>{hint}</Text> : null}
  </View>;
}

export function ScreenHeader({ title, back = false, onBack, right }: { title: string; back?: boolean; onBack?: () => void; right?: React.ReactNode }) {
  const { t: tr } = useI18n();
  return <View style={styles.header}>
    {back && <Pressable accessibilityRole="button" accessibilityLabel={tr('back')} hitSlop={12} style={styles.backButton}
      onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))}>
      <Icon name="arrowLeft" size={30} strokeWidth={1.8} />
    </Pressable>}
    <Text accessibilityRole="header" style={[styles.headerTitle, { flex: 1 }]} numberOfLines={1}>{title}</Text>
    {right}
  </View>;
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t: tr } = useI18n();
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const message = errorMessages[code] ?? (error instanceof ApiError && error.status >= 500 ? errorMessages.SERVER_UNAVAILABLE : errorMessages.UNKNOWN_ERROR);
  return <View style={styles.error}>
    <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={styles.errorText}>{message}</Text>
    {retry && <Button label={tr('retry')} onPress={retry} secondary />}
  </View>;
}

export function Loading({ label }: { label?: string }) {
  const { t: tr } = useI18n();
  return <View style={styles.loading}><ActivityIndicator color={t.colors.primary} /><Text style={styles.muted}>{label ?? tr('loading')}</Text></View>;
}

export function EmptyState({ icon, title, body, children }: { icon: IconName; title: string; body?: string; children?: React.ReactNode }) {
  return <View style={styles.empty}>
    <View style={styles.emptyIcon}><Icon name={icon} size={30} color={t.colors.primary} /></View>
    <Text style={[styles.title, { textAlign: 'center' }]}>{title}</Text>
    {body && <Text style={[styles.body, { textAlign: 'center', color: t.colors.muted }]}>{body}</Text>}
    {children}
  </View>;
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ selected }} onPress={onPress} style={[styles.chip, selected && styles.chipSelected]}>
    <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
  </Pressable>;
}

export function NewDot({ style }: { style?: ViewStyle }) {
  return <View accessibilityElementsHidden importantForAccessibility="no" style={[styles.dot, style]} />;
}

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.colors.background },
  content: { padding: t.spacing.lg, gap: t.spacing.lg, paddingBottom: 140 },
  gap: { gap: t.spacing.sm }, row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: t.spacing.md },
  header: { flexDirection: 'row', alignItems: 'center', gap: t.spacing.md, paddingHorizontal: t.spacing.lg, paddingTop: t.spacing.md, paddingBottom: t.spacing.md, minHeight: 64 },
  backButton: { width: 40, height: 40, justifyContent: 'center' },
  headerTitle: { fontFamily: fonts.bold, fontSize: 26, color: t.colors.text },
  title: { fontFamily: fonts.bold, fontSize: 22, color: t.colors.text }, hero: { fontFamily: fonts.bold, fontSize: t.font.hero, color: t.colors.text },
  body: { fontFamily: fonts.regular, fontSize: t.font.body, color: t.colors.text, lineHeight: 24 },
  muted: { fontFamily: fonts.regular, fontSize: t.font.small, color: t.colors.muted, lineHeight: 20 },
  label: { fontFamily: fonts.semibold, fontSize: t.font.body, color: t.colors.text },
  fieldLabel: { fontFamily: fonts.medium, fontSize: 15, color: t.colors.text },
  input: { minHeight: 54, paddingHorizontal: 18, borderRadius: 10, backgroundColor: t.colors.input, color: t.colors.text, fontFamily: fonts.medium, fontSize: 18 },
  inputError: { borderWidth: 1, borderColor: t.colors.error },
  errorSmall: { fontFamily: fonts.medium, fontSize: t.font.small, color: t.colors.error },
  button: { minHeight: 56, paddingHorizontal: t.spacing.lg, borderRadius: 14, backgroundColor: t.colors.primary, alignItems: 'center', justifyContent: 'center' },
  pressed: { backgroundColor: t.colors.primaryPressed },
  buttonText: { fontFamily: fonts.medium, fontSize: 20, color: t.colors.onPrimary, textAlign: 'center' },
  secondary: { backgroundColor: t.colors.tint }, secondaryText: { color: t.colors.primary },
  destructive: { backgroundColor: t.colors.error }, dim: { opacity: 0.6 },
  panel: { padding: t.spacing.lg, borderRadius: t.radius.md, backgroundColor: t.colors.surface, gap: t.spacing.md },
  sheet: { backgroundColor: t.colors.surface, borderRadius: 32, paddingVertical: t.spacing.lg },
  loading: { padding: t.spacing.xl, alignItems: 'center', gap: t.spacing.md },
  error: { padding: t.spacing.md, gap: t.spacing.md, backgroundColor: t.colors.softError, borderRadius: t.radius.sm },
  errorText: { fontFamily: fonts.medium, color: t.colors.error, fontSize: t.font.body },
  empty: { alignItems: 'center', gap: t.spacing.md, padding: t.spacing.xl },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: t.colors.softPrimary, alignItems: 'center', justifyContent: 'center' },
  chip: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: t.radius.pill, backgroundColor: t.colors.surface },
  chipSelected: { backgroundColor: t.colors.primary },
  chipText: { fontFamily: fonts.medium, fontSize: 15, color: t.colors.text }, chipTextSelected: { color: t.colors.onPrimary },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: t.colors.primary, borderWidth: 2, borderColor: t.colors.surface },
});
