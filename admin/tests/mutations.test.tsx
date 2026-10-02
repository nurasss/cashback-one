import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { Agent, BusinessDetail, CardDetail } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { AgentDetailPage, AgentsPage } from '../src/pages/AgentsPage';
import { CardDetailPage } from '../src/pages/OperationsPage';
import { BusinessEditorDialog } from '../src/features/AdminMutations';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = 'fixture-business-id';
const agentId = 'fixture-agent-id';
const cardId = 'fixture-card-id';
const business: BusinessDetail = {
  id: businessId, name: 'Fixture Market', logo_url: null, colors: null, barcode_prefixes: [], status: 'active',
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  cards_count: 1, unblocked_cards_count: 1, customers_with_cards_count: 1, agents_count: 1,
};
const agent: Agent = {
  id: agentId, business_id: businessId, business_name: business.name, status: 'active', health: 'online',
  last_seen_at: '2026-10-01T00:00:00Z', version: '1.0.0', last_sync_at: null, last_error: null,
  created_at: '2026-10-01T00:00:00Z',
};
const card: CardDetail = {
  id: cardId, business_id: businessId, business_name: business.name, barcode: '0000000000123',
  phone_masked: '••••1122', balance: '125.5000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z',
  bind_method: 'manual_barcode', bound_at: '2026-10-01T00:00:00Z', hidden_at: null,
  full_name: 'Fixture Owner', owner_language: 'ru',
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

function adminResponse(role: 'superadmin' | 'business_manager') {
  return { admin: { id: 'fixture-admin-id', login: `fixture.${role}`, role,
    business: role === 'business_manager' ? { id: businessId, name: business.name, status: 'active' } : null } };
}

function renderAdmin(element: React.ReactNode, role: 'superadmin' | 'business_manager', route = '/') {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  const mutableAgent = { ...agent };
  let cardBound = true;
  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse(role));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [business], limit: 100, offset: 0, has_more: false });
    }
    if (url.endsWith('/admin/agents?limit=25&offset=0')) {
      return json(200, { items: [mutableAgent], limit: 25, offset: 0, has_more: false });
    }
    if (url.endsWith(`/admin/agents/${agentId}`)) return json(200, mutableAgent);
    if (url.endsWith(`/admin/agents/${agentId}/rotate-key`) && method === 'POST') {
      return json(200, { agent: mutableAgent, api_key: 'agk_fixture_one_time_secret' });
    }
    if (url.endsWith(`/admin/agents/${agentId}/revoke`) && method === 'POST') {
      mutableAgent.status = 'revoked';
      return json(200, { agent: mutableAgent, status: 'revoked' });
    }
    if (url.endsWith(`/admin/agents/${agentId}/full-resync`) && method === 'POST') {
      return json(202, { command_id: 'fixture-command-id', status: 'pending', execution: 'deferred' });
    }
    if (url.endsWith('/admin/agents') && method === 'POST') {
      return json(201, { agent: mutableAgent, api_key: 'agk_fixture_create_secret' });
    }
    if (url.endsWith('/admin/businesses') && method === 'POST') {
      return json(201, business);
    }
    if (url.endsWith(`/admin/businesses/${businessId}`) && method === 'PATCH') {
      return json(200, business);
    }
    if (url.endsWith(`/admin/cards/${cardId}`)) {
      return json(200, { ...card, bind_method: cardBound ? card.bind_method : null, bound_at: cardBound ? card.bound_at : null });
    }
    if (url.endsWith(`/admin/cards/${cardId}/unbind`) && method === 'POST') {
      cardBound = false;
      return json(200, { status: 'unbound' });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<AdminProvider><MemoryRouter initialEntries={[route]}><Routes>
    <Route path="/" element={element} />
    <Route path="/agents" element={element} />
    <Route path="/agents/:agentId" element={element} />
    <Route path="/cards/:cardId" element={element} />
  </Routes></MemoryRouter></AdminProvider>);
  return fetchMock;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it('shows Agent provisioning controls to superadmin and hides them from a manager', async () => {
  const rootUser = userEvent.setup();
  renderAdmin(<AgentsPage />, 'superadmin', '/agents');
  await screen.findByText('Fixture Market');
  expect(screen.getByRole('button', { name: 'Создать агента' })).toBeInTheDocument();
  await rootUser.click(screen.getByRole('button', { name: 'Создать агента' }));
  await screen.findByLabelText('Бизнес');
  await rootUser.selectOptions(screen.getByLabelText('Бизнес'), businessId);
  await rootUser.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Создать агента' }));
  await screen.findByText('agk_fixture_create_secret');
  await rootUser.click(screen.getByRole('button', { name: 'Закрыть и удалить ключ' }));
  expect(screen.queryByText('agk_fixture_create_secret')).not.toBeInTheDocument();

  cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  renderAdmin(<AgentsPage />, 'business_manager', '/agents');
  await screen.findByText('Fixture Market');
  expect(screen.queryByRole('button', { name: 'Создать агента' })).not.toBeInTheDocument();
});

