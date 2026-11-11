import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 4180
BASE_URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = Path("/Users/nuras/Desktop/cashback-one/reports/owner-revisions-2-2026-11-11")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

MOCK_SCRIPT = """
(() => {
    localStorage.setItem('cashback_one_locale', 'ru');
    localStorage.setItem('i18nextLng', 'ru');
    window.__mockRole = window.__mockRole || 'superadmin';
    window.__mockBusinessId = window.__mockBusinessId || 'biz-keremet';
    window.__mockBusinessName = window.__mockBusinessName || 'Супермаркет «Керемет»';
    window.__mockDashboardFail = window.__mockDashboardFail || false;

    const bId = 'biz-keremet';
    const bName = 'Супермаркет «Керемет»';

    const mockBusinesses = [
        {
            id: 'biz-keremet',
            name: 'Супермаркет «Керемет»',
            android_app_id: 'kz.cashbackone.keremet',
            logo_url: 'https://cashback-qr.poscenter.kz/media/logos/keremet.webp',
            status: 'active',
            colors: { primary_color: '#0d5c3a' },
            barcode_prefixes: ['0000'],
            cards_count: 1200,
            unblocked_cards_count: 1180,
            customers_with_cards_count: 1050,
            agents_count: 2,
            created_at: '2026-11-01T00:00:00Z',
            updated_at: '2026-11-01T00:00:00Z'
        },
        {
            id: 'biz-poscenter',
            name: 'Poscenter Общий',
            android_app_id: null,
            logo_url: null,
            status: 'active',
            colors: { primary_color: '#155d4a' },
            barcode_prefixes: ['012'],
            cards_count: 500,
            unblocked_cards_count: 490,
            customers_with_cards_count: 450,
            agents_count: 1,
            created_at: '2026-11-02T00:00:00Z',
            updated_at: '2026-11-02T00:00:00Z'
        },
        { id: 'biz-3', name: 'Магазин «Алтын»', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['013'], cards_count: 50, unblocked_cards_count: 50, customers_with_cards_count: 40, agents_count: 1, created_at: '2026-11-03T00:00:00Z', updated_at: '2026-11-03T00:00:00Z' },
        { id: 'biz-4', name: 'Аптека 24', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['014'], cards_count: 60, unblocked_cards_count: 58, customers_with_cards_count: 55, agents_count: 1, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z' },
        { id: 'biz-5', name: 'Кофейня Aroma', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['015'], cards_count: 70, unblocked_cards_count: 70, customers_with_cards_count: 65, agents_count: 1, created_at: '2026-11-05T00:00:00Z', updated_at: '2026-11-05T00:00:00Z' },
        { id: 'biz-6', name: 'Электроника Plus', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['016'], cards_count: 80, unblocked_cards_count: 75, customers_with_cards_count: 70, agents_count: 1, created_at: '2026-11-06T00:00:00Z', updated_at: '2026-11-06T00:00:00Z' },
        { id: 'biz-7', name: 'Книжный Мир', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['017'], cards_count: 90, unblocked_cards_count: 90, customers_with_cards_count: 85, agents_count: 1, created_at: '2026-11-07T00:00:00Z', updated_at: '2026-11-07T00:00:00Z' },
        { id: 'biz-8', name: 'Фитнес Центр', android_app_id: null, logo_url: null, status: 'active', colors: null, barcode_prefixes: ['018'], cards_count: 100, unblocked_cards_count: 100, customers_with_cards_count: 95, agents_count: 1, created_at: '2026-11-08T00:00:00Z', updated_at: '2026-11-08T00:00:00Z' }
    ];

    const mockTiers = [
        { id: 'tier-1', business_id: bId, level: 1, priority: 1, name_ru: 'Базовый', name_kk: 'Базалық', percent: '3.00', min_turnover: '0.00', max_turnover: '50000.00', turnover_period_months: 1, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-2', business_id: bId, level: 2, priority: 2, name_ru: 'Серебряный', name_kk: 'Күміс', percent: '5.00', min_turnover: '50000.00', max_turnover: '150000.00', turnover_period_months: 3, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-3', business_id: bId, level: 3, priority: 3, name_ru: 'Золотой', name_kk: 'Алтын', percent: '7.00', min_turnover: '150000.00', max_turnover: '300000.00', turnover_period_months: 3, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-4', business_id: bId, level: 4, priority: 4, name_ru: 'Платиновый', name_kk: 'Платина', percent: '10.00', min_turnover: '300000.00', max_turnover: '500000.00', turnover_period_months: 6, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-5', business_id: bId, level: 5, priority: 5, name_ru: 'VIP', name_kk: 'VIP', percent: '12.00', min_turnover: '500000.00', max_turnover: '1000000.00', turnover_period_months: 6, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-6', business_id: bId, level: 6, priority: 6, name_ru: 'Премиум', name_kk: 'Премиум', percent: '15.00', min_turnover: '1000000.00', max_turnover: '2000000.00', turnover_period_months: 12, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-7', business_id: bId, level: 7, priority: 7, name_ru: 'Элит', name_kk: 'Элита', percent: '18.00', min_turnover: '2000000.00', max_turnover: '5000000.00', turnover_period_months: 12, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' },
        { id: 'tier-8', business_id: bId, level: 8, priority: 8, name_ru: 'Партнёр', name_kk: 'Серіктес', percent: '20.00', min_turnover: '5000000.00', max_turnover: null, turnover_period_months: 12, is_active: true, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' }
    ];

    const mockUsers = [
        { id: 'u-1', phone_masked: '+7 701 •••• 4321', language: 'ru', created_at: '2026-11-01T10:00:00Z', business_cards_count: 1 },
        { id: 'u-2', phone_masked: '+7 702 •••• 4321', language: 'kk', created_at: '2026-11-02T11:00:00Z', business_cards_count: 1 },
        { id: 'u-3', phone_masked: '+7 705 •••• 9876', language: 'ru', created_at: '2026-11-03T12:00:00Z', business_cards_count: 1 },
        { id: 'u-4', phone_masked: '+7 707 •••• 1122', language: 'ru', created_at: '2026-11-04T13:00:00Z', business_cards_count: 2 },
        { id: 'u-5', phone_masked: '+7 777 •••• 3344', language: 'kk', created_at: '2026-11-05T14:00:00Z', business_cards_count: 1 },
        { id: 'u-6', phone_masked: '+7 708 •••• 5566', language: 'ru', created_at: '2026-11-06T15:00:00Z', business_cards_count: 1 },
        { id: 'u-7', phone_masked: '+7 747 •••• 7788', language: 'ru', created_at: '2026-11-07T16:00:00Z', business_cards_count: 1 },
        { id: 'u-8', phone_masked: '+7 771 •••• 9900', language: 'kk', created_at: '2026-11-08T17:00:00Z', business_cards_count: 1 }
    ];

    const mockCards = [
        { id: 'c-1', business_id: bId, business_name: bName, barcode: '0000123454321', phone_masked: '+7 701 •••• 4321', balance: '150.00', is_blocked: false, updated_at: '2026-11-11T20:30:00Z', bind_method: 'manual', bound_at: '2026-11-01T10:00:00Z', hidden_at: null },
        { id: 'c-2', business_id: bId, business_name: bName, barcode: '9999000004321', phone_masked: '+7 702 •••• 4321', balance: '200.00', is_blocked: false, updated_at: '2026-11-10T12:30:00Z', bind_method: 'manual', bound_at: '2026-11-02T11:00:00Z', hidden_at: null },
        { id: 'c-3', business_id: bId, business_name: bName, barcode: '0000123454323', phone_masked: '+7 705 •••• 9876', balance: '350.00', is_blocked: false, updated_at: '2026-11-09T14:00:00Z', bind_method: 'manual', bound_at: '2026-11-03T12:00:00Z', hidden_at: null },
        { id: 'c-4', business_id: bId, business_name: bName, barcode: '0000123454324', phone_masked: '+7 707 •••• 1122', balance: '400.00', is_blocked: false, updated_at: '2026-11-08T15:00:00Z', bind_method: 'manual', bound_at: '2026-11-04T13:00:00Z', hidden_at: null },
        { id: 'c-5', business_id: bId, business_name: bName, barcode: '0000123454325', phone_masked: '+7 777 •••• 3344', balance: '500.00', is_blocked: false, updated_at: '2026-11-07T16:00:00Z', bind_method: 'manual', bound_at: '2026-11-05T14:00:00Z', hidden_at: null },
        { id: 'c-6', business_id: bId, business_name: bName, barcode: '0000123454326', phone_masked: '+7 708 •••• 5566', balance: '600.00', is_blocked: false, updated_at: '2026-11-06T17:00:00Z', bind_method: 'manual', bound_at: '2026-11-06T15:00:00Z', hidden_at: null },
        { id: 'c-7', business_id: bId, business_name: bName, barcode: '0000123454327', phone_masked: '+7 747 •••• 7788', balance: '700.00', is_blocked: false, updated_at: '2026-11-05T18:00:00Z', bind_method: 'manual', bound_at: '2026-11-07T16:00:00Z', hidden_at: null },
        { id: 'c-8', business_id: bId, business_name: bName, barcode: '0000123454328', phone_masked: '+7 771 •••• 9900', balance: '800.00', is_blocked: false, updated_at: '2026-11-04T19:00:00Z', bind_method: 'manual', bound_at: '2026-11-08T17:00:00Z', hidden_at: null }
    ];

    const mockAgents = [
        { id: 'agent-1', business_id: bId, business_name: bName, ip_address: '192.168.1.10', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:50:00Z', created_at: '2026-11-01T00:00:00Z', revoked_at: null },
        { id: 'agent-2', business_id: bId, business_name: bName, ip_address: '192.168.1.11', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:45:00Z', created_at: '2026-11-01T00:00:00Z', revoked_at: null },
        { id: 'agent-3', business_id: 'biz-poscenter', business_name: 'Poscenter Общий', ip_address: '192.168.2.10', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:40:00Z', created_at: '2026-11-02T00:00:00Z', revoked_at: null },
        { id: 'agent-4', business_id: 'biz-3', business_name: 'Магазин «Алтын»', ip_address: '192.168.3.10', version: '0.3.0', status: 'stale', last_heartbeat_at: '2026-11-11T12:00:00Z', created_at: '2026-11-03T00:00:00Z', revoked_at: null },
        { id: 'agent-5', business_id: 'biz-4', business_name: 'Аптека 24', ip_address: '192.168.4.10', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:30:00Z', created_at: '2026-11-04T00:00:00Z', revoked_at: null },
        { id: 'agent-6', business_id: 'biz-5', business_name: 'Кофейня Aroma', ip_address: '192.168.5.10', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:25:00Z', created_at: '2026-11-05T00:00:00Z', revoked_at: null },
        { id: 'agent-7', business_id: 'biz-6', business_name: 'Электроника Plus', ip_address: '192.168.6.10', version: '0.3.0', status: 'stale', last_heartbeat_at: '2026-11-11T15:00:00Z', created_at: '2026-11-06T00:00:00Z', revoked_at: null },
        { id: 'agent-8', business_id: 'biz-7', business_name: 'Книжный Мир', ip_address: '192.168.7.10', version: '0.4.0', status: 'online', last_heartbeat_at: '2026-11-12T01:20:00Z', created_at: '2026-11-07T00:00:00Z', revoked_at: null }
    ];

    const mockPromotions = [
        { id: 'promo-1', business_id: bId, kind: 'banner', title: 'Осенний фестиваль бонусов', subtitle: 'Бонусы до 30% на все сезонные овощи и фрукты', badge: 'Акция', body: 'Правила начисления бонусов.', image_url: null, starts_at: '2026-11-01T05:00:00Z', ends_at: '2026-11-30T18:59:59Z', is_active: true, sort_order: 10, created_at: '2026-11-01T05:00:00Z', updated_at: '2026-11-01T05:00:00Z' },
        { id: 'promo-2', business_id: bId, kind: 'offer', title: 'Кешбэк 5% бонусами', subtitle: 'Каждую среду повышенный бонус', badge: 'Кешбэк', body: 'Начисляется автоматически.', image_url: null, starts_at: '2026-11-05T05:00:00Z', ends_at: null, is_active: true, sort_order: 20, created_at: '2026-11-05T05:00:00Z', updated_at: '2026-11-05T05:00:00Z' },
        { id: 'promo-3', business_id: bId, kind: 'banner', title: 'Бонусы за покупки', subtitle: 'Двойные бонусы в выходные', badge: 'Бонусы', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-06T05:00:00Z', ends_at: null, is_active: true, sort_order: 30, created_at: '2026-11-06T05:00:00Z', updated_at: '2026-11-06T05:00:00Z' },
        { id: 'promo-4', business_id: bId, kind: 'banner', title: 'Бонусный четверг', subtitle: 'Скидки и бонусы', badge: 'Акция', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-07T05:00:00Z', ends_at: null, is_active: true, sort_order: 40, created_at: '2026-11-07T05:00:00Z', updated_at: '2026-11-07T05:00:00Z' },
        { id: 'promo-5', business_id: bId, kind: 'banner', title: 'Специальные бонусы', subtitle: 'Только для держателей карт', badge: 'VIP', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-08T05:00:00Z', ends_at: null, is_active: true, sort_order: 50, created_at: '2026-11-08T05:00:00Z', updated_at: '2026-11-08T05:00:00Z' },
        { id: 'promo-6', business_id: bId, kind: 'banner', title: 'Праздничный бонус', subtitle: 'Накопительные бонусы', badge: 'Праздник', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-09T05:00:00Z', ends_at: null, is_active: true, sort_order: 60, created_at: '2026-11-09T05:00:00Z', updated_at: '2026-11-09T05:00:00Z' },
        { id: 'promo-7', business_id: bId, kind: 'banner', title: 'Бонусы недели', subtitle: 'Новые начисления', badge: 'Неделя', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-10T05:00:00Z', ends_at: null, is_active: true, sort_order: 70, created_at: '2026-11-10T05:00:00Z', updated_at: '2026-11-10T05:00:00Z' },
        { id: 'promo-8', business_id: bId, kind: 'banner', title: 'Утренний бонус', subtitle: 'Утренние часы покупок', badge: 'Утро', body: 'Подробности в магазине.', image_url: null, starts_at: '2026-11-11T05:00:00Z', ends_at: null, is_active: true, sort_order: 80, created_at: '2026-11-11T05:00:00Z', updated_at: '2026-11-11T05:00:00Z' }
    ];

    const mockAudit = [
        { id: 'aud-1', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: bId, action: 'update_business', entity: 'business', before_state: { name: 'Керемет' }, after_state: { name: 'Супермаркет «Керемет»' }, created_at: '2026-11-12T01:30:00Z' },
        { id: 'aud-2', actor: 'manager@keremet.kz', admin_user_id: 'admin-2', business_id: bId, action: 'create_promotion', entity: 'promotion', before_state: null, after_state: { title: 'Осенний фестиваль' }, created_at: '2026-11-12T01:00:00Z' },
        { id: 'aud-3', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: null, action: 'login', entity: 'session', before_state: null, after_state: { ip: '127.0.0.1' }, created_at: '2026-11-12T00:30:00Z' },
        { id: 'aud-4', actor: 'manager@keremet.kz', admin_user_id: 'admin-2', business_id: bId, action: 'update_tier', entity: 'tier', before_state: { percent: '2.5' }, after_state: { percent: '3.0' }, created_at: '2026-11-11T20:30:00Z' },
        { id: 'aud-5', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: 'biz-poscenter', action: 'create_pos_key', entity: 'pos_key', before_state: null, after_state: { name: 'Касса 1' }, created_at: '2026-11-11T18:00:00Z' },
        { id: 'aud-6', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: bId, action: 'create_agent', entity: 'agent', before_state: null, after_state: { ip: '192.168.1.10' }, created_at: '2026-11-11T15:00:00Z' },
        { id: 'aud-7', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: null, action: 'system_check', entity: 'system', before_state: null, after_state: { status: 'healthy' }, created_at: '2026-11-11T12:00:00Z' },
        { id: 'aud-8', actor: 'superadmin@poscenter.kz', admin_user_id: 'admin-1', business_id: null, action: 'login', entity: 'session', before_state: null, after_state: { ip: '127.0.0.1' }, created_at: '2026-11-11T09:00:00Z' }
    ];

    const origFetch = window.fetch;
    window.fetch = async (input, init = {}) => {
        const url = typeof input === 'string' ? input : input.url;
        const method = init.method || 'GET';

        if (url.includes('/admin/auth/refresh')) {
            return new Response(JSON.stringify({
                access_token: 'mock-access-token',
                token_type: 'bearer',
                expires_in: 3600
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/auth/logout')) {
            return new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/me')) {
            const currentRole = window.__mockRole || 'superadmin';
            return new Response(JSON.stringify({
                admin: {
                    id: 'admin-1',
                    login: currentRole === 'superadmin' ? 'superadmin@poscenter.kz' : 'manager@keremet.kz',
                    role: currentRole,
                    business: currentRole === 'business_manager' ? {
                        id: bId,
                        name: bName,
                        status: 'active',
                        logo_url: 'https://cashback-qr.poscenter.kz/media/logos/keremet.webp',
                        android_app_id: 'kz.cashbackone.keremet'
                    } : null
                },
                admin_max_stats_period_days: 90
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/stores')) {
            return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        if (url.includes('/app-texts')) {
            return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        if (url.includes('/splash')) {
            return new Response(JSON.stringify({ media_type: 'none', is_active: false }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        if (url.includes('/pos-keys')) {
            return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/manager-access')) {
            return new Response(JSON.stringify({
                login: 'keremet_manager',
                password: 'SecretSecurePassword2026!',
                login_url: 'https://cashback-qr.poscenter.kz/admin/login',
                one_time: true
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if ((url.endsWith('/admin/businesses') || url.includes('/admin/businesses?')) && method === 'GET') {
            return new Response(JSON.stringify({
                items: mockBusinesses,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/businesses/') && method === 'GET') {
            const biz = mockBusinesses[0];
            return new Response(JSON.stringify(biz), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/dashboard')) {
            if (window.__mockDashboardFail) {
                return new Response(JSON.stringify({
                    error: { code: 'ADMIN_PERIOD_TOO_LARGE', message: 'Выберите более короткий период' }
                }), { status: 422, headers: { 'Content-Type': 'application/json' } });
            }
            return new Response(JSON.stringify({
                period_from: '2026-10-13T19:00:00Z',
                period_to: '2026-11-11T18:59:59Z',
                period_days: 30,
                cards: 2150,
                customers_with_business_cards: 1980,
                unblocked_cards: 1850,
                transactions: 8068,
                accrual_count: 5500,
                redemption_count: 2568,
                accrual_sum: '15420300.0000',
                redemption_sum: '3104500.0000',
                notifications_sent: 120,
                active_promotions: 8,
                agents: { online: 6, stale: 2, never_connected: 0, error: 0, disabled: 0 }
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/loyalty-tiers')) {
            return new Response(JSON.stringify(mockTiers), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/users')) {
            return new Response(JSON.stringify({
                items: mockUsers,
                total: mockUsers.length,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/cards')) {
            return new Response(JSON.stringify({
                items: mockCards,
                total: mockCards.length,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/agents')) {
            return new Response(JSON.stringify({
                items: mockAgents,
                total: mockAgents.length,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/promotions')) {
            return new Response(JSON.stringify({
                items: mockPromotions,
                total: mockPromotions.length,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/audit')) {
            return new Response(JSON.stringify({
                items: mockAudit,
                total: mockAudit.length,
                limit: 100,
                offset: 0,
                has_more: false
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/stores') || url.includes('/admin/pos-keys') || url.includes('/admin/notifications')) {
            return new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        return origFetch(input, init);
    };
})();
"""

