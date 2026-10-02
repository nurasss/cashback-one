import { useState } from 'react';
import { View } from 'react-native';
import { Button, Input, styles } from '../components/ui';
import { ru } from '../i18n/ru';
import { isBarcode } from '../utils/format';
export function BindForm({ submit, pending }: { submit: (barcode: string) => void; pending: boolean }) {
  const [barcode, setBarcode] = useState('');
  const [invalid, setInvalid] = useState(false);
  return <View style={styles.gap}><Input label={ru.barcode} hint={invalid ? ru.invalidBarcode : ru.barcodeHint} value={barcode} onChangeText={value => { setBarcode(value); setInvalid(false); }} editable={!pending} keyboardType="number-pad" maxLength={32} autoCorrect={false} />
    <Button label={ru.bind} disabled={pending} onPress={() => { if (!isBarcode(barcode)) { setInvalid(true); return; } submit(barcode); }} />
  </View>;
}
