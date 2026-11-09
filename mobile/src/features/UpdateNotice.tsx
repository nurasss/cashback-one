import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  AppState,
  type AppStateStatus,
  Linking,
  Modal,
  Platform,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Button } from '../components/ui';
import { DEMO_ENABLED } from '../demo/mockApi';
import { useI18n } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useThemedStyles } from '../theme/ThemeProvider';
import {
  getCurrentVersionCode,
  loadVersionInfo,
  updateDecision,
  type UpdateDecision,
  type VersionInfo,
} from './appUpdate';

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

/** Result of the last manual check from Settings. `idle` until the first press. */
export type UpdateCheckStatus = 'idle' | 'checking' | 'upToDate' | 'available' | 'error';

export interface UpdateCheck {
  /** Update checks exist only in the Android release build (not demo, not web/iOS). */
  supported: boolean;
  status: UpdateCheckStatus;
  availableVersion: string | null;
  /** Manual check: ignores the 6-hour automatic interval and a previously dismissed optional prompt. */
  checkNow: () => Promise<UpdateCheckStatus>;
  // Dialog state, consumed by UpdateDialog.
  info: VersionInfo | null;
  decision: UpdateDecision;
  visible: boolean;
  openDownload: () => Promise<void>;
  dismissOptional: () => void;
}

type Outcome = { ok: false } | { ok: true; info: VersionInfo; decision: UpdateDecision };

