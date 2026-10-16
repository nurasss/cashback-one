import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { Icon } from '../components/icons';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { CardQr } from '../types/api';

// Tokens are short-lived and server-signed; a stale or malformed payload is never rendered.
export const isQrToken = (value: string) => /^C1[A-Z2-7]{48}$/.test(value);

export function DynamicQr({ qr, loading, failed, blocked }: { qr: CardQr | undefined; loading: boolean; failed: boolean; blocked: boolean }) {
  const { t: tr } = useI18n();
  const { width } = useWindowDimensions();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const expiresAt = qr ? Date.parse(qr.expires_at) : 0;
  const valid = !!qr && isQrToken(qr.token) && expiresAt > now;
  const size = Math.max(180, Math.min(280, width - 140));
  const refreshIn = qr ? Math.max(0, Math.ceil((expiresAt - now) / 1000 - qr.ttl_seconds / 2)) : 0;

  return <View style={styles.card}>
    <View style={[styles.qrBox, { width: size, height: size }]}>
      {blocked ? <Text style={styles.message}>{tr('cardBlocked')}</Text> :
        valid ? <View accessible accessibilityLabel={tr('showToCashier')} testID="qr-code"><QRCode value={qr.token} size={size} color="#000000" backgroundColor="#FFFFFF" ecl="M" /></View> :
        loading ? <ActivityIndicator color={t.colors.primary} /> :
        <Text style={styles.message}>{failed ? tr('qrUnavailable') : tr('loading')}</Text>}
    </View>
    <View style={styles.hintRow}>
      <Icon name="scan" size={36} color={t.colors.primary} strokeWidth={2.2} />
      <Text style={styles.hint}>{tr('showToCashier')}</Text>
    </View>
    {valid && !blocked && <Text style={styles.timer}>{tr('qrRefreshIn', { seconds: refreshIn })}</Text>}
  </View>;
}

const styles = StyleSheet.create({
  card: { backgroundColor: t.colors.surface, borderRadius: 40, paddingVertical: 40, paddingHorizontal: 24, alignItems: 'center', gap: 34,
    shadowColor: t.colors.shadow, shadowOpacity: 0.04, shadowRadius: 20, shadowOffset: { width: 0, height: 6 }, elevation: 2 },
  qrBox: { alignItems: 'center', justifyContent: 'center' },
  message: { fontFamily: fonts.medium, fontSize: 16, color: t.colors.muted, textAlign: 'center' },
  hintRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  hint: { fontFamily: fonts.semibold, fontSize: 19, color: t.colors.primary },
  timer: { fontFamily: fonts.regular, fontSize: 13, color: t.colors.muted, marginTop: -18 },
});
