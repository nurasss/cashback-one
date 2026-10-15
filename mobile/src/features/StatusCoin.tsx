import { View } from 'react-native';
import Svg, { Circle, Defs, RadialGradient, Stop, LinearGradient, Text as SvgText } from 'react-native-svg';
import { fonts } from '../theme';

// Glowing level coin from the "Мой статус" design, drawn in SVG so it scales without image assets.
export function StatusCoin({ level, size = 300 }: { level: number | string; size?: number }) {
  const coin = size * 0.42;
  const c = size / 2;
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ width: size, height: size }}>
    <Svg width={size} height={size}>
      <Defs>
        <RadialGradient id="glow" cx="50%" cy="50%" r="50%">
          <Stop offset="0%" stopColor="#FF5A4E" stopOpacity="0.95" />
          <Stop offset="45%" stopColor="#FF7A6E" stopOpacity="0.55" />
          <Stop offset="100%" stopColor="#FFB2A8" stopOpacity="0" />
        </RadialGradient>
        <LinearGradient id="rim" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0%" stopColor="#F58C8C" />
          <Stop offset="100%" stopColor="#B91C2B" />
        </LinearGradient>
        <LinearGradient id="face" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0%" stopColor="#EF4B57" />
          <Stop offset="100%" stopColor="#C8212F" />
        </LinearGradient>
      </Defs>
      <Circle cx={c} cy={c} r={c} fill="url(#glow)" />
      <Circle cx={c + coin * 0.06} cy={c + coin * 0.04} r={coin / 2} fill="#A3121F" />
      <Circle cx={c} cy={c} r={coin / 2} fill="url(#rim)" />
      <Circle cx={c} cy={c} r={coin / 2 - coin * 0.09} fill="url(#face)" stroke="#F7A0A3" strokeOpacity={0.6} strokeWidth={2} />
      <SvgText x={c + 3} y={c + coin * 0.2 + 3} fontSize={coin * 0.55} fontFamily={fonts.extrabold} fill="#9E1120" textAnchor="middle">{String(level)}</SvgText>
      <SvgText x={c} y={c + coin * 0.2} fontSize={coin * 0.55} fontFamily={fonts.extrabold} fill="#F25E66" textAnchor="middle">{String(level)}</SvgText>
    </Svg>
  </View>;
}
