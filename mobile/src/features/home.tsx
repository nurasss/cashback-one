import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Image, type ImageSourcePropType, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Icon, type IconName } from '../components/icons';
import { motionEnabled, PressScale, useCountUp } from '../components/motion';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { Promotion, Tier } from '../types/api';
import { pointsText } from '../utils/format';
import { LOCAL_BANNERS, PERMANENT_OFFERS } from './promotionsArtwork';

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

type CarouselSlide =
  | { kind: 'local'; id: string; image: ImageSourcePropType; label: string; aspectRatio: number }
  | { kind: 'remote'; id: string; banner: Promotion };

export function getLoopSlides<T>(slides: readonly T[]): T[] {
  if (slides.length <= 1) return [...slides];
  return [slides[slides.length - 1]!, ...slides, slides[0]!];
}

export function getCarouselAutoplaySlot(index: number, count: number): number {
  return count > 1 ? index + 2 : 0;
}

export function getCarouselLogicalIndex(rawSlot: number, count: number): number {
  if (count <= 1) return 0;
  if (rawSlot <= 0) return count - 1;
  if (rawSlot >= count + 1) return 0;
  return rawSlot - 1;
}

// Banner = data-driven card: the opening word is highlighted, with campaign artwork on the right.
// Looping carousel: neighbours are scaled down, autoplay pauses while the user drags, the active dot stretches into a pill.
export function BannerCarousel({ banners, open, openAll }: { banners: Promotion[]; open: (id: string) => void; openAll?: () => void }) {
  const { t: tr } = useI18n();
  const handleOpenAll = openAll ?? (() => router.push('/promotions'));
  const slides: CarouselSlide[] = [
    ...LOCAL_BANNERS.map(banner => ({
      kind: 'local' as const,
      id: banner.id,
      image: banner.image,
      label: tr(banner.labelKey),
      aspectRatio: banner.aspectRatio,
    })),
    ...banners.map(banner => ({ kind: 'remote' as const, id: banner.id, banner })),
  ];
  const [index, setIndex] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const scrollX = useRef(new Animated.Value(0)).current;
  const dragging = useRef(false);
  const cardWidth = Math.max(0, containerWidth - 72);
  const step = cardWidth + 12;
  const count = slides.length;

  const settle = useCallback((rawIndex: number) => {
    if (count <= 1) return;
    if (rawIndex <= 0) scrollRef.current?.scrollTo({ x: step * count, animated: false });
    if (rawIndex >= count + 1) scrollRef.current?.scrollTo({ x: step, animated: false });
    setIndex(getCarouselLogicalIndex(rawIndex, count));
  }, [step, count]);

  useEffect(() => {
    if (cardWidth > 0 && count > 1) {
      requestAnimationFrame(() => scrollRef.current?.scrollTo({ x: step, animated: false }));
    }
  }, [cardWidth, step, count]);

  useEffect(() => {
    if (!motionEnabled || count < 2 || cardWidth === 0) return;
    let settleTimer: ReturnType<typeof setTimeout> | undefined;
    const timer = setInterval(() => {
      if (dragging.current) return;
      const nextSlot = getCarouselAutoplaySlot(index, count);
      scrollRef.current?.scrollTo({ x: nextSlot * step, animated: true });
      settleTimer = setTimeout(() => { if (!dragging.current) settle(nextSlot); }, 450);
    }, 5000);
    return () => { clearInterval(timer); if (settleTimer) clearTimeout(settleTimer); };
  }, [index, count, cardWidth, step, settle]);

  const loopSlides = getLoopSlides(slides);
  const initialOffset = count > 1 ? step : 0;
  return <View testID="banner-carousel" style={styles.carousel} onLayout={event => setContainerWidth(event.nativeEvent.layout.width)}>
    {cardWidth > 0 && <Animated.ScrollView ref={scrollRef as never} horizontal showsHorizontalScrollIndicator={false} snapToInterval={step} decelerationRate="fast"
      scrollEnabled={count > 1}
      contentOffset={{ x: initialOffset, y: 0 }} scrollEventThrottle={16}
      contentContainerStyle={{ paddingHorizontal: 36, gap: 12 }}
      nestedScrollEnabled
      onScroll={Animated.event([{ nativeEvent: { contentOffset: { x: scrollX } } }], { useNativeDriver: false })}
      onScrollBeginDrag={() => { dragging.current = true; }}
      onScrollEndDrag={() => { dragging.current = false; }}
      onMomentumScrollEnd={event => settle(Math.round(event.nativeEvent.contentOffset.x / step))}>
      {loopSlides.map((slide, slot) => {
        if (slide.kind === 'local') {
          return <Pressable key={`${slide.id}-${slot}`} testID={`banner-slide-${slot}`} accessibilityRole="button" accessibilityLabel={slide.label}
            onPress={handleOpenAll} style={[styles.banner, styles.bannerLocal, { width: cardWidth, aspectRatio: slide.aspectRatio }]}>
            <Image source={slide.image} style={styles.bannerFullImage} resizeMode="contain" accessibilityIgnoresInvertColors />
          </Pressable>;
        }
        const banner = slide.banner;
        return <Pressable key={`${banner.id}-${slot}`} testID={`banner-slide-${slot}`} accessibilityRole="button" accessibilityLabel={[banner.title, banner.subtitle].filter(Boolean).join('. ')}
          onPress={() => open(banner.id)} style={[styles.banner, { width: cardWidth }]}>
          {banner.image_url && <Image source={{ uri: banner.image_url }} style={styles.bannerImage} resizeMode="contain" accessibilityIgnoresInvertColors />}
          <View style={styles.bannerText}>
            <Text style={styles.bannerTitle} numberOfLines={2}>
              <Text style={styles.bannerTitleAccent}>{banner.title.trim().split(/\s+/)[0]} </Text>
              {banner.title.trim().split(/\s+/).slice(1).join(' ')}
            </Text>
            {banner.subtitle && <Text style={styles.bannerSubtitle} numberOfLines={3}>{banner.subtitle}</Text>}
          </View>
        </Pressable>;
      })}
    </Animated.ScrollView>}
    {count > 1 && <View style={styles.dots} accessibilityElementsHidden>
      {slides.map((slide, dot) => <Dot key={slide.id} dot={dot} count={count} step={step} scrollX={scrollX} />)}
    </View>}
  </View>;
}

