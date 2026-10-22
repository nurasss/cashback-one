import { useLocalSearchParams } from 'expo-router';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePromotion } from '../../../src/api/app';
import { FadeIn } from '../../../src/components/motion';
import { ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { useI18n } from '../../../src/i18n';
import { fonts, theme } from '../../../src/theme';
import { dayText } from '../../../src/utils/format';

export default function PromotionDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, language } = useI18n();
  const promotion = usePromotion(id);
  const item = promotion.data;
  return <SafeAreaView edges={['top', 'bottom']} style={styles.screen}>
    <ScreenHeader title={t('promotion')} back />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 0 }]}>
      {promotion.isPending ? <Loading /> : !item ? <ErrorNotice error={promotion.error} retry={() => { void promotion.refetch(); }} /> : <>
        {item.image_url && <FadeIn><Image source={{ uri: item.image_url }} style={local.image} resizeMode="contain" accessibilityIgnoresInvertColors /></FadeIn>}
        <FadeIn index={1} style={local.card}>
          {item.badge && <View style={local.badge}><Text style={local.badgeText}>{item.badge}</Text></View>}
          <Text style={local.title}>{item.title}</Text>
          {item.subtitle && <Text style={[styles.body, { color: theme.colors.muted }]}>{item.subtitle}</Text>}
          {item.body && <Text style={styles.body}>{item.body}</Text>}
          {item.ends_at && <Text style={local.until}>{t('validUntil', { date: dayText(item.ends_at, language) })}</Text>}
        </FadeIn>
      </>}
    </ScrollView>
  </SafeAreaView>;
}

const local = StyleSheet.create({
  image: { width: '100%', aspectRatio: 1.7, borderRadius: 22, backgroundColor: theme.colors.surface },
  card: { backgroundColor: theme.colors.surface, borderRadius: 22, padding: 20, gap: 10, borderWidth: 1, borderColor: 'rgba(17,17,17,0.05)' },
  badge: { alignSelf: 'flex-start', backgroundColor: theme.colors.primary, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText: { fontFamily: fonts.bold, fontSize: 11, color: theme.colors.onPrimary },
  title: { fontFamily: fonts.bold, fontSize: 20, lineHeight: 26, color: theme.colors.text },
  until: { fontFamily: fonts.semibold, fontSize: 13, color: theme.colors.primary },
});
