import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { useSession } from '../../src/auth/provider';
import { ApiError } from '../../src/api/errors';
import { walletKey } from '../../src/api/wallet';
import { Button, ErrorNotice, styles } from '../../src/components/ui';
import { BindForm } from '../../src/features/BindForm';
import { ru } from '../../src/i18n/ru';
import type { Card } from '../../src/types/api';
export default function Bind() {
  const { api } = useSession();
  const query = useQueryClient();
  const [barcode, setBarcode] = useState('');
  const mutation = useMutation({ mutationFn: ({ value, business }: { value: string; business?: string }) => api.request<Card>('/me/cards/bind', { method: 'POST', body: { barcode: value, ...(business ? { business_id: business } : {}) }, auth: true }),
    onSuccess: async card => {
      query.setQueryData<Card[]>([...walletKey, 'cards'], previous => previous ? [card, ...previous.filter(item => item.id !== card.id)] : undefined);
      await query.invalidateQueries({ queryKey: walletKey });
      query.setQueryData([...walletKey, 'card', card.id], card);
      router.replace({ pathname: '/cards/[id]', params: { id: card.id } });
    } });
  const choices = mutation.error instanceof ApiError ? mutation.error.businesses : [];
  return <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
    <Text style={styles.body}>{ru.barcodeHint}</Text><View style={styles.panel}><BindForm pending={mutation.isPending} submit={value => { setBarcode(value); mutation.mutate({ value }); }} /></View>
    {mutation.isError && <ErrorNotice error={mutation.error} />}
    {choices.length > 0 && <View style={styles.panel}><Text style={styles.title}>{ru.chooseBusiness}</Text>{choices.map(business => <Button key={business.id} label={business.name} secondary disabled={mutation.isPending} onPress={() => mutation.mutate({ value: barcode, business: business.id })} />)}</View>}
  </ScrollView></KeyboardAvoidingView>;
}
