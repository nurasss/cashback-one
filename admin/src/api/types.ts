export type AdminRole = 'superadmin' | 'business_manager';
export type AgentHealth = 'online' | 'stale' | 'never_connected' | 'error' | 'disabled';
export interface BusinessIdentity { id: string; name: string; status: string; logo_url?: string | null; android_app_id?: string | null }
export interface AdminIdentity { id: string; login: string; role: AdminRole; business: BusinessIdentity | null }
export interface AdminMe { admin: AdminIdentity; admin_max_stats_period_days: number }
export interface Page<T> { items: T[]; limit: number; offset: number; has_more: boolean }
export interface Business {
  id: string; name: string; logo_url: string | null; colors: Record<string, unknown> | null;
  barcode_prefixes: string[] | null; android_app_id?: string | null; status: string;
  loyalty_tiers?: BusinessLegacyTier[] | null; created_at: string; updated_at: string;
}
export interface BusinessLegacyTier { level: number; name?: string | null; threshold: string; percent: string }
export type PromotionKind = 'banner' | 'offer';
export interface Promotion {
  id: string; business_id: string | null; kind: PromotionKind; title: string; subtitle: string | null; badge: string | null;
  body: string | null; image_url: string | null; starts_at: string | null; ends_at: string | null; sort_order: number;
  is_active: boolean; created_at: string; updated_at: string;
}
export interface BroadcastPushResult {
  status: 'sent' | 'disabled' | 'skipped' | 'failed';
  devices: number;
  delivered: number;
}

export interface AppNotification {
  id: string;
  business_id: string | null;
  user_id: string | null;
  kind: string;
  title: string;
  body: string;
  created_at: string;
  scheduled_at?: string | null;
  push_sent_at?: string | null;
  push?: BroadcastPushResult | null;
}
export interface BusinessDetail extends Business {
  cards_count: number; unblocked_cards_count: number; customers_with_cards_count: number; agents_count: number;
}
export interface ManagerAccessDisclosure {
  login: string;
  password: string;
  login_url: string;
  one_time: true;
}
export interface BusinessCreatedResponse extends BusinessDetail {
  manager_access?: ManagerAccessDisclosure | null;
}
export interface Agent {
  id: string; business_id: string; business_name: string; status: string; health: AgentHealth;
  last_seen_at: string | null; version: string | null; last_sync_at: string | null; last_error: string | null; created_at: string;
}
export interface AgentKeyDisclosure { agent: Agent; api_key: string }
export interface PosKey {
  id: string;
  business_id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  status: 'active' | 'revoked';
}
export interface PosKeyDisclosure {
  pos_key: PosKey;
  api_key: string;
}
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
export interface ImageUploadResponse {
  url: string;
  width: number;
  height: number;
  bytes: number;
}
export interface LocalizedText {
  ru: string | null;
  kk: string | null;
}
export interface StoreCoordinateCandidate {
  address: string;
  latitude: number;
  longitude: number;
}

export interface StoreResolveCoordinatesResponse {
  status: 'found' | 'ambiguous' | 'not_found' | 'error';
  message?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  resolved_address?: string | null;
  candidates?: StoreCoordinateCandidate[];
}

export interface BusinessStore {
  id: string;
  business_id: string;
  title_ru: string;
  title_kk: string;
  address_ru: string;
  address_kk: string;
  map_url: string | null;
  sort_order: number;
  is_active: boolean;
  latitude?: number | null;
  longitude?: number | null;
  created_at: string;
  updated_at: string;
}
export interface AppTexts {
  home_text?: LocalizedText;
  home_store_note_lead: LocalizedText;
  balance_delay_note: LocalizedText;
}
export interface BusinessStoreInput {
  title_ru: string;
  title_kk: string;
  address_ru: string;
  address_kk: string;
  map_url?: string | null;
  sort_order?: number;
  is_active?: boolean;
  latitude?: number | null;
  longitude?: number | null;
}
export interface LoyaltyTier {
  id: string;
  business_id: string;
  level: number;
  priority: number;
  name_ru: string;
  name_kk: string;
  description_ru: string | null;
  description_kk: string | null;
  image_url: string | null;
  turnover_period_months: number;
  min_turnover: string;
  max_turnover: string | null;
  percent: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface LoyaltyTierInput {
  level: number;
  priority?: number;
  name_ru: string;
  name_kk: string;
  description_ru?: string | null;
  description_kk?: string | null;
  image_url?: string | null;
  turnover_period_months: number;
  min_turnover: number | string;
  max_turnover?: number | string | null;
  percent: number | string;
  is_active?: boolean;
}
export interface BusinessSplashConfig {
  business_id: string;
  enabled: boolean;
  media_type: 'image' | 'video' | null;
  media_url: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  file_size: number | null;
  version: string | null;
}
export interface BusinessSplashUpdateRequest {
  enabled: boolean;
  media_type?: 'image' | 'video' | null;
  media_url?: string | null;
  width?: number | null;
  height?: number | null;
  duration_seconds?: number | null;
  file_size?: number | null;
}
export interface SplashMediaUploadResponse {
  media_type: 'image' | 'video';
  url: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  bytes: number;
}
