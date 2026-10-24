import { useEffect, useRef, useState } from 'react';
import { AppState, Linking, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { CameraView, PermissionStatus, useCameraPermissions, type BarcodeType } from 'expo-camera';
import { Icon } from '../components/icons';
import { Button } from '../components/ui';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';

// Card numbers are the only accepted scan result: exactly 4–13 digits after trim, kept as a string.
const SCANNABLE_BARCODE_TYPES: BarcodeType[] = ['qr', 'code128', 'code39', 'ean13', 'ean8', 'upc_a', 'upc_e', 'itf14', 'codabar'];
const isScannedCardNumber = (data: string): boolean => /^[0-9]{4,13}$/.test(data.trim());

export function CardScanner({ onCode, onClose }: { onCode: (barcode: string) => void; onClose: () => void }) {
  const { t: tr } = useI18n();
  const [permission, requestPermission] = useCameraPermissions();
  const [notCardNumber, setNotCardNumber] = useState(false);
  const handled = useRef(false);
  const granted = permission?.granted === true;
  const grantedRef = useRef(granted);
  grantedRef.current = granted;

  // The permission is requested when the scanner opens (button press), never at app start.
  useEffect(() => {
    if (!permission?.granted) void requestPermission();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The camera must be off while the app is backgrounded; closing unmounts CameraView.
  // Android sends the app to the background while the system permission dialog is shown,
  // so only a running camera (permission already granted) closes the scanner.
  useEffect(() => {
    const subscription = AppState.addEventListener('change', state => {
      if (state === 'background' && grantedRef.current) onClose();
    });
    return () => subscription.remove();
  }, [onClose]);

  const handleScanned = (result: { data: string }) => {
    // Only the first valid reading is handled; later events are ignored until the scanner closes.
    if (handled.current) return;
    const value = result.data.trim();
    if (isScannedCardNumber(value)) {
      handled.current = true;
      onCode(value);
      return;
    }
    setNotCardNumber(true);
  };

  // "Not granted yet" (undetermined, dialog still open) is not a refusal.
  const denied = permission?.status === PermissionStatus.DENIED;

  return <Modal visible transparent={false} animationType="slide" onRequestClose={onClose} statusBarTranslucent>
    <View style={styles.full}>
      {granted
        ? <CameraView style={StyleSheet.absoluteFill} onBarcodeScanned={handleScanned}
            barcodeScannerSettings={{ barcodeTypes: SCANNABLE_BARCODE_TYPES }} />
        : <View style={[StyleSheet.absoluteFill, styles.noCamera]} testID="camera-unavailable" />}
      <Pressable accessibilityRole="button" accessibilityLabel={tr('close')} hitSlop={12} onPress={onClose} style={styles.close}>
        <Icon name="x" size={22} color={t.colors.onPrimary} />
      </Pressable>
      {denied
        ? <View style={styles.deniedCard}>
            <Text style={styles.deniedTitle}>{tr('cameraPermissionTitle')}</Text>
            <Text style={styles.deniedText}>{tr('cameraPermissionDenied')}</Text>
            <Button label={tr('openSettings')} onPress={() => void Linking.openSettings()} />
          </View>
        : <>
            <View pointerEvents="none" style={styles.frameBorder} />
            <Text style={styles.hint}>{tr('scanCardHint')}</Text>
            {notCardNumber && <Text accessibilityRole="alert" style={styles.reject}>{tr('notCardNumber')}</Text>}
          </>}
    </View>
  </Modal>;
}

const styles = StyleSheet.create({
  full: { flex: 1, backgroundColor: '#111118', alignItems: 'center', justifyContent: 'center' },
  noCamera: { backgroundColor: '#111118' },
  close: {
    position: 'absolute', top: 18, right: 18, width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(17,17,24,0.6)', alignItems: 'center', justifyContent: 'center',
  },
  frameBorder: {
    width: 264, height: 168, borderWidth: 2, borderRadius: 20, borderColor: t.colors.onPrimary,
    backgroundColor: 'transparent',
  },
  hint: {
    position: 'absolute', bottom: 132, left: 32, right: 32, textAlign: 'center', color: t.colors.onPrimary,
    fontFamily: fonts.medium, fontSize: 14, lineHeight: 20,
  },
  reject: {
    position: 'absolute', bottom: 96, left: 32, right: 32, textAlign: 'center', color: t.colors.onPrimary,
    fontFamily: fonts.bold, fontSize: 13,
  },
  deniedCard: {
    marginHorizontal: 24, padding: 20, gap: 12, borderRadius: 24, backgroundColor: t.colors.surface,
    alignItems: 'center',
  },
  deniedTitle: { color: t.colors.text, fontFamily: fonts.bold, fontSize: 17, textAlign: 'center' },
  deniedText: { color: t.colors.muted, fontFamily: fonts.regular, fontSize: 14, lineHeight: 20, textAlign: 'center' },
});
