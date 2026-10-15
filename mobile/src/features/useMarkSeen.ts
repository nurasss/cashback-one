import { useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef } from 'react';
import { keys } from '../api/app';
import { useSession } from '../auth/provider';

// When a tab with "new" content is opened, tell the server once and refresh the tab bar badges.
export function useMarkSeen(path: '/me/promotions/seen' | '/me/notifications/read', hasNew: boolean) {
  const { api } = useSession();
  const query = useQueryClient();
  const sending = useRef(false);
  useFocusEffect(useCallback(() => {
    if (!hasNew || sending.current) return;
    sending.current = true;
    api.request<void>(path, { method: 'POST', auth: true })
      .then(() => query.invalidateQueries({ queryKey: keys.badges }))
      .catch(() => { /* Badge stays until the next successful visit. */ })
      .finally(() => { sending.current = false; });
  }, [api, hasNew, path, query]));
}
