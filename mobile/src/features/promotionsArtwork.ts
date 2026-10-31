import type { ImageSourcePropType } from 'react-native';

export type PermanentOfferKey = 'offerHitsDiscount' | 'offerWeeklyPromo' | 'offerCardBonus' | 'offerFreshProducts';

export type PermanentOffer = {
  id: 'hits-discount' | 'weekly-promo' | 'card-bonus' | 'fresh-products';
  labelKey: PermanentOfferKey;
  image: ImageSourcePropType;
};

export type LocalBanner = {
  id: 'local-car-prize' | 'local-coffee-machine' | 'local-stickers';
  labelKey: 'bannerCarPrize' | 'bannerCoffeeMachine' | 'bannerStickers';
  image: ImageSourcePropType;
  aspectRatio: number;
};

export const LOCAL_BANNERS: readonly LocalBanner[] = [
  {
    id: 'local-car-prize',
    labelKey: 'bannerCarPrize',
    image: require('../../assets/promotions/banner-car-prize.png') as ImageSourcePropType,
    aspectRatio: 675 / 294,
  },
  {
    id: 'local-coffee-machine',
    labelKey: 'bannerCoffeeMachine',
    image: require('../../assets/promotions/banner-coffee-machine.png') as ImageSourcePropType,
    aspectRatio: 2000 / 862,
  },
  {
    id: 'local-stickers',
    labelKey: 'bannerStickers',
    image: require('../../assets/promotions/banner-stickers.png') as ImageSourcePropType,
    aspectRatio: 2000 / 860,
  },
] as const;

export type PromotionBodyKey = 'offerHitsDiscountBody' | 'offerCardBonusBody' | 'offerWeeklyPromoBody' | 'offerFreshProductsBody';

export type PromotionCard = {
  id: 'art-hits-discount' | 'art-card-bonus' | 'art-weekly-promo' | 'art-fresh-products';
  image: ImageSourcePropType;
  titleKey: PermanentOfferKey;
  bodyKey: PromotionBodyKey;
};

export const PROMOTION_CARDS: readonly PromotionCard[] = [
  {
    id: 'art-hits-discount',
    image: require('../../assets/promotions/promo-hits-discount.png') as ImageSourcePropType,
    titleKey: 'offerHitsDiscount',
    bodyKey: 'offerHitsDiscountBody',
  },
  {
    id: 'art-card-bonus',
    image: require('../../assets/promotions/promo-card-bonus.png') as ImageSourcePropType,
    titleKey: 'offerCardBonus',
    bodyKey: 'offerCardBonusBody',
  },
  {
    id: 'art-weekly-promo',
    image: require('../../assets/promotions/promo-weekly.png') as ImageSourcePropType,
    titleKey: 'offerWeeklyPromo',
    bodyKey: 'offerWeeklyPromoBody',
  },
  {
    id: 'art-fresh-products',
    image: require('../../assets/promotions/promo-fresh-products.png') as ImageSourcePropType,
    titleKey: 'offerFreshProducts',
    bodyKey: 'offerFreshProductsBody',
  },
] as const;

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
