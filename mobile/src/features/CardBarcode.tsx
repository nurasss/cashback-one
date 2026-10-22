import { PixelRatio, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { useI18n } from '../i18n';
import { fonts, theme as t } from '../theme';
import type { Card } from '../types/api';
import { code128Bars, isCode128Number, QUIET_ZONE_MODULES } from './code128';

const BAR_HEIGHT = 96;
// Screen content padding (2 × 20) plus card padding (2 × 20) around the code.
const SIDE_SPACE = 80;

// Static Code 128 of the card number, separate from the dynamic QR: it is never built from or mixed with a C1 token.
// The number is passed through as the exact string (leading zeros, no padding); nothing is drawn for a missing card or an invalid number.
export function CardBarcode({ card }: { card: Pick<Card, 'barcode' | 'is_blocked' | 'business'> | undefined }) {
  const { t: tr } = useI18n();
  const { width } = useWindowDimensions();
  if (!card || !isCode128Number(card.barcode)) return null;
  const encoded = code128Bars(card.barcode);
  if (!encoded) return null;

  const available = Math.max(200, Math.min(360, width - SIDE_SPACE));
  const totalModules = encoded.modules + QUIET_ZONE_MODULES * 2;
  // Whole device pixels per module keep the bar edges sharp; the quiet zones are part of the white area.
  const ratio = PixelRatio.get();
  const moduleSize = Math.max(1, Math.floor((available * ratio) / totalModules)) / ratio;
  const codeWidth = totalModules * moduleSize;
  const path = encoded.bars.map(bar => `M${bar.x + QUIET_ZONE_MODULES} 0h${bar.width}v${BAR_HEIGHT}h-${bar.width}z`).join('');
  const label = `${tr('barcodeTitle')}: ${card.business.name}. ${tr('barcodeCaption')} ${card.barcode.split('').join(' ')}`;

  return <View style={styles.card} testID="card-barcode">
    <Text style={styles.business} numberOfLines={2}>{card.business.name}</Text>
    {card.is_blocked ? <Text style={styles.blocked}>{tr('cardBlocked')}</Text> : <>
      <View accessible accessibilityRole="image" accessibilityLabel={label} style={[styles.white, { width: Math.max(available, codeWidth) }]}>
        <Svg testID="card-barcode-svg" width={codeWidth} height={BAR_HEIGHT} viewBox={`0 0 ${totalModules} ${BAR_HEIGHT}`} preserveAspectRatio="none">
          <Path d={path} fill="#000000" />
        </Svg>
      </View>
      <View style={styles.numberBlock}>
        <Text style={styles.caption}>{tr('barcodeCaption')}</Text>
        <Text style={styles.number} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7} selectable>{card.barcode}</Text>
      </View>
    </>}
  </View>;
}

const styles = StyleSheet.create({
  card: { backgroundColor: t.colors.surface, borderRadius: 28, paddingVertical: 24, paddingHorizontal: 20, alignItems: 'center', gap: 16,
    shadowColor: t.colors.shadow, shadowOpacity: 0.04, shadowRadius: 20, shadowOffset: { width: 0, height: 6 }, elevation: 2 },
  business: { fontFamily: fonts.bold, fontSize: 16, color: t.colors.text, textAlign: 'center' },
  white: { backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  numberBlock: { alignItems: 'center', gap: 2 },
  caption: { fontFamily: fonts.semibold, fontSize: 11, color: t.colors.muted, textTransform: 'uppercase', letterSpacing: 0.8 },
  number: { fontFamily: fonts.bold, fontSize: 22, letterSpacing: 1.5, color: t.colors.text },
  blocked: { fontFamily: fonts.medium, fontSize: 14, color: t.colors.muted, textAlign: 'center' },
});
