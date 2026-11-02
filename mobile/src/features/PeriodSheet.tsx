import { useState } from 'react';
import {
  Animated,
  Keyboard,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useKeyboardLift } from '../components/useKeyboardLift';
import { Button } from '../components/ui';
import { useI18n } from '../i18n';
import { fonts, theme } from '../theme';
import { birthDateInputText, birthDateToApi, birthDateToUi } from '../utils/format';

export interface PeriodSheetProps {
  initial?: { from: string; to: string } | null;
  onApply: (period: { from: string; to: string }) => void;
  onClose: () => void;
}

export function PeriodSheet({ initial, onApply, onClose }: PeriodSheetProps) {
  const { t } = useI18n();
  const insets = useSafeAreaInsets();
  const lift = useKeyboardLift();

  const [fromText, setFromText] = useState(
    initial?.from ? birthDateToUi(initial.from) : ''
  );
  const [toText, setToText] = useState(
    initial?.to ? birthDateToUi(initial.to) : ''
  );
  const [error, setError] = useState<string | null>(null);

  const handleRequestClose = () => {
    if (lift.keyboardVisible.current) {
      Keyboard.dismiss();
      return;
    }
    onClose();
  };

  const handleApply = () => {
    const fromApi = birthDateToApi(fromText);
    const toApi = birthDateToApi(toText);

    if (!fromText.trim() || !toText.trim() || !fromApi || !toApi) {
      setError(t('invalidDate'));
      return;
    }

    const now = new Date();
    // End of today in local time
    const endOfToday = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      23,
      59,
      59,
      999
    );

    const [fy = 0, fm = 1, fd = 1] = fromApi.split('-').map(Number);
    const fromDate = new Date(fy, fm - 1, fd, 0, 0, 0, 0);

    const [ty = 0, tm = 1, td = 1] = toApi.split('-').map(Number);
    const toDate = new Date(ty, tm - 1, td, 0, 0, 0, 0);

    if (fromDate.getTime() > endOfToday.getTime() || toDate.getTime() > endOfToday.getTime()) {
      setError(t('invalidDate'));
      return;
    }

    if (fromDate.getTime() > toDate.getTime()) {
      setError(t('invalidPeriod'));
      return;
    }

    setError(null);
    onApply({ from: fromApi, to: toApi });
    onClose();
  };

  return (
    <Modal
      transparent
      animationType="slide"
      onRequestClose={handleRequestClose}
      statusBarTranslucent
    >
      <View style={styles.modalOverlay}>
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel={t('cancel')}
        />
        <Animated.View
          ref={lift.ref}
          collapsable={false}
          onLayout={lift.onLayout}
          pointerEvents="box-none"
          style={[styles.sheetWrap, lift.style]}
        >
          <View
            style={[
              styles.sheet,
              {
                maxHeight: lift.maxHeight ?? '88%',
                paddingBottom: Math.max(32, insets.bottom + 20),
              },
            ]}
          >
            <View style={styles.sheetHandle} />
            <Text style={styles.sheetTitle}>{t('periodCustom')}</Text>
            <ScrollView
              bounces={false}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={styles.sheetContent}
            >
              <View style={styles.inputGroup}>
                <Text style={styles.fieldLabel}>{t('periodFrom')}</Text>
                <TextInput
                  value={fromText}
                  onChangeText={next => {
                    setFromText(birthDateInputText(next));
                    setError(null);
                  }}
                  accessibilityLabel={t('periodFrom')}
                  placeholder={t('birthDatePh')}
                  placeholderTextColor={theme.colors.placeholder}
                  keyboardType="number-pad"
                  maxLength={10}
                  style={[
                    styles.input,
                    error ? { borderWidth: 1, borderColor: theme.colors.error } : null,
                  ]}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.fieldLabel}>{t('periodTo')}</Text>
                <TextInput
                  value={toText}
                  onChangeText={next => {
                    setToText(birthDateInputText(next));
                    setError(null);
                  }}
                  accessibilityLabel={t('periodTo')}
                  placeholder={t('birthDatePh')}
                  placeholderTextColor={theme.colors.placeholder}
                  keyboardType="number-pad"
                  maxLength={10}
                  style={[
                    styles.input,
                    error ? { borderWidth: 1, borderColor: theme.colors.error } : null,
                  ]}
                />
              </View>

              {error && <Text style={styles.error}>{error}</Text>}
            </ScrollView>
            <Button label={t('periodApply')} onPress={handleApply} />
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: { flex: 1, justifyContent: 'flex-end' },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheetWrap: { flex: 1, width: '100%', justifyContent: 'flex-end' },
  sheet: {
    flexShrink: 1,
    maxHeight: '88%',
    backgroundColor: theme.colors.surface,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: 24,
    paddingTop: 16,
    gap: 16,
  },
  sheetHandle: {
    alignSelf: 'center',
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: theme.colors.border,
  },
  sheetTitle: { fontFamily: fonts.bold, fontSize: 18, color: theme.colors.text },
  sheetContent: { gap: 16, paddingBottom: 4 },
  inputGroup: { gap: 6 },
  fieldLabel: {
    fontFamily: fonts.semibold,
    fontSize: 12,
    color: theme.colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  input: {
    minHeight: 48,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: theme.colors.input,
    color: theme.colors.text,
    fontFamily: fonts.medium,
    fontSize: 16,
  },
  error: { fontFamily: fonts.medium, fontSize: 13, color: theme.colors.error },
});
