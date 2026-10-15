import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ApiError } from '../../src/api/errors';
import { walletKey } from '../../src/api/wallet';
import { useSession } from '../../src/auth/provider';
import { Button, ErrorNotice, ScreenHeader, styles } from '../../src/components/ui';
import { useActiveCard } from '../../src/features/activeCard';
import { BindForm } from '../../src/features/BindForm';
import { useI18n } from '../../src/i18n';
import type { Card } from '../../src/types/api';

export default function Bind() {
  const { t } = useI18n();
  const { api } = useSession();
  const { select } = useActiveCard();
  const query = useQueryClient();
  const [barcode, setBarcode] = useState('');
  const mutation = useMutation({
    mutationFn: ({ value, business }: { value: string; business?: string }) => api.request<Card>('/me/cards/bind',
      { method: 'POST', body: { barcode: value, ...(business ? { business_id: business } : {}) }, auth: true }),
    onSuccess: async card => {
      query.setQueryData<Card[]>([...walletKey, 'cards'], previous => previous ? [card, ...previous.filter(item => item.id !== card.id)] : undefined);
      await query.invalidateQueries({ queryKey: walletKey });
      select(card.id);
      router.back();
    },
  });
  const choices = mutation.error instanceof ApiError ? mutation.error.businesses : [];
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('bind')} back />
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { paddingTop: 0 }]}>
        <View style={styles.panel}><BindForm pending={mutation.isPending} submit={value => { setBarcode(value); mutation.mutate({ value }); }} /></View>
        {mutation.isError && <ErrorNotice error={mutation.error} />}
        {choices.length > 0 && <View style={styles.panel}><Text style={styles.title}>{t('chooseBusiness')}</Text>
          {choices.map(business => <Button key={business.id} label={business.name} secondary disabled={mutation.isPending}
            onPress={() => mutation.mutate({ value: barcode, business: business.id })} />)}</View>}
      </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}
