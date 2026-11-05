import React from 'react';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle, type TextStyle } from 'react-native';
import { getClientConfig } from '../config/client';
import { useI18n } from '../i18n';
import { fonts, theme } from '../theme';

export interface BrandBadgeProps {
  height?: number;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export function BrandBadge({ height = 24, style, textStyle }: BrandBadgeProps) {
  const client = getClientConfig();
  const { t, language } = useI18n();

  if (client.Logo) {
    const LogoComponent = client.Logo;
    const appLabel =
      client.app_name[language === 'kz' ? 'kk' : 'ru'] ||
      client.app_name.ru ||
      client.android_label ||
      client.slug;
    return (
      <View style={{ alignSelf: 'flex-start' }}>
        <LogoComponent height={height} accessibilityLabel={appLabel} />
      </View>
    );
  }

  return (
    <View style={[styles.brandBadge, style]}>
      <Text style={[styles.brandBadgeText, textStyle]}>{t('bonusCurrency')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  brandBadge: {
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 4,
  },
  brandBadgeText: {
    fontFamily: fonts.extrabold,
    fontSize: 13,
    color: theme.colors.onPrimary,
    letterSpacing: 0.4,
  },
});
