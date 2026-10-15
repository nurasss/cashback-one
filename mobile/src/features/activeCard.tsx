import { createContext, useContext, useState, type ReactNode } from 'react';
import { useCards } from '../api/wallet';
import type { Card } from '../types/api';

// The card used for the QR, balance and status screens; defaults to the first card in the wallet.
const Context = createContext<{ selectedId: string | null; select: (id: string) => void } | null>(null);

export function ActiveCardProvider({ children }: { children: ReactNode }) {
  const [selectedId, select] = useState<string | null>(null);
  return <Context.Provider value={{ selectedId, select }}>{children}</Context.Provider>;
}

export function useActiveCard(): { card: Card | undefined; cards: ReturnType<typeof useCards>; select: (id: string) => void } {
  const context = useContext(Context);
  const cards = useCards();
  const list = cards.data ?? [];
  const card = list.find(item => item.id === context?.selectedId) ?? list[0];
  return { card, cards, select: context?.select ?? (() => {}) };
}
