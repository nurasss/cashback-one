export type AdminRole = 'superadmin' | 'business_manager';
export type AgentHealth = 'online' | 'stale' | 'never_connected' | 'error' | 'disabled';
export interface BusinessIdentity { id: string; name: string; status: string }
export interface AdminIdentity { id: string; login: string; role: AdminRole; business: BusinessIdentity | null }
export interface AdminMe { admin: AdminIdentity }
export interface Page<T> { items: T[]; limit: number; offset: number; has_more: boolean }
export interface Business {
  id: string; name: string; logo_url: string | null; colors: Record<string, unknown> | null;
  barcode_prefixes: string[] | null; status: string; created_at: string; updated_at: string;
}
export interface BusinessDetail extends Business {
  cards_count: number; unblocked_cards_count: number; customers_with_cards_count: number; agents_count: number;
}
export interface Agent {
  id: string; business_id: string; business_name: string; status: string; health: AgentHealth;
  last_seen_at: string | null; version: string | null; last_sync_at: string | null; last_error: string | null; created_at: string;
}
export interface Dashboard {
  business_id: string | null; business_name: string | null; period_from: string; period_to: string; period_days: number;
  customers_with_business_cards: number; cards: number; unblocked_cards: number; transactions: number;
  agents: { online: number; stale: number; never_connected: number; error: number; disabled: number };
}
export interface Card {
  id: string; business_id: string; business_name: string; barcode: string; phone_masked: string | null;
  balance: string; is_blocked: boolean; updated_at: string; bind_method: string | null; bound_at: string | null; hidden_at: string | null;
}
export interface CardDetail extends Card { full_name: string | null; owner_language: string | null }
export interface AdminUser {
  id: string; phone_masked: string | null; language: string; created_at: string; business_cards_count: number;
}
export interface AdminUserDetail { id: string; phone: string | null; language: string; created_at: string; cards: Page<Card> }
export interface AuditItem { id: string; actor: string; action: string; entity: string; created_at: string }
export interface AdminAccessToken { access_token: string; token_type: 'bearer'; expires_in: number }
export interface PageQuery { limit: number; offset: number }
