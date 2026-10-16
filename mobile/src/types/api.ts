export interface Tokens { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export interface CodeRequestResult { status: string; expires_in: number }
export interface Tier {
  level: number; name: string | null; percent: string; max_percent: string; spend_total: string | null;
  next_level: number | null; next_threshold: string | null; remaining: string | null;
  levels?: { level: number; name: string | null; threshold: string; percent: string }[];
}
export interface Card {
  id: string; barcode: string; balance: string; is_blocked: boolean; updated_at: string; bound_at: string; bind_method: string;
  business: { id: string; name: string; branding: { logo_url: string | null; primary_color: string | null; accent_color: string | null } | null };
  tier?: Tier | null;
}
export interface Transaction { id: string; external_id: string; type: string; amount: string; balance_after: string; occurred_at: string; receipt_ref: string | null; store: string | null }
export interface HistoryPage { items: Transaction[]; next_cursor: string | null; has_more: boolean }
export interface BusinessChoice { id: string; name: string }
export type Gender = 'male' | 'female';
export interface Profile {
  phone: string | null; language: string; first_name: string | null; last_name: string | null; email: string | null; gender: Gender | null;
  city: string | null; address: string | null; birth_date: string | null; iin: string | null; company: string | null;
}
export interface Promotion {
  id: string; business_id: string | null; kind: 'banner' | 'offer'; title: string; subtitle: string | null; badge: string | null;
  body: string | null; image_url: string | null; starts_at: string | null; ends_at: string | null; is_new: boolean;
}
export interface Promotions { banners: Promotion[]; offers: Promotion[]; has_new: boolean }
export interface AppNotification { id: string; kind: string; title: string; body: string; created_at: string; is_unread: boolean }
export interface Notifications { items: AppNotification[]; unread_count: number }
export interface Badges { promotions_new: boolean; notifications_unread: number }
export interface CardQr { token: string; expires_at: string; ttl_seconds: number }
