import { cleanup, configure } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';

configure({ asyncUtilTimeout: 4000 });

// Polyfill web localStorage for Node 25+ environments where globalThis.localStorage is an empty stub
if (typeof window !== 'undefined' && typeof window.localStorage?.getItem !== 'function') {
  const store = new Map<string, string>();
  const mockStorage: Storage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => { store.set(key, String(value)); },
    removeItem: (key: string) => { store.delete(key); },
    clear: () => { store.clear(); },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() { return store.size; },
  };
  Object.defineProperty(window, 'localStorage', { value: mockStorage, writable: true, configurable: true });
}

afterEach(() => cleanup());
