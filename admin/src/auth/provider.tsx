import { createContext, useContext, useEffect, useState, useSyncExternalStore, type PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdminSession } from './session';

interface SessionContextValue {
  session: AdminSession;
  view: ReturnType<AdminSession['snapshot']>;
  continueToLogin(): void;
}
const SessionContext = createContext<SessionContextValue | null>(null);

export function AdminProvider({ children }: PropsWithChildren) {
  const [query] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 30_000 }, mutations: { retry: false } },
  }));
  const [session] = useState(() => new AdminSession(() => query.clear()));
  const view = useSyncExternalStore(session.subscribe, session.snapshot, session.snapshot);
  useEffect(() => { void session.bootstrap(); }, [session]);
  return (
    <SessionContext.Provider value={{ session, view, continueToLogin: () => session.continueToLogin() }}>
      <QueryClientProvider client={query}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
}

export function useAdminSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('AdminProvider is required');
  return value;
}
