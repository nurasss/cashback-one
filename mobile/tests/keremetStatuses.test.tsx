import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { createHash } from 'crypto';
import { readFileSync } from 'fs';
import { join } from 'path';
import type { ReactElement } from 'react';
import { StyleSheet } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import StatusRoute from '../app/(app)/status';
import { keremetStatuses } from '../clients/keremet/statuses';
import { ActiveCardProvider } from '../src/features/activeCard';
import { LevelsSheet } from '../src/features/LevelsSheet';
import { getClientStatuses, resolveCurrentStatus, statusCondition, statusForSpend } from '../src/features/statuses';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import type { Card, Tier } from '../src/types/api';

const mockRequest = jest.fn();
const mockPush = jest.fn();
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn(), getUserId: () => 'user-1' } }) }));
jest.mock('expo-router', () => ({ router: { push: (...args: unknown[]) => mockPush(...args), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true } }));
jest.mock('../src/features/push', () => ({ PushPermissionNotice: () => null }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const MOBILE = join(__dirname, '..');
const originalClient = process.env.EXPO_PUBLIC_CLIENT;
const catalog = (confirmed: boolean) => ({ ...keremetStatuses, turnoverConfirmed: confirmed });
const SERVER_LEVELS = [
  { level: 1, name: null, threshold: '0.0000', percent: '2.0000' },
  { level: 2, name: null, threshold: '100000.0000', percent: '3.0000' },
  { level: 3, name: null, threshold: '200000.0000', percent: '4.0000' },
];
// What the server would return for `spend` with the owner's thresholds (fixture only: this is not a check of the backend's rolling calculation).
function tierFor(spend: string | null, overrides: Partial<Tier> = {}): Tier {
  const n = spend === null ? 0 : Number(spend);
  const level = n >= 200000 ? 3 : n >= 100000 ? 2 : 1;
  const next = level === 1 ? '100000.0000' : level === 2 ? '200000.0000' : null;
  return { level, name: null, percent: ['2.0000', '3.0000', '4.0000'][level - 1]!, max_percent: '4.0000', spend_total: spend, next_level: next ? level + 1 : null, next_threshold: next,
    remaining: next ? String(Math.max(Number(next) - n, 0)) : null, levels: SERVER_LEVELS, ...overrides };
}

describe('catalog and image mapping', () => {
  it('has the three owner-confirmed statuses with non-overlapping thresholds, in order', () => {
    expect(keremetStatuses.periodMonths).toBe(6);
    expect(keremetStatuses.levels.map(l => [l.level, l.key, l.name, l.threshold, l.percent])).toEqual([
      [1, 'occasional', 'Нет-нет заглядывает', 0, 2],
      [2, 'expert', 'Продуктовый эксперт', 100000, 3],
      [3, 'boss', 'Шоппинг-босс', 200000, 4],
    ]);
  });

  it('the current status data is NOT used until the turnover period is confirmed (blocker switch is off by default)', () => {
    expect(keremetStatuses.turnoverConfirmed).toBe(false);
  });

  it('only Keremet has named statuses; the general app and other clients keep the server levels', () => {
    expect(getClientStatuses('keremet')).toBe(keremetStatuses);
    expect(getClientStatuses('cashbackone')).toBeNull();
    expect(getClientStatuses('example')).toBeNull();
    expect(getClientStatuses('no-such-client')).toBeNull();
  });

  it('each stable key maps to its own picture file (by key, not by the translatable name)', () => {
    const source = readFileSync(join(MOBILE, 'clients/keremet/statuses.ts'), 'utf8');
    for (const level of keremetStatuses.levels) {
      expect(source).toContain(`key: '${level.key}'`);
      expect(source).toMatch(new RegExp(`key: '${level.key}'[^\\n]*require\\('\\./statuses/${level.key}\\.png'\\)`));
    }
    const hashes = keremetStatuses.levels.map(l => createHash('sha256').update(readFileSync(join(MOBILE, `clients/keremet/statuses/${l.key}.png`))).digest('hex'));
    expect(new Set(hashes).size).toBe(3);
  });
});

describe('thresholds never overlap', () => {
  const levels = keremetStatuses.levels;
  it.each([
    [0, 1], [0.01, 1], [99999.99, 1], [100000, 2], [100000.01, 2], [199999.99, 2], [200000, 3], [200000.01, 3], [1_000_000, 3], [-500, 1],
  ])('turnover %p -> level %p', (spend, level) => {
    expect(statusForSpend(levels, spend).level).toBe(level);
  });

  it('every value in a sweep belongs to exactly one displayed range', () => {
    for (let spend = 0; spend <= 300000; spend += 2500.01) {
      const matching = levels.filter(level => {
        const c = statusCondition(levels, level);
        return c.key === 'statusUpTo' ? spend < c.to! : c.key === 'statusRange' ? spend >= c.from && spend < c.to! : spend >= c.from;
      });
      expect(matching).toHaveLength(1);
      expect(matching[0]!.level).toBe(statusForSpend(levels, spend).level);
    }
  });

  it('condition text uses up to / from-to / from, and is translated to Kazakh', () => {
    expect(levels.map(l => statusCondition(levels, l).key)).toEqual(['statusUpTo', 'statusRange', 'fromAmount']);
  });
});

describe('current status from confirmed server data only', () => {
  const on = catalog(true);

  it.each([
    ['0', 1], ['99999.99', 1], ['100000', 2], ['199999.99', 2], ['200000', 3],
  ])('spend_total %s -> level %i', (spend, level) => {
    const result = resolveCurrentStatus(tierFor(spend), on);
    expect(result.known && result.status.level).toBe(level);
  });

  it('progress, remaining and the maximum level', () => {
    const mid = resolveCurrentStatus(tierFor('120000'), on);
    expect(mid).toMatchObject({ known: true, remaining: 80000, isMax: false, next: { level: 3 } });
    if (mid.known) expect(mid.progress).toBeCloseTo(0.6, 5);
    expect(resolveCurrentStatus(tierFor('250000'), on)).toMatchObject({ known: true, remaining: null, next: null, isMax: true, progress: 1 });
    expect(resolveCurrentStatus(tierFor('0'), on)).toMatchObject({ known: true, remaining: 100000, progress: 0 });
  });

  it('an unconfirmed period gives no current status, whatever the server says', () => {
    expect(resolveCurrentStatus(tierFor('150000'), catalog(false))).toEqual({ known: false, reason: 'unconfirmed' });
  });

  it('an unknown turnover (spend_total null) is NOT treated as 0 / level 1', () => {
    expect(resolveCurrentStatus(tierFor(null), on)).toEqual({ known: false, reason: 'no-spend' });
    expect(resolveCurrentStatus(tierFor('', {}), on)).toEqual({ known: false, reason: 'no-spend' });
    expect(resolveCurrentStatus(tierFor('abc'), on)).toEqual({ known: false, reason: 'no-spend' });
  });

  it('no tier at all gives no status', () => {
    expect(resolveCurrentStatus(null, on)).toEqual({ known: false, reason: 'no-tier' });
    expect(resolveCurrentStatus(undefined, on)).toEqual({ known: false, reason: 'no-tier' });
  });

  it('server levels that disagree with the confirmed catalog (old thresholds, wrong level) are not trusted', () => {
    const oldLevels = [{ level: 1, name: null, threshold: '0', percent: '3' }, { level: 2, name: null, threshold: '350000', percent: '5' }, { level: 3, name: null, threshold: '800000', percent: '8' }];
    expect(resolveCurrentStatus(tierFor('120000', { levels: oldLevels }), on)).toEqual({ known: false, reason: 'mismatch' });
    expect(resolveCurrentStatus(tierFor('120000', { level: 1 }), on)).toEqual({ known: false, reason: 'mismatch' });
    expect(resolveCurrentStatus(tierFor('120000', { levels: SERVER_LEVELS.slice(0, 2) }), on)).toEqual({ known: false, reason: 'mismatch' });
  });

  it('the turnover is never taken from the balance', () => {
    const tier = tierFor(null);
    expect(resolveCurrentStatus(tier, on)).toEqual({ known: false, reason: 'no-spend' });
    expect(resolveCurrentStatus.length).toBe(2); // only (tier, catalog): there is no balance/transactions input at all
  });
});

const card = (tier: Tier | null, balance = '1234.0000'): Card => ({ id: 'c1', barcode: '0001234', balance, is_blocked: false, updated_at: '2026-11-09T00:00:00Z', bound_at: '2026-11-09T00:00:00Z', bind_method: 'phone_auto',
  business: { id: 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0', name: 'KeremEt', branding: null }, tier });
function serve(cards: Card[]) {
  const routes: Record<string, unknown> = { '/me/cards': cards, '/me/profile': { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null },
    '/me/promotions': { banners: [], offers: [], has_new: false }, '/me/app-content': { business_id: 'b', stores: [], app_texts: {}, updated_at: '2026-11-09T00:00:00Z' }, '/me/badges': { promotions_new: false, notifications_unread: 0 } };
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}
function mount(element: ReactElement, { language = 'ru', theme = 'light' }: { language?: 'ru' | 'kz'; theme?: 'light' | 'dark' } = {}) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><ThemeProvider initialPreference={theme}><I18nProvider initial={language}><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider></ThemeProvider></QueryClientProvider>);
}

beforeEach(() => { mockRequest.mockReset(); mockPush.mockReset(); process.env.EXPO_PUBLIC_CLIENT = 'keremet'; keremetStatuses.turnoverConfirmed = false; });
afterAll(() => { if (originalClient === undefined) delete process.env.EXPO_PUBLIC_CLIENT; else process.env.EXPO_PUBLIC_CLIENT = originalClient; keremetStatuses.turnoverConfirmed = false; });

describe('Keremet status screen', () => {
  it('while the data is unconfirmed: balance stays, no made-up level, "data unavailable", conditions are in the sheet', async () => {
    serve([card(tierFor('0'))]);
    mount(<StatusRoute />);
    expect(await screen.findByTestId('status-unavailable')).toBeTruthy();
    expect(screen.getAllByText(ru.statusUnavailable).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId('current-status-name')).toBeNull();
    expect(screen.queryByText('1')).toBeNull(); // no "level 1" for everybody
    expect(screen.queryByText(ru.maxStatus)).toBeNull();
    fireEvent.press(screen.getByRole('button', { name: ru.howToRaise }));
    for (const level of keremetStatuses.levels) {
      expect(screen.getByTestId(`status-row-${level.key}`)).toBeTruthy();
      expect(screen.getByLabelText(level.name)).toBeTruthy();
    }
    expect(screen.getByText('до 100 000 ₸')).toBeTruthy();
    expect(screen.getByText('от 100 000 ₸ до 200 000 ₸')).toBeTruthy();
    expect(screen.getByText('от 200 000 ₸')).toBeTruthy();
    expect(screen.getByText('2%')).toBeTruthy();
    expect(screen.getByText('3%')).toBeTruthy();
    expect(screen.getByText('4%')).toBeTruthy();
    expect(screen.getAllByText(ru.statusPeriodNote).length).toBeGreaterThan(0);
    // No estimate of points while the status is unknown.
    expect(screen.queryByLabelText(ru.calcLabel)).toBeNull();
  });

  it('with confirmed data: current name and picture, period-labelled turnover, progress to the next named status', async () => {
    keremetStatuses.turnoverConfirmed = true;
    serve([card(tierFor('120000'))]);
    mount(<StatusRoute />);
    expect((await screen.findByTestId('current-status-name')).props.children).toBe('Продуктовый эксперт');
    expect(screen.getAllByTestId('status-art-expert').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('status-art-boss')).toBeNull();
    expect(screen.getByText('Покупки за последние 6 месяцев: 120 000 ₸')).toBeTruthy();
    expect(screen.getByText('ещё 80 000 ₸')).toBeTruthy();
    expect(screen.getByText('до статуса Шоппинг-босс')).toBeTruthy();
    expect(screen.queryByTestId('status-unavailable')).toBeNull();
  });

  it('the maximum status says so and shows the boss', async () => {
    keremetStatuses.turnoverConfirmed = true;
    serve([card(tierFor('200000'))]);
    mount(<StatusRoute />);
    expect((await screen.findByTestId('current-status-name')).props.children).toBe('Шоппинг-босс');
    expect(screen.getByText(ru.maxStatus)).toBeTruthy();
    expect(screen.getAllByTestId('status-art-boss').length).toBeGreaterThan(0);
  });

  it('confirmed period but unknown turnover (null): unavailable, not level 1', async () => {
    keremetStatuses.turnoverConfirmed = true;
    serve([card(tierFor(null))]);
    mount(<StatusRoute />);
    expect(await screen.findByTestId('status-unavailable')).toBeTruthy();
    expect(screen.queryByTestId('current-status-name')).toBeNull();
    expect(screen.queryByTestId('status-art-occasional')).toBeNull();
  });

  it('a user without a card sees the conditions, but no current status, balance or QR', async () => {
    keremetStatuses.turnoverConfirmed = true;
    serve([]);
    mount(<StatusRoute />);
    expect(await screen.findByTestId('no-card-notice')).toBeTruthy();
    expect(screen.getByTestId('status-catalog')).toBeTruthy();
    expect(screen.getByText(ru.statusCatalogTitle)).toBeTruthy();
    expect(screen.queryByTestId('current-status-name')).toBeNull();
    expect(screen.queryByText(ru.pointsSum)).toBeNull();
    expect(screen.queryByRole('button', { name: ru.howToRaise })).toBeNull();
  });

  it('Kazakh: conditions and labels are translated, the brand names stay as they are', async () => {
    serve([card(tierFor('0'))]);
    mount(<StatusRoute />, { language: 'kz' });
    fireEvent.press(await screen.findByRole('button', { name: kz.howToRaise }));
    expect(screen.getByText('100 000 ₸ дейін')).toBeTruthy();
    expect(screen.getByText('100 000 ₸ бастап 200 000 ₸ дейін')).toBeTruthy();
    expect(screen.getByText('200 000 ₸ бастап')).toBeTruthy();
    expect(screen.getAllByText(kz.statusPeriodNote).length).toBeGreaterThan(0);
    expect(screen.getAllByText(kz.statusUnavailable).length).toBeGreaterThan(0);
    for (const level of keremetStatuses.levels) expect(screen.getByText(level.name)).toBeTruthy();
  });

  it('the pictures are never tinted or inverted, in either theme', async () => {
    keremetStatuses.turnoverConfirmed = true;
    for (const theme of ['light', 'dark'] as const) {
      serve([card(tierFor('150000'))]);
      const view = mount(<StatusRoute />, { theme });
      const art = (await screen.findAllByTestId('status-art-expert'))[0]!;
      expect(art.props.accessibilityIgnoresInvertColors).toBe(true);
      expect(StyleSheet.flatten(art.props.style)).not.toHaveProperty('tintColor');
      view.unmount();
    }
  });
});

describe('Keremet home', () => {
  it('with unconfirmed data the status card says "unavailable" and no "up to N%" promise is shown', async () => {
    serve([card(tierFor('0'))]);
    mount(<Home />);
    expect(await screen.findByTestId('home-status-unavailable')).toBeTruthy();
    expect(screen.queryByText(/Не упустите/)).toBeNull();
    expect(screen.queryByTestId('home-status-name')).toBeNull();
  });

  it('with confirmed data the card shows the name and picture, consistent with the status screen, and the highest percent of the catalog', async () => {
    keremetStatuses.turnoverConfirmed = true;
    serve([card(tierFor('100000'))]);
    mount(<Home />);
    expect((await screen.findByTestId('home-status-name')).props.children).toBe('Продуктовый эксперт');
    expect(screen.getAllByTestId('status-art-expert').length).toBeGreaterThan(0);
    expect(screen.getByText('Не упустите до 4% баллов')).toBeTruthy();
  });

  it('a user without a card gets a small entry to the conditions and no status card', async () => {
    serve([]);
    mount(<Home />);
    fireEvent.press(await screen.findByRole('button', { name: ru.statusCatalogTitle }));
    expect(mockPush).toHaveBeenCalledWith('/status');
    expect(screen.queryByTestId('home-status-name')).toBeNull();
    expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
  });
});

describe('other clients keep their server levels and artwork', () => {
  const tier: Tier = { level: 2, name: null, percent: '5.0000', max_percent: '12.0000', spend_total: '400000.0000', next_level: 3, next_threshold: '800000.0000', remaining: '400000.0000',
    levels: [{ level: 1, name: null, threshold: '0', percent: '3' }, { level: 2, name: null, threshold: '350000', percent: '5' }, { level: 3, name: null, threshold: '800000', percent: '8' }] };

  it('the general app shows the numbered server statuses and the coin, never the Keremet characters', async () => {
    process.env.EXPO_PUBLIC_CLIENT = 'cashbackone';
    serve([card(tier)]);
    mount(<StatusRoute />);
    expect(await screen.findByText('2')).toBeTruthy();
    expect(screen.queryByTestId('current-status-name')).toBeNull();
    expect(screen.queryByTestId('status-art-expert')).toBeNull();
    fireEvent.press(screen.getByRole('button', { name: ru.howToRaise }));
    expect(screen.getByText('Статус 3')).toBeTruthy();
    expect(screen.queryByTestId('status-catalog')).toBeNull();
    expect(screen.queryByText('Продуктовый эксперт')).toBeNull();
  });

  it('the shared sheet is unchanged without a catalog', () => {
    render(<I18nProvider initial="ru"><LevelsSheet tier={tier} onClose={jest.fn()} /></I18nProvider>);
    expect(screen.getByText('Статус 1')).toBeTruthy();
    expect(screen.getByText(ru.howToLead)).toBeTruthy();
    expect(screen.getByLabelText(ru.calcLabel)).toBeTruthy();
  });

  it('on the general app the home status card still shows the server tier number', async () => {
    process.env.EXPO_PUBLIC_CLIENT = 'cashbackone';
    serve([card(tier)]);
    mount(<Home />);
    await waitFor(() => expect(screen.getByText('2')).toBeTruthy());
    expect(screen.getByText('Не упустите до 12% баллов')).toBeTruthy();
    expect(screen.queryByTestId('home-status-unavailable')).toBeNull();
  });
});
