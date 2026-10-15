import { NavLink } from 'react-router-dom';
import type { AdminRole } from '../api/types';

interface NavItem { path: string; label: string; icon: string; roles: readonly AdminRole[] }
export const adminNavigation: readonly NavItem[] = [
  { path: '/', label: 'Обзор', icon: '▦', roles: ['superadmin', 'business_manager'] },
  { path: '/businesses', label: 'Бизнесы', icon: '◫', roles: ['superadmin'] },
  { path: '/agents', label: 'Агенты', icon: '⌁', roles: ['superadmin', 'business_manager'] },
  { path: '/operations', label: 'Карты и клиенты', icon: '▤', roles: ['superadmin', 'business_manager'] },
  { path: '/content', label: 'Приложение', icon: '◈', roles: ['superadmin', 'business_manager'] },
  { path: '/audit', label: 'Журнал событий', icon: '≋', roles: ['superadmin', 'business_manager'] },
];

export function Navigation({ role }: { role: AdminRole }) {
  return (
    <nav className="side-nav" aria-label="Основная навигация">
      {adminNavigation.filter(item => item.roles.includes(role)).map(item => (
        <NavLink key={item.path} to={item.path} end={item.path === '/'} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          <span className="nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
