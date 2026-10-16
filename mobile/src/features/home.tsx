import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Icon, type IconName } from '../components/icons';
import { motionEnabled, PressScale, useCountUp } from '../components/motion';
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

// Banner = data-driven card: the opening word is highlighted, with campaign artwork on the right.
// Looping carousel: neighbours are scaled down, autoplay pauses while the user drags, the active dot stretches into a pill.
export function BannerCarousel({ banners, open }: { banners: Promotion[]; open: (id: string) => void }) {
  const [index, setIndex] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const scrollX = useRef(new Animated.Value(0)).current;
  const dragging = useRef(false);
  const cardWidth = Math.max(0, containerWidth - 72);
  const step = cardWidth + 12;
  const count = banners.length;

  const settle = useCallback((rawIndex: number) => {
    if (rawIndex <= 0) scrollRef.current?.scrollTo({ x: step * count, animated: false });
    if (rawIndex >= count + 1) scrollRef.current?.scrollTo({ x: step, animated: false });
    setIndex(rawIndex <= 0 ? count - 1 : rawIndex > count ? 0 : rawIndex - 1);
  }, [step, count]);

  useEffect(() => {
    if (cardWidth > 0) requestAnimationFrame(() => scrollRef.current?.scrollTo({ x: step, animated: false }));
  }, [cardWidth, step, count]);

  useEffect(() => {
    if (!motionEnabled || count < 2 || cardWidth === 0) return;
    let settleTimer: ReturnType<typeof setTimeout> | undefined;
    const timer = setInterval(() => {
      if (dragging.current) return;
      const next = index + 2;
      scrollRef.current?.scrollTo({ x: next * step, animated: true });
      settleTimer = setTimeout(() => { if (!dragging.current) settle(next); }, 450);
    }, 5000);
    return () => { clearInterval(timer); if (settleTimer) clearTimeout(settleTimer); };
  }, [index, count, cardWidth, step, settle]);

  if (count === 0) return null;
  const loopBanners = [banners[count - 1]!, ...banners, banners[0]!];
  return <View style={styles.carousel} onLayout={event => setContainerWidth(event.nativeEvent.layout.width)}>
    {cardWidth > 0 && <Animated.ScrollView ref={scrollRef as never} horizontal showsHorizontalScrollIndicator={false} snapToInterval={step} decelerationRate="fast"
      contentOffset={{ x: step, y: 0 }} scrollEventThrottle={16}
      contentContainerStyle={{ paddingHorizontal: 36, gap: 12 }}
      onScroll={Animated.event([{ nativeEvent: { contentOffset: { x: scrollX } } }], { useNativeDriver: false })}
      onScrollBeginDrag={() => { dragging.current = true; }}
      onScrollEndDrag={() => { dragging.current = false; }}
      onMomentumScrollEnd={event => settle(Math.round(event.nativeEvent.contentOffset.x / step))}>
      {loopBanners.map((banner, slot) => <Pressable key={`${banner.id}-${slot}`} accessibilityRole="button" accessibilityLabel={[banner.title, banner.subtitle].filter(Boolean).join('. ')}
        onPress={() => open(banner.id)} style={[styles.banner, { width: cardWidth }]}>
        {banner.image_url && <Image source={{ uri: banner.image_url }} style={styles.bannerImage} resizeMode="contain" accessibilityIgnoresInvertColors />}
        <View style={styles.bannerText}>
          <Text style={styles.bannerTitle} numberOfLines={2}>
            <Text style={styles.bannerTitleAccent}>{banner.title.trim().split(/\s+/)[0]} </Text>
            {banner.title.trim().split(/\s+/).slice(1).join(' ')}
          </Text>
          {banner.subtitle && <Text style={styles.bannerSubtitle} numberOfLines={3}>{banner.subtitle}</Text>}
        </View>
      </Pressable>)}
    </Animated.ScrollView>}
    {count > 1 && <View style={styles.dots} accessibilityElementsHidden>
      {banners.map((banner, dot) => <Dot key={banner.id} dot={dot} count={count} step={step} scrollX={scrollX} />)}
    </View>}
  </View>;
}

// Dot `dot` is "full" while slot dot+1 is centred; the loop clones (slot 0 and count+1) also light the last / first dot.
function Dot({ dot, count, step, scrollX }: { dot: number; count: number; step: number; scrollX: Animated.Value }) {
  const peaks = [dot + 1, ...(dot === count - 1 ? [0] : []), ...(dot === 0 ? [count + 1] : [])];
  const slots = Array.from(new Set(peaks.flatMap(p => [p - 1, p, p + 1]))).sort((x, y) => x - y);
  const inputRange = slots.map(slot => slot * step);
  const full = (slot: number) => peaks.includes(slot);
  const width = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? 24 : 8)), extrapolate: 'clamp' });
  const backgroundColor = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? t.colors.primary : '#D9D9DD')), extrapolate: 'clamp' });
  return <Animated.View style={[styles.pageDot, { width, backgroundColor }]} />;
}

