import Constants from 'expo-constants';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon } from '../../src/components/icons';
import { PressScale } from '../../src/components/motion';
import { Button, ScreenHeader, useUiStyles } from '../../src/components/ui';
import { getCurrentVersionCode } from '../../src/features/appUpdate';
import { useUpdateCheck } from '../../src/features/UpdateNotice';
import { useI18n } from '../../src/i18n';
import { fonts, THEME_PREFERENCES, type Colors, type ThemePreference } from '../../src/theme';
import { useTheme, useThemedStyles } from '../../src/theme/ThemeProvider';

const themeLabels = { light: 'themeLight', dark: 'themeDark', system: 'themeSystem' } as const satisfies Record<ThemePreference, string>;

export default function SettingsScreen() {
  const { t } = useI18n();
  const styles = useUiStyles();
  const local = useThemedStyles(makeLocal);
  const { colors, preference, setPreference } = useTheme();
  const update = useUpdateCheck();

  const version = Constants.expoConfig?.version?.trim();
  const versionCode = getCurrentVersionCode();
  const versionLabel = version
    ? `${t('appVersion', { version })}${versionCode ? ` (${versionCode})` : ''}`
    : null;

  const statusText = update.status === 'checking' ? t('updateChecking')
    : update.status === 'upToDate' ? t('updateUpToDate')
    : update.status === 'available' && update.availableVersion ? t('updateAvailable', { version: update.availableVersion })
    : update.status === 'error' ? t('updateCheckFailed') : null;

  return <SafeAreaView edges={['top', 'bottom']} style={styles.screen}>
    <ScreenHeader title={t('settings')} back />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 0, gap: 16 }]}>
      <View style={local.card}>
        <Text accessibilityRole="header" style={styles.title}>{t('themeTitle')}</Text>
        <View accessibilityRole="radiogroup">
          {THEME_PREFERENCES.map((value, index) => {
            const selected = preference === value;
            return <PressScale key={value} accessibilityRole="radio" accessibilityLabel={t(themeLabels[value])} accessibilityState={{ selected }}
              onPress={() => setPreference(value)} scale={0.99} style={[local.option, index > 0 && local.optionBorder]}>
              <Text style={local.optionText}>{t(themeLabels[value])}</Text>
              {selected && <Icon name="check" size={22} color={colors.primaryText} />}
            </PressScale>;
          })}
        </View>
      </View>
      <View style={local.card}>
        <Text accessibilityRole="header" style={styles.title}>{t('aboutApp')}</Text>
        {versionLabel && <Text testID="settings-version" style={styles.muted}>{versionLabel}</Text>}
        {update.supported && <>
          <Button label={t('checkUpdates')} secondary disabled={update.status === 'checking'} onPress={() => { void update.checkNow(); }} />
          {statusText && <Text testID="update-status" accessibilityLiveRegion="polite" style={[local.status, update.status === 'error' && { color: colors.error }]}>{statusText}</Text>}
        </>}
      </View>
    </ScrollView>
  </SafeAreaView>;
}

const makeLocal = (c: Colors) => StyleSheet.create({
  card: { backgroundColor: c.surface, borderRadius: 22, padding: 20, gap: 12, borderWidth: 1, borderColor: c.cardBorder },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 50 },
  optionBorder: { borderTopWidth: 1, borderTopColor: c.border },
  optionText: { fontFamily: fonts.medium, fontSize: 16, color: c.text },
  status: { fontFamily: fonts.medium, fontSize: 14, lineHeight: 20, color: c.muted, textAlign: 'center' },
});
