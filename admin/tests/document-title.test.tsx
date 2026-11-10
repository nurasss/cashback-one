import { describe, expect, it } from 'vitest';
import { adminKk, adminRu } from '../src/i18n/admin';
import { resolveAdminDocumentTitle } from '../src/utils/documentTitle';
import type { SessionView } from '../src/auth/session';

describe('resolveAdminDocumentTitle', () => {
  const managerViewWithBusiness: SessionView = {
    status: 'authenticated',
    admin: {
      id: 'mgr-1',
      login: 'keremet_mgr',
      role: 'business_manager',
      business: { id: 'biz-1', name: 'Keremet Store', status: 'active' },
    },
  };

  const managerViewWithoutBusiness: SessionView = {
    status: 'authenticated',
    admin: {
      id: 'mgr-2',
      login: 'nomarket_mgr',
      role: 'business_manager',
      business: null as any,
    },
  };

  const superadminView: SessionView = {
    status: 'authenticated',
    admin: {
      id: 'super-1',
      login: 'root',
      role: 'superadmin',
      business: null,
    },
  };

  const anonymousView: SessionView = {
    status: 'anonymous',
  };

  describe('Business Manager (RU)', () => {
    it('formats overview as Главная with business name', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Главная — Keremet Store — Cashback One');
    });

    it('formats without business name if missing', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin',
        view: managerViewWithoutBusiness,
        t: adminRu,
      });
      expect(title).toBe('Главная — Cashback One');
    });

    it('formats clients / operations tab as Клиенты', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/operations',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Клиенты — Keremet Store — Cashback One');
    });

    it('formats content tab as Приложение', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/content',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Приложение — Keremet Store — Cashback One');
    });

    it('formats statuses tab as Статусы', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/statuses',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Статусы — Keremet Store — Cashback One');
    });

    it('formats notifications tab as Рассылки', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/notifications',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Рассылки — Keremet Store — Cashback One');
    });

    it('formats settings tab as Настройки', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/settings',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Настройки — Keremet Store — Cashback One');
    });

    it('masks card details without exposing barcode', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/cards/2000000000012',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Карта — Keremet Store — Cashback One');
      expect(title).not.toContain('2000000000012');
    });

    it('masks user details without exposing user id or phone', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/users/77011234567',
        view: managerViewWithBusiness,
        t: adminRu,
      });
      expect(title).toBe('Клиент — Keremet Store — Cashback One');
      expect(title).not.toContain('77011234567');
    });
  });

  describe('Superadmin (RU)', () => {
    it('formats overview as Обзор with Cashback One Admin suffix', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin',
        view: superadminView,
        t: adminRu,
      });
      expect(title).toBe('Обзор — Cashback One Admin');
    });

    it('formats businesses list', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/businesses',
        view: superadminView,
        t: adminRu,
      });
      expect(title).toBe('Бизнесы — Cashback One Admin');
    });

    it('formats business detail', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/businesses/00000000-0000-0000-0000-000000000001',
        view: superadminView,
        t: adminRu,
      });
      expect(title).toBe('Бизнес — Cashback One Admin');
    });

    it('formats agents list and detail', () => {
      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/agents',
          view: superadminView,
          t: adminRu,
        })
      ).toBe('Агенты — Cashback One Admin');

      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/agents/agent-123',
          view: superadminView,
          t: adminRu,
        })
      ).toBe('Агент — Cashback One Admin');
    });

    it('formats operations as Карты и клиенты for superadmin', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/operations',
        view: superadminView,
        t: adminRu,
      });
      expect(title).toBe('Карты и клиенты — Cashback One Admin');
    });

    it('formats audit as Журнал событий', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/audit',
        view: superadminView,
        t: adminRu,
      });
      expect(title).toBe('Журнал событий — Cashback One Admin');
    });
  });

  describe('Login & Anonymous', () => {
    it('formats login in Russian', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/login',
        view: anonymousView,
        t: adminRu,
      });
      expect(title).toBe('Вход в систему — Cashback One Admin');
    });

    it('formats login in Kazakh', () => {
      const title = resolveAdminDocumentTitle({
        pathname: '/admin/login',
        view: anonymousView,
        t: adminKk,
      });
      expect(title).toBe('Жүйеге кіру — Cashback One Admin');
    });
  });

  describe('Kazakh Locale (KK)', () => {
    it('formats manager navigation in Kazakh', () => {
      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin',
          view: managerViewWithBusiness,
          t: adminKk,
        })
      ).toBe('Басты бет — Keremet Store — Cashback One');

      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/content',
          view: managerViewWithBusiness,
          t: adminKk,
        })
      ).toBe('Қолданба — Keremet Store — Cashback One');

      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/statuses',
          view: managerViewWithBusiness,
          t: adminKk,
        })
      ).toBe('Дәрежелер — Keremet Store — Cashback One');

      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/notifications',
          view: managerViewWithBusiness,
          t: adminKk,
        })
      ).toBe('Хабарламалар — Keremet Store — Cashback One');
    });

    it('formats superadmin navigation in Kazakh', () => {
      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin',
          view: superadminView,
          t: adminKk,
        })
      ).toBe('Шолу — Cashback One Admin');

      expect(
        resolveAdminDocumentTitle({
          pathname: '/admin/businesses',
          view: superadminView,
          t: adminKk,
        })
      ).toBe('Бизнестер — Cashback One Admin');
    });
  });

  describe('Privacy & Security', () => {
    it('never leaks tokens, passwords, keys or phone numbers into document title', () => {
      const sensitiveInputs = [
        '/admin/cards/77011234567',
        '/admin/users/77029876543',
        '/admin/agents/api_key_sec_12345',
        '/admin/settings?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
      ];
      for (const pathname of sensitiveInputs) {
        const title = resolveAdminDocumentTitle({
          pathname,
          view: managerViewWithBusiness,
          t: adminRu,
        });
        expect(title).not.toContain('77011234567');
        expect(title).not.toContain('77029876543');
        expect(title).not.toContain('api_key_sec_12345');
        expect(title).not.toContain('eyJhbGci');
      }
    });
  });
});
