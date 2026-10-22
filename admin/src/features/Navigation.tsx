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

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  roles: readonly AdminRole[];
}

export const adminNavigation: readonly NavItem[] = [
  { path: '/admin', label: 'Обзор', icon: IconOverview, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/businesses', label: 'Бизнесы', icon: IconBusinesses, roles: ['superadmin'] },
  { path: '/admin/agents', label: 'Агенты', icon: IconAgents, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/operations', label: 'Карты и клиенты', icon: IconCards, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/content', label: 'Приложение', icon: IconContent, roles: ['superadmin', 'business_manager'] },
  { path: '/admin/audit', label: 'Журнал событий', icon: IconAudit, roles: ['superadmin', 'business_manager'] },
];

export function Navigation({ role }: { role: AdminRole }) {
  return (
    <nav className="side-nav" aria-label="Основная навигация">
      {adminNavigation.filter(item => item.roles.includes(role)).map(item => {
        const Icon = item.icon;
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
            <span className="nav-label">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
