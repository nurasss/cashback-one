import { useEffect } from 'react';
import type { SessionView } from '../auth/session';
import type { AdminTranslations } from '../i18n/admin';

export interface DocumentTitleOptions {
  pathname: string;
  view?: SessionView;
  t: AdminTranslations;
}

export function resolveAdminDocumentTitle({ pathname, view, t }: DocumentTitleOptions): string {
  // Normalize path by stripping trailing slashes, keep root as /admin
  const cleanPath = pathname.replace(/\/+$/, '') || '/admin';

  if (cleanPath === '/admin/login' || cleanPath === '/login') {
    return `${t.login.cardTitle} — Cashback One Admin`;
  }

  const role = view && view.status === 'authenticated' ? view.admin.role : undefined;
  const isManager = role === 'business_manager';
  const businessName = isManager && view && view.status === 'authenticated'
    ? view.admin.business?.name?.trim()
    : undefined;

  const brandSuffix = isManager
    ? (businessName ? `${businessName} — Cashback One` : 'Cashback One')
    : 'Cashback One Admin';

  let section = '';

  if (cleanPath === '/admin' || cleanPath === '') {
    section = isManager ? t.layout.nav.home : t.layout.nav.overview;
  } else if (cleanPath === '/admin/operations') {
    section = isManager ? t.layout.nav.clients : t.layout.nav.operations;
  } else if (cleanPath === '/admin/content') {
    section = t.layout.nav.content;
  } else if (cleanPath === '/admin/statuses') {
    section = t.layout.nav.statuses;
  } else if (cleanPath === '/admin/notifications') {
    section = t.layout.nav.notifications;
  } else if (cleanPath === '/admin/settings') {
    section = t.layout.nav.settings;
  } else if (cleanPath === '/admin/businesses') {
    section = t.layout.nav.businesses;
  } else if (/^\/admin\/businesses\/[^/]+$/.test(cleanPath)) {
    section = t.layout.titles?.businessDetail || 'Бизнес';
  } else if (cleanPath === '/admin/agents') {
    section = t.layout.nav.agents;
  } else if (/^\/admin\/agents\/[^/]+$/.test(cleanPath)) {
    section = t.layout.titles?.agentDetail || 'Агент';
  } else if (/^\/admin\/cards\/[^/]+$/.test(cleanPath)) {
    section = t.layout.titles?.cardDetail || 'Карта';
  } else if (/^\/admin\/users\/[^/]+$/.test(cleanPath)) {
    section = t.layout.titles?.userDetail || 'Клиент';
  } else if (cleanPath === '/admin/audit') {
    section = t.layout.nav.audit;
  } else {
    section = t.routes.adminNotFoundTitle;
  }

  return `${section} — ${brandSuffix}`;
}

export function useAdminDocumentTitle(options: DocumentTitleOptions): void {
  const title = resolveAdminDocumentTitle(options);
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = title;
    }
  }, [title]);
}
