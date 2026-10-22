import type { ImageSourcePropType } from 'react-native';
import type { Dictionary } from '../i18n/ru';

export type PermanentOfferKey = 'offerHitsDiscount' | 'offerWeeklyPromo' | 'offerCardBonus' | 'offerFreshProducts';

export type PermanentOffer = {
  id: 'hits-discount' | 'weekly-promo' | 'card-bonus' | 'fresh-products';
  labelKey: PermanentOfferKey;
  image: ImageSourcePropType;
};

export const LOCAL_BANNER = {
  id: 'local-car-prize',
  labelKey: 'bannerCarPrize' as keyof Dictionary,
  image: require('../../assets/promotions/banner-car-prize.png') as ImageSourcePropType,
};

export const PERMANENT_OFFERS: readonly PermanentOffer[] = [
  {
    id: 'hits-discount',
    labelKey: 'offerHitsDiscount',
    image: require('../../assets/promotions/offer-hits-discount.png') as ImageSourcePropType,
  },
  {
    id: 'weekly-promo',
    labelKey: 'offerWeeklyPromo',
    image: require('../../assets/promotions/offer-weekly-promo.png') as ImageSourcePropType,
  },
  {
    id: 'card-bonus',
    labelKey: 'offerCardBonus',
    image: require('../../assets/promotions/offer-card-bonus.png') as ImageSourcePropType,
  },
  {
    id: 'fresh-products',
    labelKey: 'offerFreshProducts',
    image: require('../../assets/promotions/offer-fresh-products.png') as ImageSourcePropType,
  },
] as const;