it('keeps Admin key rotation confirmation and clears one-time key after modal close', async () => {
  const user = userEvent.setup();
  const confirm = vi.fn(() => true);
  vi.stubGlobal('confirm', confirm);
  const fetchMock = renderAdmin(<AgentDetailPage />, 'superadmin', `/agents/${agentId}`);
  await screen.findByText('Состояние соединения');
  await user.click(screen.getByRole('button', { name: 'Ротировать ключ' }));
  await screen.findByText('agk_fixture_one_time_secret');
  expect(confirm.mock.calls[0]?.[0]).toContain('Старый ключ сразу перестанет работать');
  const rotation = vi.mocked(fetchMock).mock.calls.find(([url]) => String(url).endsWith('/rotate-key'));
  expect(rotation?.[1]?.method).toBe('POST');
  await user.click(screen.getByRole('button', { name: 'Закрыть и удалить ключ' }));
  expect(screen.queryByText('agk_fixture_one_time_secret')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Отозвать' }));
  await waitFor(() => expect(screen.getByText('revoked')).toBeInTheDocument());
  expect(confirm).toHaveBeenCalledTimes(2);
});

it('shows full-resync as pending/deferred and manager detail has no mutation controls', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('confirm', vi.fn(() => true));
  renderAdmin(<AgentDetailPage />, 'superadmin', `/agents/${agentId}`);
  await screen.findByText('Состояние соединения');
  await user.click(screen.getByRole('button', { name: 'Запросить полную синхронизацию' }));
  await screen.findByText(/Запрос синхронизации создан · pending/);
  expect(screen.getByText(/Выполнение отложено/)).toBeInTheDocument();
  expect(screen.queryByText(/Синхронизация завершена/)).not.toBeInTheDocument();

  cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  renderAdmin(<AgentDetailPage />, 'business_manager', `/agents/${agentId}`);
  await screen.findByText('Состояние соединения');
  expect(screen.queryByRole('button', { name: 'Ротировать ключ' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Отозвать' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Запросить полную синхронизацию' })).not.toBeInTheDocument();
});

it('validates business form and sends create/edit through the typed API client', async () => {
  const user = userEvent.setup();
  const onSaved = vi.fn();
  const fetchMock = renderAdmin(<BusinessEditorDialog onClose={() => {}} onSaved={onSaved} />, 'superadmin');
  await user.type(await screen.findByLabelText('Название'), 'New Business');
  await user.type(screen.getByLabelText('Логотип (HTTPS URL или пусто)'), 'http://logo.example.test/image.png');
  await user.click(screen.getByRole('button', { name: 'Создать' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('HTTPS URL');
  expect(vi.mocked(fetchMock).mock.calls.some(([url]) => String(url).endsWith('/admin/businesses'))).toBe(false);

  await user.clear(screen.getByLabelText('Логотип (HTTPS URL или пусто)'));
  await user.click(screen.getByRole('button', { name: 'Создать' }));
  await waitFor(() => expect(onSaved).toHaveBeenCalled());
  const create = vi.mocked(fetchMock).mock.calls.find(([url]) => String(url).endsWith('/admin/businesses'));
  expect(create?.[1]?.method).toBe('POST');
  expect(JSON.parse(String(create?.[1]?.body))).toMatchObject({ name: 'New Business', status: 'active', barcode_prefixes: [] });

  cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  const editFetch = renderAdmin(<BusinessEditorDialog business={business} onClose={() => {}} onSaved={onSaved} />, 'superadmin');
  const statusSelect = await screen.findByLabelText('Статус');
  await user.clear(screen.getByLabelText('Название'));
  await user.type(screen.getByLabelText('Название'), 'Edited Market');
  await user.selectOptions(statusSelect, 'inactive');
  await user.click(screen.getByRole('button', { name: 'Сохранить' }));
  await waitFor(() => expect(vi.mocked(editFetch).mock.calls.some(([url, init]) => String(url).endsWith(`/admin/businesses/${businessId}`) && init?.method === 'PATCH')).toBe(true));
});

it('requires explicit unbind confirmation and refreshes only the binding state', async () => {
  const user = userEvent.setup();
  const confirm = vi.fn(() => true);
  vi.stubGlobal('confirm', confirm);
  const fetchMock = renderAdmin(<CardDetailPage />, 'business_manager', `/cards/${cardId}`);
  await screen.findByText('Fixture Owner');
  await user.click(screen.getByRole('button', { name: 'Отвязать карту' }));
  expect(confirm.mock.calls[0]?.[0]).toContain('Fixture Market');
  expect(confirm.mock.calls[0]?.[0]).toContain('••••1122');
  expect(confirm.mock.calls[0]?.[0]).toContain('0000000000123');
  await screen.findByText('Привязка удалена. Карта и баланс сохранены.');
  expect(screen.getByText('125,5')).toBeInTheDocument();
  expect(screen.getByText('Не привязана')).toBeInTheDocument();
  const call = vi.mocked(fetchMock).mock.calls.find(([url]) => String(url).endsWith('/unbind'));
  expect(call?.[1]?.method).toBe('POST');
});
