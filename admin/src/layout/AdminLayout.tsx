import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { type PropsWithChildren, useEffect, useRef, useState } from 'react';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { Navigation } from '../features/Navigation';
import { IconBuilding, IconLogout } from '../components/Icons';
import { LanguageSwitcher } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';
import { resolveBusinessLogoSource } from '../utils/businessLogo';

function setDocumentFaviconHref(href: string): void {
  const link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
  if (link && link.getAttribute('href') !== href) {
    link.setAttribute('href', href);
  }
}

export function AdminLayout({ children }: PropsWithChildren) {
  const { session, view } = useAdminSession();
  const t = useAdminTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const [isOpen, setIsOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  const openMenu = () => {
    setIsOpen(true);
  };

  const closeMenu = (returnFocus = false) => {
    setIsOpen(false);
    if (returnFocus) {
      menuButtonRef.current?.focus();
    }
  };

  // Close menu on route change
  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname, location.search]);

  // Close menu on window resize > 760px
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 760) {
        setIsOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Close menu on Escape key and return focus
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMenu(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen]);

  // Lock body scroll when menu is open; restore on close and unmount
  useEffect(() => {
    if (!isOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [isOpen]);

  // Move focus to first link in menu upon opening
  useEffect(() => {
    if (isOpen) {
      const firstLink = sidebarRef.current?.querySelector<HTMLAnchorElement>('a');
      firstLink?.focus();
    }
  }, [isOpen]);

  const handleSidebarClick = (e: React.MouseEvent) => {
    const link = (e.target as HTMLElement).closest('a');
    if (link) {
      closeMenu(false);
    }
  };

  const { activeBusiness } = useActiveBusiness();
  const effectiveBusiness = view.status === 'authenticated' && view.admin.role === 'business_manager'
    ? view.admin.business
    : activeBusiness;
  const effectiveLogoUrl = view.status === 'authenticated' ? effectiveBusiness?.logo_url ?? null : null;

  // Dynamic Favicon: bound to the same safe business logo_url as AccountAvatar; fallback /brand-mark.png
  useEffect(() => {
    if (view.status !== 'authenticated') {
      setDocumentFaviconHref('/brand-mark.png');
      return () => setDocumentFaviconHref('/brand-mark.png');
    }

    const source = resolveBusinessLogoSource(effectiveLogoUrl);
    if (!source.ok) {
      setDocumentFaviconHref('/brand-mark.png');
      return () => setDocumentFaviconHref('/brand-mark.png');
    }

    let cancelled = false;
    const targetSrc = source.src;
    setDocumentFaviconHref('/brand-mark.png');

    if (typeof Image === 'undefined') {
      setDocumentFaviconHref(targetSrc);
      return () => {
        cancelled = true;
        setDocumentFaviconHref('/brand-mark.png');
      };
    }

    const probe = new Image();
    probe.referrerPolicy = 'no-referrer';
    probe.onload = () => {
      if (!cancelled) {
        setDocumentFaviconHref(targetSrc);
      }
    };
    probe.onerror = () => {
      if (!cancelled) {
        setDocumentFaviconHref('/brand-mark.png');
      }
    };
    probe.src = targetSrc;

    return () => {
      cancelled = true;
      probe.onload = null;
      probe.onerror = null;
      setDocumentFaviconHref('/brand-mark.png');
    };
  }, [view.status, effectiveLogoUrl]);

  if (view.status !== 'authenticated') return null;
  const { admin } = view;
  const signOut = async () => {
    await session.logout();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="app-frame">
      <aside
        id="admin-sidebar"
        ref={sidebarRef}
        className={`sidebar${isOpen ? ' is-open' : ''}`}
        onClick={handleSidebarClick}
      >
        <div className="sidebar-brand-container">
          <NavLink className="brand-lockup" to="/admin" aria-label={t.layout.brandAria}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="27" height="27" />
            </div>
            <div className="brand-text">
              <strong>poscenter.kz</strong>
            </div>
          </NavLink>
        </div>

        <Navigation role={admin.role} />

        <div className="sidebar-footer">
          <div className="sidebar-note">
            <div className="sidebar-note-header">
              <span className="security-dot" aria-hidden="true" />
              <span className="security-title">{t.layout.viewMode}</span>
            </div>
            <small>{t.layout.viewModeNote}</small>
          </div>
        </div>
      </aside>

      {isOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={() => closeMenu(true)}
          aria-label={t.layout.closeMenu}
        />
      )}

      <div className="mobile-bar">
        <button
          type="button"
          ref={menuButtonRef}
          className="mobile-menu-btn"
          onClick={() => {
            if (isOpen) {
              closeMenu(true);
            } else {
              openMenu();
            }
          }}
          aria-label={t.layout.openMenu}
          aria-expanded={isOpen}
          aria-controls="admin-sidebar"
        >
          <svg
            className="mobile-menu-icon"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>

        <div className="mobile-brand" aria-hidden="true">
          <div className="brand-mark-wrap">
            <img src="/brand-mark.png" alt="" className="brand-mark-img" width="32" height="32" />
          </div>
          <div className="brand-text">
            <strong>poscenter<span>.kz</span></strong>
          </div>
        </div>
      </div>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context">
            <span className="context-platform">{t.layout.platform}</span>
            <span className="context-divider" aria-hidden="true">/</span>
            <span className="context-business">
              <IconBuilding className="context-icon" aria-hidden="true" />
              <strong>{admin.business?.name ?? t.layout.allBusinesses}</strong>
            </span>
          </div>

          <div className="account-menu">
            <LanguageSwitcher className="topbar-lang-switcher" />
            <AccountAvatar login={admin.login} logoUrl={effectiveBusiness?.logo_url ?? null} />
            <div className="account-copy">
              <strong>{admin.login}</strong>
              <span className="account-role-pill">
                {admin.role === 'superadmin' ? t.layout.roles.superadmin : t.layout.roles.business_manager}
              </span>
            </div>
            <button
              className="button button-secondary signout-button"
              type="button"
              onClick={() => { void signOut(); }}
              title={t.layout.signoutTitle}
            >
              <IconLogout className="button-icon" aria-hidden="true" />
              <span>{t.layout.signout}</span>
            </button>
          </div>
        </header>

        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}

export function AccountAvatar({ login, logoUrl }: { login: string; logoUrl: string | null }) {
  const source = resolveBusinessLogoSource(logoUrl);
  const [failed, setFailed] = useState(false);
  const safeUrl = source.ok ? source.src : null;

  useEffect(() => setFailed(false), [safeUrl]);

  return (
    <div className={`account-avatar${safeUrl && !failed ? ' has-logo' : ''}`} aria-hidden="true">
      {safeUrl && !failed ? (
        <img src={safeUrl} alt="" referrerPolicy="no-referrer" style={{ objectFit: 'contain' }} onError={() => setFailed(true)} />
      ) : (
        login.slice(0, 1).toUpperCase() || '?'
      )}
    </div>
  );
}
