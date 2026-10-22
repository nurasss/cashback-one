import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Dimensions, Keyboard, Platform, type KeyboardEvent, type View } from 'react-native';

export function overlap(sheetBottom: number, keyboardTop: number, margin = 10): number {
  return sheetBottom > keyboardTop ? sheetBottom - keyboardTop + margin : 0;
}

// Measure the unshifted viewport containing the bottom-aligned sheet. Its bottom
// is the sheet's resting bottom; internal padding never changes this measurement.
// A native resize therefore replaces, rather than adds to, our keyboard lift.
export function useKeyboardLift() {
  const ref = useRef<View>(null);
  const keyboardVisible = useRef(false);
  const coordinates = useRef<{ screenY: number; height: number } | null>(null);
  const paddingBottom = useRef(new Animated.Value(0)).current;
  const [maxHeight, setMaxHeight] = useState<number>();
  const frame = useRef<number | null>(null);
  const generation = useRef(0);

  const measure = useCallback(() => {
    const version = ++generation.current;
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      ref.current?.measureInWindow((_x, y, _width, height) => {
        if (version !== generation.current) return;
        const keyboard = coordinates.current;
        const top = keyboard?.screenY ?? Dimensions.get('screen').height;
        const lift = keyboard ? overlap(y + height, top) : 0;
        setMaxHeight(Math.max(0, height - lift - 24));
        paddingBottom.stopAnimation();
        Animated.timing(paddingBottom, { toValue: lift, duration: 160, useNativeDriver: false }).start();
      });
    });
  }, [paddingBottom]);

  useEffect(() => {
    const show = (event: KeyboardEvent) => {
      keyboardVisible.current = true;
      const { screenY, height } = event.endCoordinates;
      coordinates.current = { screenY: Number.isFinite(screenY) ? screenY : Dimensions.get('screen').height - height, height };
      measure();
    };
    const hide = () => {
      keyboardVisible.current = false;
      coordinates.current = null;
      ++generation.current;
      paddingBottom.stopAnimation();
      Animated.timing(paddingBottom, { toValue: 0, duration: 160, useNativeDriver: false }).start();
      measure();
    };
    const shown = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow', show);
    const hidden = Keyboard.addListener(Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide', hide);
    // Also handle an editor opened while the keyboard was already visible.
    const current = Keyboard.metrics();
    if (current) {
      keyboardVisible.current = true;
      coordinates.current = { screenY: current.screenY, height: current.height };
      measure();
    }
    return () => {
      shown.remove(); hidden.remove();
      ++generation.current;
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      paddingBottom.stopAnimation();
    };
  }, [measure, paddingBottom]);

  return { ref, onLayout: measure, style: { paddingBottom }, maxHeight, keyboardVisible };
}
