// Demo mode (EXPO_PUBLIC_DEMO=1): an in-memory stand-in for the Cloud API with sample data, so the app can be
// viewed without WhatsApp delivery or a customer database. Never used unless the flag is set at build time.
import type { Badges, Card, CardQr, HistoryPage, Notifications, Profile, Promotion, Promotions, Tokens, Transaction, WalletAvailability } from '../types/api';

export const DEMO_ENABLED = process.env.EXPO_PUBLIC_DEMO === '1';
export const DEMO_BASE_URL = 'https://demo.invalid';
export const demoTokens: Tokens = { access_token: 'demo-access', refresh_token: 'demo-refresh', token_type: 'bearer', expires_in: 900 };

// Sample artwork served next to the demo build (cut from the design mockup); real content comes from the admin by URL.
const IMG = '/demo/img/';
const REF_IMG = `${IMG}reference-redesign/`;
const daysAgo = (days: number, hour = 12) => { const d = new Date(); d.setDate(d.getDate() - days); d.setHours(hour, 15, 0, 0); return d.toISOString(); };

export function createDemoApi() {
  const card: Card = {
    id: 'demo-card', barcode: '0123456789012', balance: '0.0000', is_blocked: false, updated_at: daysAgo(0), bound_at: daysAgo(30), bind_method: 'phone_auto',
    business: { id: 'demo-business', name: 'POSCENTER Маркет', branding: null },
    tier: {
      level: 1, name: 'Статус 1', percent: '3.0000', max_percent: '12.0000', spend_total: '0.0000', next_level: 2, next_threshold: '350000.0000', remaining: '350000.0000',
      levels: [
        { level: 1, name: null, threshold: '0.0000', percent: '3.0000' }, { level: 2, name: null, threshold: '350000.0000', percent: '5.0000' },
        { level: 3, name: null, threshold: '800000.0000', percent: '8.0000' }, { level: 4, name: null, threshold: '1500000.0000', percent: '12.0000' },
      ],
    },
  };
  const transactions: Transaction[] = [
    { id: 't5', external_id: 'e5', type: 'accrual', amount: '2450.0000', balance_after: '2450.0000', occurred_at: daysAgo(0, 9), receipt_ref: null, store: 'Магазин №2' },
    { id: 't4', external_id: 'e4', type: 'redemption', amount: '1500.0000', balance_after: '0.0000', occurred_at: daysAgo(1), receipt_ref: null, store: 'Магазин №1' },
    { id: 't3', external_id: 'e3', type: 'accrual', amount: '1500.0000', balance_after: '1500.0000', occurred_at: daysAgo(2), receipt_ref: null, store: 'Магазин №1' },
    { id: 't2', external_id: 'e2', type: 'accrual', amount: '830.0000', balance_after: '0.0000', occurred_at: daysAgo(9), receipt_ref: null, store: 'Магазин №3' },
    { id: 't1', external_id: 'e1', type: 'accrual', amount: '420.0000', balance_after: '830.0000', occurred_at: daysAgo(15), receipt_ref: null, store: 'Магазин №1' },
  ];
  const offer = (id: string, title: string, badge: string, extra: Partial<Promotion> = {}): Promotion => ({
    id, business_id: null, kind: 'offer', title, subtitle: null, badge, body: null, image_url: null, starts_at: null, ends_at: null, is_new: true, ...extra,
  });
  const promotions: Promotions = {
    banners: [
      { ...offer('b1', 'Выиграй авто', ''), kind: 'banner', subtitle: 'и другие ценные призы', badge: null, image_url: `${REF_IMG}banner-car-ribbon.png` },
      { ...offer('b2', 'Кэшбэк до 12%', ''), kind: 'banner', subtitle: 'за каждую покупку', badge: null, image_url: `${IMG}card.jpg` },
      { ...offer('b3', 'Подарки за покупки', ''), kind: 'banner', subtitle: 'каждый день', badge: null, image_url: `${IMG}gifts.jpg` },
    ],
    offers: [
      offer('o1', 'Покупайте выгодно', 'Скидка на хиты', { image_url: `${REF_IMG}offer-basket.png`, body: 'Скидки до 30% на популярные товары каждую неделю.' }),
      offer('o2', 'Товары по лучшим ценам', 'Акция недели', { image_url: `${REF_IMG}offer-discount-tag.png`, ends_at: new Date(Date.now() + 7 * 86_400_000).toISOString(), body: 'Специальные цены на товары недели.' }),
      offer('o3', 'Больше бонусов', 'Выгодно с картой', { image_url: `${REF_IMG}offer-loyalty-coins.png`, body: 'Оплачивайте картой и получайте повышенный кешбэк.' }),
      offer('o4', 'Свежие продукты', 'Суперцена', { image_url: `${REF_IMG}offer-fresh-produce.png` }),
    ],
    has_new: true,
  };
  let promotionsSeen = false;
  let notificationsRead = false;
  const notifications = [
    { id: 'n4', kind: 'accrual', title: 'Чек 15 000 ₸', body: '450,00 баллов начислено по статусу 3%.', created_at: daysAgo(0, 9) },
    { id: 'n3', kind: 'info', title: 'Добро пожаловать в ONE', body: 'QR-код готов. Покажите его кассиру — баллы начислятся после каждой покупки.', created_at: daysAgo(2) },
    { id: 'n2', kind: 'info', title: 'Хиты недели в зале', body: 'Красные ценники: молоко, хлеб и овощи. Не пропустите купон.', created_at: daysAgo(3) },
    { id: 'n1', kind: 'info', title: '2-й статус от 350 000 ₸', body: 'Сейчас 3%. На 4-м статусе каждая покупка даёт 12%.', created_at: daysAgo(4) },
  ];
  let profile: Profile = { phone: '+7 7•• ••• •• 26', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };

  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  const error = (status: number, code: string) => json({ error: { code, message: code } }, status);
  const readBody = (init?: RequestInit): Record<string, unknown> => { try { return init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {}; } catch { return {}; } };

  // Same shape as a real QR token: "C1" + 48 chars of the base32 alphabet. Rotates every call so the dynamic QR visibly refreshes.
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const qr = (): CardQr => ({
    token: 'C1' + Array.from({ length: 48 }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join(''),
    expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60,
  });

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input));
    const path = url.pathname;
    const method = (init?.method ?? 'GET').toUpperCase();
    if (path === '/auth/refresh') return json(demoTokens);
    if (path === '/auth/logout') return json({ status: 'ok' });
    if (path === '/me/wallet' && method === 'GET') return json({ apple: false, google: false } satisfies WalletAvailability);
    if (path === '/me/cards' && method === 'GET') return json([card]);
    if (path === '/me/cards/bind') return json(card);
    if (path === `/me/cards/${card.id}` && method === 'GET') return json(card);
    if (path === `/me/cards/${card.id}` && method === 'DELETE') return new Response(null, { status: 204 });
    if (path === `/me/cards/${card.id}/qr`) return json(qr());
    if (path === `/me/cards/${card.id}/transactions`) {
      const type = url.searchParams.get('type');
      const items = type ? transactions.filter(t => t.type === type) : transactions;
      return json({ items, next_cursor: null, has_more: false } satisfies HistoryPage);
    }
    if (path === '/me/profile' && method === 'GET') return json(profile);
    if (path === '/me/profile' && method === 'PATCH') { profile = { ...profile, ...readBody(init) } as Profile; return json(profile); }
    if (path === '/me/promotions' && method === 'GET') {
      const mark = (list: Promotion[]) => list.map(p => ({ ...p, is_new: !promotionsSeen && p.is_new }));
      return json({ banners: mark(promotions.banners), offers: mark(promotions.offers), has_new: !promotionsSeen } satisfies Promotions);
    }
    if (path === '/me/promotions/seen') { promotionsSeen = true; return new Response(null, { status: 204 }); }
    const promo = /^\/me\/promotions\/([^/]+)$/.exec(path);
    if (promo) {
      const found = [...promotions.banners, ...promotions.offers].find(p => p.id === promo[1]);
      return found ? json(found) : error(404, 'PROMOTION_NOT_FOUND');
    }
    if (path === '/me/notifications' && method === 'GET') {
      return json({ items: notifications.map(n => ({ ...n, is_unread: !notificationsRead })), unread_count: notificationsRead ? 0 : notifications.length } satisfies Notifications);
    }
    if (path === '/me/notifications/read') { notificationsRead = true; return new Response(null, { status: 204 }); }
    if (path === '/me/badges') return json({ promotions_new: !promotionsSeen, notifications_unread: notificationsRead ? 0 : notifications.length } satisfies Badges);
    return error(404, 'NOT_FOUND');
  };
}
