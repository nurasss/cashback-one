import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { BusinessDetail, ManagerAccessDisclosure } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { BusinessDetailPage, BusinessesPage } from '../src/pages/BusinessesPage';
import { ManagerAccessDialog } from '../src/features/AdminMutations';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = 'fixture-biz-id';

const business: BusinessDetail = {
  id: businessId,
  name: 'Кафе Уют',
  logo_url: null,
  colors: null,
  barcode_prefixes: [],
  status: 'active',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  cards_count: 5,
  unblocked_cards_count: 5,
  customers_with_cards_count: 5,
  agents_count: 1,
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

function adminResponse(role: 'superadmin' | 'business_manager') {
  return {
    admin: {
      id: 'fixture-admin-id',
      login: `fixture.${role}`,
      role,
      business: role === 'business_manager' ? { id: businessId, name: business.name, status: 'active' } : null,
    },
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it('renders ManagerAccessDialog with one-time credentials and supports copy-all', async () => {
  const user = userEvent.setup();
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('navigator', {
    clipboard: { writeText },
  });

  const disclosure: ManagerAccessDisclosure = {
    login: 'kafe-uyut',
    password: 'MockSecurePass16x',
    login_url: 'https://cashback-qr.poscenter.kz',
    one_time: true,
  };

  const onClose = vi.fn();
  const { rerender } = render(<ManagerAccessDialog disclosure={disclosure} onClose={onClose} />);

  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByText('Доступ клиента к админке')).toBeInTheDocument();
  expect(screen.getByText(/Пароль показан один раз и не сохраняется/i)).toBeInTheDocument();
  expect(screen.getByLabelText('Ссылка для входа')).toHaveTextContent('https://cashback-qr.poscenter.kz');
  expect(screen.getByLabelText('Логин менеджера')).toHaveTextContent('kafe-uyut');
  expect(screen.getByLabelText('Пароль менеджера')).toHaveTextContent('MockSecurePass16x');

  // Copy all button
  const copyBtn = screen.getByRole('button', { name: 'Скопировать всё' });
  await user.click(copyBtn);
  expect(writeText).toHaveBeenCalledWith(
    'Ссылка: https://cashback-qr.poscenter.kz\nЛогин: kafe-uyut\nПароль: MockSecurePass16x'
  );
  expect(await screen.findByText('Скопировано в буфер обмена.')).toBeInTheDocument();

  // Close button
  const closeBtn = screen.getByRole('button', { name: 'Закрыть' });
  await user.click(closeBtn);
  expect(onClose).toHaveBeenCalled();

  // Clearing disclosure removes password from DOM
  rerender(<div />);
  expect(screen.queryByText('MockSecurePass16x')).not.toBeInTheDocument();
});

it('shows ManagerAccessDialog after business creation and clears on close', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const createdBusiness = {
    ...business,
    id: 'new-biz-id',
    name: 'Магазин Весна',
    manager_access: {
      login: 'magazin-vesna',
      password: 'CreatedSecret16x',
      login_url: 'https://cashback-qr.poscenter.kz',
      one_time: true,
    },
  };

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=25&offset=0')) {
      return json(200, { items: [business], limit: 25, offset: 0, has_more: false });
    }
    if (url.endsWith('/admin/businesses') && method === 'POST') {
      return json(201, createdBusiness);
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/businesses']}>
        <Routes>
          <Route path="/businesses" element={<BusinessesPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  // Wait for businesses table to render
  expect(await screen.findByText('Кафе Уют')).toBeInTheDocument();

  // Open creation modal
  const createBtn = screen.getByRole('button', { name: 'Создать бизнес' });
  await user.click(createBtn);

  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(within(screen.getByRole('dialog')).getByRole('heading', { name: 'Создать бизнес' })).toBeInTheDocument();

  // Fill in name and submit
  const nameInput = screen.getByLabelText('Название');
  await user.clear(nameInput);
  await user.type(nameInput, 'Магазин Весна');

  const submitBtn = screen.getByRole('button', { name: 'Создать' });
  await user.click(submitBtn);

  // ManagerAccessDialog must appear with created credentials
  expect(await screen.findByText('Доступ клиента к админке')).toBeInTheDocument();
  expect(screen.getByLabelText('Логин менеджера')).toHaveTextContent('magazin-vesna');
  expect(screen.getByLabelText('Пароль менеджера')).toHaveTextContent('CreatedSecret16x');

  // Close the disclosure dialog
  const closeBtn = screen.getByRole('button', { name: 'Закрыть' });
  await user.click(closeBtn);

  // Dialog and secret must be completely gone from DOM
  await waitFor(() => {
    expect(screen.queryByText('Доступ клиента к админке')).not.toBeInTheDocument();
    expect(screen.queryByText('CreatedSecret16x')).not.toBeInTheDocument();
  });
});

it('supports resetting manager credentials on business detail page', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  vi.stubGlobal('confirm', vi.fn(() => true));

  const resetDisclosure: ManagerAccessDisclosure = {
    login: 'kafe-uyut',
    password: 'ResetSecretPass16',
    login_url: 'https://cashback-qr.poscenter.kz',
    one_time: true,
  };

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith(`/admin/businesses/${businessId}`) && method === 'GET') {
      return json(200, business);
    }
    if (url.endsWith(`/admin/businesses/${businessId}/manager-access`) && method === 'POST') {
      return json(200, resetDisclosure);
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={[`/businesses/${businessId}`]}>
        <Routes>
          <Route path="/businesses/:businessId" element={<BusinessDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  // Wait for detail page
  expect(await screen.findByText('Кафе Уют')).toBeInTheDocument();

  const resetBtn = screen.getByRole('button', { name: 'Выдать доступ / Сбросить пароль' });
  await user.click(resetBtn);

  expect(window.confirm).toHaveBeenCalledWith(
    'Старый пароль перестанет работать, активные входы менеджера будут завершены.'
  );

  // Disclosure modal appears
  expect(await screen.findByText('Доступ клиента к админке')).toBeInTheDocument();
  expect(screen.getByLabelText('Пароль менеджера')).toHaveTextContent('ResetSecretPass16');

  // Close modal
  const closeBtn = screen.getByRole('button', { name: 'Закрыть' });
  await user.click(closeBtn);

  await waitFor(() => {
    expect(screen.queryByText('ResetSecretPass16')).not.toBeInTheDocument();
  });
});

it('hides reset manager access button from business_manager', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const fetchMock: typeof fetch = vi.fn(async (input) => {
    const url = String(input);
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('business_manager'));
    if (url.endsWith(`/admin/businesses/${businessId}`)) {
      return json(200, business);
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={[`/businesses/${businessId}`]}>
        <Routes>
          <Route path="/businesses/:businessId" element={<BusinessDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  expect(await screen.findByText('Кафе Уют')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Выдать доступ / Сбросить пароль' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Изменить бизнес' })).not.toBeInTheDocument();
});
