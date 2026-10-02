import { router } from 'expo-router';
import { Alert, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useCards } from '../../src/api/wallet';
import { useSession } from '../../src/auth/provider';
import { Button, ErrorNotice, Loading, styles } from '../../src/components/ui';
import { WalletList } from '../../src/features/WalletList';
import { ru } from '../../src/i18n/ru';
import { dateText } from '../../src/utils/format';
export default function Wallet() {
  const cards = useCards();
  const { session } = useSession();
  const header = <View style={styles.gap}><Text style={styles.title}>{ru.subtitle}</Text>
    <Button label={ru.logout} secondary onPress={() => { void session.logout().then(failed => { if (failed) Alert.alert(ru.logout, ru.revokeFailed); }); }} />
    {cards.dataUpdatedAt > 0 && <Text style={styles.muted}>{ru.lastLoaded}: {dateText(cards.dataUpdatedAt)}</Text>}
    {cards.isError && <><ErrorNotice error={cards.error} retry={() => { void cards.refetch(); }} />{cards.data && <Text style={styles.muted}>{ru.stale}</Text>}</>}
  </View>;
  return <SafeAreaView edges={['bottom']} style={styles.screen}>
    {cards.isPending ? <Loading /> : cards.data ? <WalletList cards={cards.data} header={header} refreshing={cards.isRefetching} refresh={() => { void cards.refetch(); }}
      open={id => router.push({ pathname: '/cards/[id]', params: { id } })} bind={() => router.push('/bind')} /> : <View style={styles.content}>{header}<Button label={ru.bind} onPress={() => router.push('/bind')} /></View>}
  </SafeAreaView>;
}