def main():
    import urllib.request
    admin_dir = Path("/Users/nuras/Desktop/cashback-one/admin")
    proc = subprocess.Popen(
        ["npm", "run", "preview", "--", "--port", str(PORT), "--host", "127.0.0.1"],
        cwd=str(admin_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Wait for server
        for _ in range(30):
            try:
                urllib.request.urlopen(BASE_URL)
                break
            except Exception:
                time.sleep(0.5)

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
            )

            # -------------------------------------------------------------
            # 1. Настройки (Settings cards) - desktop & mobile
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "01_settings_cards_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Настройки десктоп 1366px: иконка 44px справа вверху, заголовок и кнопка выровнены по левому краю", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            f_m = OUT_DIR / "01_settings_cards_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Настройки мобильные 390px: адаптивная вёрстка карточек с иконкой справа", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 2. Ошибка периода с «Назад» и после возврата
            # Dashboard with period error
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.add_init_script("window.__mockDashboardFail = true;")
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "02_period_error_with_back_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Дашборд десктоп: форма фильтров и выбор бизнеса остались на экране, рядом плашка ошибки и кнопка «Назад»", "sha256": sha256_file(f)})

            # Click "Назад" to recover
            page.evaluate("window.__mockDashboardFail = false;")
            page.click('button:has-text("Назад")')
            page.wait_for_timeout(600)
            f_rec = OUT_DIR / "02b_period_error_recovered_desktop.png"
            page.screenshot(path=str(f_rec), full_page=False)
            results.append({"name": f_rec.name, "desc": "Дашборд десктоп после нажатия «Назад»: восстановлен рабочий период, метрики отображаются", "sha256": sha256_file(f_rec)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.add_init_script("window.__mockDashboardFail = true;")
            page_m.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            f_m = OUT_DIR / "02_period_error_with_back_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Дашборд мобильный: сохранение фильтров при ошибке периода и кнопка «Назад»", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 3. Подсказка о 90 днях и блокировка «Обновить»
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            from_input = page.locator('.filter-controls input[type="date"]').nth(0)
            to_input = page.locator('.filter-controls input[type="date"]').nth(1)
            from_input.fill('2026-01-01')
            to_input.fill('2026-06-01')
            page.wait_for_timeout(400)
            f = OUT_DIR / "03_period_too_large_guard_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Дашборд десктоп: период >90 дней показывает подсказку, кнопка «Обновить» заблокирована", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            page_m.locator('.filter-controls input[type="date"]').nth(0).fill('2026-01-01')
            page_m.locator('.filter-controls input[type="date"]').nth(1).fill('2026-06-01')
            page_m.wait_for_timeout(400)
            f_m = OUT_DIR / "03_period_too_large_guard_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Дашборд мобильный: подсказка о лимите 90 дней и блокировка кнопки", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 4. Дата и время в UTC+5 (Астана)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "04_astana_time_utc5_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Дашборд десктоп: подпись «Время Астаны (UTC+5)» вместо UTC", "sha256": sha256_file(f)})
            ctx.close()

            # -------------------------------------------------------------
            # 5. Выпадающий список (select) с достаточным отступом справа
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/businesses", wait_until="networkidle")
            page.wait_for_timeout(600)
            page.click('button:has-text("Создать бизнес")')
            page.wait_for_timeout(400)
            f = OUT_DIR / "05_select_dropdown_padding_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Диалог бизнеса десктоп: поля формы и select со свободным отступом до шеврона", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/businesses", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            page_m.click('button:has-text("Создать бизнес")')
            page_m.wait_for_timeout(400)
            f_m = OUT_DIR / "05_select_dropdown_padding_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Диалог бизнеса мобильный: поля формы и select", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 6. Окно «Доступ клиента к админке» (п.14)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.on("dialog", lambda d: d.accept())
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/businesses/biz-keremet", wait_until="networkidle")
            page.wait_for_timeout(600)
            page.click('button:has-text("Выдать доступ")')
            page.wait_for_timeout(500)
            f = OUT_DIR / "06_manager_access_dialog_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Окно доступа десктоп: кнопка «Скопировать всё» по центру, нижняя «Закрыть» убрана", "sha256": sha256_file(f)})

            # Click copy all to verify reserved height
            page.click('button:has-text("Скопировать всё")')
            page.wait_for_timeout(300)
            f_copied = OUT_DIR / "06b_manager_access_copied_desktop.png"
            page.screenshot(path=str(f_copied), full_page=False)
            results.append({"name": f_copied.name, "desc": "Окно доступа после копирования: статус отображается без сдвига разметки", "sha256": sha256_file(f_copied)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.on("dialog", lambda d: d.accept())
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/businesses/biz-keremet", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            page_m.click('button:has-text("Выдать доступ")')
            page_m.wait_for_timeout(500)
            f_m = OUT_DIR / "06_manager_access_dialog_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Окно доступа мобильное: кнопка «Скопировать всё» по центру", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 7. Логотип бизнеса (список бизнесов, детальная, аватарка)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/businesses", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "07_business_logo_list_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Список бизнесов десктоп: колонка «Логотип» отображает логотип или «Нет»", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/businesses", wait_until="networkidle")
            page_m.wait_for_timeout(600)
            f_m = OUT_DIR / "07_business_logo_list_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Список бизнесов мобильный: колонка логотипа", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 8. Шапка лендинга (убрана «Для бизнеса» рядом с «Вход для бизнеса»)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.goto(f"{BASE_URL}/", wait_until="networkidle")
            page.wait_for_timeout(500)
            f = OUT_DIR / "08_landing_header_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Шапка лендинга десктоп: кнопка «Для бизнеса» убрана рядом со ссылкой «Вход для бизнеса»", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.goto(f"{BASE_URL}/", wait_until="networkidle")
            page_m.wait_for_timeout(500)
            f_m = OUT_DIR / "08_landing_header_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Шапка лендинга мобильная: только «Вход для бизнеса» и переключатель языка", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 9. Блоки лендинга с «бонусами»
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.goto(f"{BASE_URL}/#bonus", wait_until="networkidle")
            page.locator('#bonus').scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            f = OUT_DIR / "09_landing_bonus_wording_desktop.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Блок лендинга «Бонусы» десктоп: формулировки «Как работают бонусы», без «баллы»", "sha256": sha256_file(f)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.goto(f"{BASE_URL}/#bonus", wait_until="networkidle")
            page_m.locator('#bonus').scroll_into_view_if_needed()
            page_m.wait_for_timeout(500)
            f_m = OUT_DIR / "09_landing_bonus_wording_mobile.png"
            page_m.screenshot(path=str(f_m), full_page=False)
            results.append({"name": f_m.name, "desc": "Блок лендинга «Бонусы» мобильный: правильные формулировки", "sha256": sha256_file(f_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # 10. Таблицы суперадминистратора по 7 строк с кнопкой «Все (N)»
            # Businesses table
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/businesses", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10a_superadmin_table_businesses_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Бизнесы: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Agents table
            page.goto(f"{BASE_URL}/admin/agents", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10b_superadmin_table_agents_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Агенты: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Statuses table
            page.goto(f"{BASE_URL}/admin/statuses", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10c_superadmin_table_statuses_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Статусы: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Content table
            page.goto(f"{BASE_URL}/admin/content", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10d_superadmin_table_content_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Контент: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Audit table
            page.goto(f"{BASE_URL}/admin/audit", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10e_superadmin_table_audit_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Журнал: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Operations (cards)
            page.goto(f"{BASE_URL}/admin/operations", wait_until="networkidle")
            page.wait_for_timeout(600)
            f = OUT_DIR / "10f_superadmin_table_cards_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Карты: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})

            # Operations (users)
            page.click('button:has-text("По телефону")')
            page.wait_for_timeout(600)
            f = OUT_DIR / "10g_superadmin_table_users_7_rows.png"
            page.screenshot(path=str(f), full_page=False)
            results.append({"name": f.name, "desc": "Суперадминистратор — Клиенты: компактная таблица ровно 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(f)})
            ctx.close()

            # -------------------------------------------------------------
            # Inspection of scrolls and buttons across screens (Point 8)
            screens_to_check = [
                ('/admin', 'Главная / Обзор'),
                ('/admin/businesses', 'Бизнесы'),
                ('/admin/operations', 'Карты / Клиенты'),
                ('/admin/statuses', 'Статусы лояльности'),
                ('/admin/content', 'Контент и баннеры'),
                ('/admin/agents', 'Агенты касс'),
                ('/admin/settings', 'Настройки'),
                ('/admin/audit', 'Журнал действий'),
            ]

            scroll_report = []
            for path_str, name in screens_to_check:
                for width, height, mode in [(1366, 768, 'desktop'), (390, 844, 'mobile')]:
                    ctx_s = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=(mode == 'mobile'))
                    page_s = ctx_s.new_page()
                    page_s.add_init_script(MOCK_SCRIPT)
                    page_s.goto(f"{BASE_URL}{path_str}", wait_until="networkidle")
                    page_s.wait_for_timeout(400)

                    # Check for nested scrollable elements
                    nested_scrolls = page_s.evaluate("""
                        () => {
                            const elements = Array.from(document.querySelectorAll('*'));
                            const scrollables = [];
                            for (const el of elements) {
                                if (el === document.body || el === document.documentElement) continue;
                                const style = window.getComputedStyle(el);
                                const hasScrollY = (style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
                                if (hasScrollY && !el.classList.contains('table-responsive')) {
                                    scrollables.push({ tag: el.tagName, className: el.className, id: el.id, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight });
                                }
                            }
                            return scrollables;
                        }
                    """)
                    scroll_report.append({
                        "screen": f"{name} ({mode} {width}x{height})",
                        "nested_scrolls": nested_scrolls,
                        "status": "ОК (нет лишних прокруток)" if not nested_scrolls else f"Вложенная прокрутка: {nested_scrolls}"
                    })
                    ctx_s.close()

            browser.close()

        print(json.dumps({"results": results, "scroll_report": scroll_report}, indent=2, ensure_ascii=False))

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

if __name__ == '__main__':
    main()
