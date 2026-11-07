import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { ContentPage } from '../src/pages/ContentPage';
import type { AppNotification } from '../src/api/types';

const businessId = 'fixture-business-id';
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function renderContent(options?: {
  role?: 'superadmin' | 'business_manager';
  locale?: 'ru' | 'kk';
  notifications?: AppNotification[];
  createNotificationResponse?: unknown;
}) {
  const role = options?.role ?? 'superadmin';
  const locale = options?.locale ?? 'ru';
  window.localStorage.setItem('c1_site_lang', locale);

  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';

    if (url.endsWith('/admin/auth/refresh')) {
      return json(200, {
        access_token: 'fixture-access',
        token_type: 'bearer',
        expires_in: 900,
      });
    }
    if (url.endsWith('/admin/me')) {
      return json(200, {
        admin: {
          id: 'admin-1',
          login: 'admin@poscenter.kz',
          role,
          business:
            role === 'business_manager'
              ? { id: businessId, name: 'Fixture Market', status: 'active' }
              : null,
        },
      });
    }
    if (url.includes('/admin/businesses?')) {
      return json(200, {
        items: [{ id: businessId, name: 'Fixture Market' }],
        limit: 100,
        offset: 0,
        has_more: false,
      });
    }
    if (url.includes('/admin/promotions?')) {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/notifications?')) {
      return json(200, {
        items: options?.notifications ?? [],
        limit: 25,
        offset: 0,
        has_more: false,
      });
    }
    if (url.endsWith('/admin/notifications') && method === 'POST') {
      const resp = options?.createNotificationResponse ?? {
        id: 'note-created',
        business_id: null,
        user_id: null,
        kind: 'info',
        title: 'Заголовок',
        body: 'Текст',
        created_at: '2026-11-07T12:00:00Z',
      };
      return json(201, resp);
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });

  vi.stubGlobal('fetch', fetchMock);

  render(
    <LocaleProvider initialLocale={locale}>
      <AdminProvider>
        <MemoryRouter>
          <Routes>
            <Route path="/" element={<ContentPage />} />
          </Routes>
        </MemoryRouter>
      </AdminProvider>
    </LocaleProvider>,
  );

  return fetchMock;
}

