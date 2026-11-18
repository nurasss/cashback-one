export interface Tokens { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export interface CodeRequestResult { status: string; expires_in: number }
export interface AppLoyaltyTier {
  id: string;
  level: number;
  priority: number;
  name_ru: string;
  name_kk: string;
  description_ru: string | null;
  description_kk: string | null;
  image_url: string | null;
  /** Historical value kept by the server for compatibility; lifetime turnover ignores it and the app never shows it. */
  turnover_period_months?: number;
  min_turnover: string;
  max_turnover: string | null;
  percent: string;
}

export interface CardLoyaltyStatus {
  known: boolean;
  reason?: 'unconfirmed' | 'stale' | 'no_match' | string | null;
  tier_id?: string | null;
  level?: number | null;
  name?: string | null;
  percent?: string | null;
  turnover_amount?: string | null;
  coverage_months?: number | null;
  calculated_at?: string | null;
  program_version?: number | null;
}

export interface Tier {
  level: number; name: string | null; percent: string; max_percent: string; spend_total: string | null;
  next_level: number | null; next_threshold: string | null; remaining: string | null;
  levels?: { level: number; name: string | null; threshold: string; percent: string }[];
}
export interface Card {
  id: string; barcode: string; balance: string; is_blocked: boolean; updated_at: string; bound_at: string; bind_method: string;
  business: { id: string; name: string; branding: { logo_url: string | null; primary_color: string | null; accent_color: string | null } | null };
  tier?: Tier | null;
  loyalty_status?: CardLoyaltyStatus | null;
}
export interface Transaction { id: string; external_id: string; type: string; amount: string; balance_after: string; occurred_at: string; receipt_ref: string | null; store: string | null }
export interface HistoryPage { items: Transaction[]; next_cursor: string | null; has_more: boolean }
export interface BusinessChoice { id: string; name: string }
export type Gender = 'male' | 'female';
export interface Profile {
  phone: string | null; language: string; first_name: string | null; last_name: string | null; email: string | null; gender: Gender | null;
  city: string | null; address: string | null; birth_date: string | null; iin: string | null; company: string | null;
  avatar_url?: string | null;
}
export interface Promotion {
  id: string; business_id: string | null; kind: 'banner' | 'offer'; title: string; subtitle: string | null; badge: string | null;
  body: string | null; image_url: string | null; starts_at: string | null; ends_at: string | null; is_new: boolean;
}
export interface Promotions { banners: Promotion[]; offers: Promotion[]; has_new: boolean }
export interface AppNotification { id: string; kind: string; title: string; body: string; created_at: string; is_unread: boolean }
export interface Notifications { items: AppNotification[]; unread_count: number }
export interface NotificationsMarkRead { read: string[]; already_read: string[]; ignored: string[]; unread_count: number }
export interface Badges { promotions_new: boolean; notifications_unread: number }
export interface CardQr { token: string; expires_at: string; ttl_seconds: number }
export interface WalletAvailability { apple: boolean; google: boolean }
export interface WalletLinkRequest { platform: 'apple' | 'google' }
export interface WalletLinkResponse { url: string; expires_at: string | null }
export interface AppStoreItem {
  id: string;
  title_ru: string;
  title_kk: string;
  address_ru: string;
  address_kk: string;
  map_url: string | null;
  sort_order: number;
  latitude?: number | null;
  longitude?: number | null;
}
export interface LocalizedText {
  ru?: string | null;
  kk?: string | null;
}
export interface CustomerAppTexts {
  // Standalone text of the home screen (max 2000 chars). Optional: an older server does not send it. Not shown next to the addresses.
  home_text?: LocalizedText | null;
  // Legacy "phrase before the address", kept by the server only for old app versions; the current app does not use it.
  home_store_note_lead?: LocalizedText | null;
  balance_delay_note?: LocalizedText | null;
}
export interface AppContent {
  business_id: string;
  stores: AppStoreItem[];
  app_texts: CustomerAppTexts;
  loyalty_tiers?: AppLoyaltyTier[];
  loyalty_tiers_version?: number;
  updated_at: string;
}
