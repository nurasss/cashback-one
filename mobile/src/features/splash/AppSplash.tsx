import { Image } from 'expo-image';
import { StatusBar } from 'expo-status-bar';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, BackHandler, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getClientConfig } from '../../config/client';
import { DEMO_ENABLED } from '../../demo/mockApi';
import { useI18n } from '../../i18n';
import { fonts } from '../../theme';
import {
  CONFIG_TIMEOUT_MS,
  mustWaitForConfig,
  resolveSplash,
  VIDEO_MAX_SECONDS,
  type Splash,
} from './splashConfig';
import { setSplashActive } from './splashGate';

// Fullscreen launch splash shown INSIDE the app after the native splash:
//  - covers the entire screen including system bars, edge-to-edge;
//  - video and image fill proportionally with contentFit="cover" (no distortion, no bars);
//  - once per cold start (subsequent tab changes or foreground returns never show it again);
//  - pure dark background prevents any white flash or home screen flickering before first frame;
//  - smooth fade-out transition after playback finishes;
//  - muted, non-looping;
//  - checking watchdog of 2 s ensures hanging network, AsyncStorage or config never blocks the app indefinitely;
//  - a configuration or media load that takes longer than 2 s, or any error, ends it at once: an ordinary launch.
export const IMAGE_SHOW_MS = 2000;
export const MEDIA_LOAD_TIMEOUT_MS = 2000;
export const CHECKING_WATCHDOG_MS = 2000;
export const SPLASH_FADE_OUT_MS = 300;

let handledThisLaunch = false;
/** Test hook: a new "cold start". */
export function resetSplashForTests(): void {
  handledThisLaunch = false;
  setSplashActive(false);
}

type Phase = 'checking' | 'show' | 'done';

export function AppSplash() {
  const [phase, setPhase] = useState<Phase>(() => {
    if (handledThisLaunch || DEMO_ENABLED) return 'done';
    handledThisLaunch = true;
    return 'checking';
  });
  const [splash, setSplash] = useState<Splash | null>(null);
  const { t } = useI18n();
  const isDoneRef = useRef(phase === 'done');

  const finish = useCallback(() => {
    if (isDoneRef.current) return;
    isDoneRef.current = true;
    setPhase('done');
  }, []);

  useEffect(() => {
    if (phase !== 'checking') return;
    let cancelled = false;

    // Guaranteed watchdog: if checking exceeds budget, force finish to ordinary launch
    const watchdog = setTimeout(() => {
      if (!cancelled && !isDoneRef.current) {
        cancelled = true;
        finish();
      }
    }, CHECKING_WATCHDOG_MS);

    // Also support Back button during checking phase
    const back = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!cancelled && !isDoneRef.current) {
        cancelled = true;
        finish();
        return true;
      }
      return false;
    });

    void (async () => {
      try {
        let appId = '';
        let businessId: string | null = null;
        try {
          const client = getClientConfig();
          appId = client.android_app_id;
          businessId = client.business_id;
        } catch {
          /* no client: ordinary launch */
        }
        if (!appId) {
          if (!cancelled && !isDoneRef.current) finish();
          return;
        }
        const expected = { businessId };

        // A cache that says "disabled" never delays the launch: the check runs in the background for the next start.
        const shouldWait = await mustWaitForConfig(appId, expected);
        if (cancelled || isDoneRef.current) return;

        if (!shouldWait) {
          void resolveSplash(appId, expected, CONFIG_TIMEOUT_MS);
          if (!cancelled && !isDoneRef.current) finish();
          return;
        }

        const resolution = await resolveSplash(appId, expected, CONFIG_TIMEOUT_MS);
        if (cancelled || isDoneRef.current) return;

        if (resolution.splash) {
          setSplash(resolution.splash);
          setPhase('show');
        } else {
          finish();
        }
      } catch {
        if (!cancelled && !isDoneRef.current) finish();
      } finally {
        clearTimeout(watchdog);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(watchdog);
      back.remove();
    };
  }, [phase, finish]);

  useEffect(() => {
    setSplashActive(phase !== 'done');
    return () => {
      setSplashActive(false);
    };
  }, [phase]);

  if (phase === 'done') return null;
  if (phase === 'checking' || !splash) {
    return (
      <View
        testID="splash-checking"
        pointerEvents="auto"
        style={styles.overlay}
      >
        <StatusBar hidden={true} translucent={true} backgroundColor="transparent" />
        <Pressable
          testID="splash-skip"
          accessibilityRole="button"
          accessibilityLabel={t('splashSkip')}
          onPress={finish}
          style={StyleSheet.absoluteFillObject}
        />
      </View>
    );
  }
  return <SplashStage splash={splash} onDone={finish} />;
}

