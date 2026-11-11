import { NavLink, useLocation } from 'react-router-dom';
import type { ComponentType, SVGProps } from 'react';
import type { AdminRole } from '../api/types';
import {
  IconOverview,
  IconBusinesses,
  IconAgents,
  IconCards,
  IconContent,
  IconStatus,
  IconAudit,
  IconSend,
  IconSettings,
} from '../components/Icons';
import { useAdminTranslation } from '../i18n/admin';

export interface NavItem {
  path: string;
  label: string;
  navKey:
    | 'overview'
    | 'home'
    | 'businesses'
    | 'agents'
    | 'operations'
    | 'clients'
    | 'statuses'
    | 'content'
    | 'notifications'
    | 'audit'
    | 'settings';
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  roles: readonly AdminRole[];
  secondary?: boolean;
}

export const adminNavigation: readonly NavItem[] = [
  // Superadmin
  { path: '/admin', navKey: 'overview', label: 'Обзор', icon: IconOverview, roles: ['superadmin'] },
  { path: '/admin/businesses', navKey: 'businesses', label: 'Бизнесы', icon: IconBusinesses, roles: ['superadmin'] },
  { path: '/admin/agents', navKey: 'agents', label: 'Агенты', icon: IconAgents, roles: ['superadmin'] },
  { path: '/admin/operations', navKey: 'operations', label: 'Карты и клиенты', icon: IconCards, roles: ['superadmin'] },
  { path: '/admin/statuses', navKey: 'statuses', label: 'Статусы', icon: IconStatus, roles: ['superadmin'] },
  { path: '/admin/content', navKey: 'content', label: 'Приложение', icon: IconContent, roles: ['superadmin'] },
  { path: '/admin/audit', navKey: 'audit', label: 'Журнал событий', icon: IconAudit, roles: ['superadmin'] },

  // Business Manager (client cabinet)
  { path: '/admin', navKey: 'home', label: 'Главная', icon: IconOverview, roles: ['business_manager'] },
  { path: '/admin/operations', navKey: 'clients', label: 'Клиенты', icon: IconCards, roles: ['business_manager'] },
  { path: '/admin/statuses', navKey: 'statuses', label: 'Статусы', icon: IconStatus, roles: ['business_manager'] },
  { path: '/admin/content', navKey: 'content', label: 'Приложение', icon: IconContent, roles: ['business_manager'] },
  { path: '/admin/notifications', navKey: 'notifications', label: 'Рассылки', icon: IconSend, roles: ['business_manager'] },
  { path: '/admin/settings', navKey: 'settings', label: 'Настройки', icon: IconSettings, roles: ['business_manager'], secondary: true },
];

export function isNavActive(item: NavItem, currentPath: string, role: AdminRole): boolean {
  if (item.path === '/admin') {
    return currentPath === '/admin';
  }
  if (item.path === '/admin/operations') {
    return (
      currentPath === '/admin/operations' ||
      currentPath.startsWith('/admin/operations/') ||
      currentPath.startsWith('/admin/cards') ||
      currentPath.startsWith('/admin/users')
    );
  }
  if (item.path === '/admin/settings') {
    return (
      currentPath === '/admin/settings' ||
      currentPath.startsWith('/admin/settings/') ||
      (role === 'business_manager' &&
        (currentPath.startsWith('/admin/agents') || currentPath.startsWith('/admin/audit')))
    );
  }
  if (item.path === '/admin/businesses') {
    return currentPath.startsWith('/admin/businesses');
  }
  if (item.path === '/admin/agents') {
    return currentPath.startsWith('/admin/agents');
  }
  if (item.path === '/admin/statuses') {
    return currentPath.startsWith('/admin/statuses');
  }
  if (item.path === '/admin/content') {
    return currentPath.startsWith('/admin/content');
  }
  if (item.path === '/admin/notifications') {
    return currentPath.startsWith('/admin/notifications');
  }
  if (item.path === '/admin/audit') {
    return currentPath.startsWith('/admin/audit');
  }
  return currentPath === item.path;
}

export function Navigation({ role }: { role: AdminRole }) {
  const t = useAdminTranslation();
  const location = useLocation();

  const items = adminNavigation.filter(item => item.roles.includes(role));
  const mainItems = items.filter(item => !item.secondary);
  const secondaryItems = items.filter(item => item.secondary);

  const renderLink = (item: NavItem) => {
    const Icon = item.icon;
    const label = t.layout.nav[item.navKey] ?? item.label;
    const active = isNavActive(item, location.pathname, role);

    return (
      <NavLink
        key={`${item.roles.join('-')}-${item.path}-${item.navKey}`}
        to={item.path}
        end={item.path === '/admin'}
        className={active ? 'nav-link active' : 'nav-link'}
        aria-current={active ? 'page' : undefined}
        onClick={() => {
          if (active && item.path === '/admin') {
            window.dispatchEvent(new Event('admin-dashboard-reset'));
          }
        }}
      >
        <span className="nav-icon" aria-hidden="true">
          <Icon />
        </span>
        <span className="nav-label">{label}</span>
      </NavLink>
    );
  };

  return (
    <nav className="side-nav" aria-label={t.layout.navAria}>
      <div className="nav-main">
        {mainItems.map(renderLink)}
      </div>
      {secondaryItems.length > 0 && (
        <div className="nav-secondary">
          {secondaryItems.map(renderLink)}
        </div>
      )}
    </nav>
  );
}
