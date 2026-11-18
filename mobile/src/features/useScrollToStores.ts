import { useCallback, useEffect, useRef, useState } from 'react';
import type { LayoutChangeEvent, ScrollView } from 'react-native';

// Scrolls a screen to its stores section when it was opened with `section=stores` (the "Where can I spend my bonuses?" link).
//
// `y` from onLayout is relative to the PARENT of the measured view, so the measured view must be a direct child of the
// ScrollView content (not inside an animated wrapper) for `y` to be a scroll offset. The stores list is empty until app-content
// arrives, so scrolling waits until the section has a height. `token` (the `at` route parameter) lets a screen that is already
// mounted scroll again when it is opened once more; the same (section, token) pair scrolls only once.
export function useScrollToStores(section: string | undefined, token: string | undefined) {
  const scrollRef = useRef<ScrollView>(null);
  const [layout, setLayout] = useState<{ y: number; height: number } | null>(null);
  const handled = useRef<string | null>(null);

  useEffect(() => {
    if (section !== 'stores' || !layout || layout.height <= 0) return;
    const key = `${section}:${token ?? ''}`;
    if (handled.current === key) return;
    handled.current = key;
    scrollRef.current?.scrollTo({ y: Math.max(0, layout.y - 12), animated: true });
  }, [section, token, layout]);

  const onStoresLayout = useCallback((event: LayoutChangeEvent) => {
    const { y, height } = event.nativeEvent.layout;
    setLayout(previous => (previous && previous.y === y && previous.height === height ? previous : { y, height }));
  }, []);

  return { scrollRef, onStoresLayout };
}
