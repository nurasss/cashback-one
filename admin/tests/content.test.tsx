import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ContentPage } from '../src/pages/ContentPage';
import type { Promotion } from '../src/api/types';

const businessId = 'fixture-business-id';
const promotion: Promotion = {
  id: 'fixture-promo-id', business_id: null, kind: 'banner', title: 'Выиграй авто', subtitle: null, badge: null, body: null,
  image_url: null, starts_at: null, ends_at: null, sort_order: 0, is_active: true,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
};
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function renderContent(role: 'superadmin' | 'business_manager') {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 });
    if (url.endsWith('/admin/me')) return json(200, { admin: { id: 'a', login: 'fixture', role,
      business: role === 'business_manager' ? { id: businessId, name: 'Fixture Market', status: 'active' } : null } });
    if (url.includes('/admin/businesses?')) return json(200, { items: [{ id: businessId, name: 'Fixture Market' }], limit: 100, offset: 0, has_more: false });
    if (url.includes('/admin/promotions?')) return json(200, { items: [promotion], limit: 25, offset: 0, has_more: false });
    if (url.includes('/admin/notifications?')) return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    if (url.endsWith('/admin/promotions') && method === 'POST') return json(201, { ...promotion, id: 'new' });
    if (url.endsWith('/admin/notifications') && method === 'POST') return json(201, { id: 'n', business_id: null, user_id: null, kind: 'info', title: 't', body: 'b', created_at: '2026-10-01T00:00:00Z' });
    if (url.endsWith(`/admin/promotions/${promotion.id}`) && method === 'DELETE') return new Response(null, { status: 204 });
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<AdminProvider><MemoryRouter><Routes><Route path="/" element={<ContentPage />} /></Routes></MemoryRouter></AdminProvider>);
  return fetchMock;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it('lets a superadmin create a business offer and delete a banner', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('confirm', vi.fn(() => true));
  const fetchMock = renderContent('superadmin');
  await screen.findByText('Выиграй авто');
  expect(screen.getByText('Баннер на главной')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: 'Добавить акцию' }));
  const dialog = await screen.findByRole('dialog');
  await within(dialog).findByRole('option', { name: 'Fixture Market' });
  await user.selectOptions(within(dialog).getByLabelText('Для кого'), businessId);
  await user.type(within(dialog).getByLabelText('Заголовок'), 'Скидка на хиты');
  await user.type(within(dialog).getByLabelText('Плашка (например, «Акция недели»)'), 'Скидка');
  await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const create = vi.mocked(fetchMock).mock.calls.find(([url, init]) => String(url).endsWith('/admin/promotions') && init?.method === 'POST');
  expect(JSON.parse(String(create?.[1]?.body))).toMatchObject({ business_id: businessId, kind: 'offer', title: 'Скидка на хиты', badge: 'Скидка', is_active: true });

  await user.click(screen.getByRole('button', { name: 'Удалить' }));
  await waitFor(() => expect(vi.mocked(fetchMock).mock.calls.some(([url, init]) => String(url).endsWith(`/admin/promotions/${promotion.id}`) && init?.method === 'DELETE')).toBe(true));
});

it('pins a manager to their own business when sending a notification', async () => {
  const user = userEvent.setup();
  const fetchMock = renderContent('business_manager');
  await screen.findByText('Выиграй авто');
  expect(screen.queryByLabelText('Бизнес')).not.toBeInTheDocument();
  await user.click(screen.getByRole('tab', { name: 'Уведомления' }));
  await user.click(await screen.findByRole('button', { name: 'Отправить уведомление' }));
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).queryByLabelText('Кому')).not.toBeInTheDocument();
  await user.type(within(dialog).getByLabelText('Заголовок'), 'Новая акция');
  await user.type(within(dialog).getByLabelText('Текст'), 'Скидки до 30%');
  await user.click(within(dialog).getByRole('button', { name: 'Отправить' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const sent = vi.mocked(fetchMock).mock.calls.find(([url, init]) => String(url).endsWith('/admin/notifications') && init?.method === 'POST');
  expect(JSON.parse(String(sent?.[1]?.body))).toEqual({ title: 'Новая акция', body: 'Скидки до 30%' });
});