// Dot `dot` is "full" while slot dot+1 is centred; the loop clones (slot 0 and count+1) also light the last / first dot.
function Dot({ dot, count, step, scrollX }: { dot: number; count: number; step: number; scrollX: Animated.Value }) {
  const peaks = [dot + 1, ...(dot === count - 1 ? [0] : []), ...(dot === 0 ? [count + 1] : [])];
  const slots = Array.from(new Set(peaks.flatMap(p => [p - 1, p, p + 1]))).sort((x, y) => x - y);
  const inputRange = slots.map(slot => slot * step);
  const full = (slot: number) => peaks.includes(slot);
  const width = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? 18 : 6)), extrapolate: 'clamp' });
  const backgroundColor = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? t.colors.primary : '#D9D9DD')), extrapolate: 'clamp' });
  return <Animated.View testID={`banner-dot-${dot}`} style={[styles.pageDot, { width, backgroundColor }]} />;
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
        <Icon name="chevronRight" size={22} />
      </View>
    </LinearGradient>
  </PressScale>;
}

export function PermanentOffersGrid({ onOpenAll }: { onOpenAll?: () => void }) {
  const { t: tr } = useI18n();
  const handleOpenAll = onOpenAll ?? (() => router.push('/promotions'));
  const rows = [
    PERMANENT_OFFERS.slice(0, 2),
    PERMANENT_OFFERS.slice(2, 4),
  ];
  return <View testID="permanent-offers-grid" style={styles.permanentGrid}>
    {rows.map((row, r) => <View key={r} style={styles.permanentGridRow}>
      {row.map(offer => <PressScale key={offer.id} testID={`permanent-card-${offer.id}`} accessibilityRole="button" accessibilityLabel={tr(offer.labelKey)}
        onPress={handleOpenAll} style={styles.permanentGridCard}>
        <Image source={offer.image} style={styles.permanentGridImage} resizeMode="contain" accessibilityIgnoresInvertColors />
      </PressScale>)}
    </View>)}
  </View>;
}

const offerIcons: IconName[] = ['percent', 'gift', 'card', 'cart'];

