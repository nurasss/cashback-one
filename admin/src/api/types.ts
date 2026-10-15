export type AdminRole = 'superadmin' | 'business_manager';
export type AgentHealth = 'online' | 'stale' | 'never_connected' | 'error' | 'disabled';
export interface BusinessIdentity { id: string; name: string; status: string }
export interface AdminIdentity { id: string; login: string; role: AdminRole; business: BusinessIdentity | null }
export interface AdminMe { admin: AdminIdentity }
export interface Page<T> { items: T[]; limit: number; offset: number; has_more: boolean }
export interface Business {
  id: string; name: string; logo_url: string | null; colors: Record<string, unknown> | null;
  barcode_prefixes: string[] | null; status: string; loyalty_tiers?: LoyaltyTier[] | null; created_at: string; updated_at: string;
}
export interface LoyaltyTier { level: number; name?: string | null; threshold: string; percent: string }
export type PromotionKind = 'banner' | 'offer';
export interface Promotion {
  id: string; business_id: string | null; kind: PromotionKind; title: string; subtitle: string | null; badge: string | null;
  body: string | null; image_url: string | null; starts_at: string | null; ends_at: string | null; sort_order: number;
  is_active: boolean; created_at: string; updated_at: string;
}
export interface AppNotification { id: string; business_id: string | null; user_id: string | null; kind: string; title: string; body: string; created_at: string }
export interface BusinessDetail extends Business {
  cards_count: number; unblocked_cards_count: number; customers_with_cards_count: number; agents_count: number;
}
export interface Agent {
  id: string; business_id: string; business_name: string; status: string; health: AgentHealth;
  last_seen_at: string | null; version: string | null; last_sync_at: string | null; last_error: string | null; created_at: string;
}
export interface AgentKeyDisclosure { agent: Agent; api_key: string }
export interface AgentCommand { command_id: string; status: 'pending' | 'running' | 'completed' | 'failed'; execution: 'deferred' }
export interface CardUnbindResult { status: 'unbound' | 'already_unbound' }
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
export interface AuditItem {
  id: string; actor: string; admin_user_id: string | null; business_id: string | null;
  action: string; entity: string; before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null; created_at: string;
}
export interface AdminAccessToken { access_token: string; token_type: 'bearer'; expires_in: number }
export interface PageQuery { limit: number; offset: number }
