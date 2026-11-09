import { useCallback, useMemo } from 'react';
import { Alert, Linking, Text, type StyleProp, type TextStyle } from 'react-native';
import { getClientConfig } from '../config/client';
import { useI18n } from '../i18n';
import { useTheme } from '../theme/ThemeProvider';
import { splitLinks } from '../utils/links';

// Text with tappable http(s) links (see src/utils/links.ts). Text without links renders exactly as a plain <Text>.
// A link opens in the external browser only on tap: never automatically, and no API tokens are attached.
export function LinkedText({ text, style }: { text: string; style?: StyleProp<TextStyle> }) {
  const { t, language } = useI18n();
  const { colors } = useTheme();
  const segments = useMemo(() => splitLinks(text), [text]);

  const open = useCallback(async (url: string) => {
    try {
      // No canOpenURL pre-check: on Android 11+ it needs extra manifest queries; a rejection is handled here instead.
      await Linking.openURL(url);
    } catch {
      let title = t('app');
      try { title = getClientConfig().app_name[language === 'kz' ? 'kk' : 'ru'] || title; } catch { /* keep the default title */ }
      Alert.alert(title, t('linkOpenFailed'));
    }
  }, [language, t]);

  if (!segments.some(segment => segment.url !== undefined)) return <Text style={style}>{text}</Text>;
  return <Text style={style}>
    {segments.map((segment, index) => segment.url
      ? <Text key={index} accessibilityRole="link" onPress={() => { void open(segment.url!); }}
        style={{ color: colors.primaryText, textDecorationLine: 'underline' }}>{segment.text}</Text>
      : segment.text)}
  </Text>;
}
