import React, { useEffect, useRef, useState } from 'react';
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
import { fonts, theme as t } from '../theme';
import {
  fetchVersionInfo,
  getCurrentVersionCode,
  updateDecision,
  type UpdateDecision,
  type VersionInfo,
} from './appUpdate';

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

export function UpdateNotice({
  demoEnabled = DEMO_ENABLED,
}: {
  demoEnabled?: boolean;
} = {}) {
  const { t: tr } = useI18n();
  const [info, setInfo] = useState<VersionInfo | null>(null);
  const [decision, setDecision] = useState<UpdateDecision>('none');
  const [visible, setVisible] = useState(false);

  const dismissedOptional = useRef(false);
  const lastCheckTime = useRef<number>(0);
  const isMounted = useRef(true);
  const inFlight = useRef(false);

  useEffect(() => {
    isMounted.current = true;
    if (Platform.OS !== 'android' || demoEnabled) {
      return;
    }

    const checkUpdate = async () => {
      const currentCode = getCurrentVersionCode();
      if (!currentCode) return;
      if (inFlight.current) return;

      inFlight.current = true;
      lastCheckTime.current = Date.now();
      try {
        const versionInfo = await fetchVersionInfo();
        if (!isMounted.current) return;

        if (!versionInfo) {
          return;
        }

        const nextDecision = updateDecision(versionInfo, currentCode);
        setInfo(versionInfo);
        setDecision(nextDecision);

        if (nextDecision === 'required') {
          setVisible(true);
        } else if (nextDecision === 'optional') {
          if (!dismissedOptional.current) {
            setVisible(true);
          } else {
            setVisible(false);
          }
        } else {
          setVisible(false);
        }
      } finally {
        inFlight.current = false;
      }
    };

    void checkUpdate();

    const handleAppStateChange = (nextState: AppStateStatus) => {
      if (nextState === 'active') {
        const now = Date.now();
        if (now - lastCheckTime.current >= SIX_HOURS_MS) {
          void checkUpdate();
        }
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);

    return () => {
      isMounted.current = false;
      subscription.remove();
    };
  }, [demoEnabled]);

  if (Platform.OS !== 'android' || demoEnabled || !visible || decision === 'none' || !info) {
    return null;
  }

  const handleUpdate = async () => {
    try {
      await Linking.openURL(info.download_url);
      if (decision === 'optional') {
        setVisible(false);
      }
    } catch {
      // Opening failure does not crash the app; dialog remains visible
    }
  };

  const handleLater = () => {
    dismissedOptional.current = true;
    setVisible(false);
  };

  const handleRequestClose = () => {
    if (decision === 'optional') {
      handleLater();
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
              onPress={handleUpdate}
            />
            {decision === 'optional' && (
              <Button
                label={tr('updateLater')}
                secondary
                onPress={handleLater}
              />
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  dialog: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: t.colors.surface,
    borderRadius: 24,
    padding: 24,
    gap: 14,
  },
  title: {
    fontFamily: fonts.bold,
    fontSize: 20,
    color: t.colors.text,
    textAlign: 'center',
  },
  body: {
    fontFamily: fonts.regular,
    fontSize: 15,
    lineHeight: 22,
    color: t.colors.muted,
    textAlign: 'center',
  },
  actions: {
    marginTop: 6,
    gap: 10,
  },
});
