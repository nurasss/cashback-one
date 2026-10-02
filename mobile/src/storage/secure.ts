import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import { ApiError } from '../api/errors';
import type { Tokens } from '../types/api';
import { parseTokens } from '../auth/tokens';
export interface TokenStore { read(): Promise<Tokens | null>; write(tokens: Tokens): Promise<void>; clear(): Promise<void> }
const TOKEN_KEY = 'cashback-one.session.v1';
const DEVICE_KEY = 'cashback-one.device.v1';
const options = { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };
export const tokenStore: TokenStore = {
  async read() {
    try {
      const raw = await SecureStore.getItemAsync(TOKEN_KEY, options);
      if (!raw) return null;
      try { return parseTokens(JSON.parse(raw)); }
      catch { await tokenStore.clear(); return null; }
    } catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  },
  async write(tokens) {
    try { await SecureStore.setItemAsync(TOKEN_KEY, JSON.stringify(tokens), options); }
    catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  },
  async clear() {
    try { await SecureStore.deleteItemAsync(TOKEN_KEY, options); }
    catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  },
};
let devicePromise: Promise<string> | undefined;
export function deviceId(): Promise<string> {
  devicePromise ??= (async () => {
    try {
      let id = await SecureStore.getItemAsync(DEVICE_KEY, options);
      if (!id) { id = Crypto.randomUUID(); await SecureStore.setItemAsync(DEVICE_KEY, id, options); }
      return id;
    } catch { devicePromise = undefined; throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  })();
  return devicePromise;
}