function useUpdateController({ demoEnabled, auto }: { demoEnabled: boolean; auto: boolean }): UpdateCheck {
  const supported = Platform.OS === 'android' && !demoEnabled;
  const [info, setInfo] = useState<VersionInfo | null>(null);
  const [decision, setDecision] = useState<UpdateDecision>('none');
  const [visible, setVisible] = useState(false);
  const [status, setStatus] = useState<UpdateCheckStatus>('idle');

  const dismissedOptional = useRef(false);
  const lastCheckTime = useRef<number>(0);
  const isMounted = useRef(true);
  const inFlight = useRef<Promise<Outcome> | null>(null);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  // One request at a time: an automatic and a manual check that overlap share the same answer.
  const request = useCallback((): Promise<Outcome> | null => {
    const currentCode = getCurrentVersionCode();
    if (!currentCode) return null;
    if (!inFlight.current) {
      lastCheckTime.current = Date.now();
      inFlight.current = (async (): Promise<Outcome> => {
        try {
          const result = await loadVersionInfo();
          return result.ok ? { ok: true, info: result.info, decision: updateDecision(result.info, currentCode) } : { ok: false };
        } finally {
          inFlight.current = null;
        }
      })();
    }
    return inFlight.current;
  }, []);

  const apply = useCallback((outcome: Outcome, manual: boolean) => {
    if (!outcome.ok) return;
    setInfo(outcome.info);
    setDecision(outcome.decision);
    if (outcome.decision === 'required') {
      setVisible(true);
    } else if (outcome.decision === 'optional') {
      if (manual) dismissedOptional.current = false;
      setVisible(!dismissedOptional.current);
    } else {
      setVisible(false);
    }
  }, []);

  const checkNow = useCallback(async (): Promise<UpdateCheckStatus> => {
    if (!supported) return 'error';
    const pending = request();
    if (!pending) {
      if (isMounted.current) setStatus('error');
      return 'error';
    }
    if (isMounted.current) setStatus('checking');
    const outcome = await pending;
    if (!isMounted.current) return outcome.ok ? (outcome.decision === 'none' ? 'upToDate' : 'available') : 'error';
    apply(outcome, true);
    const next: UpdateCheckStatus = !outcome.ok ? 'error' : outcome.decision === 'none' ? 'upToDate' : 'available';
    setStatus(next);
    return next;
  }, [apply, request, supported]);

  useEffect(() => {
    if (!auto || !supported) return;

    const checkUpdate = async () => {
      const pending = request();
      if (!pending) return;
      const outcome = await pending;
      if (!isMounted.current) return;
      apply(outcome, false);
    };

    void checkUpdate();

    const handleAppStateChange = (nextState: AppStateStatus) => {
      if (nextState === 'active' && Date.now() - lastCheckTime.current >= SIX_HOURS_MS) {
        void checkUpdate();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);
    return () => subscription.remove();
  }, [apply, auto, request, supported]);

  const openDownload = useCallback(async () => {
    if (!info) return;
    try {
      await Linking.openURL(info.download_url);
      if (decision === 'optional') setVisible(false);
    } catch {
      // Opening failure does not crash the app; dialog remains visible
    }
  }, [decision, info]);

  const dismissOptional = useCallback(() => {
    dismissedOptional.current = true;
    setVisible(false);
  }, []);

  const availableVersion = info && decision !== 'none' ? info.latest_version : null;
  return useMemo(
    () => ({ supported, status, availableVersion, checkNow, info, decision, visible, openDownload, dismissOptional }),
    [supported, status, availableVersion, checkNow, info, decision, visible, openDownload, dismissOptional],
  );
}

// Exported only so a local snapshot harness can feed a fixed state to the real UpdateDialog; the app uses UpdateProvider.
export const Context = createContext<UpdateCheck | null>(null);

/** Runs the automatic checks (launch + return to foreground) and shares the manual check with Settings. */
export function UpdateProvider({ children, demoEnabled = DEMO_ENABLED }: { children: React.ReactNode; demoEnabled?: boolean }) {
  const controller = useUpdateController({ demoEnabled, auto: true });
  return <Context.Provider value={controller}>{children}</Context.Provider>;
}

/** Manual-check state for Settings. Without a provider it still works, only without the automatic dialog. */
export function useUpdateCheck(): UpdateCheck {
  const shared = useContext(Context);
  const own = useUpdateController({ demoEnabled: DEMO_ENABLED, auto: false });
  return shared ?? own;
}

export function UpdateDialog() {
  const { t: tr } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const controller = useContext(Context);
  if (!controller) return null;
  const { supported, visible, decision, info, openDownload, dismissOptional } = controller;
  if (!supported || !visible || decision === 'none' || !info) {
    return null;
  }

  const handleRequestClose = () => {
    if (decision === 'optional') {
      dismissOptional();
    }
  };

  return (
    <Modal
      transparent
      animationType="fade"
      visible={visible}
      onRequestClose={handleRequestClose}
      statusBarTranslucent
    >
      <View style={styles.overlay}>
        <View style={styles.dialog}>
          <Text accessibilityRole="header" style={styles.title}>
            {tr('updateTitle')}
          </Text>
          <Text style={styles.body}>
            {decision === 'required' ? tr('updateRequiredBody') : tr('updateBody')}
          </Text>
          <View style={styles.actions}>
            <Button
              label={tr('updateNow')}
              onPress={openDownload}
            />
            {decision === 'optional' && (
              <Button
                label={tr('updateLater')}
                secondary
                onPress={dismissOptional}
              />
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

/** Standalone notice: automatic checks plus the dialog. The app root uses UpdateProvider + UpdateDialog instead. */
export function UpdateNotice({
  demoEnabled = DEMO_ENABLED,
}: {
  demoEnabled?: boolean;
} = {}) {
  return (
    <UpdateProvider demoEnabled={demoEnabled}>
      <UpdateDialog />
    </UpdateProvider>
  );
}

const makeStyles = (c: Colors) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: c.overlay,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  dialog: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: c.surface,
    borderRadius: 24,
    padding: 24,
    gap: 14,
  },
  title: {
    fontFamily: fonts.bold,
    fontSize: 20,
    color: c.text,
    textAlign: 'center',
  },
  body: {
    fontFamily: fonts.regular,
    fontSize: 15,
    lineHeight: 22,
    color: c.muted,
    textAlign: 'center',
  },
  actions: {
    marginTop: 6,
    gap: 10,
  },
});
