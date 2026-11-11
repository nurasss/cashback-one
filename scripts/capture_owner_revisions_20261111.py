import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 4174
BASE_URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = Path("/Users/nuras/Desktop/cashback-one/reports/owner-revisions-2026-11-11")
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

        if (url.includes('/admin/businesses') && method === 'GET') {
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

        if (url.includes('/loyalty-tiers')) {
            return new Response(JSON.stringify(mockTiers), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
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

        if (url.includes('/admin/stores')) {
            return new Response(JSON.stringify({ items: [
                { id: 's-1', business_id: bId, name: 'Магазин №1 Самал', address: 'мкр. Самал-2, д. 111', is_active: true }
            ] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }

        if (url.includes('/admin/pos-keys')) {
            return new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
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

            # 1. Dashboard: 4-digit date input
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            p1 = OUT_DIR / "01_dashboard_date_4_digit_validation.png"
            page.screenshot(path=str(p1), full_page=False)
            results.append({"file": p1.name, "item": 1, "sha256": sha256_file(p1)})
            ctx.close()

            # 2. Favicon tests (Keremet manager, Superadmin select Keremet, switch other, logout to login screen)
            # 2a: Keremet manager login
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script("window.__mockRole = 'business_manager';")
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)

            # Check DOM link href (no page.evaluate mutation)
            fav_href_manager = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_manager == "/keremet-favicon.png", f"Expected /keremet-favicon.png, got {fav_href_manager}"
            resp_k = page.request.get(f"{BASE_URL}/keremet-favicon.png")
            assert resp_k.status == 200, f"Expected 200 for /keremet-favicon.png, got {resp_k.status}"

            p2 = OUT_DIR / "02_keremet_favicon_manager_active.png"
            page.screenshot(path=str(p2), full_page=False)
            results.append({"file": p2.name, "item": 2, "sha256": sha256_file(p2), "href": fav_href_manager, "http_status": resp_k.status})
            ctx.close()

            # 2b: Superadmin selects Keremet, then switches to other, then logs out
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script("window.__mockRole = 'superadmin';")
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)

            # Superadmin initial state: all businesses -> /brand-mark.png
            fav_href_initial = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_initial == "/brand-mark.png", f"Expected /brand-mark.png for superadmin default, got {fav_href_initial}"

            # Superadmin selects Keremet
            biz_select = page.locator('select[aria-label="Бизнес"]')
            biz_select.select_option(value='biz-keremet')
            page.wait_for_timeout(400)
            fav_href_super_k = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_super_k == "/keremet-favicon.png", f"Expected /keremet-favicon.png after selecting Keremet, got {fav_href_super_k}"
            p2b = OUT_DIR / "02b_keremet_favicon_superadmin_selected.png"
            page.screenshot(path=str(p2b), full_page=False)
            results.append({"file": p2b.name, "item": 2, "sha256": sha256_file(p2b), "href": fav_href_super_k})

            # Superadmin switches to Poscenter Общий (other business)
            biz_select.select_option(value='biz-poscenter')
            page.wait_for_timeout(400)
            fav_href_other = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_other == "/brand-mark.png", f"Expected /brand-mark.png after switching to other business, got {fav_href_other}"
            resp_brand = page.request.get(f"{BASE_URL}/brand-mark.png")
            assert resp_brand.status == 200, f"Expected 200 for /brand-mark.png, got {resp_brand.status}"
            p2c = OUT_DIR / "02c_poscenter_favicon_switched_other.png"
            page.screenshot(path=str(p2c), full_page=False)
            results.append({"file": p2c.name, "item": 2, "sha256": sha256_file(p2c), "href": fav_href_other, "http_status": resp_brand.status})

            # Superadmin logs out -> screen /admin/login
            page.click('button.signout-button')
            page.wait_for_url("**/admin/login")
            page.wait_for_timeout(400)
            fav_href_logout = page.evaluate("() => document.querySelector('link[rel~=\"icon\"]')?.getAttribute('href')")
            assert fav_href_logout == "/brand-mark.png", f"Expected /brand-mark.png on login screen, got {fav_href_logout}"
            p2d = OUT_DIR / "02d_poscenter_favicon_logout_screen.png"
            page.screenshot(path=str(p2d), full_page=False)
            results.append({"file": p2d.name, "item": 2, "sha256": sha256_file(p2d), "href": fav_href_logout})
            ctx.close()

            # 3. Operations: «Номер карты» and default user listing
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/operations", wait_until="networkidle")
            page.wait_for_timeout(600)

            # Search card suffix
            card_input = page.locator('.search-panel input').first
            card_input.fill('4321')
            page.click('button:has-text("Найти")')
            page.wait_for_timeout(500)
            p3 = OUT_DIR / "03_clients_search_card_suffix_4321.png"
            page.screenshot(path=str(p3), full_page=False)
            results.append({"file": p3.name, "item": 3, "sha256": sha256_file(p3)})

            # Switch to phone tab: default user listing
            page.click('button:has-text("По телефону")')
            page.wait_for_timeout(600)
            p3b = OUT_DIR / "03b_clients_users_default_listing.png"
            page.screenshot(path=str(p3b), full_page=False)
            results.append({"file": p3b.name, "item": 3, "sha256": sha256_file(p3b)})
            ctx.close()

            # 4. Statuses: level input typing allowing empty and validation
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/statuses", wait_until="networkidle")
            page.wait_for_timeout(600)

            page.click('button:has-text("Добавить статус")')
            page.wait_for_timeout(500)
            lvl = page.locator('input#tier-level')
            lvl.fill('')
            page.wait_for_timeout(300)
            p4 = OUT_DIR / "04_statuses_level_input_typing.png"
            page.screenshot(path=str(p4), full_page=False)
            results.append({"file": p4.name, "item": 4, "sha256": sha256_file(p4)})
            ctx.close()

            # 5. Home: Red button with white text and renamed link
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            p5 = OUT_DIR / "05_home_red_button_white_text.png"
            page.screenshot(path=str(p5), full_page=False)
            results.append({"file": p5.name, "item": 5, "sha256": sha256_file(p5)})
            ctx.close()

            # 6. Compact table: 7 rows default + «Все ({count})»
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin/statuses", wait_until="networkidle")
            page.wait_for_timeout(600)
            p6 = OUT_DIR / "06_compact_table_7_rows_default.png"
            page.screenshot(path=str(p6), full_page=False)
            results.append({"file": p6.name, "item": 6, "sha256": sha256_file(p6)})

            # Click "Все (8)" to expand
            expand = page.locator('button:has-text("Все (8)")')
            if expand.count() > 0:
                expand.click()
                page.wait_for_timeout(400)
            p6b = OUT_DIR / "06b_compact_table_expanded_all.png"
            page.screenshot(path=str(p6b), full_page=False)
            results.append({"file": p6b.name, "item": 6, "sha256": sha256_file(p6b)})
            ctx.close()

            # 7. Sidebar header: Reduced logo by 25%, no LOYALTY · ADMIN
            ctx = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = ctx.new_page()
            page.add_init_script(MOCK_SCRIPT)
            page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
            page.wait_for_timeout(600)
            header = page.locator('.sidebar-brand-container')
            p7 = OUT_DIR / "07_sidebar_header_reduced_logo.png"
            header.screenshot(path=str(p7))
            results.append({"file": p7.name, "item": 7, "sha256": sha256_file(p7)})
            ctx.close()

            # 8. Settings: Centering on Desktop & Mobile
            # Desktop
            ctx_d = browser.new_context(viewport={'width': 1366, 'height': 768})
            p_d = ctx_d.new_page()
            p_d.add_init_script(MOCK_SCRIPT)
            p_d.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            p_d.wait_for_timeout(600)
            p8 = OUT_DIR / "08_settings_alignment_desktop.png"
            p_d.screenshot(path=str(p8), full_page=False)
            results.append({"file": p8.name, "item": 8, "sha256": sha256_file(p8)})
            ctx_d.close()

            # Mobile
            ctx_m = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
            p_m = ctx_m.new_page()
            p_m.add_init_script(MOCK_SCRIPT)
            p_m.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
            p_m.wait_for_timeout(600)
            p8b = OUT_DIR / "08b_settings_alignment_mobile.png"
            p_m.screenshot(path=str(p8b), full_page=False)
            results.append({"file": p8b.name, "item": 8, "sha256": sha256_file(p8b)})
            ctx_m.close()

            browser.close()

        with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print("\n--- CAPTURED SCREENSHOTS ---")
        for r in results:
            print(f"{r['item']} | {r['file']} | {r['sha256']}")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
