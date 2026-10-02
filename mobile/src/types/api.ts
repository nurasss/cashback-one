export interface Tokens { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export interface Challenge { challenge_id: string; code: string; login_url: string; expires_in: number; expires_at: string }
export interface ChallengeStatus { status: string; access_token?: string; refresh_token?: string; token_type?: string; expires_in?: number }
export interface SmsRequestResult { status: string; expires_in: number }
export interface Card {
  id: string; barcode: string; balance: string; is_blocked: boolean; updated_at: string; bound_at: string; bind_method: string;
  business: { id: string; name: string; branding: { logo_url: string | null; primary_color: string | null; accent_color: string | null } | null };
}
export interface Transaction { id: string; external_id: string; type: string; amount: string; balance_after: string; occurred_at: string; receipt_ref: string | null; store: string | null }
export interface HistoryPage { items: Transaction[]; next_cursor: string | null; has_more: boolean }
export interface BusinessChoice { id: string; name: string }
