import { Image, Text, View } from 'react-native';
import { fonts } from '../theme';

// Keep the level data live while using the generated artwork for the glossy medal and glow.
export function StatusCoin({ level, size = 210 }: { level: number | string; size?: number }) {
  const imageSize = size * 0.86;
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
    <Image source={require('../../assets/reference-redesign/status-coin-level-1.png')} resizeMode="contain" style={{ width: imageSize, height: imageSize, position: 'absolute' }} />
    <Text style={{ fontFamily: fonts.extrabold, fontSize: size * 0.16, color: '#FF737A', lineHeight: size * 0.2,
      textShadowColor: '#8E1520', textShadowOffset: { width: 1, height: 3 }, textShadowRadius: 2, marginTop: size * 0.03 }}>{String(level)}</Text>
  </View>;
}
