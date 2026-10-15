import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ApiError } from '../src/api/errors';
import { useSession } from '../src/auth/provider';
import { Button, ErrorNotice, Input, styles } from '../src/components/ui';
import { useI18n } from '../src/i18n';
import { deviceId } from '../src/storage/secure';
import { fonts, theme } from '../src/theme';
import type { CodeRequestResult, Tokens } from '../src/types/api';
import { phoneText } from '../src/utils/format';

const RESEND_SECONDS = 30;

export default function Login() {
  const { api, session } = useSession();
  const { t } = useI18n();
  const [phone, setPhone] = useState('+7');
  const [sentPhone, setSentPhone] = useState('');
  const [code, setCode] = useState('');
  const [expiresAt, setExpiresAt] = useState(0);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const expired = sentPhone !== '' && now >= expiresAt;
  const resendIn = Math.max(0, Math.ceil((resendAt - now) / 1000));

  async function run(work: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try { await work(); } catch (err) { setError(err); } finally { inFlight.current = false; setBusy(false); }
  }
  const requestCode = (target: string) => run(async () => {
    const result = await api.request<CodeRequestResult>('/auth/whatsapp/request', { method: 'POST', body: { phone: target, device_id: await deviceId() } });
    setSentPhone(target); setCode(''); setExpiresAt(Date.now() + result.expires_in * 1000); setResendAt(Date.now() + RESEND_SECONDS * 1000);
  });
  const verify = () => run(async () => {
    const tokens = await api.request<Tokens>('/auth/whatsapp/verify', { method: 'POST', body: { phone: sentPhone, device_id: await deviceId(), code } });
    await session.accept(tokens);
  });

  return <SafeAreaView style={styles.screen}>
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={local.content}>
        <View style={local.brand}><Text style={local.brandText}>{t('bonusCurrency')}</Text></View>
        <Text style={local.title}>{t('loginTitle')}</Text>
        <Text style={[styles.body, { color: theme.colors.muted }]}>{t('loginBody')}</Text>
        {!sentPhone ? <View style={local.form}>
          <Input label={t('phone')} hint={t('phoneHint')} value={phone} onChangeText={setPhone} editable={!busy}
            keyboardType="phone-pad" autoComplete="tel" textContentType="telephoneNumber" maxLength={20} />
          <Button label={t('requestCode')} disabled={busy || phone.replace(/\D/g, '').length < 10} onPress={() => { void requestCode(phone.trim()); }} />
        </View> : <View style={local.form}>
          <Text style={styles.body}>{t('codeSent')} <Text style={{ fontFamily: fonts.semibold }}>{phoneText(sentPhone) || sentPhone}</Text></Text>
          <Input label={t('code')} hint={t('codeHint')} value={code} onChangeText={value => setCode(value.replace(/\D/g, ''))} editable={!busy}
            keyboardType="number-pad" autoComplete="one-time-code" textContentType="oneTimeCode" maxLength={6} autoFocus />
          {expired && <ErrorNotice error={new ApiError('OTP_EXPIRED')} />}
          <Button label={t('verify')} disabled={busy || !/^\d{6}$/.test(code) || expired} onPress={() => { void verify(); }} />
          <Button label={resendIn > 0 ? `${t('resendIn')} ${resendIn} ${t('seconds')}` : t('resend')} secondary disabled={busy || resendIn > 0}
            onPress={() => { void requestCode(sentPhone); }} />
          <Button label={t('changePhone')} secondary disabled={busy} onPress={() => { setSentPhone(''); setCode(''); setError(null); }} />
        </View>}
        {error !== null && <ErrorNotice error={error} />}
        <Text style={[styles.muted, { textAlign: 'center' }]}>{t('sessionNote')}</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  content: { padding: theme.spacing.lg, gap: theme.spacing.lg, paddingTop: theme.spacing.xxl },
  brand: { alignSelf: 'flex-start', backgroundColor: theme.colors.primary, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 8 },
  brandText: { fontFamily: fonts.extrabold, fontSize: 22, color: theme.colors.onPrimary },
  title: { fontFamily: fonts.bold, fontSize: 34, color: theme.colors.text },
  form: { gap: theme.spacing.md, backgroundColor: theme.colors.surface, borderRadius: 24, padding: theme.spacing.lg },
});
