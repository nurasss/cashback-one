import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
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
    business: {
      id: 'b-1',
      name: 'Keremet Bonus',
      status: 'active',
      logo_url: 'https://cdn.example.test/keremet-logo.webp',
      android_app_id: 'kz.cashbackone.keremet',
    },
  },
};

const mockSession = {
  logout: async () => {
    mockView = { status: 'anonymous' };
  },
};

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    session: mockSession,
    view: mockView,
  }),
}));

class FakeProbeImage {
  static instances: FakeProbeImage[] = [];
  referrerPolicy = '';
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private _src = '';

  constructor() {
    FakeProbeImage.instances.push(this);
  }

  get src(): string {
    return this._src;
  }

  set src(val: string) {
    this._src = val;
  }
}

describe('Favicon & Business Logo Binding (A16-02)', () => {
  let faviconLink: HTMLLinkElement;

  beforeEach(() => {
    FakeProbeImage.instances = [];
    vi.stubGlobal('Image', FakeProbeImage);
    faviconLink = document.createElement('link');
    faviconLink.rel = 'icon';
    faviconLink.href = '/brand-mark.png';
    document.head.appendChild(faviconLink);
  });

  afterEach(() => {
    cleanup();
    faviconLink.remove();
    vi.unstubAllGlobals();
  });

  it('retains isKeremetBusiness helper contract while favicon uses business logo_url for any business', () => {
    expect(isKeremetBusiness({ android_app_id: 'kz.cashbackone.keremet' })).toBe(true);
    expect(isKeremetBusiness({ name: 'Керемет', android_app_id: null })).toBe(false);
    expect(isKeremetBusiness(null)).toBe(false);
  });

  it('binds favicon and AccountAvatar to business logo_url for business_manager regardless of brand name, and restores /brand-mark.png on unmount', () => {
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-1',
        login: 'manager_alpha',
        role: 'business_manager',
        business: {
          id: 'b-alpha',
          name: 'Alpha Coffee',
          status: 'active',
          logo_url: 'https://cdn.example.test/alpha.webp',
          android_app_id: null,
        },
      },
    };

    const { container, unmount } = render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <div>Dashboard Content</div>
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>,
    );

    const avatarImg = container.querySelector('.account-avatar img');
    expect(avatarImg).toHaveAttribute('src', 'https://cdn.example.test/alpha.webp');
    expect(FakeProbeImage.instances).toHaveLength(1);
    expect(FakeProbeImage.instances[0]!.referrerPolicy).toBe('no-referrer');

    act(() => {
      FakeProbeImage.instances[0]!.onload?.();
    });
    expect(faviconLink.getAttribute('href')).toBe('https://cdn.example.test/alpha.webp');

    unmount();
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });

  it('falls back to /brand-mark.png when logo_url is null, unsafe http://, or fails to load', () => {
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-2',
        login: 'manager_http',
        role: 'business_manager',
        business: {
          id: 'b-2',
          name: 'Beta',
          status: 'active',
          logo_url: 'http://insecure.test/logo.png',
          android_app_id: null,
        },
      },
    };

    const { container, rerender } = render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <div>Content</div>
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>,
    );

    // Unsafe URL -> letter fallback in avatar, /brand-mark.png in favicon, zero probe requests
    expect(container.querySelector('.account-avatar img')).toBeNull();
    expect(container.querySelector('.account-avatar')).toHaveTextContent('M');
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
    expect(FakeProbeImage.instances).toHaveLength(0);

    // Now valid HTTPS URL that fails onerror -> favicon remains /brand-mark.png
    mockView = {
      status: 'authenticated',
      admin: {
        id: 'u-2',
        login: 'manager_broken',
        role: 'business_manager',
        business: {
          id: 'b-2',
          name: 'Beta',
          status: 'active',
          logo_url: 'https://cdn.example.test/broken.webp',
          android_app_id: null,
        },
      },
    };
    rerender(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <div>Content</div>
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>,
    );
    expect(FakeProbeImage.instances).toHaveLength(1);
    act(() => {
      FakeProbeImage.instances[0]!.onerror?.();
    });
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });

  it('handles superadmin switch, All businesses fallback, logout reset, and slow-image race condition without overwriting newer state', async () => {
    const user = userEvent.setup();
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
            type="button"
            onClick={() => setActiveBusiness({
              id: 'b-1',
              name: 'Slow First',
              logo_url: 'https://cdn.example.test/first.webp',
              android_app_id: 'kz.cashbackone.keremet',
            })}
          >
            Select First
          </button>
          <button
            type="button"
            onClick={() => setActiveBusiness({
              id: 'b-2',
              name: 'Fast Second',
              logo_url: 'https://cdn.example.test/second.webp',
              android_app_id: null,
            })}
          >
            Select Second
          </button>
          <button type="button" onClick={() => setActiveBusiness(null)}>
            Select All
          </button>
        </div>
      );
    }

    const { rerender } = render(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <TestSelector />
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>,
    );

    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');

    await user.click(screen.getByText('Select First'));
    const slowProbe = FakeProbeImage.instances[0]!;
    expect(slowProbe.src).toBe('https://cdn.example.test/first.webp');

    // Before first finishes loading, user switches to Second
    await user.click(screen.getByText('Select Second'));
    const secondProbe = FakeProbeImage.instances[1]!;
    expect(secondProbe.src).toBe('https://cdn.example.test/second.webp');

    act(() => {
      secondProbe.onload?.();
    });
    expect(faviconLink.getAttribute('href')).toBe('https://cdn.example.test/second.webp');

    // Late onload from cancelled first probe MUST NOT overwrite newer favicon
    act(() => {
      slowProbe.onload?.();
    });
    expect(faviconLink.getAttribute('href')).toBe('https://cdn.example.test/second.webp');

    // Switching to All resets to /brand-mark.png
    await user.click(screen.getByText('Select All'));
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');

    // Re-selecting business and then signing out resets favicon back to /brand-mark.png
    await user.click(screen.getByText('Select Second'));
    act(() => {
      FakeProbeImage.instances[FakeProbeImage.instances.length - 1]!.onload?.();
    });
    expect(faviconLink.getAttribute('href')).toBe('https://cdn.example.test/second.webp');

    mockView = { status: 'anonymous' };
    rerender(
      <MemoryRouter>
        <ActiveBusinessProvider>
          <AdminLayout>
            <TestSelector />
          </AdminLayout>
        </ActiveBusinessProvider>
      </MemoryRouter>,
    );
    expect(faviconLink.getAttribute('href')).toBe('/brand-mark.png');
  });
});
