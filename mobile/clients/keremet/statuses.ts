import type { ImageSourcePropType } from 'react-native';

// Keremet fallback loyalty statuses (used only when an older server omits `loyalty_tiers`). Thresholds do not overlap:
// turnover < 100 000 -> level 1; 100 000 <= turnover < 200 000 -> level 2; turnover >= 200 000 -> level 3.
// Images are 640 px derivatives of the owner's originals (docs/assets/keremet-statuses/, untouched); they are matched by the stable
// `level`/`key`, never by the (translatable) name. Names are brand names and stay in Russian in the Kazakh interface until the owner
// approves Kazakh names.
export interface ClientStatus {
  level: number;
  key: 'occasional' | 'expert' | 'boss';
  name: string;
  /** Lower bound in tenge, inclusive. The next level's threshold is the (exclusive) upper bound of this one. */
  threshold: number;
  /** Accrual percent shown for information; the cashier/ONE applies the real accrual. */
  percent: number;
  image: ImageSourcePropType;
}

export interface ClientStatuses {
  /**
   * Whether the server's `spend_total` is confirmed lifetime turnover. While false the app shows the
   * catalog for information only and "status data is not available yet" instead of a current status (switching this on
   * happens only after server confirmation via `loyalty_status`).
   */
  turnoverConfirmed: boolean;
  levels: ClientStatus[];
}

export const keremetStatuses: ClientStatuses = {
  turnoverConfirmed: false,
  levels: [
    { level: 1, key: 'occasional', name: 'Нет-нет заглядывает', threshold: 0, percent: 2, image: require('./statuses/occasional.png') as ImageSourcePropType },
    { level: 2, key: 'expert', name: 'Продуктовый эксперт', threshold: 100000, percent: 3, image: require('./statuses/expert.png') as ImageSourcePropType },
    { level: 3, key: 'boss', name: 'Шоппинг-босс', threshold: 200000, percent: 4, image: require('./statuses/boss.png') as ImageSourcePropType },
  ],
};
