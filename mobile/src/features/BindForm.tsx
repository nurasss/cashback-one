import { useState } from 'react';
import { View } from 'react-native';
import { Button, Input } from '../components/ui';
import { useI18n } from '../i18n';
import { CardScanner } from './CardScanner';
import { isBarcode } from '../utils/format';

export function BindForm({ submit, pending }: { submit: (barcode: string) => void; pending: boolean }) {
  const { t } = useI18n();
  const [barcode, setBarcode] = useState('');
  const [invalid, setInvalid] = useState(false);
  const [scanning, setScanning] = useState(false);
  return <View style={{ gap: 16 }}>
    <Input label={t('barcode')} hint={t('barcodeHint')} error={invalid ? t('invalidBarcode') : undefined} value={barcode}
      onChangeText={value => { setBarcode(value); setInvalid(false); }} editable={!pending} keyboardType="number-pad" maxLength={32} autoCorrect={false} />
    <Button label={t('scanWithCamera')} secondary disabled={pending} onPress={() => setScanning(true)} />
    <Button label={t('bind')} disabled={pending} onPress={() => { if (!isBarcode(barcode)) { setInvalid(true); return; } submit(barcode); }} />
    {scanning && <CardScanner
      onCode={value => { setScanning(false); setBarcode(value); setInvalid(false); }}
      onClose={() => setScanning(false)} />}
  </View>;
}
