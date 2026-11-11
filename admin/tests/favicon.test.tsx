import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { isKeremetBusiness, ActiveBusinessProvider, useActiveBusiness } from '../src/context/ActiveBusinessContext';
import { AdminLayout } from '../src/layout/AdminLayout';
import type { SessionView } from '../src/auth/session';

let mockView: SessionView = {
  status: 'authenticated',
  admin: {
    id: 'u-1',
    login: 'manager_keremet',
    role: 'business_manager',
    business: { id: 'b-1', name: 'Keremet Bonus', status: 'active', android_app_id: 'kz.cashbackone.keremet' },
  },
};

const mockSession = {
  logout: async () => {},
};

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    session: mockSession,
    view: mockView,
  }),
}));

describe('Favicon & Active Business', () => {
  let faviconLink: HTMLLinkElement;

  beforeEach(() => {
    faviconLink = document.createElement('link');
    faviconLink.rel = 'icon';
    faviconLink.href = '/brand-mark.png';
    document.head.appendChild(faviconLink);
  });

  afterEach(() => {
    faviconLink.remove();
  });

  it('isKeremetBusiness identifies Keremet strictly by android_app_id, name without app_id yields false', () => {
    expect(isKeremetBusiness({ android_app_id: 'kz.cashbackone.keremet' })).toBe(true);
    expect(isKeremetBusiness({ name: 'Керемет', android_app_id: 'kz.cashbackone.keremet' })).toBe(true);
    expect(isKeremetBusiness({ name: 'Керемет' })).toBe(false);
    expect(isKeremetBusiness({ name: 'Керемет', android_app_id: null })).toBe(false);
    expect(isKeremetBusiness({ name: 'Keremet Bonus' })).toBe(false);
    expect(isKeremetBusiness({ name: 'Super Store', android_app_id: 'kz.other.store' })).toBe(false);
    expect(isKeremetBusiness(null)).toBe(false);
    expect(isKeremetBusiness(undefined)).toBe(false);
  });

  it('business with name "Керемет" without android_app_id retains general favicon', () => {
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-1',
        login: 'manager_keremet',
        role: 'business_manager',
        business: { id: 'b-1', name: 'Керемет', status: 'active', android_app_id: null },
      },
    };

    render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <div>Dashboard Content</div>
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>
    );

    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });

  it('switches favicon to /keremet-favicon.png for Keremet manager, and restores on unmount', () => {
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-1',
        login: 'manager_keremet',
        role: 'business_manager',
        business: { id: 'b-1', name: 'Keremet Bonus', status: 'active', android_app_id: 'kz.cashbackone.keremet' },
      },
    };

    const { unmount } = render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <div>Dashboard Content</div>
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>
    );

    expect(faviconLink.getAttribute('href')).toBe('/keremet-favicon.png');

    unmount();
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });

  it('superadmin can switch active business to Keremet and then to another business', async () => {
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-super',
        login: 'superadmin',
        role: 'superadmin',
        business: null,
      },
    };

    function TestSelector() {
      const { setActiveBusiness } = useActiveBusiness();
      return (
        <div>
          <button
            onClick={() => setActiveBusiness({ id: 'b-k', name: 'Керемет', android_app_id: 'kz.cashbackone.keremet' })}
          >
            Select Keremet
          </button>
          <button
            onClick={() => setActiveBusiness({ id: 'b-other', name: 'Other Shop', android_app_id: 'kz.other.shop' })}
          >
            Select Other
          </button>
          <button onClick={() => setActiveBusiness(null)}>Select All</button>
        </div>
      );
    }

    render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <TestSelector />
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>
    );

    // Initial superadmin state without active business -> /brand-mark.png
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');

    // Select Keremet
    await userEvent.click(screen.getByText('Select Keremet'));
    expect(faviconLink.getAttribute('href')).toBe('/keremet-favicon.png');

    // Select Other
    await userEvent.click(screen.getByText('Select Other'));
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');

    // Select All
    await userEvent.click(screen.getByText('Select All'));
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });
});
