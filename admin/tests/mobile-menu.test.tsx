import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminLayout } from '../src/layout/AdminLayout';
import { LocaleProvider, LOCALE_STORAGE_KEY } from '../src/i18n/LocaleContext';
import { adminRu, adminKk, getAdminTranslations } from '../src/i18n/admin';
import type { AdminRole } from '../src/api/types';

let currentRole: AdminRole = 'superadmin';

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    session: { logout: vi.fn() },
    view: {
      status: 'authenticated',
      admin: {
        id: 'fixture-admin',
        login: 'fixture.admin',
        role: currentRole,
        business: currentRole === 'business_manager' ? { id: 'biz-1', name: 'Fixture Store' } : null,
      },
    },
  }),
}));

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
}

function renderLayout(locale: 'ru' | 'kk' = 'ru', initialRoute = '/admin') {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  document.documentElement.lang = locale;
  return render(
    <LocaleProvider>
      <MemoryRouter initialEntries={[initialRoute]}>
        <AdminLayout>
          <LocationDisplay />
          <Routes>
            <Route path="/admin" element={<div>Overview Screen</div>} />
            <Route path="/admin/agents" element={<div>Agents Screen</div>} />
            <Route path="/admin/businesses" element={<div>Businesses Screen</div>} />
            <Route path="/admin/operations" element={<div>Operations Screen</div>} />
            <Route path="/admin/content" element={<div>Content Screen</div>} />
            <Route path="/admin/audit" element={<div>Audit Screen</div>} />
          </Routes>
        </AdminLayout>
      </MemoryRouter>
    </LocaleProvider>,
  );
}

afterEach(() => {
  cleanup();
  currentRole = 'superadmin';
  document.body.style.overflow = '';
  document.documentElement.lang = 'ru';
});

describe('Mobile Menu (admin/src/layout/AdminLayout)', () => {
  it('contains expected layout translation strings in RU and KK', () => {
    expect(adminRu.layout.openMenu).toBe('Открыть меню');
    expect(adminRu.layout.closeMenu).toBe('Закрыть меню');
    expect(adminKk.layout.openMenu).toBe('Мәзірді ашу');
    expect(adminKk.layout.closeMenu).toBe('Мәзірді жабу');

    expect(getAdminTranslations('ru').layout.openMenu).toBe('Открыть меню');
    expect(getAdminTranslations('ru').layout.closeMenu).toBe('Закрыть меню');
    expect(getAdminTranslations('kk').layout.openMenu).toBe('Мәзірді ашу');
    expect(getAdminTranslations('kk').layout.closeMenu).toBe('Мәзірді жабу');
  });

  describe.each(['ru', 'kk'] as const)('locale: %s', (locale) => {
    const t = locale === 'ru' ? adminRu : adminKk;

    it('toggles menu with button, updates aria-expanded and is-open class', async () => {
      const user = userEvent.setup();
      renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar');
      expect(sidebar).toBeInTheDocument();
      expect(sidebar).toHaveAttribute('id', 'admin-sidebar');
      expect(sidebar?.classList.contains('is-open')).toBe(false);
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
      expect(toggleBtn).toHaveAttribute('aria-controls', 'admin-sidebar');

      // Click button -> menu opens
      await user.click(toggleBtn);
      expect(sidebar?.classList.contains('is-open')).toBe(true);
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');

      // Click button again -> menu closes
      await user.click(toggleBtn);
      expect(sidebar?.classList.contains('is-open')).toBe(false);
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    });

    it('focuses the first link in the sidebar when opened', async () => {
      const user = userEvent.setup();
      renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar')!;
      const firstLink = sidebar.querySelector('a')!;
      expect(firstLink).toBeTruthy();

      await user.click(toggleBtn);
      expect(document.activeElement).toBe(firstLink);
    });

    it('closes on backdrop click and returns focus to menu button', async () => {
      const user = userEvent.setup();
      renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar')!;

      await user.click(toggleBtn);
      expect(sidebar.classList.contains('is-open')).toBe(true);

      const backdrop = screen.getByRole('button', { name: t.layout.closeMenu });
      expect(backdrop).toBeInTheDocument();
      expect(backdrop).toHaveClass('sidebar-backdrop');

      await user.click(backdrop);
      expect(sidebar.classList.contains('is-open')).toBe(false);
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
      expect(document.activeElement).toBe(toggleBtn);
    });

    it('closes on Escape key and returns focus to menu button', async () => {
      const user = userEvent.setup();
      renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar')!;

      await user.click(toggleBtn);
      expect(sidebar.classList.contains('is-open')).toBe(true);

      fireEvent.keyDown(window, { key: 'Escape' });
      expect(sidebar.classList.contains('is-open')).toBe(false);
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
      expect(document.activeElement).toBe(toggleBtn);
    });

    it('closes on section navigation link click, changes route, and does not return focus to menu button', async () => {
      const user = userEvent.setup();
      renderLayout(locale, '/admin');

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar')!;

      await user.click(toggleBtn);
      expect(sidebar.classList.contains('is-open')).toBe(true);

      const agentsLink = screen.getByRole('link', { name: new RegExp(t.layout.nav.agents) });
      expect(agentsLink).toBeInTheDocument();

      await user.click(agentsLink);
      expect(sidebar.classList.contains('is-open')).toBe(false);
      expect(screen.getByTestId('location-path')).toHaveTextContent('/admin/agents');
      expect(document.activeElement).not.toBe(toggleBtn);
    });

    it('locks body scroll when open and restores scroll on close and unmount', async () => {
      const user = userEvent.setup();
      const { unmount } = renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      expect(document.body.style.overflow).not.toBe('hidden');

      // Open -> scroll locked
      await user.click(toggleBtn);
      expect(document.body.style.overflow).toBe('hidden');

      // Close -> scroll restored
      await user.click(toggleBtn);
      expect(document.body.style.overflow).toBe('');

      // Open again -> unmount -> scroll restored
      await user.click(toggleBtn);
      expect(document.body.style.overflow).toBe('hidden');
      unmount();
      expect(document.body.style.overflow).toBe('');
    });

    it('closes when window resizes wider than 760px', async () => {
      const user = userEvent.setup();
      renderLayout(locale);

      const toggleBtn = screen.getByRole('button', { name: t.layout.openMenu });
      const sidebar = document.getElementById('admin-sidebar')!;

      await user.click(toggleBtn);
      expect(sidebar.classList.contains('is-open')).toBe(true);

      // Simulate resize > 760px
      window.innerWidth = 1024;
      fireEvent(window, new Event('resize'));
      expect(sidebar.classList.contains('is-open')).toBe(false);
    });
  });

  describe('Role-based navigation', () => {
    it('business_manager cannot see Businesses section', () => {
      currentRole = 'business_manager';
      renderLayout('ru');

      expect(screen.queryByRole('link', { name: /Бизнесы/ })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Обзор/ })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Агенты/ })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Карты и клиенты/ })).toBeInTheDocument();
    });

    it('superadmin sees Businesses section', () => {
      currentRole = 'superadmin';
      renderLayout('ru');

      expect(screen.getByRole('link', { name: /Бизнесы/ })).toBeInTheDocument();
    });

    it('business_manager cannot see Businesses section in KK', () => {
      currentRole = 'business_manager';
      renderLayout('kk');

      expect(screen.queryByRole('link', { name: /Бизнестер/ })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Шолу/ })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Агенттер/ })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Карталар мен клиенттер/ })).toBeInTheDocument();
    });
  });
});
