import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { Icon, type IconName } from '../components/icons';
import { NewDot } from '../components/ui';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { Promotion, Tier } from '../types/api';
import { pointsText } from '../utils/format';

export function BalanceHeader({ phone, balance }: { phone: string; balance: string }) {
  const { t: tr } = useI18n();
  return <View style={styles.headerRow}>
    <Text style={styles.phone} numberOfLines={1}>{phone}</Text>
    <View style={styles.balanceGroup} accessible accessibilityLabel={`${tr('pointsSum')}: ${pointsText(balance)}`}>
      <Text style={styles.balance}>{pointsText(balance)}</Text>
      <View style={styles.brandBadge}><Text style={styles.brandBadgeText}>{tr('bonusCurrency')}</Text></View>
    </View>
  </View>;
}

export function BannerCarousel({ banners, open }: { banners: Promotion[]; open: (id: string) => void }) {
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState(0);
  const cardWidth = width - 48 - 24;
  const step = cardWidth + 12;
  if (banners.length === 0) return null;
  return <View style={styles.carousel}>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} snapToInterval={step} decelerationRate="fast"
      contentContainerStyle={{ paddingHorizontal: 36, gap: 12 }}
      onMomentumScrollEnd={event => setIndex(Math.round(event.nativeEvent.contentOffset.x / step))}>
      {banners.map(banner => <Pressable key={banner.id} accessibilityRole="button" accessibilityLabel={banner.title} onPress={() => open(banner.id)}
        style={[styles.banner, { width: cardWidth }]}>
        {banner.image_url ? <Image source={{ uri: banner.image_url }} style={StyleSheet.absoluteFill} resizeMode="cover" accessibilityIgnoresInvertColors /> :
          <View style={styles.bannerFallback}>
            <Text style={styles.bannerTitle} numberOfLines={3}>{banner.title}</Text>
            {banner.subtitle && <Text style={styles.bannerSubtitle} numberOfLines={2}>{banner.subtitle}</Text>}
          </View>}
      </Pressable>)}
    </ScrollView>
    {banners.length > 1 && <View style={styles.dots} accessibilityElementsHidden>
      {banners.map((banner, dot) => <View key={banner.id} style={[styles.pageDot, dot === index && styles.pageDotActive]} />)}
    </View>}
  </View>;
}

export function StatusCard({ tier, balance, onPress }: { tier: Tier | null | undefined; balance: string; onPress: () => void }) {
  const { t: tr } = useI18n();
  return <Pressable accessibilityRole="button" accessibilityLabel={`${tr('yourStatus')} ${tier?.level ?? ''}. ${tr('pointsSum')} ${pointsText(balance)}`}
    onPress={onPress} style={({ pressed }) => [styles.statusCard, pressed && { opacity: 0.85 }]}>
    <View style={{ gap: 6 }}>
      <Text style={styles.statusCaption}>{tr('yourStatus')}</Text>
      <Text style={styles.statusValue}>{tier ? tier.level : '—'}</Text>
    </View>
    <View style={styles.statusRight}>
      <View style={{ gap: 6, alignItems: 'flex-end' }}>
        <Text style={styles.statusCaption}>{tr('pointsSum')}</Text>
        <Text style={styles.statusValue}>{pointsText(balance)}</Text>
      </View>
      <Icon name="chevronRight" size={26} />
    </View>
  </Pressable>;
}

const offerIcons: IconName[] = ['percent', 'gift', 'card', 'cart'];

export function OfferCard({ offer, index, onPress, wide = false }: { offer: Promotion; index: number; onPress: () => void; wide?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={[offer.badge, offer.title].filter(Boolean).join('. ')} onPress={onPress}
    style={({ pressed }) => [styles.offer, wide && styles.offerWide, pressed && { opacity: 0.85 }]}>
    <View style={styles.offerTop}>
      {offer.badge ? <View style={styles.offerBadge}>
        <Icon name={offerIcons[index % offerIcons.length] ?? 'tag'} size={20} color={t.colors.onPrimary} strokeWidth={2.2} />
        <Text style={styles.offerBadgeText} numberOfLines={2}>{offer.badge}</Text>
      </View> : <View />}
      <Icon name="chevronRight" size={22} />
    </View>
    <Text style={[styles.offerTitle, offer.image_url ? styles.offerTitleWithImage : null]} numberOfLines={3}>{offer.title}</Text>
    {offer.image_url && <Image source={{ uri: offer.image_url }} style={styles.offerImage} resizeMode="contain" accessibilityIgnoresInvertColors />}
    {offer.is_new && <NewDot style={styles.offerNew} />}
  </Pressable>;
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingHorizontal: 24, paddingVertical: 16 },
  phone: { fontFamily: fonts.medium, fontSize: 20, color: t.colors.text, flexShrink: 1 },
  balanceGroup: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  balance: { fontFamily: fonts.medium, fontSize: 20, color: t.colors.text },
  brandBadge: { backgroundColor: t.colors.primary, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 7 },
  brandBadgeText: { fontFamily: fonts.extrabold, fontSize: 18, color: t.colors.onPrimary, letterSpacing: -0.5 },
  carousel: { gap: 18, paddingBottom: 22 },
  banner: { height: 196, borderRadius: 26, overflow: 'hidden', backgroundColor: t.colors.background },
  bannerFallback: { flex: 1, padding: 22, justifyContent: 'center', gap: 8, backgroundColor: t.colors.softPrimary },
  bannerTitle: { fontFamily: fonts.extrabold, fontSize: 28, lineHeight: 32, color: t.colors.primary, textTransform: 'uppercase' },
  bannerSubtitle: { fontFamily: fonts.bold, fontSize: 16, color: t.colors.text, textTransform: 'uppercase' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 10 },
  pageDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#D9D9DD' },
  pageDotActive: { backgroundColor: t.colors.primary },
  statusCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: t.colors.status, borderRadius: 30, paddingHorizontal: 30, paddingVertical: 22 },
  statusRight: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  statusCaption: { fontFamily: fonts.medium, fontSize: 17, color: t.colors.text },
  statusValue: { fontFamily: fonts.bold, fontSize: 36, color: t.colors.text },
  offer: { flexBasis: '47%', flexGrow: 1, minHeight: 200, borderRadius: 24, padding: 16, backgroundColor: t.colors.tint, overflow: 'hidden', gap: 18 },
  offerWide: { flexBasis: 'auto', flexGrow: 0, minHeight: 150 },
  offerTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  offerBadge: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: t.colors.primary, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 6, maxWidth: '82%' },
  offerBadgeText: { fontFamily: fonts.semibold, fontSize: 12, lineHeight: 15, color: t.colors.onPrimary, flexShrink: 1 },
  offerTitle: { fontFamily: fonts.bold, fontSize: 17, lineHeight: 22, color: t.colors.text },
  offerTitleWithImage: { maxWidth: '72%' },
  offerImage: { position: 'absolute', right: -6, bottom: -6, width: '62%', height: '58%' },
  offerNew: { position: 'absolute', top: 10, left: 10 },
});
