import { useLocalSearchParams } from 'expo-router';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePromotion } from '../../../src/api/app';
import { ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { useI18n } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import { dayText } from '../../../src/utils/format';

export default function PromotionDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, language } = useI18n();
  const promotion = usePromotion(id);
  const item = promotion.data;
  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('promotion')} back />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 0 }]}>
      {promotion.isPending ? <Loading /> : !item ? <ErrorNotice error={promotion.error} retry={() => { void promotion.refetch(); }} /> : <>
        {item.image_url && <Image source={{ uri: item.image_url }} style={local.image} resizeMode="cover" accessibilityIgnoresInvertColors />}
        <View style={local.card}>
          {item.badge && <View style={local.badge}><Text style={local.badgeText}>{item.badge}</Text></View>}
          <Text style={local.title}>{item.title}</Text>
          {item.subtitle && <Text style={[styles.body, { color: theme.colors.muted }]}>{item.subtitle}</Text>}
          {item.body && <Text style={styles.body}>{item.body}</Text>}
          {item.ends_at && <Text style={local.until}>{t('validUntil', { date: dayText(item.ends_at, language) })}</Text>}
        </View>
      </>}
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  image: { width: '100%', aspectRatio: 1.7, borderRadius: 26, backgroundColor: theme.colors.surface },
  card: { backgroundColor: theme.colors.surface, borderRadius: 26, padding: 22, gap: 12 },
  badge: { alignSelf: 'flex-start', backgroundColor: theme.colors.primary, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 5 },
  badgeText: { fontFamily: fonts.semibold, fontSize: 13, color: theme.colors.onPrimary },
  title: { fontFamily: fonts.bold, fontSize: 24, color: theme.colors.text },
  until: { fontFamily: fonts.semibold, fontSize: 15, color: theme.colors.primary },
});