// Offer card: badge + title on top, picture in a rounded frame at the bottom (works with any photo from the admin).
export function OfferCard({ offer, index, onPress, wide = false, fill = false }: { offer: Promotion; index: number; onPress: () => void; wide?: boolean; fill?: boolean }) {
  return <PressScale accessibilityRole="button" accessibilityLabel={[offer.badge, offer.title].filter(Boolean).join('. ')} onPress={onPress}
    style={[styles.offer, index === 0 || index === 3 ? styles.offerPink : styles.offerGray, wide && styles.offerWide, fill && styles.offerFill]}>
    {offer.image_url ? <Image source={{ uri: offer.image_url }} style={wide ? styles.offerImageWide : styles.offerImage} resizeMode="contain" accessibilityIgnoresInvertColors /> : null}
    {offer.badge ? <View style={styles.offerBadge}>
      <Icon name={offerIcons[index % offerIcons.length] ?? 'tag'} size={12} color={t.colors.onPrimary} strokeWidth={2.4} />
      <Text style={styles.offerBadgeText} numberOfLines={1}>{offer.badge}</Text>
    </View> : null}
    <Text style={[styles.offerTitle, wide && styles.offerTitleWide]} numberOfLines={3}>{offer.title}</Text>
  </PressScale>;
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12 },
  phone: { fontFamily: fonts.medium, fontSize: 15, color: t.colors.text, flexShrink: 1 },
  balanceGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  balance: { fontFamily: fonts.semibold, fontSize: 15, color: t.colors.text },
  brandBadge: { backgroundColor: t.colors.primary, borderRadius: 999, paddingHorizontal: 11, paddingVertical: 4 },
  brandBadgeText: { fontFamily: fonts.extrabold, fontSize: 13, color: t.colors.onPrimary, letterSpacing: 0.4 },
  carousel: { gap: 12, paddingBottom: 12 },
  banner: { aspectRatio: 2.4, borderRadius: 22, overflow: 'hidden', backgroundColor: '#F1F1F4', justifyContent: 'center' },
  bannerLocal: { backgroundColor: 'transparent' },
  bannerFullImage: { width: '100%', height: '100%' },
  bannerImage: { position: 'absolute', top: 0, bottom: 0, right: 0, width: '49%', height: '90%' },
  bannerText: { width: '50%', paddingLeft: 18, gap: 6, zIndex: 1 },
  bannerTitle: { fontFamily: fonts.extrabold, fontSize: 17, lineHeight: 20, color: t.colors.text, textTransform: 'uppercase' },
  bannerTitleAccent: { color: t.colors.primary },
  bannerSubtitle: { fontFamily: fonts.bold, fontSize: 11, lineHeight: 15, color: t.colors.muted, textTransform: 'uppercase', letterSpacing: 0.3 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6 },
  pageDot: { height: 6, borderRadius: 3, backgroundColor: '#D9D9DD' },
  pageDotActive: { backgroundColor: t.colors.primary },
  statusWrap: { borderRadius: 22, overflow: 'hidden', shadowColor: '#F28A75', shadowOpacity: 0.18, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 3 },
  statusCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14 },
  statusRight: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1, minWidth: 0 },
  statusCaption: { fontFamily: fonts.semibold, fontSize: 11, color: 'rgba(17,17,17,0.6)', textTransform: 'uppercase', letterSpacing: 0.8 },
  statusValue: { fontFamily: fonts.extrabold, fontSize: 26, color: t.colors.text },
  permanentGrid: { gap: 12, paddingHorizontal: 20 },
  permanentGridRow: { flexDirection: 'row', gap: 12 },
  permanentGridCard: { flex: 1, aspectRatio: 378 / 312, backgroundColor: 'transparent' },
  permanentGridImage: { width: '100%', height: '100%' },
  offer: { flexBasis: '47%', flexGrow: 1, borderRadius: 20, padding: 14, backgroundColor: '#F3F3F5', overflow: 'hidden', gap: 10, borderWidth: 1, borderColor: 'rgba(17,17,17,0.05)' },
  offerPink: { backgroundColor: '#FCE9EC' },
  offerGray: { backgroundColor: '#F1F1F4' },
  offerWide: { flexBasis: 'auto', flexGrow: 0, minHeight: 112, justifyContent: 'center' },
  offerBadge: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: t.colors.primary, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4, maxWidth: '100%', zIndex: 1 },
  offerBadgeText: { fontFamily: fonts.bold, fontSize: 10, lineHeight: 13, color: t.colors.onPrimary, flexShrink: 1 },
  offerTitle: { fontFamily: fonts.bold, fontSize: 14, lineHeight: 18, color: t.colors.text, width: '75%', zIndex: 1 },
  offerImage: { position: 'absolute', right: -6, bottom: -4, width: '62%', height: '55%', zIndex: 0 },
  offerImageWide: { position: 'absolute', right: 8, top: 8, bottom: 8, width: '34%', zIndex: 0 },
  offerTitleWide: { width: '60%', fontSize: 15, lineHeight: 19 },
  offerFill: { flexBasis: 0, minHeight: 0 },
});
