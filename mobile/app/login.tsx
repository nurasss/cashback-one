import { useEffect, useRef, useState } from 'react';
import { AppState, KeyboardAvoidingView, Linking, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useSession } from '../src/auth/provider';
import { ApiError } from '../src/api/errors';
import { Button, ErrorNotice, Input, styles } from '../src/components/ui';
import { ru } from '../src/i18n/ru';
import { deviceId } from '../src/storage/secure';
import type { Challenge, ChallengeStatus, SmsRequestResult, Tokens } from '../src/types/api';

export default function Login() {
  const { api, session } = useSession();
  const [mode, setMode] = useState<'choose' | 'wa' | 'sms'>('choose');
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [phone, setPhone] = useState('+7');
  const [sentPhone, setSentPhone] = useState('');
  const [code, setCode] = useState('');
  const [smsExpiry, setSmsExpiry] = useState(0);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(true);
  const inFlight = useRef(false);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const remaining = challenge ? Math.max(0, Math.ceil((Date.parse(challenge.expires_at) - now) / 1000)) : 0;
  const smsRemaining = Math.max(0, Math.ceil((smsExpiry - now) / 1000));
  async function run(work: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try { await work(); } catch (err) { setError(err); }
    finally { inFlight.current = false; setBusy(false); }
  }
  async function createChallenge() {
    await run(async () => {
      const result = await api.request<Challenge>('/auth/challenge', { method: 'POST', body: { device_id: await deviceId() } });
      setChallenge(result); setMode('wa'); setPolling(true);
    });
  }
  useEffect(() => {
    if (mode !== 'wa' || !challenge || !polling) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const check = async () => {
      if (cancelled) return;
      if (AppState.currentState !== 'active' || inFlight.current) { timer = setTimeout(check, 2000); return; }
      if (Date.now() >= Date.parse(challenge.expires_at)) { setPolling(false); setError(new ApiError('CHALLENGE_EXPIRED')); return; }
      inFlight.current = true; setBusy(true);
      try {
        const status = await api.request<ChallengeStatus>(`/auth/challenge/${encodeURIComponent(challenge.challenge_id)}`, { headers: { 'X-Device-Id': await deviceId() } });
        if (status.status === 'confirmed' && status.access_token && status.refresh_token && status.expires_in !== undefined && status.token_type) {
          await session.accept({ access_token: status.access_token, refresh_token: status.refresh_token, expires_in: status.expires_in, token_type: status.token_type });
          return;
        }
        if (cancelled) return;
        if (status.status === 'expired') throw new ApiError('CHALLENGE_EXPIRED');
        if (status.status !== 'pending') throw new ApiError('INVALID_RESPONSE');
        setError(null); timer = setTimeout(check, 2000);
      } catch (err) { if (!cancelled) { setPolling(false); setError(err); } }
      finally { inFlight.current = false; if (!cancelled) setBusy(false); }
    };
    timer = setTimeout(check, 500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [api, challenge, mode, polling, session]);
  function reset() { if (busy) return; setMode('choose'); setChallenge(null); setCode(''); setError(null); setSentPhone(''); setSmsExpiry(0); }
  return <SafeAreaView style={styles.screen}><KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
    <Text style={styles.muted}>{ru.app}</Text><Text style={styles.hero}>{ru.loginTitle}</Text><Text style={styles.body}>{ru.loginBody}</Text>
    {mode === 'choose' && <View style={styles.gap}><Button label={ru.whatsapp} disabled={busy} onPress={() => { void createChallenge(); }} /><Button label={ru.sms} secondary disabled={busy} onPress={() => { setMode('sms'); setError(null); }} /></View>}
    {mode === 'wa' && challenge && <View style={styles.panel}>
      <Text style={styles.body}>{ru.waInstruction}</Text><Text selectable style={styles.hero}>{challenge.code}</Text>
      <Text style={styles.muted}>{ru.remaining} {remaining} {ru.seconds}</Text>
      <Button label={ru.openWhatsapp} disabled={busy || remaining === 0} onPress={() => { void run(async () => {
        const url = new URL(challenge.login_url);
        if (url.protocol !== 'https:' || url.hostname !== 'wa.me') throw new ApiError('INVALID_RESPONSE');
        try { await Linking.openURL(challenge.login_url); } catch { throw new ApiError('NETWORK_UNAVAILABLE'); }
      }); }} />
      {polling && remaining > 0 && <Text accessibilityLiveRegion="polite" style={styles.muted}>{ru.waiting}</Text>}
      {!polling && remaining > 0 && <Button label={ru.check} secondary disabled={busy} onPress={() => { setError(null); setPolling(true); }} />}
      {remaining === 0 && <Button label={ru.newChallenge} disabled={busy} onPress={() => { void createChallenge(); }} />}
      <Button label={ru.sms} secondary disabled={busy} onPress={() => { setChallenge(null); setMode('sms'); setError(null); }} />
    </View>}
    {mode === 'sms' && <View style={styles.panel}>
      <Input label={ru.phone} hint={ru.phoneHint} value={phone} onChangeText={value => { setPhone(value); setSentPhone(''); setCode(''); setSmsExpiry(0); }} editable={!busy} keyboardType="phone-pad" autoComplete="tel" textContentType="telephoneNumber" maxLength={32} />
      <Button label={sentPhone ? ru.resend : ru.requestSms} disabled={busy || !phone.trim() || now < resendAt} secondary={!!sentPhone} onPress={() => { void run(async () => {
        const result = await api.request<SmsRequestResult>('/auth/sms/request', { method: 'POST', body: { phone: phone.trim(), device_id: await deviceId() } });
        setSentPhone(phone.trim()); setCode(''); setSmsExpiry(Date.now() + result.expires_in * 1000); setResendAt(Date.now() + 30000);
      }); }} />
      {now < resendAt && <Text style={styles.muted}>{ru.resend}: {Math.ceil((resendAt - now) / 1000)} {ru.seconds}</Text>}
      {sentPhone && <><Input label={ru.otp} hint={ru.otpHint} value={code} onChangeText={setCode} editable={!busy} keyboardType="number-pad" autoComplete="sms-otp" textContentType="oneTimeCode" maxLength={6} />
        <Text accessibilityLiveRegion="polite" style={styles.muted}>{ru.remaining} {smsRemaining} {ru.seconds}</Text>
        {smsRemaining === 0 && <ErrorNotice error={new ApiError('OTP_EXPIRED')} />}
        <Button label={ru.verify} disabled={busy || !/^[0-9]{6}$/.test(code) || smsRemaining === 0} onPress={() => { void run(async () => {
          const tokens = await api.request<Tokens>('/auth/sms/verify', { method: 'POST', body: { phone: sentPhone, device_id: await deviceId(), code } });
          await session.accept(tokens); setCode('');
        }); }} />
      </>}
    </View>}
    {error !== null && <ErrorNotice error={error} />}
    {mode !== 'choose' && <Button label={ru.cancel} secondary disabled={busy} onPress={reset} />}
  </ScrollView></KeyboardAvoidingView></SafeAreaView>;
}
