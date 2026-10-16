import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Icon } from '../components/icons';
import { motionEnabled, PressScale, useCountUp } from '../components/motion';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { Promotion, Tier } from '../types/api';
import { amountText, percentText, pointsText } from '../utils/format';

export function HomeHeader({ name, phone }: { name: string | null | undefined; phone: string }) {
  const { t: tr } = useI18n();
  return <View style={styles.headerRow}>
    <View style={{ flexShrink: 1, gap: 2 }}>
      <Text style={styles.hello} numberOfLines={1}>{name ? tr('helloName', { name }) : tr('hello')}</Text>
      <Text style={styles.phone} numberOfLines={1}>{phone}</Text>
    </View>
    <View style={styles.brandBadge}><Text style={styles.brandBadgeText}>{tr('bonusCurrency')}</Text></View>
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
  const cardWidth = Math.max(0, containerWidth - 56);
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
      contentContainerStyle={{ paddingHorizontal: 28, gap: 12 }}
      onScroll={Animated.event([{ nativeEvent: { contentOffset: { x: scrollX } } }], { useNativeDriver: false })}
      onScrollBeginDrag={() => { dragging.current = true; }}
      onScrollEndDrag={() => { dragging.current = false; }}
      onMomentumScrollEnd={event => settle(Math.round(event.nativeEvent.contentOffset.x / step))}>
      {loopBanners.map((banner, slot) => <Pressable key={`${banner.id}-${slot}`} accessibilityRole="button" accessibilityLabel={[banner.title, banner.subtitle].filter(Boolean).join('. ')}
        onPress={() => open(banner.id)} style={[styles.banner, { width: cardWidth }]}>
        {banner.image_url && <Image source={{ uri: banner.image_url }} style={styles.bannerImage} resizeMode="cover" accessibilityIgnoresInvertColors />}
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
  const width = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? 18 : 6)), extrapolate: 'clamp' });
  const backgroundColor = scrollX.interpolate({ inputRange, outputRange: slots.map(slot => (full(slot) ? t.colors.primary : '#D9D9DD')), extrapolate: 'clamp' });
  return <Animated.View style={[styles.pageDot, { width, backgroundColor }]} />;
}

