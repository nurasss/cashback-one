import { Platform } from 'react-native';
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
      if (Platform.OS === 'web') {
        const raw = typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
        if (!raw) return null;
        try { return parseTokens(JSON.parse(raw)); }
        catch { await tokenStore.clear(); return null; }
      }
      const raw = await SecureStore.getItemAsync(TOKEN_KEY, options);
      if (!raw) return null;
      try { return parseTokens(JSON.parse(raw)); }
      catch { await tokenStore.clear(); return null; }
    } catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  },
  async write(tokens) {
    try {
      if (Platform.OS === 'web') {
        if (typeof window !== 'undefined') window.localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
        return;
      }
      await SecureStore.setItemAsync(TOKEN_KEY, JSON.stringify(tokens), options);
    } catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
  },
  async clear() {
    try {
      if (Platform.OS === 'web') {
        if (typeof window !== 'undefined') window.localStorage.removeItem(TOKEN_KEY);
        return;
      }
      await SecureStore.deleteItemAsync(TOKEN_KEY, options);
    } catch { throw new ApiError('SECURE_STORAGE_UNAVAILABLE'); }
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
