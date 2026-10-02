import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query';
import { AppState } from 'react-native';
import { Session } from './session';
import { tokenStore } from '../storage/secure';
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: ReactNode }) {
  const [query] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30000 }, mutations: { retry: false } } }));
  const [session] = useState(() => new Session(tokenStore, process.env.EXPO_PUBLIC_API_BASE_URL ?? '', () => query.clear(), () => {
    void query.invalidateQueries({ refetchType: 'none' });
  }));
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
