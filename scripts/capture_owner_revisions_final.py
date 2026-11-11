import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 4175
BASE_URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = Path("/Users/nuras/Desktop/cashback-one/reports/owner-revisions-2026-11-11/final")
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
    window.__mockRole = window.__mockRole || 'business_manager';
    window.__mockBusinessId = window.__mockBusinessId || 'biz-keremet';
    window.__mockBusinessName = window.__mockBusinessName || 'Супермаркет «Керемет»';

    const bId = 'biz-keremet';
    const bName = 'Супермаркет «Керемет»';

    const mockBusinesses = [
        { id: 'biz-keremet', name: 'Супермаркет «Керемет»', android_app_id: 'kz.cashbackone.keremet', status: 'active', colors: { primary_color: '#0d5c3a' }, barcode_prefixes: ['0000'] },
        { id: 'biz-poscenter', name: 'Poscenter Общий', status: 'active', colors: { primary_color: '#155d4a' }, barcode_prefixes: ['012'] },
        { id: 'biz-3', name: 'Магазин «Алтын»', status: 'active', colors: { primary_color: '#d4af37' }, barcode_prefixes: ['013'] },
        { id: 'biz-4', name: 'Аптека 24', status: 'active', colors: { primary_color: '#008080' }, barcode_prefixes: ['014'] },
        { id: 'biz-5', name: 'Кофейня Aroma', status: 'active', colors: { primary_color: '#6f4e37' }, barcode_prefixes: ['015'] },
        { id: 'biz-6', name: 'Электроника Plus', status: 'active', colors: { primary_color: '#003366' }, barcode_prefixes: ['016'] },
        { id: 'biz-7', name: 'Книжный Мир', status: 'active', colors: { primary_color: '#800020' }, barcode_prefixes: ['017'] },
        { id: 'biz-8', name: 'Фитнес Центр', status: 'active', colors: { primary_color: '#ff4500' }, barcode_prefixes: ['018'] }
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
        { id: 'u-1', phone_masked: '+7 701 •••• 4321', language: 'ru', created_at: '2026-11-01T10:00:00Z', cards_count: 1 },
        { id: 'u-2', phone_masked: '+7 702 •••• 4321', language: 'kk', created_at: '2026-11-02T11:00:00Z', cards_count: 1 },
        { id: 'u-3', phone_masked: '+7 705 •••• 9876', language: 'ru', created_at: '2026-11-03T12:00:00Z', cards_count: 1 },
        { id: 'u-4', phone_masked: '+7 707 •••• 1122', language: 'ru', created_at: '2026-11-04T13:00:00Z', cards_count: 2 },
        { id: 'u-5', phone_masked: '+7 777 •••• 3344', language: 'kk', created_at: '2026-11-05T14:00:00Z', cards_count: 1 },
        { id: 'u-6', phone_masked: '+7 708 •••• 5566', language: 'ru', created_at: '2026-11-06T15:00:00Z', cards_count: 1 },
        { id: 'u-7', phone_masked: '+7 747 •••• 7788', language: 'ru', created_at: '2026-11-07T16:00:00Z', cards_count: 1 },
        { id: 'u-8', phone_masked: '+7 771 •••• 9900', language: 'kk', created_at: '2026-11-08T17:00:00Z', cards_count: 1 }
    ];

    const mockCards = [
        { id: 'c-1', barcode: '0000123454321', phone_masked: '+7 701 •••• 4321', balance: '150.00', turnover: '45000.00', is_blocked: false, full_name: 'Айдар Смагулов', updated_at: '2026-11-10T12:00:00Z' },
        { id: 'c-2', barcode: '9999000004321', phone_masked: '+7 702 •••• 4321', balance: '200.00', turnover: '62000.00', is_blocked: false, full_name: 'Гульнара Каримова', updated_at: '2026-11-10T12:30:00Z' }
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
            return new Response(JSON.stringify({ status: 'ok' }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/me')) {
            const currentRole = window.__mockRole || 'business_manager';
            return new Response(JSON.stringify({
                admin: {
                    id: 'admin-1',
                    login: currentRole === 'superadmin' ? 'superadmin@poscenter.kz' : 'manager@keremet.kz',
                    role: currentRole,
                    business: currentRole === 'business_manager' ? {
                        id: bId,
                        name: bName,
                        status: 'active',
                        android_app_id: 'kz.cashbackone.keremet',
                        colors: { primary_color: '#0d5c3a' }
                    } : null
                }
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/loyalty-tiers')) {
            return new Response(JSON.stringify(mockTiers), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/stores')) {
            return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/pos-keys')) {
            return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if ((url.endsWith('/admin/businesses') || url.includes('/admin/businesses?')) && method === 'GET') {
            return new Response(JSON.stringify({ items: mockBusinesses, total: mockBusinesses.length, page: 1, size: 50, pages: 1 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/dashboard')) {
            return new Response(JSON.stringify({
                business_id: null,
                business_name: null,
                period_from: '2026-10-01T00:00:00Z',
                period_to: '2026-11-11T23:59:59Z',
                period_days: 42,
                customers_with_business_cards: 1540,
                cards: 1707,
                unblocked_cards: 1695,
                transactions: 8068,
                agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
                period: { from: '2026-10-01T00:00:00Z', to: '2026-11-11T23:59:59Z' },
                stats: {
                    total_cards: 1707,
                    active_cards: 1695,
                    total_users: 1540,
                    transactions_count: 8068,
                    turnover_sum: '15420300.00',
                    accrued_bonuses_sum: '462609.00',
                    redeemed_bonuses_sum: '310450.00'
                },
                daily_turnover: []
            }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/cards') && !url.includes('/search')) {
            return new Response(JSON.stringify({ items: mockCards, total: mockCards.length, page: 1, size: 25, pages: 1 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/cards/search')) {
            return new Response(JSON.stringify({ items: mockCards, total: mockCards.length, page: 1, size: 20, pages: 1 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/users/search')) {
            return new Response(JSON.stringify({ items: mockUsers.slice(0, 2), total: 2, page: 1, size: 20, pages: 1 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/users')) {
            return new Response(JSON.stringify({ items: mockUsers, total: mockUsers.length, page: 1, size: 20, pages: 1 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (url.includes('/admin/agents')) {
            return new Response(JSON.stringify({ items: [
                { id: 'a-1', business_id: bId, name: 'KONS2 Агент', version: '0.4.0', status: 'online', last_seen_at: '2026-11-11T09:40:00Z' }
            ] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/audit')) {
            return new Response(JSON.stringify({ items: [], total: 0, page: 1, size: 20, pages: 0 }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/content/promotions')) {
            return new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/content/notices')) {
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
            # Frame 1: Sidebar with reduced logo (-25%) and no LOYALTY · ADMIN
            # Desktop
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(500)
            p1_d = OUT_DIR / "01_sidebar_reduced_logo_desktop.png"
            page.screenshot(path=str(p1_d), full_page=False)
            results.append({"name": p1_d.name, "desc": "Сайдбар десктоп: логотип уменьшен на 25%, надпись LOYALTY · ADMIN удалена", "sha256": sha256_file(p1_d)})
            ctx.close()

            # Mobile (sidebar in drawer / header)
            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page_m.wait_for_timeout(500)
            p1_m = OUT_DIR / "01b_sidebar_reduced_logo_mobile.png"
            page_m.screenshot(path=str(p1_m), full_page=False)
            results.append({"name": p1_m.name, "desc": "Шапка мобильная: уменьшенный логотип", "sha256": sha256_file(p1_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # Frame 2: Compact table >7 rows collapsed & expanded
            # Collapsed (7 rows + «Все (8)»)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/statuses", wait_until="networkidle")
            page.wait_for_timeout(500)
            p2_col_d = OUT_DIR / "02a_compact_table_collapsed_desktop.png"
            page.screenshot(path=str(p2_col_d), full_page=False)
            results.append({"name": p2_col_d.name, "desc": "Таблица статусов десктоп: свёрнута до 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(p2_col_d)})

            # Expanded (8 rows + «Свернуть»)
            page.click('button:has-text("Все (8)")')
            page.wait_for_timeout(400)
            p2_exp_d = OUT_DIR / "02b_compact_table_expanded_desktop.png"
            page.screenshot(path=str(p2_exp_d), full_page=False)
            results.append({"name": p2_exp_d.name, "desc": "Таблица статусов десктоп: развёрнуты все 8 строк с кнопкой «Свернуть»", "sha256": sha256_file(p2_exp_d)})
            ctx.close()

            # Mobile collapsed & expanded
            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/statuses", wait_until="networkidle")
            page_m.wait_for_timeout(500)
            p2_col_m = OUT_DIR / "02c_compact_table_collapsed_mobile.png"
            page_m.screenshot(path=str(p2_col_m), full_page=False)
            results.append({"name": p2_col_m.name, "desc": "Таблица статусов mobile: свёрнута до 7 строк с кнопкой «Все (8)»", "sha256": sha256_file(p2_col_m)})

            page_m.click('button:has-text("Все (8)")')
            page_m.wait_for_timeout(400)
            p2_exp_m = OUT_DIR / "02d_compact_table_expanded_mobile.png"
            page_m.screenshot(path=str(p2_exp_m), full_page=False)
            results.append({"name": p2_exp_m.name, "desc": "Таблица статусов mobile: развёрнута на все 8 строк", "sha256": sha256_file(p2_exp_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # Frame 3: «Клиенты» (Operations): card search by suffix & default user list
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/operations", wait_until="networkidle")
            page.wait_for_timeout(500)

            # Search by suffix 4321
            card_input = page.locator('.search-panel input').first
            card_input.fill('4321')
            page.click('button:has-text("Найти")')
            page.wait_for_timeout(500)
            p3_card_d = OUT_DIR / "03a_clients_search_card_suffix_desktop.png"
            page.screenshot(path=str(p3_card_d), full_page=False)
            results.append({"name": p3_card_d.name, "desc": "Клиенты десктоп: поиск по суффиксу 4321, найдено 2 карты разных пользователей", "sha256": sha256_file(p3_card_d)})

            # Default user list
            page.click('button:has-text("По телефону")')
            page.wait_for_timeout(500)
            p3_user_d = OUT_DIR / "03b_clients_default_users_list_desktop.png"
            page.screenshot(path=str(p3_user_d), full_page=False)
            results.append({"name": p3_user_d.name, "desc": "Клиенты десктоп: вкладка «По телефону», список пользователей загружен сразу без ввода", "sha256": sha256_file(p3_user_d)})
            ctx.close()

            # Mobile search & default users
            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/operations", wait_until="networkidle")
            page_m.wait_for_timeout(500)

            card_input_m = page_m.locator('.search-panel input').first
            card_input_m.fill('4321')
            page_m.click('button:has-text("Найти")')
            page_m.wait_for_timeout(500)
            p3_card_m = OUT_DIR / "03c_clients_search_card_suffix_mobile.png"
            page_m.screenshot(path=str(p3_card_m), full_page=False)
            results.append({"name": p3_card_m.name, "desc": "Клиенты mobile: поиск карты по суффиксу 4321", "sha256": sha256_file(p3_card_m)})

            page_m.click('button:has-text("По телефону")')
            page_m.wait_for_timeout(500)
            p3_user_m = OUT_DIR / "03d_clients_default_users_list_mobile.png"
            page_m.screenshot(path=str(p3_user_m), full_page=False)
            results.append({"name": p3_user_m.name, "desc": "Клиенты mobile: список пользователей по умолчанию", "sha256": sha256_file(p3_user_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # Frame 4: Dashboard with invalid year (apply button disabled)
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(500)

            # Set invalid date in from input (e.g. from > to or invalid)
            # In Chrome date input, filling 2029-01-01 when max is today causes invalid range, or clearing to empty
            from_input = page.locator('input[type="date"]').first
            from_input.fill('2029-01-01')
            page.wait_for_timeout(400)

            # Check button is disabled
            apply_btn = page.locator('.filter-panel button.button-primary')
            is_disabled = apply_btn.is_disabled()
            assert is_disabled, "Expected apply button to be disabled for invalid period"

            p4_d = OUT_DIR / "04_dashboard_invalid_date_disabled_btn_desktop.png"
            page.screenshot(path=str(p4_d), full_page=False)
            results.append({"name": p4_d.name, "desc": "Дашборд десктоп: некорректная дата (кнопка применения отключена)", "sha256": sha256_file(p4_d)})
            ctx.close()

            # Mobile dashboard
            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page_m.wait_for_timeout(500)
            from_input_m = page_m.locator('input[type="date"]').first
            from_input_m.fill('2029-01-01')
            page_m.wait_for_timeout(400)
            p4_m = OUT_DIR / "04b_dashboard_invalid_date_disabled_btn_mobile.png"
            page_m.screenshot(path=str(p4_m), full_page=False)
            results.append({"name": p4_m.name, "desc": "Дашборд mobile: некорректная дата (кнопка применения отключена)", "sha256": sha256_file(p4_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # Frame 5: Settings with vertically centered titles
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            page.wait_for_timeout(500)
            p5_d = OUT_DIR / "05a_settings_vertical_centering_desktop.png"
            page.screenshot(path=str(p5_d), full_page=False)
            results.append({"name": p5_d.name, "desc": "Настройки десктоп: заголовки блоков выровнены по центру по вертикали", "sha256": sha256_file(p5_d)})
            ctx.close()

            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            page_m = ctx_m.new_page()
            page_m.add_init_script(MOCK_SCRIPT)
            page_m.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            page_m.wait_for_timeout(500)
            p5_m = OUT_DIR / "05b_settings_vertical_centering_mobile.png"
            page_m.screenshot(path=str(p5_m), full_page=False)
            results.append({"name": p5_m.name, "desc": "Настройки mobile: вертикальное выравнивание заголовков", "sha256": sha256_file(p5_m)})
            ctx_m.close()

            # -------------------------------------------------------------
            # Frame 6: Favicon verification
            # 6a: Keremet manager
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script("window.__mockRole = 'business_manager';")
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(500)
            fav_href_manager = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_manager == "/keremet-favicon.png", f"Expected /keremet-favicon.png, got {fav_href_manager}"
            p6_k = OUT_DIR / "06a_favicon_keremet_manager.png"
            page.screenshot(path=str(p6_k), full_page=False)
            results.append({"name": p6_k.name, "desc": f"Фавикон менеджера Керемет: href={fav_href_manager}", "sha256": sha256_file(p6_k)})
            ctx.close()

            # 6b: Superadmin switches to Poscenter Общий
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script("window.__mockRole = 'superadmin';")
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(500)

            biz_select = page.locator('select[aria-label="Бизнес"]')
            biz_select.select_option(value='biz-poscenter')
            page.wait_for_timeout(400)
            fav_href_other = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_other == "/brand-mark.png", f"Expected /brand-mark.png, got {fav_href_other}"
            p6_s = OUT_DIR / "06b_favicon_superadmin_other_business.png"
            page.screenshot(path=str(p6_s), full_page=False)
            results.append({"name": p6_s.name, "desc": f"Фавикон суперадмина при переключении на другой бизнес: href={fav_href_other}", "sha256": sha256_file(p6_s)})
            ctx.close()

            browser.close()

        with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print("\n--- CAPTURED FINAL SCREENSHOTS ---")
        for r in results:
            print(f"{r['name']} | {r['sha256']} | {r['desc']}")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
