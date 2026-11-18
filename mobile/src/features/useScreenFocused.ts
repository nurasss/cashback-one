import * as ExpoRouter from 'expo-router';

// Whether the screen that owns this component is the focused one in the navigation stack.
// Outside a navigator (isolated component tests, a mocked router) there is no navigation context: the screen counts as focused.
// The context is either present for the whole life of the component or absent for the whole life, so the hook order is stable.
export function useScreenFocused(): boolean {
  const useIsFocused = (ExpoRouter as { useIsFocused?: () => boolean }).useIsFocused;
  if (typeof useIsFocused !== 'function') return true;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useIsFocused();
  } catch {
    return true;
  }
}
