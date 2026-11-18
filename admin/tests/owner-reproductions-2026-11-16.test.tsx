import { useEffect, useState } from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { errorFromResponse, messageForError } from '../src/api/errors';
import { AdminProvider } from '../src/auth/provider';
import { NumericInput, normalizeNumericPaste } from '../src/components/NumericInput';
import { ActiveBusinessProvider, useActiveBusiness } from '../src/context/ActiveBusinessContext';
import { BusinessEditorDialog } from '../src/features/AdminMutations';
import { Navigation } from '../src/features/Navigation';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { AdminLayout } from '../src/layout/AdminLayout';
import { ContentPage, PromotionDialog } from '../src/pages/ContentPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { TierDialog } from '../src/pages/StatusesPage';
import type { BusinessDetail, LoyaltyTier, Promotion } from '../src/api/types';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('Owner reproductions regression suite (2026-11-16)', () => {
  describe('K16-01: Loyalty tier decimals, whitespace paste, inline 409 CONFLICT without raw English/SQL', () => {
    it('normalizes pasted comma/whitespace numbers, keeps empty max_turnover as null, and shows inline localized 409 conflict without auto-shifting neighbors', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const requests: Array<{ method: string; url: string; body: unknown }> = [];
      let conflictOnce = true;

      const existingTier: LoyaltyTier = {
        id: 'tier-1',
        business_id: 'biz-1',
        level: 1,
        priority: 1,
        name_ru: 'Бронза',
        name_kk: 'Қола',
        description_ru: null,
        description_kk: null,
        min_turnover: 0,
        max_turnover: 200000,
        percent: 2,
        image_url: null,
        is_active: true,
      };

      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'biz-1', name: 'Demo', status: 'active' } },
            admin_max_stats_period_days: 90,
          });
        }
        if (url.includes('/loyalty-tiers/') && method === 'PATCH') {
          const parsedBody = init?.body ? JSON.parse(String(init.body)) : null;
          requests.push({ method, url, body: parsedBody });
          if (conflictOnce) {
            conflictOnce = false;
            return json(409, {
              error: {
                code: 'CONFLICT',
                message: 'Turnover range overlaps with tier Серебро [200000; ∞)',
              },
            });
          }
          return json(200, { ...existingTier, ...parsedBody });
        }
        return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
      }));

      const onSaved = vi.fn();
      const onClose = vi.fn();
      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <TierDialog businessId="biz-1" tier={existingTier} onClose={onClose} onSaved={onSaved} />
          </AdminProvider>
        </LocaleProvider>,
      );

      const maxInput = screen.getByLabelText('Максимальный оборот, ₸') as HTMLInputElement;
      const percentInput = screen.getByLabelText('Процент начисления бонусов, %') as HTMLInputElement;

      // Replace 200000 with formatted paste "300 000" and percent with comma "2,5" -> causes server 409 overlap
      await user.clear(maxInput);
      fireEvent.paste(maxInput, {
        clipboardData: { getData: () => '300 000' },
      });
      await user.clear(percentInput);
      fireEvent.paste(percentInput, {
        clipboardData: { getData: () => '2,5' },
      });
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      await waitFor(() => {
        expect(requests).toHaveLength(1);
      });
      expect(requests[0]!.body).toMatchObject({
        min_turnover: 0,
        max_turnover: 300000,
        percent: 2.5,
      });

      // Single field-level error alert under the last edited erroneous threshold (maxInput), linked to both threshold inputs via aria-describedby, with no top #tier-form-error and no raw English "overlaps with tier"
      const overlapMessage = /Диапазон оборота пересекается с другим активным статусом \(200\s000 ₸\+\)/;
      const minInput = screen.getByLabelText('Минимальный оборот, ₸') as HTMLInputElement;
      const maxErrorEl = document.getElementById('tier-max-error');
      expect(document.getElementById('tier-form-error')).toBeNull();
      expect(document.getElementById('tier-min-error')).toBeNull();
      expect(maxErrorEl).not.toBeNull();
      expect(maxErrorEl).toHaveAttribute('role', 'alert');
      expect(maxErrorEl?.textContent).toMatch(overlapMessage);
      expect(screen.getAllByText(overlapMessage)).toHaveLength(1);
      expect(screen.queryByText(/overlaps with tier/i)).not.toBeInTheDocument();
      expect(minInput).toHaveAttribute('aria-invalid', 'true');
      expect(minInput).toHaveAttribute('aria-describedby', 'tier-max-error');
      expect(maxInput).toHaveAttribute('aria-invalid', 'true');
      expect(maxInput).toHaveAttribute('aria-describedby', 'tier-max-error');
      expect(onClose).not.toHaveBeenCalled();

      // Fix to valid non-overlapping bound -> succeeds cleanly
      await user.clear(maxInput);
      await user.type(maxInput, '150000');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      await waitFor(() => {
        expect(onSaved).toHaveBeenCalledTimes(1);
        expect(onClose).toHaveBeenCalledTimes(1);
      });
      expect(requests[1]!.body).toMatchObject({ max_turnover: 150000, percent: 2.5 });
    });

    it('translates structured LOYALTY_TIER_RANGE_OVERLAP conflicts, level_exists, priority_exists, limit_reached, and generic 409 safely in RU and KK', () => {
      const structuredOverlap = errorFromResponse(409, {
        error: {
          code: 'CONFLICT',
          message: 'Turnover range [0.00; 300000) overlaps with tier',
          reason: 'LOYALTY_TIER_RANGE_OVERLAP',
          fields: ['min_turnover', 'max_turnover'],
          conflicts: [
            { level: 2, name_ru: 'Продуктовый эксперт', name_kk: 'Азық-түлік сарапшысы', min_turnover: '100000.00', max_turnover: '200000.00' },
            { level: 3, name_ru: 'Шоппинг-босс', name_kk: 'Шоппинг-босс', min_turnover: '200000.00', max_turnover: null },
          ],
        },
      });
      expect(structuredOverlap.detail?.conflictKind).toBe('turnover_overlap');
      expect(structuredOverlap.detail?.fields).toEqual(['min_turnover', 'max_turnover']);
      expect(messageForError(structuredOverlap, 'ru')).toContain('«Продуктовый эксперт»');
      expect(messageForError(structuredOverlap, 'ru')).toContain('«Шоппинг-босс»');
      expect(messageForError(structuredOverlap, 'kk')).toContain('«Азық-түлік сарапшысы»');

      const levelErr = errorFromResponse(409, { error: { code: 'CONFLICT', message: 'Tier with level 2 already exists' } });
      expect(levelErr.detail?.conflictKind).toBe('level_exists');
      expect(messageForError(levelErr, 'ru')).toBe('Статус с таким номером уровня уже существует.');
      expect(messageForError(levelErr, 'kk')).toBe('Мұндай деңгей нөмірі бар дәреже бұрыннан бар.');

      const generic409 = errorFromResponse(409, { error: { code: 'CONFLICT', message: 'SQLSTATE[23505] unique constraint failed' } });
      expect(messageForError(generic409, 'ru')).not.toMatch(/SQLSTATE|constraint/i);
      expect(messageForError(generic409, 'kk')).not.toMatch(/SQLSTATE|constraint/i);
    });

    it('rejects negative/ambiguous/exponent/multi-separator pastes cleanly in normalizeNumericPaste without silent value corruption', () => {
      // Malformed / disallowed inputs -> MUST return null
      expect(normalizeNumericPaste('-1 000', true, false)).toBeNull();
      expect(normalizeNumericPaste('\u22121 000', true, false)).toBeNull();
      expect(normalizeNumericPaste('1,5', false, false)).toBeNull();
      expect(normalizeNumericPaste('1.5', false, false)).toBeNull();
      expect(normalizeNumericPaste('1e3 ', true, false)).toBeNull();
      expect(normalizeNumericPaste('1E3', true, false)).toBeNull();
      expect(normalizeNumericPaste('12.34.56 ', true, false)).toBeNull();
      expect(normalizeNumericPaste('1,2,3', true, false)).toBeNull();
      expect(normalizeNumericPaste('1,2,3', false, false)).toBeNull();
      expect(normalizeNumericPaste('12 34', true, false)).toBeNull();
      expect(normalizeNumericPaste('1 000\u00A0000', true, false)).toBeNull();
      expect(normalizeNumericPaste('+100', true, false)).toBeNull();
      expect(normalizeNumericPaste('1 000 ₸', true, false)).toBeNull();
      expect(normalizeNumericPaste('.5', true, false)).toBeNull();
      expect(normalizeNumericPaste('5.', true, false)).toBeNull();
      expect(normalizeNumericPaste('   ', true, false)).toBeNull();

      // Valid unambiguous pastes
      expect(normalizeNumericPaste('90 000', true, false)).toBe('90000');
      expect(normalizeNumericPaste('90 000', false, false)).toBe('90000');
      expect(normalizeNumericPaste('90\u00A0000', true, false)).toBe('90000');
      expect(normalizeNumericPaste('90\u202F000', true, false)).toBe('90000');
      expect(normalizeNumericPaste('2,5', true, false)).toBe('2.5');
      expect(normalizeNumericPaste('2.5', true, false)).toBe('2.5');
      expect(normalizeNumericPaste('0', true, false)).toBe('0');
      expect(normalizeNumericPaste('-0', true, true)).toBe('0');
      expect(normalizeNumericPaste('-15', false, true)).toBe('-15');
      expect(normalizeNumericPaste('-1 000', true, true)).toBe('-1000');
      expect(normalizeNumericPaste('\u22121 000', true, true)).toBe('-1000');
      expect(normalizeNumericPaste('\u22121\u202F250,5', true, true)).toBe('-1250.5');
    });

    it('preserves controlled form state and submitted payload on invalid handlePaste in TierDialog and supports allowNegative in PromotionDialog', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const sentRequests: Array<{ url: string; body: Record<string, unknown> }> = [];
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'biz-1', name: 'Demo', status: 'active' } },
            admin_max_stats_period_days: 90,
          });
        }
        if (method === 'PATCH' && url.includes('/loyalty-tiers/')) {
          const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
          sentRequests.push({ url, body });
          return json(200, { id: 'tier-1', ...body });
        }
        if (method === 'POST' && url.includes('/admin/promotions')) {
          const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
          sentRequests.push({ url, body });
          return json(201, { id: 'promo-1', ...body });
        }
        return json(404, { error: { code: 'NOT_FOUND' } });
      }));

      const tier: LoyaltyTier = {
        id: 'tier-1',
        business_id: 'biz-1',
        level: 1,
        priority: 1,
        name_ru: 'Бронза',
        name_kk: 'Қола',
        description_ru: null,
        description_kk: null,
        min_turnover: 0,
        max_turnover: 200000,
        percent: 2,
        image_url: null,
        is_active: true,
      };

      const { unmount } = render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <TierDialog businessId="biz-1" tier={tier} onClose={vi.fn()} onSaved={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );

      const levelInput = screen.getByLabelText('Номер уровня') as HTMLInputElement;
      const minInput = screen.getByLabelText('Минимальный оборот, ₸') as HTMLInputElement;
      const maxInput = screen.getByLabelText('Максимальный оборот, ₸') as HTMLInputElement;
      const percentInput = screen.getByLabelText('Процент начисления бонусов, %') as HTMLInputElement;

      // Invalid pastes MUST NOT mutate prior values into positive/integer/mangled numbers
      for (const badDecimal of ['-1 000', '\u22121 000', '1e3 ', '12.34.56 ', '1,2,3']) {
        fireEvent.paste(maxInput, { clipboardData: { getData: () => badDecimal } });
        expect(maxInput.value).toBe('200000');
      }
      fireEvent.paste(levelInput, { clipboardData: { getData: () => '1,5' } });
      expect(levelInput.value).toBe('1');
      fireEvent.paste(percentInput, { clipboardData: { getData: () => '1e3 ' } });
      expect(percentInput.value).toBe('2');

      // Submitting now sends original untouched numeric values
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentRequests).toHaveLength(1));
      expect(sentRequests[0]!.body).toMatchObject({
        level: 1,
        min_turnover: 0,
        max_turnover: 200000,
        percent: 2,
      });

      // Crucial safe fallback check: formatted paste without known caret/selection (selectionStart/End=null, execCommand absent)
      // MUST NOT blindly replace the entire field (e.g. 200000 -> 90000)
      fireEvent.paste(maxInput, { clipboardData: { getData: () => '90 000' } });
      expect(maxInput.value).toBe('200000');

      // Now valid formatted pastes into cleared fields (NBSP, narrow-NBSP, comma decimal) update controlled state and payload
      await user.clear(minInput);
      fireEvent.paste(minInput, { clipboardData: { getData: () => '10\u00A0000' } });
      await user.clear(maxInput);
      fireEvent.paste(maxInput, { clipboardData: { getData: () => '90\u202F000' } });
      await user.clear(percentInput);
      fireEvent.paste(percentInput, { clipboardData: { getData: () => '2,5' } });
      expect(minInput.value).toBe('10000');
      expect(maxInput.value).toBe('90000');
      expect(percentInput.value).toBe('2.5');

      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentRequests).toHaveLength(2));
      expect(sentRequests[1]!.body).toMatchObject({
        level: 1,
        min_turnover: 10000,
        max_turnover: 90000,
        percent: 2.5,
      });
      unmount();

      // PromotionDialog sort_order has allowNegative=true, decimal=false
      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <PromotionDialog onClose={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );
      const sortInput = screen.getByLabelText('Сортировка') as HTMLInputElement;
      expect(sortInput.value).toBe('0');

      // Reject decimal / exponent in integer sort_order
      fireEvent.paste(sortInput, { clipboardData: { getData: () => '1,5' } });
      expect(sortInput.value).toBe('0');
      fireEvent.paste(sortInput, { clipboardData: { getData: () => '1e3 ' } });
      expect(sortInput.value).toBe('0');

      // Accept negative Unicode minus and valid negative integer into cleared field
      await user.clear(sortInput);
      fireEvent.paste(sortInput, { clipboardData: { getData: () => '\u221215' } });
      expect(sortInput.value).toBe('-15');

      await user.type(screen.getByLabelText('Заголовок'), 'Тест сортировки');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentRequests).toHaveLength(3));
      expect(sentRequests[2]!.body.sort_order).toBe(-15);
    });

    it('preserves native caret/selection paste for plain values, inserts formatted text at caret/selection via execCommand, and rejects invalid combined results', () => {
      // 1) Minimal DOM double check: plain valid paste '5' into '100' MUST NOT call preventDefault()
      const handleEvents: string[] = [];
      const { unmount } = render(
        <div>
          <label htmlFor="plain-num">Plain</label>
          <NumericInput
            id="plain-num"
            defaultValue="100"
            onPaste={e => {
              handleEvents.push(e.clipboardData?.getData('text') ?? '');
            }}
          />
        </div>,
      );
      const plainInput = screen.getByLabelText('Plain') as HTMLInputElement;
      const pasteEv = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
      Object.defineProperty(pasteEv, 'clipboardData', {
        value: { getData: () => '5' },
      });
      plainInput.dispatchEvent(pasteEv);
      expect(handleEvents).toEqual(['5']);
      expect(pasteEv.defaultPrevented).toBe(false);
      expect(plainInput.value).toBe('100');
      unmount();

      // 2) Caret & partial selection via selectionStart/selectionEnd (100+5 at end/start/mid, select all, 1234 sel 34 -> 1290)
      const { unmount: unmountSel } = render(
        <div>
          <label htmlFor="sel-dec">Dec</label>
          <NumericInput id="sel-dec" decimal defaultValue="100" />
          <label htmlFor="sel-neg">Neg</label>
          <NumericInput id="sel-neg" allowNegative decimal defaultValue="100" />
        </div>,
      );
      const selDec = screen.getByLabelText('Dec') as HTMLInputElement;
      const selNeg = screen.getByLabelText('Neg') as HTMLInputElement;

      const withSelection = (el: HTMLInputElement, value: string, start: number, end: number, text: string) => {
        el.value = value;
        Object.defineProperty(el, 'selectionStart', { configurable: true, get: () => start });
        Object.defineProperty(el, 'selectionEnd', { configurable: true, get: () => end });
        const ev = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
        Object.defineProperty(ev, 'clipboardData', { value: { getData: () => text } });
        el.dispatchEvent(ev);
        return ev;
      };

      // Plain '5' into '100' at end/start/all: defaultPrevented MUST remain false (browser inserts at caret/selection)
      expect(withSelection(selDec, '100', 3, 3, '5').defaultPrevented).toBe(false);
      expect(withSelection(selDec, '100', 0, 0, '5').defaultPrevented).toBe(false);
      expect(withSelection(selDec, '100', 0, 3, '5').defaultPrevented).toBe(false);

      // Formatted paste '90 000' at end of '100' -> '10090000'; in '1234' selecting '34' + '90\u202F000' -> '1290000'
      const fmtEndEv = withSelection(selDec, '100', 3, 3, '90 000');
      expect(fmtEndEv.defaultPrevented).toBe(true);
      expect(selDec.value).toBe('10090000');

      const fmtPartialEv = withSelection(selDec, '1234', 2, 4, '90\u202F000');
      expect(fmtPartialEv.defaultPrevented).toBe(true);
      expect(selDec.value).toBe('1290000');

      // Formatted decimal '2,5' at end of '1' -> '12.5'
      const fmtDecEv = withSelection(selDec, '1', 1, 1, '2,5');
      expect(fmtDecEv.defaultPrevented).toBe(true);
      expect(selDec.value).toBe('12.5');

      // Glued invalid combinations MUST be rejected (defaultPrevented=true, value preserved)
      const doubleDotEv = withSelection(selDec, '12.5', 4, 4, '1.5');
      expect(doubleDotEv.defaultPrevented).toBe(true);
      expect(selDec.value).toBe('12.5');

      const badEndNegEv = withSelection(selNeg, '100', 3, 3, '-5');
      expect(badEndNegEv.defaultPrevented).toBe(true);
      expect(selNeg.value).toBe('100');

      const badPreMinusEv = withSelection(selNeg, '-15', 0, 0, '5');
      expect(badPreMinusEv.defaultPrevented).toBe(true);
      expect(selNeg.value).toBe('-15');

      const okStartNegEv = withSelection(selNeg, '100', 0, 0, '\u22125');
      expect(okStartNegEv.defaultPrevented).toBe(true);
      expect(selNeg.value).toBe('-5100');
      unmountSel();

      // 3) Chromium <input type="number"> path (selectionStart=null, execCommand insertText + undo rollback)
      let buffer = '100';
      let bad = false;
      const origExec = (document as { execCommand?: unknown }).execCommand;
      const execCalls: Array<{ cmd: string; val?: string }> = [];
      (document as { execCommand: (cmd: string, showUI?: boolean, val?: string) => boolean }).execCommand = (
        cmd: string,
        _showUI?: boolean,
        val?: string,
      ) => {
        execCalls.push({ cmd, val });
        if (cmd === 'insertText' && val !== undefined) {
          if (val === '-5') {
            buffer = '';
            bad = true;
          } else {
            buffer = `${buffer}${val}`;
            bad = false;
          }
          return true;
        }
        if (cmd === 'undo') {
          buffer = '100';
          bad = false;
          return true;
        }
        return false;
      };
      try {
        function ControlledExecHarness() {
          const [val, setVal] = useState('100');
          return (
            <div>
              <label htmlFor="exec-num">Exec</label>
              <NumericInput id="exec-num" allowNegative decimal value={val} onChange={e => setVal(e.target.value)} />
            </div>
          );
        }
        const { unmount: unmountExec } = render(<ControlledExecHarness />);
        const execIn = screen.getByLabelText('Exec') as HTMLInputElement;
        Object.defineProperty(execIn, 'value', {
          configurable: true,
          get: () => buffer,
          set: v => {
            buffer = v;
          },
        });
        Object.defineProperty(execIn, 'validity', {
          configurable: true,
          get: () => ({ badInput: bad }),
        });

        // Formatted '90 000' appended to '100' via execCommand -> '10090000'
        fireEvent.paste(execIn, { clipboardData: { getData: () => '90 000' } });
        expect(buffer).toBe('10090000');

        // Attempt invalid combined '-5' -> triggers badInput -> automatic undo restores prior value without clearing
        buffer = '100';
        fireEvent.paste(execIn, { clipboardData: { getData: () => '-5' } });
        expect(buffer).toBe('100');
        expect(execCalls.some(c => c.cmd === 'undo')).toBe(true);
        unmountExec();
      } finally {
        if (origExec === undefined) {
          delete (document as { execCommand?: unknown }).execCommand;
        } else {
          (document as { execCommand?: unknown }).execCommand = origExec;
        }
      }
    });

    it('safely handles technical failures: execCommand absent, insertText=false, and insertText=true + invalidCombined + undo=false without replacing 100 or corrupting payload', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const patchRequests: Array<Record<string, unknown>> = [];
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'biz-1', name: 'Demo', status: 'active' } },
            admin_max_stats_period_days: 90,
          });
        }
        if (method === 'PATCH' && url.includes('/loyalty-tiers/')) {
          const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
          patchRequests.push(body);
          return json(200, { id: 'tier-1', ...body });
        }
        return json(404, { error: { code: 'NOT_FOUND' } });
      }));

      const tier: LoyaltyTier = {
        id: 'tier-1',
        business_id: 'biz-1',
        level: 1,
        priority: 1,
        name_ru: 'Бронза',
        name_kk: 'Қола',
        description_ru: null,
        description_kk: null,
        min_turnover: 0,
        max_turnover: 100,
        percent: 2,
        image_url: null,
        is_active: true,
      };

      const origExec = (document as { execCommand?: unknown }).execCommand;

      try {
        // 1. selectionStart/End=null, execCommand absent:
        // Pasting formatted '90 000' into maxInput (holding 100) MUST NOT replace 100 with 90000
        delete (document as { execCommand?: unknown }).execCommand;

        const { unmount: unmount1 } = render(
          <LocaleProvider initialLocale="ru">
            <AdminProvider>
              <TierDialog businessId="biz-1" tier={tier} onClose={vi.fn()} onSaved={vi.fn()} />
            </AdminProvider>
          </LocaleProvider>,
        );

        const maxInput1 = screen.getByLabelText('Максимальный оборот, ₸') as HTMLInputElement;
        expect(maxInput1.value).toBe('100');

        const pasteEv1 = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
        Object.defineProperty(pasteEv1, 'clipboardData', { value: { getData: () => '90 000' } });
        maxInput1.dispatchEvent(pasteEv1);

        expect(pasteEv1.defaultPrevented).toBe(true);
        expect(maxInput1.value).toBe('100'); // NOT 90000!

        await user.click(screen.getByRole('button', { name: 'Сохранить' }));
        await waitFor(() => expect(patchRequests).toHaveLength(1));
        expect(patchRequests[0]!.max_turnover).toBe(100); // Payload preserves 100!
        unmount1();

        // Minimal DOM-double without addEventListener calling onPaste: does not throw TypeError
        const bareInput = { value: '100', dispatchEvent: vi.fn() } as unknown as HTMLInputElement;
        const dummyPasteEv = {
          currentTarget: bareInput,
          defaultPrevented: false,
          preventDefault: vi.fn(),
          clipboardData: { getData: () => '90 000' },
        } as unknown as ClipboardEvent<HTMLInputElement>;
        expect(() => {
          const harness = NumericInput({ decimal: true, defaultValue: '100' });
          harness.props.onPaste?.(dummyPasteEv);
        }).not.toThrow();
        expect(bareInput.value).toBe('100');

        // 2. selectionStart/End=null, document.execCommand returns false for insertText:
        (document as { execCommand: (cmd: string, showUI?: boolean, val?: string) => boolean }).execCommand = vi.fn().mockReturnValue(false);

        const { unmount: unmount2 } = render(
          <LocaleProvider initialLocale="ru">
            <AdminProvider>
              <TierDialog businessId="biz-1" tier={tier} onClose={vi.fn()} onSaved={vi.fn()} />
            </AdminProvider>
          </LocaleProvider>,
        );

        const maxInput2 = screen.getByLabelText('Максимальный оборот, ₸') as HTMLInputElement;
        expect(maxInput2.value).toBe('100');

        const pasteEv2 = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
        Object.defineProperty(pasteEv2, 'clipboardData', { value: { getData: () => '90 000' } });
        maxInput2.dispatchEvent(pasteEv2);

        expect(pasteEv2.defaultPrevented).toBe(true);
        expect(maxInput2.value).toBe('100'); // NOT 90000!

        await user.click(screen.getByRole('button', { name: 'Сохранить' }));
        await waitFor(() => expect(patchRequests).toHaveLength(2));
        expect(patchRequests[1]!.max_turnover).toBe(100);
        unmount2();

        // 3. selectionStart/End=null, insertText=true + invalidCombined + undo=false:
        // Even if execCommand undo fails/returns false, input.value MUST be restored to prevValue (100)
        let customBad = false;
        const undoMock = vi.fn().mockReturnValue(false);

        function ControlledUndoFailHarness() {
          const [val, setVal] = useState('100');
          return (
            <div>
              <label htmlFor="harness-input">Harness</label>
              <NumericInput id="harness-input" allowNegative decimal value={val} onChange={e => setVal(e.target.value)} />
            </div>
          );
        }
        const { unmount: unmount3 } = render(<ControlledUndoFailHarness />);
        const harnessIn = screen.getByLabelText('Harness') as HTMLInputElement;

        (document as { execCommand: (cmd: string, showUI?: boolean, val?: string) => boolean }).execCommand = (
          cmd: string,
          _showUI?: boolean,
          val?: string,
        ) => {
          if (cmd === 'insertText' && val !== undefined) {
            const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
            proto?.call(harnessIn, '');
            customBad = true;
            return true;
          }
          if (cmd === 'undo') {
            return undoMock();
          }
          return false;
        };

        Object.defineProperty(harnessIn, 'validity', {
          configurable: true,
          get: () => ({ badInput: customBad }),
        });

        const pasteEv3 = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
        Object.defineProperty(pasteEv3, 'clipboardData', { value: { getData: () => '-5' } });
        harnessIn.dispatchEvent(pasteEv3);

        expect(undoMock).toHaveBeenCalled();
        expect(harnessIn.value).toBe('100'); // Guaranteed restored to 100 despite undo failure!
        unmount3();
      } finally {
        if (origExec === undefined) {
          delete (document as { execCommand?: unknown }).execCommand;
        } else {
          (document as { execCommand?: unknown }).execCommand = origExec;
        }
      }
    });
  });

  describe('K16-03 / K16-04: Schedule checkboxes, untouched ISO seconds preservation, 15s guard, and field-level 422', () => {
    it('sends starts_at=null and ends_at=null when checked even if disabled inputs held text, and preserves initial timestamps with seconds on edit', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const payloads: Array<Record<string, unknown>> = [];
      let failWith422 = false;

      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'biz-1', name: 'Demo', status: 'active' } },
            admin_max_stats_period_days: 90,
          });
        }
        if (url.includes('/admin/promotions')) {
          const parsed = init?.body ? JSON.parse(String(init.body)) : {};
          payloads.push(parsed);
          if (failWith422) {
            return json(422, {
              error: {
                code: 'VALIDATION_ERROR',
                message: 'starts_at cannot be in the past',
              },
            });
          }
          return json(method === 'POST' ? 201 : 200, { id: 'promo-new', ...parsed });
        }
        return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
      }));

      // 1. Editing existing promo with past start with non-zero seconds: unchecking neither should send verbatim ISO strings
      const existingPromo: Promotion = {
        id: 'promo-1',
        business_id: 'biz-1',
        kind: 'banner',
        title: 'Старый баннер',
        subtitle: null,
        badge: null,
        body: null,
        image_url: 'https://cdn.example.test/banner.webp',
        starts_at: '2025-05-01T09:15:42Z',
        ends_at: '2030-05-01T09:15:42Z',
        sort_order: 1,
        is_active: true,
        created_at: '2025-04-30T00:00:00Z',
        updated_at: '2025-04-30T00:00:00Z',
      };

      const onCloseEdit = vi.fn();
      const { unmount } = render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <PromotionDialog promotion={existingPromo} onClose={onCloseEdit} />
          </AdminProvider>
        </LocaleProvider>,
      );

      expect(screen.getByRole('checkbox', { name: 'Начать сейчас' })).not.toBeChecked();
      expect(screen.getByRole('checkbox', { name: 'Бессрочно' })).not.toBeChecked();

      await user.clear(screen.getByLabelText('Заголовок'));
      await user.type(screen.getByLabelText('Заголовок'), 'Обновлённый баннер');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      await waitFor(() => expect(onCloseEdit).toHaveBeenCalledTimes(1));
      expect(payloads[0]!.starts_at).toBe('2025-05-01T09:15:42Z');
      expect(payloads[0]!.ends_at).toBe('2030-05-01T09:15:42Z');
      unmount();

      // 2. New promotion: fill title + uploaded image, submit immediately -> starts_at=null, ends_at=null
      // Also test server 422 preserves form inputs + image_url and shows field-level error
      failWith422 = true;
      const onCloseCreate = vi.fn();
      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <PromotionDialog onClose={onCloseCreate} />
          </AdminProvider>
        </LocaleProvider>,
      );

      await user.type(screen.getByLabelText('Заголовок'), 'Новая акция');
      await user.type(screen.getByPlaceholderText('https://…'), 'https://cdn.example.test/promo.webp');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      await waitFor(() => expect(payloads).toHaveLength(2));
      expect(payloads[1]!.starts_at).toBeNull();
      expect(payloads[1]!.ends_at).toBeNull();
      expect(onCloseCreate).not.toHaveBeenCalled();
      expect((screen.getByLabelText('Заголовок') as HTMLInputElement).value).toBe('Новая акция');
      expect((screen.getByPlaceholderText('https://…') as HTMLInputElement).value).toBe('https://cdn.example.test/promo.webp');
      expect(screen.getAllByText(/Дата начала показа не может быть в прошлом/i).length).toBeGreaterThanOrEqual(1);

      // 3. Unchecked with empty explicit date requires explicit date
      await user.click(screen.getByRole('checkbox', { name: 'Начать сейчас' }));
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(screen.getByText('Укажите дату начала показа или включите «Начать сейчас».')).toBeInTheDocument();

      // Re-check Start Now and fix server response -> succeeds with starts_at=null
      failWith422 = false;
      await user.click(screen.getByRole('checkbox', { name: 'Начать сейчас' }));
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(onCloseCreate).toHaveBeenCalledTimes(1));
    });
  });

  describe('S16-01 / S16-02 / S16-03: CSS rules for native select chevron & dialog URL overflow + BusinessEditorDialog session sync', () => {
    it('defines native select appearance: none with right-offset chevron and min-width: 0 overflow protection in admin.css', () => {
      const css = readFileSync(resolve(__dirname, '../src/styles/admin.css'), 'utf-8');
      expect(css).toMatch(/appearance:\s*none;/);
      expect(css).toMatch(/padding-right:\s*38px;/);
      expect(css).toMatch(/background-position:\s*right 12px center;/);
      expect(css).toMatch(/\.image-upload-preview-card[\s\S]*overflow:\s*hidden;/);
      expect(css).toMatch(/\.image-upload-info-url[\s\S]*text-overflow:\s*ellipsis;/);
      expect(css).toMatch(/\.dashboard-period-hint-row[\s\S]*margin-top:\s*14px;/);
    });

    it('BusinessEditorDialog keeps all fields, handles long logo URL, and updates avatar + favicon immediately on PATCH without re-login', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const faviconLink = document.createElement('link');
      faviconLink.rel = 'icon';
      faviconLink.href = '/brand-mark.png';
      document.head.appendChild(faviconLink);

      class InstantImage {
        referrerPolicy = '';
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        set src(_v: string) {
          setTimeout(() => this.onload?.(), 0);
        }
      }
      vi.stubGlobal('Image', InstantImage);

      const initialBusiness: BusinessDetail = {
        id: 'biz-k',
        name: 'Керемет',
        logo_url: 'https://cdn.example.test/old.webp',
        colors: { primary: '#ff3a4d' },
        barcode_prefixes: ['290'],
        android_app_id: 'kz.cashbackone.keremet',
        status: 'active',
        loyalty_tiers: [{ level: 1, name: 'База', threshold: 0, percent: 2 }],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
        cards_count: 10,
        unblocked_cards_count: 10,
        customers_with_cards_count: 5,
        agents_count: 1,
      };

      const longUrl = `https://cdn.example.test/media/businesses/${'very-long-segment-'.repeat(5)}logo.webp`;

      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-s', login: 'super', role: 'superadmin', business: null },
            admin_max_stats_period_days: 90,
          });
        }
        if (url.endsWith(`/admin/businesses/${initialBusiness.id}`) && method === 'PATCH') {
          const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
          return json(200, { ...initialBusiness, ...body });
        }
        return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
      }));

      function SeedActiveBusiness() {
        const { activeBusiness, setActiveBusiness } = useActiveBusiness();
        useEffect(() => {
          if (!activeBusiness) {
            setActiveBusiness({
              id: initialBusiness.id,
              name: initialBusiness.name,
              logo_url: initialBusiness.logo_url,
              android_app_id: initialBusiness.android_app_id,
            });
          }
        }, [activeBusiness, setActiveBusiness]);
        return null;
      }

      function Wrapper() {
        return (
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <AdminProvider>
                <SeedActiveBusiness />
                <AdminLayout>
                  <BusinessEditorDialog business={initialBusiness} onClose={vi.fn()} onSaved={vi.fn()} />
                </AdminLayout>
              </AdminProvider>
            </LocaleProvider>
          </MemoryRouter>
        );
      }

      try {
        render(<Wrapper />);
        const logoInput = await screen.findByPlaceholderText('https://…');
        fireEvent.change(logoInput, { target: { value: longUrl } });
        await user.click(screen.getByRole('button', { name: 'Сохранить' }));

        await waitFor(() => {
          expect(faviconLink.getAttribute('href')).toBe(longUrl);
        });
        expect(document.querySelector('.account-avatar img')).toHaveAttribute('src', longUrl);
      } finally {
        faviconLink.remove();
      }
    });
  });

  describe('S16-04 / S16-05: Malformed year vs reversed range, Back button recovery, and preserved business/locale', () => {
    it('shows invalid-year message for 0268-01-01, recovers via Back on both local and server errors, and keeps selected business', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const dashboardUrls: string[] = [];
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-s', login: 'super', role: 'superadmin', business: null },
            admin_max_stats_period_days: 90,
            admin_stats_unlimited_period: true,
          });
        }
        if (url.includes('/admin/businesses?')) {
          return json(200, {
            items: [{ id: 'biz-42', name: 'Market 42', status: 'active', logo_url: null, colors: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' }],
            limit: 100,
            offset: 0,
            has_more: false,
          });
        }
        if (url.includes('/admin/dashboard')) {
          dashboardUrls.push(url);
          return json(200, {
            period_from: '2026-10-18T19:00:00Z',
            period_to: '2026-11-16T18:59:59Z',
            period_days: 30,
            businesses_total: 1,
            businesses_active: 1,
            cards_total: 20,
            users_total: 10,
            bound_cards_total: 15,
            unbound_cards_total: 5,
            transactions: 30,
            accrual_count: 20,
            redemption_count: 10,
            accrual_sum: '1000.0000',
            redemption_sum: '500.0000',
            notifications_sent: 2,
            active_promotions: 1,
            agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
          });
        }
        return json(404, { error: { code: 'NOT_FOUND' } });
      }));

      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <ActiveBusinessProvider>
              <MemoryRouter initialEntries={['/admin']}>
                <Navigation role="superadmin" />
                <Routes>
                  <Route path="/admin" element={<DashboardPage />} />
                </Routes>
              </MemoryRouter>
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );

      expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();

      // Select Market 42 and confirm it stays selected after invalid year + Back
      const bizSelect = screen.getByLabelText('Бизнес') as HTMLSelectElement;
      await waitFor(() => expect(screen.getByRole('option', { name: 'Market 42' })).toBeInTheDocument());
      await user.selectOptions(bizSelect, 'biz-42');

      const fromInput = screen.getByLabelText('С') as HTMLInputElement;
      const workingFrom = fromInput.value;
      fireEvent.change(fromInput, { target: { value: '0268-01-01' } });

      // Must say invalid 4-digit year, NOT reversed range!
      expect(screen.getByText('Укажите корректную дату с четырёхзначным годом.')).toBeInTheDocument();
      expect(screen.queryByText(/раньше начала/i)).not.toBeInTheDocument();

      // 15:04: no Back under the date error. Refresh stays active, does not request a report,
      // and does not rewrite the typed year. The selected business stays selected.
      await waitFor(() => expect(dashboardUrls.length).toBeGreaterThan(0));
      const dashCountBefore = dashboardUrls.length;
      expect(screen.queryByRole('button', { name: 'Назад' })).not.toBeInTheDocument();
      const refreshBtn = screen.getByRole('button', { name: 'Обновить' });
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      expect(dashboardUrls).toHaveLength(dashCountBefore);
      expect(fromInput.value).toBe('0268-01-01');
      expect(bizSelect.value).toBe('biz-42');

      fireEvent.change(fromInput, { target: { value: workingFrom } });
      expect(fromInput.value).toBe(workingFrom);
      expect(bizSelect.value).toBe('biz-42');
      expect(screen.queryByText('Укажите корректную дату с четырёхзначным годом.')).not.toBeInTheDocument();

      // Active nav link "Обзор" resets invalid date while keeping selected business
      fireEvent.change(fromInput, { target: { value: '0268-01-01' } });
      expect(screen.getByText('Укажите корректную дату с четырёхзначным годом.')).toBeInTheDocument();
      await user.click(screen.getByRole('link', { name: 'Обзор' }));
      expect(fromInput.value).toBe(workingFrom);
      expect(bizSelect.value).toBe('biz-42');
    });
  });

  describe('A16-01: Upload slot specifications in RU & KK with aria-describedby', () => {
    it.each(['ru', 'kk'] as const)('shows distinct accurate specs for offer, banner, status, business logo, and splash (%s)', async locale => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: { id: 'adm-s', login: 'super', role: 'superadmin', business: null },
            admin_max_stats_period_days: 90,
          });
        }
        if (url.includes('/admin/businesses?')) {
          return json(200, {
            items: [{ id: 'biz-1', name: 'Demo', status: 'active', logo_url: null, colors: null, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' }],
            limit: 100,
            offset: 0,
            has_more: false,
          });
        }
        if (url.includes('/admin/promotions?')) return json(200, { items: [], limit: 25, offset: 0, has_more: false });
        if (url.includes('/admin/notifications?')) return json(200, { items: [], limit: 25, offset: 0, has_more: false });
        if (url.includes('/stores')) return json(200, []);
        if (url.includes('/app-texts')) return json(200, { home_store_note_lead: { ru: '', kk: '' }, balance_delay_note: { ru: '', kk: '' } });
        if (url.includes('/splash')) return json(200, { business_id: 'biz-1', enabled: false, media_type: null, media_url: null, width: null, height: null, duration_seconds: null, file_size: null, version: null });
        if (url.includes('/loyalty-tiers')) return json(200, []);
        return json(200, {});
      }));

      // 1. PromotionDialog: offer vs banner
      const { unmount: unmountPromo } = render(
        <LocaleProvider initialLocale={locale}>
          <AdminProvider>
            <PromotionDialog onClose={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );
      const offerHintEl = screen.getByText(/800×600 px \(4:3\)/);
      expect(offerHintEl.textContent).toMatch(/10 МиБ/);
      expect(offerHintEl.textContent).toMatch(/40 Мп/);
      expect(offerHintEl.textContent).toMatch(/1600 px/);
      expect(offerHintEl.textContent).not.toMatch(/МБ/);
      expect(document.getElementById('promo-image')).toHaveAttribute('aria-describedby', 'promo-image-hint');
      const kindSelect = await screen.findByLabelText(locale === 'ru' ? 'Где показывать' : 'Қайда көрсету');
      await user.selectOptions(kindSelect, 'banner');
      const bannerHintEl = screen.getByText(/1200×500 px \(2\.4:1\)/);
      expect(bannerHintEl.textContent).toMatch(/10 МиБ/);
      expect(bannerHintEl.textContent).toMatch(/40 Мп/);
      expect(bannerHintEl.textContent).not.toMatch(/МБ/);
      unmountPromo();

      // 2. TierDialog (Status image)
      const { unmount: unmountTier } = render(
        <LocaleProvider initialLocale={locale}>
          <AdminProvider>
            <TierDialog businessId="biz-1" onClose={vi.fn()} onSaved={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );
      const tierHintEl = screen.getByText(/512×512 px \(1:1\).*contain/);
      expect(tierHintEl.textContent).toMatch(/10 МиБ/);
      expect(tierHintEl.textContent).toMatch(/40 Мп/);
      expect(tierHintEl.textContent).toMatch(/1600 px/);
      expect(tierHintEl.textContent).not.toMatch(/МБ/);
      expect(document.getElementById('tier-image')).toHaveAttribute('aria-describedby', 'tier-image-hint');
      unmountTier();

      // 3. BusinessEditorDialog (Logo / Avatar / Favicon)
      const { unmount: unmountBiz } = render(
        <LocaleProvider initialLocale={locale}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <BusinessEditorDialog onClose={vi.fn()} onSaved={vi.fn()} />
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );
      const logoHintEl = screen.getByText(/512×512 px \(1:1\).*512 px/);
      expect(logoHintEl.textContent).toMatch(/10 МиБ/);
      expect(logoHintEl.textContent).toMatch(/40 Мп/);
      expect(logoHintEl.textContent).not.toMatch(/МБ/);
      expect(document.getElementById('business-logo')).toHaveAttribute('aria-describedby', 'business-logo-hint');
      unmountBiz();

      // 4. ContentPage splash tab
      render(
        <LocaleProvider initialLocale={locale}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <MemoryRouter initialEntries={['/admin/content']}>
                <Routes>
                  <Route path="/admin/content" element={<ContentPage />} />
                </Routes>
              </MemoryRouter>
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );
      await user.click(await screen.findByRole('tab', { name: locale === 'ru' ? 'Магазины и инфо' : 'Дүкендер мен мәтіндер' }));
      const contentBizSelect = await screen.findByLabelText('Бизнес');
      await waitFor(() => expect(screen.getByRole('option', { name: 'Demo' })).toBeInTheDocument());
      await user.selectOptions(contentBizSelect, 'biz-1');
      const splashHintEl = await screen.findByText(/1080×1920 px \(9:16\).*H\.264/);
      expect(splashHintEl.textContent).toMatch(/5 МиБ.*40 Мп.*2560 px.*MP4.*15 МиБ/);
      expect(splashHintEl.textContent).not.toMatch(/МБ/);
      expect(screen.getByTestId('splash-upload-btn')).toHaveAttribute('aria-describedby', 'splash-limits-hint');
    });
  });
});
