import { useKeyboardLift } from '../src/components/useKeyboardLift';
import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ApiError } from '../src/api/errors';
import { useSession } from '../src/auth/provider';
import { FadeIn } from '../src/components/motion';
import { Button, ErrorNotice, Input, styles } from '../src/components/ui';
import { useI18n } from '../src/i18n';
import { deviceId } from '../src/storage/secure';
import { fonts, theme } from '../src/theme';
import type { CodeRequestResult, Tokens } from '../src/types/api';
import { phoneText } from '../src/utils/format';

const RESEND_SECONDS = 30;

export default function Login() {
  const lift = useKeyboardLift();
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
    <Animated.View ref={lift.ref} collapsable={false} onLayout={lift.onLayout} style={[styles.screen, lift.style]}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={local.content}>
        <FadeIn style={{ gap: 12 }}>
          <View style={local.brand}><Text style={local.brandText}>{t('bonusCurrency')}</Text></View>
          <Text style={local.title}>{t('loginTitle')}</Text>
          <Text style={[styles.body, { color: theme.colors.muted }]}>{t('loginBody')}</Text>
        </FadeIn>
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
          <Button label={t('changePhone')} secondary disabled={busy} onPress={() => { setSentPhone(''); setCode(''); setError(null); }} />
          {resendIn > 0 ? (
            <Text style={local.resendCountdown}>
              {`${t('resendIn')} ${resendIn} ${t('seconds')}`}
            </Text>
          ) : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('resend')}
              disabled={busy}
              onPress={() => { void requestCode(sentPhone); }}
              hitSlop={10}
              style={({ pressed }) => [local.resendLinkWrap, pressed && { opacity: 0.6 }]}
            >
              <Text style={local.resendLinkText}>{t('resend')}</Text>
            </Pressable>
          )}
        </View>}
        {error !== null && <ErrorNotice error={error} />}
        <Text style={[styles.muted, { textAlign: 'center' }]}>{t('sessionNote')}</Text>
      </ScrollView>
    </Animated.View>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  content: { padding: 20, gap: 20, paddingTop: 56 },
  brand: { alignSelf: 'flex-start', backgroundColor: theme.colors.primary, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 6, marginBottom: 8 },
  brandText: { fontFamily: fonts.extrabold, fontSize: 16, color: theme.colors.onPrimary, letterSpacing: 0.4 },
  title: { fontFamily: fonts.bold, fontSize: 26, lineHeight: 32, color: theme.colors.text },
  form: { gap: 14, backgroundColor: theme.colors.surface, borderRadius: 22, padding: 20, borderWidth: 1, borderColor: 'rgba(17,17,17,0.05)' },
  resendCountdown: { fontFamily: fonts.medium, fontSize: 14, color: theme.colors.muted, textAlign: 'center', paddingVertical: 8 },
  resendLinkWrap: { alignSelf: 'center', paddingVertical: 8, paddingHorizontal: 12 },
  resendLinkText: { fontFamily: fonts.semibold, fontSize: 14, color: theme.colors.primary, textAlign: 'center', textDecorationLine: 'underline' },
});
