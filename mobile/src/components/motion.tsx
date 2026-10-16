import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, Platform, Pressable, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';

// Animations are skipped under Jest so tests see final values immediately.
export const motionEnabled = process.env.NODE_ENV !== 'test';
const native = Platform.OS !== 'web';
const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/** Pressable that springs down slightly while pressed. */
export function PressScale({ children, style, scale = 0.96, ...props }: Omit<PressableProps, 'style' | 'children'> & { children: ReactNode; style?: StyleProp<ViewStyle>; scale?: number }) {
  const value = useRef(new Animated.Value(1)).current;
  const to = (target: number) => { if (motionEnabled) Animated.spring(value, { toValue: target, speed: 40, bounciness: 6, useNativeDriver: native }).start(); };
  return <AnimatedPressable {...props} style={[style, { transform: [{ scale: value }] }]}
    onPressIn={event => { to(scale); props.onPressIn?.(event); }} onPressOut={event => { to(1); props.onPressOut?.(event); }}>{children}</AnimatedPressable>;
}

/** Fades and slides children up on mount; `index` staggers siblings. */
export function FadeIn({ children, index = 0, style }: { children: ReactNode; index?: number; style?: StyleProp<ViewStyle> }) {
  const value = useRef(new Animated.Value(motionEnabled ? 0 : 1)).current;
  useEffect(() => {
    if (!motionEnabled) return;
    Animated.timing(value, { toValue: 1, duration: 420, delay: 70 * index, easing: Easing.out(Easing.cubic), useNativeDriver: native }).start();
  }, [index, value]);
  return <Animated.View style={[style, { opacity: value, transform: [{ translateY: value.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }] }]}>{children}</Animated.View>;
}

/** Counts a number up to its target; returns the current display value. */
export function useCountUp(target: number, duration = 900) {
  const [shown, setShown] = useState(motionEnabled ? 0 : target);
  const from = useRef(motionEnabled ? 0 : target);
  useEffect(() => {
    if (!motionEnabled) { setShown(target); return; }
    const start = from.current;
    const began = Date.now();
    let frame: ReturnType<typeof requestAnimationFrame>;
    const tick = () => {
      const p = Math.min(1, (Date.now() - began) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      const next = start + (target - start) * eased;
      from.current = next; setShown(next);
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return shown;
}
