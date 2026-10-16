import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { keys, useProfile } from '../../../src/api/app';
import { useSession } from '../../../src/auth/provider';
import { Button, ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { Avatar, FieldSheet, LanguageSwitch, ProfileRow } from '../../../src/features/profile';
import { useI18n, type Language } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import type { Gender, Profile } from '../../../src/types/api';
import { birthDateToApi, birthDateToUi, initials } from '../../../src/utils/format';

type Form = { first_name: string; last_name: string; email: string; gender: string; city: string; address: string; birth_date: string; iin: string; company: string };
type SheetField = Exclude<keyof Form, 'first_name' | 'last_name'>;
const toForm = (p: Profile): Form => ({
  first_name: p.first_name ?? '', last_name: p.last_name ?? '', email: p.email ?? '', gender: p.gender ?? '', city: p.city ?? '',
  address: p.address ?? '', birth_date: birthDateToUi(p.birth_date), iin: p.iin ?? '', company: p.company ?? '',
});

export default function ProfileScreen() {
  const { t, language, setLanguage } = useI18n();
  const { api, session } = useSession();
  const query = useQueryClient();
  const profile = useProfile();
  const [form, setForm] = useState<Form | null>(null);
  const [sheet, setSheet] = useState<SheetField | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (profile.data && !form) setForm(toForm(profile.data)); }, [profile.data, form]);

  const update = (field: keyof Form, value: string) => { setForm(current => current ? { ...current, [field]: value } : current); setSaved(false); };
  const patch = async (body: Record<string, unknown>) => {
    const next = await api.request<Profile>('/me/profile', { method: 'PATCH', auth: true, body });
    query.setQueryData(keys.profile, next);
    return next;
  };
  const changeLanguage = (next: Language) => {
    const previous = language;
    setLanguage(next);
    void patch({ language: next }).catch(err => { setLanguage(previous); setError(err); });
  };
  const save = async () => {
    if (!form || !profile.data) return;
    const original = toForm(profile.data);
    const body: Record<string, unknown> = {};
    for (const key of Object.keys(form) as (keyof Form)[]) {
      if (form[key] === original[key]) continue;
      body[key] = key === 'birth_date' ? birthDateToApi(form[key]) : form[key].trim() || null;
    }
    if (Object.keys(body).length === 0) { setSaved(true); return; }
    setSaving(true); setError(null);
    try { setForm(toForm(await patch(body))); setSaved(true); } catch (err) { setError(err); } finally { setSaving(false); }
  };
  const logout = () => Alert.alert(t('logoutConfirm'), undefined, [{ text: t('cancel'), style: 'cancel' }, { text: t('logout'), style: 'destructive',
    onPress: () => { void session.logout().then(failed => { if (failed) Alert.alert(t('logout'), t('revokeFailed')); }); } }]);

  const genderLabel = (value: string) => value === 'male' ? t('male') : value === 'female' ? t('female') : '';
  const sheets: Record<SheetField, { title: string; hint?: string; placeholder?: string; keyboardType?: 'default' | 'email-address' | 'number-pad'; maxLength?: number;
    options?: { value: Gender; label: string }[]; validate?: (value: string) => string | null }> = {
    email: { title: t('email'), placeholder: t('emailPh'), keyboardType: 'email-address', maxLength: 255,
      validate: value => !value || /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(value) ? null : t('invalidEmail') },
    gender: { title: t('gender'), options: [{ value: 'male', label: t('male') }, { value: 'female', label: t('female') }] },
    city: { title: t('city'), maxLength: 100 },
    address: { title: t('address'), maxLength: 255 },
    birth_date: { title: t('birthDate'), placeholder: t('birthDatePh'), keyboardType: 'number-pad', maxLength: 10,
      validate: value => birthDateToApi(value) === undefined ? t('invalidDate') : null },
    iin: { title: t('iin'), hint: t('iinHint'), keyboardType: 'number-pad', maxLength: 12, validate: value => !value || /^\d{12}$/.test(value) ? null : t('invalidIin') },
    company: { title: t('company'), maxLength: 255 },
  };

  return <SafeAreaView edges={['top']} style={[styles.screen, { backgroundColor: theme.colors.surface }]}>
    <ScreenHeader title={t('myProfile')} back onBack={() => router.navigate('/')}
      right={<LanguageSwitch value={language} onChange={changeLanguage} disabled={!profile.data} />} />
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { paddingTop: 8, gap: 6 }]}>
        {profile.isPending || !form ? (profile.isError ? <ErrorNotice error={profile.error} retry={() => { void profile.refetch(); }} /> : <Loading />) : <>
          <Avatar initials={initials(form.first_name, form.last_name)} />
          <View style={{ gap: 12 }}>
            <Field label={t('firstName')} value={form.first_name} placeholder={t('firstNamePh')} onChange={value => update('first_name', value)} />
            <Field label={t('lastName')} value={form.last_name} placeholder={t('lastNamePh')} onChange={value => update('last_name', value)} />
          </View>
          <View style={local.divider} />
          <View>
            <ProfileRow label={t('email')} value={form.email} placeholder={t('emailPh')} onPress={() => setSheet('email')} />
            <ProfileRow label={t('gender')} value={genderLabel(form.gender)} onPress={() => setSheet('gender')} />
            <ProfileRow label={t('city')} value={form.city} onPress={() => setSheet('city')} />
            <ProfileRow label={t('address')} value={form.address} onPress={() => setSheet('address')} />
            <ProfileRow label={t('birthDate')} value={form.birth_date} onPress={() => setSheet('birth_date')} />
            <ProfileRow label={t('iin')} value={form.iin} onPress={() => setSheet('iin')} />
            <ProfileRow label={t('company')} value={form.company} onPress={() => setSheet('company')} />
          </View>
          {error !== null && <ErrorNotice error={error} />}
          {saved && <Text accessibilityLiveRegion="polite" style={local.saved}>{t('saved')}</Text>}
          <Button label={saving ? t('loading') : t('save')} disabled={saving} onPress={() => { void save(); }} style={{ borderRadius: 12, minHeight: 50 }} />
          <View style={local.links}>
            <ProfileRow icon="history" label={t('accrualHistory')} onPress={() => router.push('/history')} />
            <ProfileRow icon="card" label={t('myCards')} onPress={() => router.push('/cards')} />
            <ProfileRow icon="logout" label={t('logout')} onPress={logout} />
          </View>
        </>}
      </ScrollView>
    </KeyboardAvoidingView>
    {sheet && form && <FieldSheet {...sheets[sheet]} initial={form[sheet]} onClose={() => setSheet(null)}
      onDone={value => { update(sheet, value); setSheet(null); }} />}
  </SafeAreaView>;
}

function Field({ label, value, placeholder, onChange }: { label: string; value: string; placeholder: string; onChange: (value: string) => void }) {
  return <View style={{ gap: 10 }}>
    <Text style={local.fieldLabel}>{label}</Text>
    <TextInput accessibilityLabel={label} value={value} placeholder={placeholder} placeholderTextColor={theme.colors.placeholder} maxLength={100}
      onChangeText={onChange} style={[styles.input, local.profileInput]} />
  </View>;
}

const local = StyleSheet.create({
  fieldLabel: { fontFamily: fonts.medium, fontSize: 15, color: theme.colors.text },
  profileInput: { minHeight: 42, fontSize: 17 },
  divider: { height: 1, backgroundColor: theme.colors.border },
  saved: { fontFamily: fonts.medium, fontSize: 15, color: theme.colors.success, textAlign: 'center' },
  links: { backgroundColor: theme.colors.background, borderRadius: 22, paddingHorizontal: 18, paddingVertical: 4 },
});