describe('Scheduled Notifications in Admin', () => {
  beforeEach(() => {
    // Fix current time at 2026-11-07T12:00:00Z (17:00 Astana time)
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-07T12:00:00.000Z'));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    window.localStorage.clear();
  });

  it.each(['ru', 'kk'] as const)(
    'toggles between "Сейчас" and "В указанное время", showing date input only when scheduled (%s)',
    async locale => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderContent({ locale });

      const tabName = locale === 'kk' ? 'Хабарламалар' : 'Уведомления';
      const sendBtnName = locale === 'kk' ? 'Хабарлама жіберу' : 'Отправить уведомление';
      const sendNowLabel = locale === 'kk' ? 'Қазір' : 'Сейчас';
      const sendScheduledLabel = locale === 'kk' ? 'Көрсетілген уақытта' : 'В указанное время';
      const dateLabel =
        locale === 'kk'
          ? 'Күні мен уақыты (Астана уақыты)'
          : 'Дата и время (время Астаны)';
      const submitSendBtn = locale === 'kk' ? 'Жіберу' : 'Отправить';
      const submitScheduleBtn = locale === 'kk' ? 'Жоспарлау' : 'Запланировать';

      await user.click(await screen.findByRole('tab', { name: tabName }));
      await user.click(await screen.findByRole('button', { name: sendBtnName }));
      const dialog = await screen.findByRole('dialog');

      // Default: "Сейчас" is checked, date input does not exist
      const radioNow = within(dialog).getByLabelText(sendNowLabel);
      const radioScheduled = within(dialog).getByLabelText(sendScheduledLabel);
      expect(radioNow).toBeChecked();
      expect(radioScheduled).not.toBeChecked();
      expect(within(dialog).queryByLabelText(dateLabel)).not.toBeInTheDocument();
      expect(
        within(dialog).getByRole('button', { name: submitSendBtn }),
      ).toBeInTheDocument();

      // Switch to scheduled mode
      await user.click(radioScheduled);
      expect(radioScheduled).toBeChecked();
      expect(radioNow).not.toBeChecked();
      expect(within(dialog).getByLabelText(dateLabel)).toBeInTheDocument();
      expect(
        within(dialog).getByRole('button', { name: submitScheduleBtn }),
      ).toBeInTheDocument();

      // Switch back to "Сейчас"
      await user.click(radioNow);
      expect(radioNow).toBeChecked();
      expect(within(dialog).queryByLabelText(dateLabel)).not.toBeInTheDocument();
      expect(
        within(dialog).getByRole('button', { name: submitSendBtn }),
      ).toBeInTheDocument();
    },
    15_000,
  );

  it('validates empty, past, and too far date without sending API request', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = renderContent({ locale: 'ru' });

    await user.click(await screen.findByRole('tab', { name: 'Уведомления' }));
    await user.click(await screen.findByRole('button', { name: 'Отправить уведомление' }));
    const dialog = await screen.findByRole('dialog');

    await user.type(within(dialog).getByLabelText('Заголовок'), 'Заголовок акции');
    await user.type(within(dialog).getByLabelText('Текст'), 'Текст акции');
    await user.click(within(dialog).getByLabelText('В указанное время'));

    const dateInput = within(dialog).getByLabelText('Дата и время (время Астаны)');
    const submitBtn = within(dialog).getByRole('button', { name: 'Запланировать' });

    // 1. Empty date
    await user.click(submitBtn);
    expect(
      await within(dialog).findByText('Укажите дату и время отправки.'),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(fetchMock)
        .mock.calls.some(
          ([url, init]) =>
            String(url).endsWith('/admin/notifications') && init?.method === 'POST',
        ),
    ).toBe(false);

    // 2. Past date: current system time is 2026-11-07T12:00Z = 17:00 Astana time.
    // Enter 16:00 (past)
    fireEvent.change(dateInput, { target: { value: '2026-11-07T16:00' } });
    await user.click(submitBtn);
    expect(
      await within(dialog).findByText('Время отправки не может быть в прошлом.'),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(fetchMock)
        .mock.calls.some(
          ([url, init]) =>
            String(url).endsWith('/admin/notifications') && init?.method === 'POST',
        ),
    ).toBe(false);

    // 3. Date > 30 days ahead: 2026-12-15T18:00 (> 30 days from Nov 7)
    fireEvent.change(dateInput, { target: { value: '2026-12-15T18:00' } });
    await user.click(submitBtn);
    expect(
      await within(dialog).findByText(
        'Время отправки не может быть позже, чем через 30 дней.',
      ),
    ).toBeInTheDocument();
    expect(
      vi
        .mocked(fetchMock)
        .mock.calls.some(
          ([url, init]) =>
            String(url).endsWith('/admin/notifications') && init?.method === 'POST',
        ),
    ).toBe(false);
  }, 15_000);

  it('converts Astana local time to UTC in scheduled notification request', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = renderContent({ locale: 'ru' });

    await user.click(await screen.findByRole('tab', { name: 'Уведомления' }));
    await user.click(await screen.findByRole('button', { name: 'Отправить уведомление' }));
    const dialog = await screen.findByRole('dialog');

    await user.type(within(dialog).getByLabelText('Заголовок'), 'Вечерняя скидка');
    await user.type(within(dialog).getByLabelText('Текст'), 'Скидка на всё меню 15%');
    await user.click(within(dialog).getByLabelText('В указанное время'));

    const dateInput = within(dialog).getByLabelText('Дата и время (время Астаны)');
    // Current is 17:00 Astana (12:00 UTC). Enter 18:00 Astana (13:00 UTC).
    fireEvent.change(dateInput, { target: { value: '2026-11-07T18:00' } });

    await user.click(within(dialog).getByRole('button', { name: 'Запланировать' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    const postCall = vi
      .mocked(fetchMock)
      .mock.calls.find(
        ([url, init]) =>
          String(url).endsWith('/admin/notifications') && init?.method === 'POST',
      );
    expect(postCall).toBeDefined();
    const payload = JSON.parse(String(postCall?.[1]?.body));
    expect(payload).toEqual({
      title: 'Вечерняя скидка',
      body: 'Скидка на всё меню 15%',
      send_push: true,
      scheduled_at: '2026-11-07T13:00:00.000Z',
    });
  }, 15_000);

  it.each([
    {
      locale: 'ru' as const,
      expectedScheduledWithPush: 'Запланировано на 07.11 18:00',
      expectedScheduledNoPush: 'Запланировано на 08.11 10:00',
      expectedSent: 'Отправлено',
    },
    {
      locale: 'kk' as const,
      expectedScheduledWithPush: '07.11 18:00 уақытына жоспарланған',
      expectedScheduledNoPush: '08.11 10:00 уақытына жоспарланған',
      expectedSent: 'Жіберілді',
    },
  ])(
    'renders table statuses: "Запланировано на ..." (with push & without push) and "Отправлено" ($locale)',
    async ({
      locale,
      expectedScheduledWithPush,
      expectedScheduledNoPush,
      expectedSent,
    }) => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      // Current system time is 2026-11-07T12:00:00Z (17:00 Astana)
      const notifications: AppNotification[] = [
        {
          id: 'note-1-sched-push',
          business_id: null,
          user_id: null,
          kind: 'info',
          title: 'Акция 1',
          body: 'Запланирована с push',
          scheduled_at: '2026-11-07T13:00:00.000Z', // 18:00 Astana (future)
          push_sent_at: null,
          created_at: '2026-11-07T11:00:00.000Z',
        },
        {
          id: 'note-2-sched-nopush',
          business_id: null,
          user_id: null,
          kind: 'info',
          title: 'Акция 2',
          body: 'Запланирована без push (сервер выставил push_sent_at = scheduled_at)',
          scheduled_at: '2026-11-08T05:00:00.000Z', // 10:00 Astana on 08.11 (future)
          push_sent_at: '2026-11-08T05:00:00.000Z', // Server pre-fills push_sent_at for send_push=false
          created_at: '2026-11-07T11:00:00.000Z',
        },
        {
          id: 'note-3-sent',
          business_id: null,
          user_id: null,
          kind: 'info',
          title: 'Акция 3',
          body: 'Уже отправлена',
          scheduled_at: null,
          push_sent_at: '2026-10-01T10:00:00.000Z',
          created_at: '2026-10-01T10:00:00.000Z',
        },
      ];

      renderContent({ locale, notifications });

      const tabName = locale === 'kk' ? 'Хабарламалар' : 'Уведомления';
      await user.click(await screen.findByRole('tab', { name: tabName }));

      expect(await screen.findByText('Акция 1')).toBeInTheDocument();
      expect(screen.getByText('Акция 2')).toBeInTheDocument();
      expect(screen.getByText('Акция 3')).toBeInTheDocument();

      // Check statuses in table
      expect(screen.getByText(expectedScheduledWithPush)).toBeInTheDocument();
      expect(screen.getByText(expectedScheduledNoPush)).toBeInTheDocument();
      expect(screen.getByText(expectedSent)).toBeInTheDocument();
    },
    15_000,
  );
});
