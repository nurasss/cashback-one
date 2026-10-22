import { useKeyboardLift } from '../components/useKeyboardLift';
import { useEffect, useRef, useState } from 'react';
import { Keyboard, Animated, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, type IconName } from '../components/icons';
import { Button, ErrorNotice } from '../components/ui';
import { useI18n, type Language } from '../i18n';
import { fonts, theme as t } from '../theme';

function useSafeInsets() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, bottom: 0, left: 0, right: 0 };
  }
}

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
    {initials ? <Text style={styles.avatarText}>{initials}</Text> : null}
  </View>;
}

export function ProfileRow({ label, value, placeholder, onPress, icon }: { label: string; value?: string; placeholder?: string; onPress: () => void; icon?: IconName }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={`${label}${value ? ': ' + value : ''}`} onPress={onPress}
    hitSlop={4} style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
    {icon && <Icon name={icon} size={20} color={t.colors.primary} />}
    <Text style={styles.rowLabel}>{label}</Text>
    <Text style={[styles.rowValue, !value && { color: t.colors.placeholder }]} numberOfLines={1}>{value || placeholder || ''}</Text>
    <Icon name="chevronRight" size={18} color={t.colors.subtle} />
  </Pressable>;
}

// Bottom sheet editor for one profile field: free text or a fixed list of options.
export function FieldSheet({ title, initial, hint, options, keyboardType = 'default', placeholder, maxLength, validate, onDone, onClose }: {
  title: string; initial: string; options?: { value: string; label: string }[]; keyboardType?: 'default' | 'email-address' | 'number-pad';
  hint?: string; placeholder?: string; maxLength?: number; validate?: (value: string) => string | null; onDone: (value: string) => void | Promise<void>; onClose: () => void;
}) {
  const { t: tr } = useI18n();
  const insets = useSafeInsets();
  const [value, setValue] = useState(initial);
  const selectedY = useRef(0);
  const [error, setError] = useState<string | null>(null);
  // `onDone` may save asynchronously: block repeat submits while it runs and keep the input and the error inside the sheet if it fails.
  const [pending, setPending] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const lift = useKeyboardLift();
  const scroll = useRef<ScrollView>(null);

  const handleRequestClose = () => {
    if (busy.current) return;
    if (lift.keyboardVisible.current) {
      Keyboard.dismiss();
      return;
    }
    onClose();
  };

  const finish = async (next: string) => {
    if (busy.current) return;
    const result = options ? next : next.trim();
    const problem = validate?.(result) ?? null;
    if (problem) { setError(problem); return; }
    busy.current = true; setPending(true); setSaveError(null);
    try { await onDone(result); }
    catch (err) { if (mounted.current) setSaveError(err); }
    finally { busy.current = false; if (mounted.current) setPending(false); }
  };

  return <Modal transparent animationType="slide" onRequestClose={handleRequestClose} statusBarTranslucent>
    <View style={styles.modalOverlay}>
      <Pressable style={styles.backdrop} onPress={() => { if (!busy.current) onClose(); }} accessibilityLabel={tr('cancel')} />
      <Animated.View ref={lift.ref} collapsable={false} onLayout={lift.onLayout} pointerEvents="box-none" style={[styles.sheetWrap, lift.style]}>
        <View style={[styles.sheet, { maxHeight: lift.maxHeight ?? '88%', paddingBottom: Math.max(32, insets.bottom + 20) }]}>
          <View style={styles.sheetHandle} />
          <Text style={styles.sheetTitle}>{title}</Text>
          {hint && <Text style={styles.sheetHint}>{hint}</Text>}
          <ScrollView ref={scroll} style={{ flexShrink: 1 }} onContentSizeChange={() => { if (options) scroll.current?.scrollTo({ y: selectedY.current, animated: false }); }} bounces={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.sheetContent}>
            {options ? options.map(option => <Pressable key={option.value} accessibilityRole="radio" accessibilityLabel={option.label} accessibilityState={{ selected: value === option.value, disabled: pending }} onLayout={event => { if (value === option.value) { selectedY.current = event.nativeEvent.layout.y; scroll.current?.scrollTo({ y: selectedY.current, animated: false }); } }}
              onPress={() => { void finish(option.value); }} style={styles.option}>
              <Text style={styles.optionText}>{option.label}</Text>
              {value === option.value && <Icon name="check" size={22} color={t.colors.primary} />}
            </Pressable>) : <View style={styles.inputWrap}>
              <TextInput value={value} onChangeText={next => { setValue(next); setError(null); setSaveError(null); }} editable={!pending} accessibilityLabel={title} placeholder={placeholder}
                placeholderTextColor={t.colors.placeholder} keyboardType={keyboardType} maxLength={maxLength} autoFocus autoCapitalize={keyboardType === 'email-address' ? 'none' : 'sentences'}
                style={[styles.input, error ? { borderWidth: 1, borderColor: t.colors.error } : null]} onSubmitEditing={() => { void finish(value); }} />
              {error && <Text style={styles.error}>{error}</Text>}

            </View>}
          </ScrollView>
          {saveError !== null && <ErrorNotice error={saveError} />}
          {!options && <Button label={pending ? tr('saving') : tr('done')} disabled={pending} onPress={() => { void finish(value); }} />}
        </View>
      </Animated.View>
    </View>
  </Modal>;
}

const styles = StyleSheet.create({
  switch: { flexDirection: 'row', backgroundColor: t.colors.input, borderRadius: 999, padding: 3 },
  switchItem: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  switchSelected: { backgroundColor: t.colors.primary },
  switchText: { fontFamily: fonts.semibold, fontSize: 13, color: t.colors.muted },
  switchTextSelected: { color: t.colors.onPrimary },
  avatar: { width: 96, height: 96, borderRadius: 48, marginVertical: 8, backgroundColor: t.colors.input, alignSelf: 'center', alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: fonts.bold, fontSize: 32, color: t.colors.muted },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44 },
  rowLabel: { fontFamily: fonts.semibold, fontSize: 14, color: t.colors.text },
  rowValue: { flex: 1, textAlign: 'right', fontFamily: fonts.regular, fontSize: 14, color: t.colors.muted },
  modalOverlay: { flex: 1, justifyContent: 'flex-end' },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheetWrap: { flex: 1, width: '100%', justifyContent: 'flex-end' },
  sheet: { flexShrink: 1, maxHeight: '88%', backgroundColor: t.colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 24, paddingTop: 16, gap: 16 },
  sheetContent: { gap: 12, paddingBottom: 4 },
  inputWrap: { gap: 16 },
  sheetHandle: { alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: t.colors.border },
  sheetTitle: { fontFamily: fonts.bold, fontSize: 18, color: t.colors.text },
  sheetHint: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 20, color: t.colors.muted },
  input: { minHeight: 48, paddingHorizontal: 16, borderRadius: 12, backgroundColor: t.colors.input, color: t.colors.text, fontFamily: fonts.medium, fontSize: 16 },
  error: { fontFamily: fonts.medium, fontSize: 13, color: t.colors.error },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 50, borderBottomWidth: 1, borderBottomColor: t.colors.border },
  optionText: { fontFamily: fonts.medium, fontSize: 16, color: t.colors.text },
});