function SplashStage({ splash, onDone }: { splash: Splash; onDone: () => void }) {
  const { t } = useI18n();
  const insets = useSafeAreaInsets();
  const finished = useRef(false);
  const opacity = useRef(new Animated.Value(1)).current;
  const [reduceMotion, setReduceMotion] = useState<boolean | null>(null);

  const end = useCallback((immediate = false) => {
    if (finished.current) return;
    finished.current = true;
    if (immediate || reduceMotion) {
      onDone();
      return;
    }
    Animated.timing(opacity, {
      toValue: 0,
      duration: SPLASH_FADE_OUT_MS,
      useNativeDriver: true,
    }).start(() => {
      onDone();
    });
  }, [onDone, opacity, reduceMotion]);

  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled().then(
      value => {
        if (alive) setReduceMotion(value);
      },
      () => {
        if (alive) setReduceMotion(false);
      },
    );
    return () => {
      alive = false;
    };
  }, []);
  // Reduced motion: a video is skipped in favour of the ordinary launch, without any artificial delay.
  useEffect(() => {
    if (reduceMotion && splash.mediaType === 'video') end(true);
  }, [reduceMotion, splash.mediaType, end]);

  useEffect(() => {
    const back = BackHandler.addEventListener('hardwareBackPress', () => {
      end(true);
      return true;
    });
    const link = Linking.addEventListener('url', () => end(true));
    return () => {
      back.remove();
      link.remove();
    };
  }, [end]);

  return (
    <Animated.View
      testID="splash-stage"
      style={[
        styles.overlay,
        { opacity },
      ]}
    >
      <StatusBar hidden={true} translucent={true} backgroundColor="transparent" />
      {reduceMotion === null ? null : splash.mediaType === 'image' ? (
        <ImageStage splash={splash} onEnd={end} />
      ) : reduceMotion ? null : (
        <VideoStage splash={splash} onEnd={end} />
      )}
      <Pressable
        testID="splash-skip"
        accessibilityRole="button"
        accessibilityLabel={t('splashSkip')}
        hitSlop={12}
        onPress={() => end(true)}
        style={StyleSheet.absoluteFillObject}
      >
        <View
          pointerEvents="none"
          style={[
            styles.skipBadge,
            {
              top: insets.top + 12,
              right: Math.max(insets.right, 0) + 16,
            },
          ]}
        >
          <Text style={styles.skipText}>{t('splashSkip')}</Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}

function ImageStage({ splash, onEnd }: { splash: Splash; onEnd: (immediate?: boolean) => void }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (ready) return;
    // Not ready within the budget: an ordinary launch.
    const timer = setTimeout(() => onEnd(true), MEDIA_LOAD_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [ready, onEnd]);

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => onEnd(false), IMAGE_SHOW_MS);
    return () => clearTimeout(timer);
  }, [ready, onEnd]);

  return (
    <Image
      testID="splash-image"
      source={{ uri: splash.mediaUrl }}
      contentFit="cover"
      style={[styles.media, { opacity: ready ? 1 : 0 }]}
      accessibilityIgnoresInvertColors
      accessible={false}
      onLoad={() => setReady(true)}
      onError={() => onEnd(true)}
    />
  );
}

function VideoStage({ splash, onEnd }: { splash: Splash; onEnd: (immediate?: boolean) => void }) {
  const player = useVideoPlayer(splash.mediaUrl, instance => {
    instance.muted = true;
    instance.volume = 0;
    instance.loop = false;
  });
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const statusSub = player.addListener('statusChange', ({ status }) => {
      if (status === 'readyToPlay') setReady(true);
      else if (status === 'error') onEnd(true);
    });
    const endSub = player.addListener('playToEnd', () => onEnd(false));
    player.muted = true;
    player.play();
    return () => {
      statusSub.remove();
      endSub.remove();
    };
  }, [player, onEnd]);

  useEffect(() => {
    if (ready) return;
    const timer = setTimeout(() => onEnd(true), MEDIA_LOAD_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [ready, onEnd]);

  useEffect(() => {
    if (!ready) return;
    // Hard ceiling, whatever the file claims.
    const timer = setTimeout(() => onEnd(false), VIDEO_MAX_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [ready, onEnd]);

  return (
    <VideoView
      testID="splash-video"
      player={player}
      contentFit="cover"
      nativeControls={false}
      fullscreenOptions={{ enable: false }}
      allowsPictureInPicture={false}
      style={[styles.media, { opacity: ready ? 1 : 0 }]}
    />
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
    zIndex: 99999,
    elevation: 99999,
    backgroundColor: '#000000',
    overflow: 'hidden',
  },
  media: {
    ...StyleSheet.absoluteFillObject,
    width: '100%',
    height: '100%',
  },
  skipBadge: {
    position: 'absolute',
    maxWidth: '88%',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  skipText: {
    fontFamily: fonts.medium,
    fontSize: 13,
    color: 'rgba(255, 255, 255, 0.85)',
    letterSpacing: 0.3,
  },
});
