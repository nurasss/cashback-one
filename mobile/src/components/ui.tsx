import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';
import { ApiError } from '../api/errors';
import { errorMessages, ru } from '../i18n/ru';
import { theme as t } from '../theme';

export function Button({ label, onPress, disabled, secondary = false, destructive = false }: { label: string; onPress: () => void; disabled?: boolean; secondary?: boolean; destructive?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [styles.button, secondary && styles.secondary, destructive && styles.destructive, (disabled || pressed) && styles.dim]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryText]}>{label}</Text>
  </Pressable>;
}
export function Input({ label, hint, ...props }: TextInputProps & { label: string; hint?: string }) {
  return <View style={styles.gap}><Text style={styles.label}>{label}</Text><TextInput {...props} accessibilityLabel={label} style={styles.input} placeholderTextColor={t.colors.muted} />{hint && <Text style={styles.muted}>{hint}</Text>}</View>;
}
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const message = errorMessages[code] ?? (error instanceof ApiError && error.status >= 500 ? errorMessages.SERVER_UNAVAILABLE : errorMessages.UNKNOWN_ERROR);
  return <View style={styles.error}><Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={styles.errorText}>{message}</Text>{retry && <Button label={ru.retry} onPress={retry} secondary />}</View>;
}
export function Loading({ label = ru.loading }: { label?: string }) {
  return <View style={styles.loading}><ActivityIndicator color={t.colors.primary} /><Text style={styles.muted}>{label}</Text></View>;
}
export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.colors.background }, content: { padding: t.spacing.lg, gap: t.spacing.lg, paddingBottom: t.spacing.xxl },
  gap: { gap: t.spacing.sm }, row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: t.spacing.md },
  title: { fontSize: t.font.title, fontWeight: '700', color: t.colors.text }, hero: { fontSize: t.font.hero, fontWeight: '700', color: t.colors.text },
  body: { fontSize: t.font.body, color: t.colors.text, lineHeight: 24 }, muted: { fontSize: t.font.small, color: t.colors.muted, lineHeight: 20 },
  label: { fontSize: t.font.body, fontWeight: '600', color: t.colors.text }, input: { minHeight: t.touch, padding: t.spacing.md, borderWidth: 1, borderColor: t.colors.border, borderRadius: t.radius.sm, backgroundColor: t.colors.surface, color: t.colors.text, fontSize: t.font.body },
  button: { minHeight: t.touch, padding: t.spacing.md, borderRadius: t.radius.sm, backgroundColor: t.colors.primary, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontSize: t.font.body, fontWeight: '600', color: t.colors.onPrimary, textAlign: 'center' }, secondary: { backgroundColor: t.colors.surface, borderWidth: 1, borderColor: t.colors.border }, secondaryText: { color: t.colors.text },
  destructive: { backgroundColor: t.colors.error }, dim: { opacity: 0.55 }, panel: { padding: t.spacing.lg, borderRadius: t.radius.md, backgroundColor: t.colors.surface, gap: t.spacing.md },
  loading: { padding: t.spacing.xl, alignItems: 'center', gap: t.spacing.md }, error: { padding: t.spacing.md, gap: t.spacing.md, backgroundColor: t.colors.softError, borderRadius: t.radius.sm }, errorText: { color: t.colors.error, fontSize: t.font.body },
});
