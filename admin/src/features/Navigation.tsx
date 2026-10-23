import { NavLink } from 'react-router-dom';
import type { ComponentType, SVGProps } from 'react';
import type { AdminRole } from '../api/types';
import {
  IconOverview,
  IconBusinesses,
  IconAgents,
  IconCards,
  IconContent,
  IconAudit,
} from '../components/Icons';
import { useAdminTranslation } from '../i18n/admin';

export interface NavItem {
  path: string;
  label: string;
  navKey: 'overview' | 'businesses' | 'agents' | 'operations' | 'content' | 'audit';
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  roles: readonly AdminRole[];
}

export const adminNavigation: readonly NavItem[] = [
  { path: '/admin', navKey: 'overview', label: 'Обзор', icon: IconOverview, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/businesses', navKey: 'businesses', label: 'Бизнесы', icon: IconBusinesses, roles: ['superadmin'] },
  { path: '/admin/agents', navKey: 'agents', label: 'Агенты', icon: IconAgents, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/operations', navKey: 'operations', label: 'Карты и клиенты', icon: IconCards, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/content', navKey: 'content', label: 'Приложение', icon: IconContent, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/audit', navKey: 'audit', label: 'Журнал событий', icon: IconAudit, roles: ['superadmin', 'business_manager'] },
];

export function Navigation({ role }: { role: AdminRole }) {
  const t = useAdminTranslation();

  return (
    <nav className="side-nav" aria-label={t.layout.navAria}>
      {adminNavigation
        .filter(item => item.roles.includes(role))
        .map(item => {
          const Icon = item.icon;
          const label = t.layout.nav[item.navKey] ?? item.label;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/admin'}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              <span className="nav-icon" aria-hidden="true">
                <Icon />
              </span>
              <span className="nav-label">{label}</span>
            </NavLink>
          );
        })}
    </nav>
  );
}
