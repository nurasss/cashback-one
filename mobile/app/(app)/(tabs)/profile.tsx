import { useKeyboardLift } from '../../../src/components/useKeyboardLift';
import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
import { useQueryClient } from '@tanstack/react-query';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Animated, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { deleteAvatar, keys, uploadAvatar, useProfile } from '../../../src/api/app';
import * as ImagePicker from 'expo-image-picker';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import { useSession } from '../../../src/auth/provider';
import { ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { Avatar, FieldSheet, LanguageSwitch, ProfileRow } from '../../../src/features/profile';
import { useI18n, type Language } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import type { Profile } from '../../../src/types/api';
import { cityOptions } from '../../../src/features/cities';
import { birthDateInputText, birthDateToApi, birthDateToUi, initials, isAdultBirthDate } from '../../../src/utils/format';

type Form = { first_name: string; last_name: string; email: string; gender: string; city: string; address: string; birth_date: string };
type SheetField = Exclude<keyof Form, 'first_name' | 'last_name'>;
const toForm = (p: Profile): Form => ({
  first_name: p.first_name ?? '', last_name: p.last_name ?? '', email: p.email ?? '', gender: p.gender ?? '', city: p.city ?? '',
  address: p.address ?? '', birth_date: birthDateToUi(p.birth_date),
});

export default function ProfileScreen() {
  const lift = useKeyboardLift();
  const insets = useSafeAreaInsets();
  const { t, language, setLanguage } = useI18n();
  const { api, session } = useSession();
  const query = useQueryClient();
  const profile = useProfile();
  const [form, setForm] = useState<Form | null>(null);
  // Latest form for code that runs after an await; every write goes through writeForm so the ref never lags behind what is on screen.
  const formRef = useRef<Form | null>(null);
  const mountedRef = useRef(true);
  const writeForm = (next: Form) => { formRef.current = next; if (mountedRef.current) setForm(next); };
  const [sheet, setSheet] = useState<SheetField | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const inFlightRef = useRef(false);
  const queuedRef = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushSaveRef = useRef<() => Promise<void>>(() => Promise.resolve());

  useEffect(() => { if (profile.data && !formRef.current) writeForm(toForm(profile.data)); }, [profile.data]);

  const patch = async (body: Record<string, unknown>) => {
    const next = await api.request<Profile>('/me/profile', { method: 'PATCH', auth: true, body });
    query.setQueryData(keys.profile, next);
    return next;
  };

  const flushSave = async () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    if (inFlightRef.current) {
      queuedRef.current = true;
      return;
    }
    const currentProfile = query.getQueryData<Profile>(keys.profile) ?? profile.data;
    if (!formRef.current || !currentProfile) return;
    const original = toForm(currentProfile);
    const current = formRef.current;
    const body: Record<string, unknown> = {};
    if (current.first_name.trim() !== original.first_name.trim()) {
      body.first_name = current.first_name.trim() || null;
    }
    if (current.last_name.trim() !== original.last_name.trim()) {
      body.last_name = current.last_name.trim() || null;
    }
    if (Object.keys(body).length === 0) {
      return;
    }

    inFlightRef.current = true;
    if (mountedRef.current) setError(null);

    // Remember what was sent: the answer is applied only to fields that still hold exactly this text.
    const sent = {
      first_name: body.first_name !== undefined ? current.first_name : undefined,
      last_name: body.last_name !== undefined ? current.last_name : undefined,
    };

    try {
      const fresh = toForm(await patch(body));
      const cur = formRef.current;
      if (cur) {
        const next = { ...cur };
        if (
          sent.first_name !== undefined &&
          cur.first_name === sent.first_name &&
          cur.first_name.trim() !== fresh.first_name.trim()
        ) {
          next.first_name = fresh.first_name;
        }
        if (
          sent.last_name !== undefined &&
          cur.last_name === sent.last_name &&
          cur.last_name.trim() !== fresh.last_name.trim()
        ) {
          next.last_name = fresh.last_name;
        }
        writeForm(next);
        const allMatches =
          next.first_name.trim() === fresh.first_name.trim() &&
          next.last_name.trim() === fresh.last_name.trim();
        if (mountedRef.current) {
          setSaved(allMatches);
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      inFlightRef.current = false;
      if (queuedRef.current) {
        queuedRef.current = false;
        void flushSaveRef.current();
      }
    }
  };
  flushSaveRef.current = flushSave;

  const update = (field: 'first_name' | 'last_name', value: string) => {
    if (formRef.current) writeForm({ ...formRef.current, [field]: value });
    setSaved(false);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void flushSaveRef.current();
    }, 800);
  };

  useFocusEffect(
    useCallback(() => {
      return () => {
        void flushSaveRef.current();
      };
    }, [])
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      void flushSaveRef.current();
    };
  }, []);

  const changeLanguage = (next: Language) => {
    const previous = language;
    setLanguage(next);
    void patch({ language: next }).catch(err => { setLanguage(previous); setError(err); });
  };

  // A sheet saves just its own field. Errors propagate to the sheet, which keeps the input; other unsaved fields are not sent.
  const commitField = async (field: SheetField, value: string) => {
    const currentProfile = query.getQueryData<Profile>(keys.profile) ?? profile.data;
    if (!currentProfile) return;
    if (value !== toForm(currentProfile)[field]) {
      const next = await patch({ [field]: field === 'birth_date' ? birthDateToApi(value) : value.trim() || null });
      const fresh = toForm(next);
      if (formRef.current) writeForm({ ...formRef.current, [field]: fresh[field] });
    }
    setSheet(null);
  };

  const pickAndUploadAvatar = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
      });
      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }
      const asset = result.assets[0];
      if (!asset?.uri) return;

      if (mountedRef.current) {
        setAvatarLoading(true);
        setError(null);
      }

      const manipulated = await manipulateAsync(
        asset.uri,
        [{ resize: { width: 512 } }],
        { compress: 0.8, format: SaveFormat.JPEG }
      );

      const next = await uploadAvatar(api, manipulated.uri);
      query.setQueryData(keys.profile, next);
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setAvatarLoading(false);
      }
    }
  };

  const removeAvatar = async () => {
    if (mountedRef.current) {
      setAvatarLoading(true);
      setError(null);
    }
    try {
      const next = await deleteAvatar(api);
      query.setQueryData(keys.profile, next);
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setAvatarLoading(false);
      }
    }
  };

  const onAvatarPress = () => {
    const currentAvatar = (query.getQueryData<Profile>(keys.profile) ?? profile.data)?.avatar_url;
    if (currentAvatar) {
      Alert.alert(
        t('avatarChange'),
        undefined,
        [
          { text: t('avatarChange'), onPress: () => { void pickAndUploadAvatar(); } },
          { text: t('avatarDelete'), style: 'destructive', onPress: () => { void removeAvatar(); } },
          { text: t('cancel'), style: 'cancel' },
        ]
      );
    } else {
      void pickAndUploadAvatar();
    }
  };

  const logout = () => Alert.alert(t('logoutConfirm'), undefined, [{ text: t('cancel'), style: 'cancel' }, { text: t('logout'), style: 'destructive',
    onPress: () => { void session.logout().then(failed => { if (failed) Alert.alert(t('logout'), t('revokeFailed')); }); } }]);

  const genderLabel = (value: string) => value === 'male' ? t('male') : value === 'female' ? t('female') : '';
  const sheets: Record<SheetField, { title: string; hint?: string; placeholder?: string; keyboardType?: 'default' | 'email-address' | 'number-pad'; maxLength?: number;
    options?: { value: string; label: string }[]; format?: (value: string) => string; validate?: (value: string) => string | null }> = {
    email: { title: t('email'), placeholder: t('emailPh'), keyboardType: 'email-address', maxLength: 255,
      validate: value => !value || /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(value) ? null : t('invalidEmail') },
    gender: { title: t('gender'), options: [{ value: 'male', label: t('male') }, { value: 'female', label: t('female') }] },
    city: { title: t('city'), options: cityOptions(t, form?.city ?? '') },
    address: { title: t('address'), maxLength: 255 },
    birth_date: { title: t('birthDate'), placeholder: t('birthDatePh'), keyboardType: 'number-pad', maxLength: 10,
      format: birthDateInputText,
      validate: value => {
        if (!value.trim()) return null;
        if (birthDateToApi(value) === undefined) return t('invalidDate');
        if (!isAdultBirthDate(value)) return t('birthDateUnder18');
        return null;
      } },
  };

  return <SafeAreaView edges={['top']} style={[styles.screen, { backgroundColor: theme.colors.surface }]}>
    <ScreenHeader title={t('myProfile')} back onBack={() => router.navigate('/')}
      right={<LanguageSwitch value={language} onChange={changeLanguage} disabled={!profile.data} />} />
    <Animated.View ref={lift.ref} collapsable={false} onLayout={lift.onLayout} style={[{ flex: 1 }, lift.style]}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16, paddingTop: 8, gap: 6 }]}>
        {profile.isPending || !form ? (profile.isError ? <ErrorNotice error={profile.error} retry={() => { void profile.refetch(); }} /> : <Loading />) : <>
          <Avatar
            initials={initials(form.first_name, form.last_name)}
            avatarUrl={(query.getQueryData<Profile>(keys.profile) ?? profile.data)?.avatar_url}
            onPress={onAvatarPress}
            loading={avatarLoading}
          />
          <View style={{ gap: 12 }}>
            <Field label={t('firstName')} value={form.first_name} placeholder={t('firstNamePh')} onChange={value => update('first_name', value)} onBlur={() => { void flushSave(); }} />
            <Field label={t('lastName')} value={form.last_name} placeholder={t('lastNamePh')} onChange={value => update('last_name', value)} onBlur={() => { void flushSave(); }} />
          </View>
          <View style={local.divider} />
          <View>
            <ProfileRow label={t('email')} value={form.email} placeholder={t('emailPh')} onPress={() => setSheet('email')} />
            <ProfileRow label={t('gender')} value={genderLabel(form.gender)} onPress={() => setSheet('gender')} />
            <ProfileRow label={t('city')} value={cityOptions(t, form.city).find(option => option.value === form.city)?.label} onPress={() => setSheet('city')} />
            <ProfileRow label={t('address')} value={form.address} onPress={() => setSheet('address')} />
            <ProfileRow label={t('birthDate')} value={form.birth_date} onPress={() => setSheet('birth_date')} />
          </View>
          {error !== null && <ErrorNotice error={error} />}
          {saved && <Text accessibilityLiveRegion="polite" style={local.saved}>{t('saved')}</Text>}
          <View style={local.links}>
            <ProfileRow icon="history" label={t('accrualHistory')} onPress={() => router.push('/history')} />
            <ProfileRow icon="card" label={t('myCards')} onPress={() => router.push('/cards')} />
            <ProfileRow icon="logout" label={t('logout')} onPress={logout} />
          </View>
        </>}
      </ScrollView>
    </Animated.View>
    {sheet && form && <FieldSheet {...sheets[sheet]} initial={form[sheet]} onClose={() => setSheet(null)}
      onDone={value => commitField(sheet, value)} />}
  </SafeAreaView>;
}

function Field({ label, value, placeholder, onChange, onBlur }: {
  label: string; value: string; placeholder: string; onChange: (value: string) => void; onBlur?: () => void;
}) {
  return <View style={{ gap: 6 }}>
    <Text style={local.fieldLabel}>{label}</Text>
    <TextInput accessibilityLabel={label} value={value} placeholder={placeholder} placeholderTextColor={theme.colors.placeholder} maxLength={100}
      onChangeText={onChange} onBlur={onBlur} style={[styles.input, local.profileInput]} />
  </View>;
}

const local = StyleSheet.create({
  fieldLabel: { fontFamily: fonts.semibold, fontSize: 11, color: theme.colors.muted, textTransform: 'uppercase', letterSpacing: 0.8 },
  profileInput: { minHeight: 46, fontSize: 15 },
  divider: { height: 1, backgroundColor: theme.colors.border },
  saved: { fontFamily: fonts.medium, fontSize: 14, color: theme.colors.success, textAlign: 'center' },
  links: { backgroundColor: theme.colors.background, borderRadius: 20, paddingHorizontal: 16, paddingVertical: 4, marginTop: 8 },
});