export function StatusCard({ tier, balance, onPress }: { tier: Tier | null | undefined; balance: string; onPress: () => void }) {
  const { t: tr } = useI18n();
  const rightLabel = tr('pointsSum');
  const counted = useCountUp(Number(balance) || 0);
  const rightValue = pointsText(Math.abs(counted - (Number(balance) || 0)) < 0.005 ? balance : counted.toFixed(2));
  return <PressScale accessibilityRole="button" accessibilityLabel={`${tr('yourStatus')} ${tier?.level ?? ''}. ${tr('pointsSum')} ${pointsText(balance)}`}
    onPress={onPress} scale={0.98} style={styles.statusWrap}>
    <LinearGradient colors={['#FFB2A4', '#FFC4B6']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.statusCard}>
      <View style={{ gap: 6 }}>
        <Text style={styles.statusCaption}>{tr('yourStatus')}</Text>
        <Text style={styles.statusValue}>{tier ? tier.level : '—'}</Text>
      </View>
      <View style={styles.statusRight}>
        <View style={{ gap: 6, alignItems: 'flex-end', flexShrink: 1, minWidth: 0 }}>
          <Text style={styles.statusCaption} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>{rightLabel}</Text>
          <Text style={styles.statusValue} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>{rightValue}</Text>
        </View>
        <Icon name="chevronRight" size={26} />
      </View>
    </LinearGradient>
  </PressScale>;
}

const offerIcons: IconName[] = ['percent', 'gift', 'card', 'cart'];

// Offer card: badge + title on top, picture in a rounded frame at the bottom (works with any photo from the admin).
export function OfferCard({ offer, index, onPress, wide = false, fill = false }: { offer: Promotion; index: number; onPress: () => void; wide?: boolean; fill?: boolean }) {
  return <PressScale accessibilityRole="button" accessibilityLabel={[offer.badge, offer.title].filter(Boolean).join('. ')} onPress={onPress}
    style={[styles.offer, index === 0 || index === 3 ? styles.offerPink : styles.offerGray, wide && styles.offerWide, fill && styles.offerFill]}>
    {offer.image_url ? <Image source={{ uri: offer.image_url }} style={[styles.offerImage, wide && styles.offerImageWide]} resizeMode="contain" accessibilityIgnoresInvertColors /> : null}
    <View style={styles.offerTop}>
      {offer.badge ? <View style={styles.offerBadge}>
        <Icon name={offerIcons[index % offerIcons.length] ?? 'tag'} size={20} color={t.colors.onPrimary} strokeWidth={2.2} />
        <Text style={styles.offerBadgeText} numberOfLines={2}>{offer.badge}</Text>
      </View> : <View />}
      <Icon name="chevronRight" size={22} color={t.colors.muted} />
    </View>
    <Text style={styles.offerTitle} numberOfLines={3}>{offer.title}</Text>
  </PressScale>;
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingHorizontal: 24, paddingVertical: 10 },
  phone: { fontFamily: fonts.medium, fontSize: 17, color: t.colors.text, flexShrink: 1 },
  balanceGroup: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  balance: { fontFamily: fonts.semibold, fontSize: 17, color: t.colors.text },
  brandBadge: { backgroundColor: t.colors.primary, borderRadius: 9, paddingHorizontal: 8, paddingVertical: 5 },
  brandBadgeText: { fontFamily: fonts.extrabold, fontSize: 15, color: t.colors.onPrimary, letterSpacing: -0.5 },
  carousel: { gap: 10, paddingBottom: 14 },
  banner: { aspectRatio: 2.35, borderRadius: 26, overflow: 'hidden', backgroundColor: '#F1F1F4', justifyContent: 'center' },
  bannerImage: { position: 'absolute', top: 0, bottom: 0, right: 0, width: '49%', height: '90%' },
  bannerText: { width: '46%', paddingLeft: 16, gap: 4, zIndex: 1 },
  bannerTitle: { fontFamily: fonts.extrabold, fontSize: 20, lineHeight: 21, color: t.colors.text, textTransform: 'uppercase' },
  bannerTitleAccent: { color: t.colors.primary },
  bannerSubtitle: { fontFamily: fonts.extrabold, fontSize: 14, lineHeight: 16, color: t.colors.text, textTransform: 'uppercase' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 10 },
  pageDot: { height: 8, borderRadius: 4, backgroundColor: '#D9D9DD' },
  pageDotActive: { backgroundColor: t.colors.primary },
  statusWrap: { borderRadius: 30, overflow: 'hidden' },
  statusCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 22, paddingVertical: 10 },
  statusRight: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1, minWidth: 0 },
  statusCaption: { fontFamily: fonts.medium, fontSize: 14, color: t.colors.text },
  statusValue: { fontFamily: fonts.extrabold, fontSize: 28, color: t.colors.text },
  offer: { flexBasis: '47%', flexGrow: 1, borderRadius: 24, padding: 12, backgroundColor: '#F3F3F5', overflow: 'hidden', gap: 8 },
  offerPink: { backgroundColor: '#FCE9EC' },
  offerGray: { backgroundColor: '#F1F1F4' },
  offerWide: { flexBasis: 'auto', flexGrow: 0 },
  offerTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, zIndex: 1 },
  offerBadge: { flexDirection: 'row', alignItems: 'center', gap: 7, backgroundColor: t.colors.primary, borderRadius: 14, paddingHorizontal: 9, paddingVertical: 6, maxWidth: '88%', zIndex: 1 },
  offerBadgeText: { fontFamily: fonts.bold, fontSize: 11, lineHeight: 13, color: t.colors.onPrimary, flexShrink: 1 },
  offerTitle: { fontFamily: fonts.extrabold, fontSize: 15, lineHeight: 18, color: t.colors.text, width: '72%', zIndex: 1 },
  offerImage: { position: 'absolute', right: -8, bottom: -3, width: '70%', height: '52%', zIndex: 0 },
  offerImageWide: { width: '70%', height: '52%' },
  offerFill: { flexBasis: 0, minHeight: 0, padding: 12, gap: 8 },
});
