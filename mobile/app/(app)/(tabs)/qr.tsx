import { useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Linking, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { requestWalletLink, useCardQr, useWalletAvailability } from '../../../src/api/app';
import { useSession } from '../../../src/auth/provider';
import { Button, Chip, EmptyState, ErrorNotice, Loading, ScreenHeader, styles } from '../../../src/components/ui';
import { Icon } from '../../../src/components/icons';
import { useActiveCard } from '../../../src/features/activeCard';
import { DynamicQr } from '../../../src/features/DynamicQr';
import { FadeIn, PressScale } from '../../../src/components/motion';
import { useI18n } from '../../../src/i18n';
import { fonts } from '../../../src/theme';

export default function QrScreen() {
  const { t } = useI18n();
  const { api } = useSession();
  const { card, cards, select } = useActiveCard();
  const qr = useCardQr(card && !card.is_blocked ? card.id : undefined);
  const wallet = useWalletAvailability({ enabled: Platform.OS !== 'web' });
  const [walletLoading, setWalletLoading] = useState(false);
  const [walletError, setWalletError] = useState<unknown | null>(null);

  const list = cards.data ?? [];
  const platform: 'apple' | 'google' | null =
    Platform.OS === 'ios' ? 'apple' : Platform.OS === 'android' ? 'google' : null;
  const isWalletAvailable =
    Platform.OS !== 'web' && platform !== null && Boolean(wallet.data?.[platform]);

  const handleAddToWallet = async () => {
    if (!card || !platform) return;
    setWalletLoading(true);
    setWalletError(null);
    try {
      const res = await requestWalletLink(api, card.id, platform);
      if (res?.url) {
        await Linking.openURL(res.url);
      }
    } catch (err) {
      setWalletError(err);
    } finally {
      setWalletLoading(false);
    }
  };

  const walletButtonLabel = platform === 'apple' ? t('addToAppleWallet') : t('addToGoogleWallet');

  return <SafeAreaView edges={['top']} style={styles.screen}>
    <ScreenHeader title={t('tabQr')} back onBack={() => router.navigate('/')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: 96 }]}>
      {cards.isPending ? <Loading /> : !card ? <EmptyState icon="card" title={t('noCardTitle')} body={t('noCardBody')}>
        <Button label={t('bind')} onPress={() => router.push('/bind')} style={{ alignSelf: 'stretch' }} />
      </EmptyState> : <>
        <FadeIn><DynamicQr qr={qr.data} loading={qr.isPending || qr.isFetching} failed={qr.isError} blocked={card.is_blocked} /></FadeIn>
        {isWalletAvailable && !card.is_blocked && (
          <FadeIn>
            <View style={{ gap: 8, alignItems: 'center', alignSelf: 'stretch' }}>
              <PressScale
                accessibilityRole="button"
                accessibilityLabel={walletButtonLabel}
                disabled={walletLoading}
                onPress={handleAddToWallet}
                scale={0.97}
                style={walletStyles.button}
              >
                {walletLoading ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <>
                    <Icon name="wallet" size={20} color="#FFFFFF" />
                    <Text style={walletStyles.buttonText}>{walletButtonLabel}</Text>
                  </>
                )}
              </PressScale>
              {walletError !== null && <ErrorNotice error={walletError} />}
            </View>
          </FadeIn>
        )}
        {list.length > 1 && <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          {list.map(item => <Chip key={item.id} label={item.business.name} selected={item.id === card.id} onPress={() => select(item.id)} />)}
        </View>}
      </>}
    </ScrollView>
  </SafeAreaView>;
}

const walletStyles = StyleSheet.create({
  button: {
    minHeight: 48,
    backgroundColor: '#000000',
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
    gap: 10,
    alignSelf: 'stretch',
  },
  buttonText: {
    fontFamily: fonts.semibold,
    fontSize: 15,
    color: '#FFFFFF',
    letterSpacing: -0.2,
  },
});