// Wallet card: the hero of the home screen — balance, current status and progress to the next one.
export function WalletCard({ tier, balance, onPress }: { tier: Tier | null | undefined; balance: string; onPress: () => void }) {
  const { t: tr } = useI18n();
  const target = Number(balance) || 0;
  const counted = useCountUp(target);
  const shown = pointsText(Math.abs(counted - target) < 0.005 ? balance : counted.toFixed(2));
  const progress = tier?.next_threshold ? Math.min(1, Math.max(0, Number(tier.spend_total ?? 0) / Number(tier.next_threshold))) : tier ? 1 : 0;
  const fill = useRef(new Animated.Value(motionEnabled ? 0 : progress)).current;
  useEffect(() => {
    if (motionEnabled) Animated.timing(fill, { toValue: progress, duration: 900, delay: 250, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start();
    else fill.setValue(progress);
  }, [fill, progress]);
  const statusLabel = tier ? (tier.name ?? tr('statusN', { level: tier.level })) : null;
  return <PressScale accessibilityRole="button" accessibilityLabel={`${tr('yourStatus')} ${tier?.level ?? ''}. ${tr('pointsSum')} ${pointsText(balance)}`}
    onPress={onPress} scale={0.98} style={styles.walletWrap}>
    <LinearGradient colors={['#F2304F', '#C8102E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.wallet}>
      <View style={[styles.orb, { width: 220, height: 220, top: -90, right: -70 }]} />
      <View style={[styles.orb, { width: 140, height: 140, bottom: -70, left: -40 }]} />
      <View style={styles.walletTop}>
        <Text style={styles.walletCaption}>{tr('yourPoints')}</Text>
        {statusLabel && <View style={styles.tierPill}>
          <Icon name="crown" size={14} color={t.colors.onPrimary} strokeWidth={2.2} />
          <Text style={styles.tierPillText}>{statusLabel} · {percentText(tier!.percent)}%</Text>
        </View>}
      </View>
      <View style={styles.walletBalanceRow}>
        <Text style={styles.walletBalance} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}>{shown}</Text>
        <Text style={styles.walletCurrency}>{tr('bonusCurrency')}</Text>
      </View>
      {tier && <View style={{ gap: 8 }}>
        <View style={styles.track}><Animated.View style={[styles.trackFill, { width: fill.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} /></View>
        <View style={styles.walletBottom}>
          <Text style={styles.walletHint} numberOfLines={1}>
            {tier.next_level ? tr('toNextStatus', { amount: amountText(tier.remaining), level: tier.next_level }) : tr('maxStatus')}
          </Text>
          <Icon name="chevronRight" size={18} color={t.colors.onPrimary} />
        </View>
      </View>}
    </LinearGradient>
  </PressScale>;
}


// Offer card: soft badge + title on top, picture anchored bottom-right (works with any photo from the admin).
export function OfferCard({ offer, onPress, wide = false, fill = false }: { offer: Promotion; index?: number; onPress: () => void; wide?: boolean; fill?: boolean }) {
  return <PressScale accessibilityRole="button" accessibilityLabel={[offer.badge, offer.title].filter(Boolean).join('. ')} onPress={onPress}
    style={[styles.offer, wide && styles.offerWide, fill && styles.offerFill]}>
    {offer.image_url ? <Image source={{ uri: offer.image_url }} style={styles.offerImage} resizeMode="contain" accessibilityIgnoresInvertColors /> : null}
    {offer.badge ? <View style={styles.offerBadge}><Text style={styles.offerBadgeText} numberOfLines={1}>{offer.badge}</Text></View> : null}
    <Text style={styles.offerTitle} numberOfLines={3}>{offer.title}</Text>
  </PressScale>;
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingHorizontal: 20, paddingTop: 14, paddingBottom: 12 },
  hello: { fontFamily: fonts.bold, fontSize: 20, color: t.colors.text },
  phone: { fontFamily: fonts.medium, fontSize: 13, color: t.colors.muted },
  brandBadge: { backgroundColor: t.colors.primary, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 6 },
  brandBadgeText: { fontFamily: fonts.extrabold, fontSize: 14, color: t.colors.onPrimary, letterSpacing: -0.3 },
  walletWrap: { marginHorizontal: 20, borderRadius: 24, overflow: 'hidden',
    shadowColor: t.colors.primary, shadowOpacity: 0.28, shadowRadius: 18, shadowOffset: { width: 0, height: 10 }, elevation: 8 },
  wallet: { padding: 20, gap: 12, overflow: 'hidden' },
  orb: { position: 'absolute', borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.09)' },
  walletTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  walletCaption: { fontFamily: fonts.medium, fontSize: 14, color: 'rgba(255,255,255,0.85)' },
  tierPill: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.18)' },
  tierPillText: { fontFamily: fonts.semibold, fontSize: 12, color: t.colors.onPrimary },
  walletBalanceRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  walletBalance: { fontFamily: fonts.extrabold, fontSize: 40, color: t.colors.onPrimary, letterSpacing: -1, flexShrink: 1 },
  walletCurrency: { fontFamily: fonts.bold, fontSize: 16, color: 'rgba(255,255,255,0.8)' },
  track: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.25)', overflow: 'hidden' },
  trackFill: { height: 6, borderRadius: 3, backgroundColor: t.colors.onPrimary },
  walletBottom: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  walletHint: { fontFamily: fonts.medium, fontSize: 13, color: 'rgba(255,255,255,0.9)', flexShrink: 1 },
  carousel: { gap: 10 },
  banner: { aspectRatio: 2.5, borderRadius: 20, overflow: 'hidden', backgroundColor: t.colors.surface, justifyContent: 'center' },
  bannerImage: { position: 'absolute', top: 0, bottom: 0, right: 0, width: '46%', height: '100%' },
  bannerText: { width: '52%', paddingLeft: 18, gap: 4, zIndex: 1 },
  bannerTitle: { fontFamily: fonts.bold, fontSize: 18, lineHeight: 22, color: t.colors.text },
  bannerTitleAccent: { color: t.colors.primary },
  bannerSubtitle: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 16, color: t.colors.muted },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6 },
  pageDot: { height: 6, borderRadius: 3 },
  offer: { flexBasis: '47%', flexGrow: 1, borderRadius: 20, padding: 14, backgroundColor: t.colors.surface, overflow: 'hidden', gap: 8 },
  offerWide: { flexBasis: 'auto', flexGrow: 0, minHeight: 130 },
  offerBadge: { alignSelf: 'flex-start', backgroundColor: t.colors.softPrimary, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, maxWidth: '100%', zIndex: 1 },
  offerBadgeText: { fontFamily: fonts.semibold, fontSize: 11, color: t.colors.primary },
  offerTitle: { fontFamily: fonts.bold, fontSize: 14, lineHeight: 18, color: t.colors.text, width: '75%', zIndex: 1 },
  offerImage: { position: 'absolute', right: -6, bottom: -4, width: '62%', height: '58%', zIndex: 0 },
  offerFill: { flexBasis: 0, minHeight: 0 },
});
