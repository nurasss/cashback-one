import { Text, View, useWindowDimensions } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { styles } from '../components/ui';
import { ru } from '../i18n/ru';
import { theme as t } from '../theme';
import { isBarcode, qrPayload } from '../utils/format';
export function CardQr({ barcode }: { barcode: string }) {
  const { width } = useWindowDimensions();
  if (!isBarcode(barcode)) return <Text accessibilityRole="alert" style={styles.body}>{ru.qrInvalid}</Text>;
  return <View style={[styles.panel, { alignItems: 'center', backgroundColor: t.colors.qr }]}>
    <Text style={styles.label}>{ru.qrHint}</Text><View accessible accessibilityLabel={`${ru.barcode}: ${barcode}`} style={{ padding: t.spacing.md, backgroundColor: t.colors.qr }}>
      <QRCode value={qrPayload(barcode)} size={Math.max(120, Math.min(240, width - t.spacing.lg * 4 - t.spacing.md * 2))} color="#000000" backgroundColor="#FFFFFF" ecl="M" />
    </View><Text selectable style={[styles.title, { textAlign: 'center' }]}>{barcode}</Text>
  </View>;
}
