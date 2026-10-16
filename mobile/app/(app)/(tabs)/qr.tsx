import { router } from 'expo-router';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useCardQr } from '../../../src/api/app';
import { Button, Chip, EmptyState, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { useActiveCard } from '../../../src/features/activeCard';
import { DynamicQr } from '../../../src/features/DynamicQr';
import { useI18n } from '../../../src/i18n';

export default function QrScreen() {
  const { t } = useI18n();
  const { card, cards, select } = useActiveCard();
  const qr = useCardQr(card && !card.is_blocked ? card.id : undefined);
  const list = cards.data ?? [];
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('tabQr')} back onBack={() => router.navigate('/')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 126 }]}>
      {cards.isPending ? <Loading /> : !card ? <EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')}>
        <Button label={t('bind')} onPress={() => router.push('/bind')} style={{ alignSelf: 'stretch' }} />
      </EmptyState> : <>
        <DynamicQr qr={qr.data} loading={qr.isPending || qr.isFetching} failed={qr.isError} blocked={card.is_blocked} />
        {list.length > 1 && <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          {list.map(item => <Chip key={item.id} label={item.business.name} selected={item.id === card.id} onPress={() => select(item.id)} />)}
        </View>}
      </>}
    </ScrollView>
  </SafeAreaView>;
}
