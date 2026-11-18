import { Image as RNImage, type ImageSourcePropType, StyleSheet, Text, View } from 'react-native';
import { Image as ExpoImage } from 'expo-image';
import { useState } from 'react';
import { Icon } from '../components/icons';
import type { ClientStatus, ClientStatuses } from '../../clients/keremet/statuses';
import { useI18n, type Language } from '../i18n';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import { amountText, percentText } from '../utils/format';
import { getTierCondition, statusCondition, type CurrentStatus, type StatusCatalog } from './statuses';

// Strict check for valid HTTP/HTTPS media URL
export function isValidImageUrl(url: unknown): boolean {
  if (typeof url !== 'string' || !url.trim()) return false;
  const trimmed = url.trim();
  if (trimmed.startsWith('javascript:') || trimmed.startsWith('data:') || trimmed.startsWith('file:')) {
    return false;
  }
  return /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(trimmed);
}

// Status artwork: server image_url, client character artwork, or a neutral icon fallback.
// In both themes: never inverted, tinted, or substituted by characters of another business.
export function StatusArt({
  status,
  size,
}: {
  status: {
    image_url?: string | null;
    localImage?: unknown;
    image?: unknown;
    key?: string;
    name?: string;
    name_ru?: string | null;
    name_kk?: string | null;
  };
  size: number;
}) {
  const [loadError, setLoadError] = useState(false);
  const [lastUrl, setLastUrl] = useState(status.image_url);
  const { colors } = useTheme();
  const { language } = useI18n();
  const artLabel = (language === 'kz' ? status.name_kk : status.name_ru) || status.name;

  // Reset error when URL changes (e.g. after refresh or tier update)
  if (status.image_url !== lastUrl) {
    setLastUrl(status.image_url);
    setLoadError(false);
  }

  // Local image (legacy Keremet)
  const localImg = status.localImage ?? status.image;
  if (localImg) {
    return (
      <RNImage
        testID={`status-art-${status.key ?? 'local'}`}
        source={localImg as ImageSourcePropType}
        resizeMode="contain"
        accessibilityIgnoresInvertColors
        accessible
        accessibilityRole="image"
        accessibilityLabel={artLabel}
        style={{ width: size, height: size }}
      />
    );
  }

  // Server image_url (only if valid and no load error)
  const isValidUrl = isValidImageUrl(status.image_url);
  if (status.image_url && isValidUrl && !loadError) {
    return (
      <ExpoImage
        testID={`status-art-${status.key ?? 'image'}`}
        source={{ uri: status.image_url }}
        contentFit="contain"
        accessibilityIgnoresInvertColors
        accessible
        accessibilityRole="image"
        accessibilityLabel={artLabel}
        style={{ width: size, height: size, borderRadius: size > 64 ? 24 : 12 }}
        onError={() => setLoadError(true)}
      />
    );
  }

  // Neutral fallback: never show another business's character!
  return (
    <View
      testID={`status-art-${status.key ?? 'fallback'}`}
      style={[
        styles.fallback,
        {
          width: size,
          height: size,
          borderRadius: size > 64 ? 24 : 12,
          backgroundColor: colors.softPrimary,
          borderColor: colors.cardBorder,
        },
      ]}
      accessibilityRole="image"
      accessibilityLabel={artLabel}
    >
      <Icon name="crown" size={Math.round(size * 0.45)} color={colors.primaryText} />
    </View>
  );
}

export function useConditionText() {
  const { t } = useI18n();
  return (levels: readonly ClientStatus[], level: ClientStatus): string => {
    const condition = statusCondition(levels, level);
    return t(condition.key, {
      amount: amountText(String(condition.to ?? condition.from)),
      from: amountText(String(condition.from)),
      to: amountText(String(condition.to ?? 0)),
    });
  };
}

// The statuses with picture, name, condition and percent. Informational: needs no card and shows no personal data.
export function StatusCatalogList({
  catalog,
  current,
  language,
}: {
  catalog: StatusCatalog | ClientStatuses;
  current?: CurrentStatus | null;
  language?: Language;
}) {
  const { t } = useI18n();
  const themeStyles = useThemedStyles(makeStyles);
  const conditionLegacy = useConditionText();

  // If ClientStatuses (legacy)
  if ('levels' in catalog) {
    return (
      <View style={themeStyles.list} testID="status-catalog">
        {catalog.levels.map(level => {
          const isCurrent = current?.known === true && current.status.level === level.level;
          return (
            <View
              key={level.level}
              testID={`status-row-${level.key}`}
              style={[themeStyles.row, isCurrent && themeStyles.rowCurrent]}
              accessibilityState={{ selected: isCurrent }}
            >
              <StatusArt status={level} size={64} />
              <View style={themeStyles.texts}>
                <Text style={themeStyles.name}>{level.name}</Text>
                <Text style={themeStyles.condition}>{conditionLegacy(catalog.levels, level)}</Text>
              </View>
              <Text style={[themeStyles.percent, isCurrent && themeStyles.percentCurrent]}>
                {percentText(String(level.percent))}%
              </Text>
            </View>
          );
        })}
        <Text style={themeStyles.note}>{t('statusLifetimeNote')}</Text>
      </View>
    );
  }

  // Unified StatusCatalog (new server contract)
  const isKz = language === 'kz';
  return (
    <View style={themeStyles.list} testID="status-catalog">
      {catalog.tiers.map(tier => {
        const isCurrent = current?.known === true && current.status.level === tier.level;
        const name = (isKz ? tier.name_kk : tier.name_ru) || tier.name_ru;
        const desc = (isKz ? tier.description_kk : tier.description_ru) || tier.description_ru;
        const condText = getTierCondition(tier, t);
        const rowTestId = tier.key ? `status-row-${tier.key}` : `status-row-level-${tier.level}`;

        return (
          <View
            key={tier.id || tier.level}
            testID={rowTestId}
            style={[themeStyles.row, isCurrent && themeStyles.rowCurrent]}
            accessibilityState={{ selected: isCurrent }}
          >
            <StatusArt status={tier} size={64} />
            <View style={themeStyles.texts}>
              <Text style={themeStyles.name}>{name}</Text>
              {desc ? <Text style={themeStyles.description}>{desc}</Text> : null}
              <Text style={themeStyles.condition}>{condText}</Text>
            </View>
            <Text style={[themeStyles.percent, isCurrent && themeStyles.percentCurrent]}>
              {percentText(tier.percent)}%
            </Text>
          </View>
        );
      })}
      <Text style={themeStyles.note}>{t('statusLifetimeNote')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
});

const makeStyles = (c: Colors) =>
  StyleSheet.create({
    list: { gap: 10 },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 12,
      backgroundColor: c.input,
      borderRadius: 16,
      padding: 10,
      borderWidth: 1.5,
      borderColor: 'transparent',
    },
    rowCurrent: { backgroundColor: c.softPrimary, borderColor: c.primary },
    texts: { flex: 1, gap: 2 },
    name: { fontFamily: fonts.bold, fontSize: 16, color: c.text, lineHeight: 21 },
    description: { fontFamily: fonts.regular, fontSize: 12, color: c.muted, lineHeight: 16 },
    condition: { fontFamily: fonts.regular, fontSize: 13, color: c.muted, lineHeight: 18 },
    percent: { fontFamily: fonts.extrabold, fontSize: 22, color: c.text },
    percentCurrent: { color: c.primaryText },
    note: { fontFamily: fonts.medium, fontSize: 12, color: c.muted, textAlign: 'center', marginTop: 2 },
  });
