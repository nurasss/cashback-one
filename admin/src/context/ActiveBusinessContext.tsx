import { createContext, useContext, useState, type PropsWithChildren } from 'react';

export interface ActiveBusinessInfo {
  id?: string | null;
  name?: string | null;
  android_app_id?: string | null;
}

export function isKeremetBusiness(business?: ActiveBusinessInfo | null): boolean {
  if (!business) return false;
  return business.android_app_id === 'kz.cashbackone.keremet';
}

interface ActiveBusinessContextValue {
  activeBusiness: ActiveBusinessInfo | null;
  setActiveBusiness: (biz: ActiveBusinessInfo | null) => void;
}

const ActiveBusinessContext = createContext<ActiveBusinessContextValue>({
  activeBusiness: null,
  setActiveBusiness: () => {},
});

export function ActiveBusinessProvider({ children }: PropsWithChildren) {
  const [activeBusiness, setActiveBusiness] = useState<ActiveBusinessInfo | null>(null);
  return (
    <ActiveBusinessContext.Provider value={{ activeBusiness, setActiveBusiness }}>
      {children}
    </ActiveBusinessContext.Provider>
  );
}

export function useActiveBusiness(): ActiveBusinessContextValue {
  return useContext(ActiveBusinessContext);
}
