// Web build (preview only): the session lives in memory and is never written to localStorage.
// Native builds use secure.ts with the platform keychain / keystore.
import type { Tokens } from '../types/api';

export interface TokenStore { read(): Promise<Tokens | null>; write(tokens: Tokens): Promise<void>; clear(): Promise<void> }
let memory: Tokens | null = null;
export const tokenStore: TokenStore = {
  async read() { return memory; },
  async write(tokens) { memory = tokens; },
  async clear() { memory = null; },
};
const id = globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
export function deviceId(): Promise<string> { return Promise.resolve(id); }
