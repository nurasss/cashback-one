// Web build (preview only): fallback to localStorage if available, otherwise in-memory.
// Native builds use secure.ts with the platform keychain / keystore.
import type { Tokens } from '../types/api';

export interface TokenStore { read(): Promise<Tokens | null>; write(tokens: Tokens): Promise<void>; clear(): Promise<void> }
const TOKEN_KEY = 'cashback-one.session.v1';

function getInitialTokens(): Tokens | null {
  if (typeof window !== 'undefined') {
    try {
      const raw = window.localStorage.getItem(TOKEN_KEY);
      if (raw) return JSON.parse(raw) as Tokens;
    } catch {
      return null;
    }
  }
  return null;
}

let memory: Tokens | null = getInitialTokens();
export const tokenStore: TokenStore = {
  async read() {
    if (!memory) memory = getInitialTokens();
    return memory;
  },
  async write(tokens) {
    memory = tokens;
    if (typeof window !== 'undefined') {
      try { window.localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens)); } catch { /* ignore */ }
    }
  },
  async clear() {
    memory = null;
    if (typeof window !== 'undefined') {
      try { window.localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
    }
  },
};
const id = globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
export function deviceId(): Promise<string> { return Promise.resolve(id); }
