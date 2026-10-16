import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query';
import { AppState } from 'react-native';
import { Session } from './session';
import { createDemoApi, DEMO_BASE_URL, DEMO_ENABLED, demoTokens } from '../demo/mockApi';
import { tokenStore, type TokenStore } from '../storage/secure';

// Demo build: preset session + in-memory API; never active unless EXPO_PUBLIC_DEMO=1 at build time.
const demoStore: TokenStore = { read: async () => demoTokens, write: async () => {}, clear: async () => {} };
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: ReactNode }) {
  const [query] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30000 }, mutations: { retry: false } } }));
  const [session] = useState(() => new Session(DEMO_ENABLED ? demoStore : tokenStore, DEMO_ENABLED ? DEMO_BASE_URL : process.env.EXPO_PUBLIC_API_BASE_URL ?? '', () => query.clear(), () => {
    void query.invalidateQueries({ refetchType: 'none' });
  }, DEMO_ENABLED ? createDemoApi() : undefined));
  useEffect(() => { void session.bootstrap(); }, [session]);
  useEffect(() => {
    const subscription = AppState.addEventListener('change', state => focusManager.setFocused(state === 'active'));
    return () => subscription.remove();
  }, []);
  return <Context.Provider value={session}><QueryClientProvider client={query}>{children}</QueryClientProvider></Context.Provider>;
}
export function useSession() {
  const session = useContext(Context);
  if (!session) throw new Error('SessionProvider is required');
  const state = useSyncExternalStore(session.subscribe, session.snapshot, session.snapshot);
  return { session, state, api: session.api };
}
