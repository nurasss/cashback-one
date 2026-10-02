import { FlatList, Pressable, Text, View } from 'react-native';
import { Button, styles } from '../components/ui';
import { ru } from '../i18n/ru';
import type { Card } from '../types/api';
import { decimalText } from '../utils/format';
import { theme as t } from '../theme';
export function WalletList({ cards, open, bind, refreshing, refresh, header }: { cards: Card[]; open: (id: string) => void; bind: () => void; refreshing: boolean; refresh: () => void; header?: React.ReactElement }) {
  return <FlatList data={cards} keyExtractor={card => card.id} contentContainerStyle={styles.content} refreshing={refreshing} onRefresh={refresh} ListHeaderComponent={header}
    ListEmptyComponent={<View style={styles.panel}><Text style={styles.title}>{ru.emptyTitle}</Text><Text style={styles.body}>{ru.emptyBody}</Text><Button label={ru.bind} onPress={bind} /></View>}
    renderItem={({ item }) => <Pressable accessibilityRole="button" accessibilityLabel={`${item.business.name}. ${ru.bonuses}: ${decimalText(item.balance)}. ${ru.showQr}`} onPress={() => open(item.id)} style={styles.panel}>
      <Text style={styles.title}>{item.business.name}</Text><Text style={styles.muted}>{ru.bonuses}</Text><Text style={{ color: t.colors.text, fontSize: t.font.balance, fontWeight: '700' }}>{decimalText(item.balance)}</Text>
      <Text style={styles.body}>{item.barcode}</Text><Text style={styles.muted}>{item.is_blocked ? ru.blocked : ru.active}</Text>
      <View style={{ borderTopWidth: 1, borderColor: t.colors.border, paddingTop: t.spacing.md }}><Text style={styles.label}>{ru.showQr} →</Text></View>
    </Pressable>}
    ListFooterComponent={cards.length > 0 ? <Button label={ru.bind} secondary onPress={bind} /> : null} />;
}
