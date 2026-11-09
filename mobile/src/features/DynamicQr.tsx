import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { Icon } from '../components/icons';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import type { CardQr } from '../types/api';

// Tokens are short-lived and server-signed; a stale or malformed payload is never rendered.
export const isQrToken = (value: string) => /^C1[A-Z2-7]{48}$/.test(value);

export function DynamicQr({
  value,
  qr,
  loading = false,
  failed = false,
  blocked,
}: {
  value?: string;
  qr?: CardQr | undefined;
  loading?: boolean;
  failed?: boolean;
  blocked: boolean;
}) {
  const { t: tr } = useI18n();
  const { width } = useWindowDimensions();
  const styles = useThemedStyles(makeStyles);
  const { colors } = useTheme();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!qr) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [qr]);
  const expiresAt = qr ? Date.parse(qr.expires_at) : 0;
  const valid = !!qr && isQrToken(qr.token) && expiresAt > now;
  const payload = value !== undefined ? value : valid ? qr.token : null;
  const size = Math.max(180, Math.min(240, width - 168));

  return <View style={styles.card}>
    <View style={[styles.qrBox, { width: size, height: size }]}>
      {blocked ? <Text style={styles.message}>{tr('cardBlocked')}</Text> :
        payload ? <View accessible accessibilityLabel={tr('showToCashier')} testID="qr-code" style={[styles.qrFrame, { width: size, height: size }]}>
          <QRCode value={payload} size={size - QR_QUIET_ZONE * 2} color={colors.qrInk} backgroundColor={colors.qr} ecl="M" /></View> :
        loading ? <ActivityIndicator color={colors.primary} /> :
        <Text style={styles.message}>{failed ? tr('qrUnavailable') : tr('loading')}</Text>}
    </View>
    <View style={styles.hintRow}>
      <Icon name="scan" size={24} color={colors.primaryText} strokeWidth={2.2} />
      <Text style={styles.hint}>{tr('showToCashier')}</Text>
    </View>
  </View>;
}

// The code always sits on an opaque white field with this margin (the quiet zone), whatever the app theme is.
export const QR_QUIET_ZONE = 12;

const makeStyles = (c: Colors) => StyleSheet.create({
  card: { backgroundColor: c.surface, borderRadius: 28, paddingVertical: 32, paddingHorizontal: 24, alignItems: 'center', gap: 24,
    shadowColor: c.shadow, shadowOpacity: 0.04, shadowRadius: 20, shadowOffset: { width: 0, height: 6 }, elevation: 2 },
  qrBox: { alignItems: 'center', justifyContent: 'center' },
  qrFrame: { alignItems: 'center', justifyContent: 'center', backgroundColor: c.qr, borderRadius: 16 },
  message: { fontFamily: fonts.medium, fontSize: 14, color: c.muted, textAlign: 'center' },
  hintRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  hint: { fontFamily: fonts.semibold, fontSize: 15, color: c.primaryText },
});
