import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Icon, type IconName } from '../components/icons';
import { Button } from '../components/ui';
import { useI18n, type Language } from '../i18n';
import { fonts, theme as t } from '../theme';

export function LanguageSwitch({ value, onChange, disabled }: { value: Language; onChange: (language: Language) => void; disabled?: boolean }) {
  const { t: tr } = useI18n();
  return <View style={styles.switch} accessibilityRole="radiogroup">
    {(['kz', 'ru'] as const).map(language => {
      const selected = value === language;
      return <Pressable key={language} accessibilityRole="radio" accessibilityState={{ selected, disabled }} disabled={disabled}
        onPress={() => onChange(language)} style={[styles.switchItem, selected && styles.switchSelected]}>
        <Text style={[styles.switchText, selected && styles.switchTextSelected]}>{language === 'kz' ? tr('langKz') : tr('langRu')}</Text>
      </Pressable>;
    })}
  </View>;
}

export function Avatar({ initials }: { initials: string }) {
  return <View style={styles.avatar} accessibilityElementsHidden>
    {initials ? <Text style={styles.avatarText}>{initials}</Text> : <Icon name="user" size={64} color={t.colors.subtle} strokeWidth={1.4} />}
  </View>;
}

export function ProfileRow({ label, value, placeholder, onPress, icon }: { label: string; value?: string; placeholder?: string; onPress: () => void; icon?: IconName }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`${label}${value ? ': ' + value : ''}`} onPress={onPress}
    style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
    {icon && <Icon name={icon} size={22} color={t.colors.primary} />}
    <Text style={styles.rowLabel}>{label}</Text>
    <Text style={[styles.rowValue, !value && { color: t.colors.subtle }]} numberOfLines={1}>{value || placeholder || ''}</Text>
    <Icon name="chevronRight" size={22} color={t.colors.subtle} />
  </Pressable>;
}

// Bottom sheet editor for one profile field: free text or a fixed list of options.
export function FieldSheet({ title, initial, options, keyboardType = 'default', placeholder, maxLength, validate, onDone, onClose }: {
  title: string; initial: string; options?: { value: string; label: string }[]; keyboardType?: 'default' | 'email-address' | 'number-pad';
  placeholder?: string; maxLength?: number; validate?: (value: string) => string | null; onDone: (value: string) => void; onClose: () => void;
}) {
  const { t: tr } = useI18n();
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const finish = (next: string) => {
    const problem = validate?.(next.trim()) ?? null;
    if (problem) { setError(problem); return; }
    onDone(next.trim());
  };
  return <Modal transparent animationType="slide" onRequestClose={onClose}>
    <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={tr('cancel')} />
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.sheetWrap}>
      <View style={styles.sheet}>
        <View style={styles.sheetHandle} />
        <Text style={styles.sheetTitle}>{title}</Text>
        {options ? options.map(option => <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ selected: value === option.value }}
          onPress={() => finish(option.value)} style={styles.option}>
          <Text style={styles.optionText}>{option.label}</Text>
          {value === option.value && <Icon name="check" size={22} color={t.colors.primary} />}
        </Pressable>) : <>
          <TextInput value={value} onChangeText={next => { setValue(next); setError(null); }} accessibilityLabel={title} placeholder={placeholder}
            placeholderTextColor={t.colors.subtle} keyboardType={keyboardType} maxLength={maxLength} autoFocus autoCapitalize={keyboardType === 'email-address' ? 'none' : 'sentences'}
            style={[styles.input, error ? { borderWidth: 1, borderColor: t.colors.error } : null]} onSubmitEditing={() => finish(value)} />
          {error && <Text style={styles.error}>{error}</Text>}
          <Button label={tr('done')} onPress={() => finish(value)} />
        </>}
      </View>
    </KeyboardAvoidingView>
  </Modal>;
}

const styles = StyleSheet.create({
  switch: { flexDirection: 'row', backgroundColor: t.colors.input, borderRadius: 14, padding: 3 },
  switchItem: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 12 },
  switchSelected: { backgroundColor: t.colors.primary },
  switchText: { fontFamily: fonts.medium, fontSize: 15, color: t.colors.subtle },
  switchTextSelected: { color: t.colors.onPrimary },
  avatar: { width: 170, height: 170, borderRadius: 85, backgroundColor: t.colors.input, alignSelf: 'center', alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: fonts.bold, fontSize: 52, color: t.colors.muted },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 58 },
  rowLabel: { fontFamily: fonts.semibold, fontSize: 19, color: t.colors.text },
  rowValue: { flex: 1, textAlign: 'right', fontFamily: fonts.regular, fontSize: 17, color: t.colors.muted },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheetWrap: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  sheet: { backgroundColor: t.colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 24, paddingBottom: 40, gap: 16 },
  sheetHandle: { alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: t.colors.border },
  sheetTitle: { fontFamily: fonts.bold, fontSize: 22, color: t.colors.text },
  input: { minHeight: 54, paddingHorizontal: 18, borderRadius: 10, backgroundColor: t.colors.input, color: t.colors.text, fontFamily: fonts.medium, fontSize: 18 },
  error: { fontFamily: fonts.medium, fontSize: 13, color: t.colors.error },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 56, borderBottomWidth: 1, borderBottomColor: t.colors.border },
  optionText: { fontFamily: fonts.medium, fontSize: 18, color: t.colors.text },
});
