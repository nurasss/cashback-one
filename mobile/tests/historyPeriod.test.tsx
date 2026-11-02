import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import HistoryScreen from '../app/(app)/history';
import { PeriodSheet } from '../src/features/PeriodSheet';
import { historyRange } from '../src/features/historyPeriod';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Card } from '../src/types/api';

const mockRequest = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const sampleCard: Card = {
  id: 'card-123',
  barcode: '1234567890123',
  balance: '1500.0000',
  is_blocked: false,
  updated_at: '2026-11-01T10:00:00Z',
  bound_at: '2026-11-01T10:00:00Z',
  bind_method: 'phone_auto',
  business: {
    id: 'biz-1',
    name: 'Супермаркет',
    branding: { logo_url: null, primary_color: '#0055FF', accent_color: '#FFCC00' },
  },
};

describe('historyRange function', () => {
  it('handles "all" with empty params', () => {
    expect(historyRange('all')).toEqual({});
  });

  it('calculates 7d, 30d, 90d based on local midnight without upper bound', () => {
    const fixedNow = new Date(2026, 10, 2, 14, 30, 0, 0); // 2026-11-02 14:30

    const range7 = historyRange('7d', fixedNow);
    const expected7From = new Date(2026, 10, 2 - 6, 0, 0, 0, 0).toISOString();
    expect(range7.from).toBe(expected7From);
    expect(range7.to).toBeUndefined();

    const range30 = historyRange('30d', fixedNow);
    const expected30From = new Date(2026, 10, 2 - 29, 0, 0, 0, 0).toISOString();
    expect(range30.from).toBe(expected30From);
    expect(range30.to).toBeUndefined();

    const range90 = historyRange('90d', fixedNow);
    const expected90From = new Date(2026, 10, 2 - 89, 0, 0, 0, 0).toISOString();
    expect(range90.from).toBe(expected90From);
    expect(range90.to).toBeUndefined();
  });

  it('handles year transition for 7d preset', () => {
    const now = new Date(2027, 0, 3);
    const range = historyRange('7d', now);
    expect(range.from).toBe(new Date(2026, 11, 28, 0, 0, 0, 0).toISOString());
    expect(range.to).toBeUndefined();
  });

  it('handles month transition for 7d preset', () => {
    const now = new Date(2026, 2, 1);
    const range = historyRange('7d', now);
    expect(range.from).toBe(new Date(2026, 1, 23, 0, 0, 0, 0).toISOString());
    expect(range.to).toBeUndefined();
  });

  it('calculates custom object range with exclusive to date next day across year boundary', () => {
    const range = historyRange({ from: '2026-12-31', to: '2026-12-31' });
    const expectedFrom = new Date(2026, 11, 31, 0, 0, 0, 0).toISOString();
    const expectedTo = new Date(2027, 0, 1, 0, 0, 0, 0).toISOString();
    expect(range.from).toBe(expectedFrom);
    expect(range.to).toBe(expectedTo);
  });
});

describe('PeriodSheet component', () => {
  it('renders localized birthDatePh in KK locale', () => {
    const screen = render(
      <I18nProvider initial="kz">
        <PeriodSheet onApply={jest.fn()} onClose={jest.fn()} />
      </I18nProvider>
    );
    expect(screen.getAllByPlaceholderText(kz.birthDatePh)).toHaveLength(2);
  });
  it('validates empty and invalid dates', () => {
    const onApply = jest.fn();
    const onClose = jest.fn();
    const screen = render(
      <I18nProvider>
        <PeriodSheet onApply={onApply} onClose={onClose} />
      </I18nProvider>
    );

    fireEvent.press(screen.getByText(ru.periodApply));
    expect(screen.getByText(ru.invalidDate)).toBeTruthy();
    expect(onApply).not.toHaveBeenCalled();

    // Partial input
    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '12.12');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '15.12.2026');
    fireEvent.press(screen.getByText(ru.periodApply));
    expect(screen.getByText(ru.invalidDate)).toBeTruthy();
    expect(onApply).not.toHaveBeenCalled();
  });

  it('rejects dates in future', () => {
    const onApply = jest.fn();
    const onClose = jest.fn();
    const screen = render(
      <I18nProvider>
        <PeriodSheet onApply={onApply} onClose={onClose} />
      </I18nProvider>
    );

    // Future year 2099
    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '01.01.2099');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '02.01.2099');
    fireEvent.press(screen.getByText(ru.periodApply));
    expect(screen.getByText(ru.invalidDate)).toBeTruthy();
    expect(onApply).not.toHaveBeenCalled();
  });

  it('rejects from > to with invalidPeriod', () => {
    const onApply = jest.fn();
    const onClose = jest.fn();
    const screen = render(
      <I18nProvider>
        <PeriodSheet onApply={onApply} onClose={onClose} />
      </I18nProvider>
    );

    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '15.10.2026');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '10.10.2026');
    fireEvent.press(screen.getByText(ru.periodApply));
    expect(screen.getByText(ru.invalidPeriod)).toBeTruthy();
    expect(onApply).not.toHaveBeenCalled();
  });

  it('applies valid range and closes sheet', () => {
    const onApply = jest.fn();
    const onClose = jest.fn();
    const screen = render(
      <I18nProvider>
        <PeriodSheet onApply={onApply} onClose={onClose} />
      </I18nProvider>
    );

    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '01.10.2026');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '15.10.2026');
    fireEvent.press(screen.getByText(ru.periodApply));

    expect(onApply).toHaveBeenCalledWith({ from: '2026-10-01', to: '2026-10-15' });
    expect(onClose).toHaveBeenCalled();
  });
});

describe('HistoryScreen period integration', () => {
  beforeEach(() => {
    mockRequest.mockClear();
  });

  it('shows period chips, calls API with date range and shows empty state', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        return Promise.resolve({ items: [], next_cursor: null, has_more: false });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    // Initial load: period "all"
    await waitFor(() => expect(screen.getByText(ru.periodAll)).toBeTruthy());
    expect(screen.getByText(ru.noHistory)).toBeTruthy();

    // Switch to 7 days
    await act(async () => {
      fireEvent.press(screen.getByText(ru.period7));
    });

    await waitFor(() => {
      const historyCall = mockRequest.mock.calls.find(call =>
        typeof call[0] === 'string' && call[0].includes('date_from=')
      );
      expect(historyCall).toBeTruthy();
      expect(historyCall[0]).not.toContain('date_to=');
    });

    // In period mode with no items, empty title is noHistoryPeriod
    await waitFor(() => expect(screen.getByText(ru.noHistoryPeriod)).toBeTruthy());
    screen.unmount();
  });

  it('opens PeriodSheet when tapping custom period chip and updates chip label on apply', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        return Promise.resolve({ items: [], next_cursor: null, has_more: false });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.resolve({});
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(ru.periodCustom)).toBeTruthy());

    // Tap "Период…" chip
    fireEvent.press(screen.getByText(ru.periodCustom));

    // PeriodSheet opens
    expect(screen.getByLabelText(ru.periodFrom)).toBeTruthy();
    expect(screen.getByLabelText(ru.periodTo)).toBeTruthy();

    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '01.10.2026');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '15.10.2026');

    await act(async () => {
      fireEvent.press(screen.getByText(ru.periodApply));
    });

    // Chip now displays formatted range
    await waitFor(() => expect(screen.getByText('01.10.2026 – 15.10.2026')).toBeTruthy());
    screen.unmount();
  });

  it('switches back to "Всё время" after selected period and issues query without dates', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        return Promise.resolve({ items: [], next_cursor: null, has_more: false });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.resolve({});
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(ru.period7)).toBeTruthy());

    // Click "7 дней"
    await act(async () => {
      fireEvent.press(screen.getByText(ru.period7));
    });
    await waitFor(() => {
      expect(mockRequest.mock.calls.some(call => typeof call[0] === 'string' && call[0].includes('date_from='))).toBe(true);
    });

    // Click "Всё время" (ru.periodAll)
    mockRequest.mockClear();
    await act(async () => {
      fireEvent.press(screen.getByText(ru.periodAll));
    });

    await waitFor(() => {
      const lastTxCall = mockRequest.mock.calls.find(call => typeof call[0] === 'string' && call[0].includes('/transactions'));
      expect(lastTxCall).toBeTruthy();
      expect(lastTxCall[0]).not.toContain('date_from=');
      expect(lastTxCall[0]).not.toContain('date_to=');
    });
    screen.unmount();
  });

  it('combines period with type filter in query URL', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        return Promise.resolve({ items: [], next_cursor: null, has_more: false });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.resolve({});
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(ru.period7)).toBeTruthy());

    // Click "7 дней" and "Списания"
    await act(async () => {
      fireEvent.press(screen.getByText(ru.period7));
      fireEvent.press(screen.getByText(ru.filterRedemption));
    });

    await waitFor(() => {
      const call = mockRequest.mock.calls.find(c =>
        typeof c[0] === 'string' && c[0].includes('type=redemption') && c[0].includes('date_from=')
      );
      expect(call).toBeTruthy();
    });
    screen.unmount();
  });

  it('paginates with "Ещё" keeping cursor and same date_from and date_to parameters', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        const isNext = path.includes('cursor=');
        return Promise.resolve({
          items: [
            {
              id: isNext ? 'tx-2' : 'tx-1',
              external_id: isNext ? 'e2' : 'e1',
              type: 'accrual',
              amount: '100.0000',
              balance_after: '100.0000',
              occurred_at: '2026-10-05T10:00:00Z',
              receipt_ref: null,
              store: 'Магазин',
            },
          ],
          has_more: !isNext,
          next_cursor: isNext ? null : 'cursor-token-123',
        });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.resolve({});
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    // Set custom range
    await waitFor(() => expect(screen.getByText(ru.periodCustom)).toBeTruthy());
    fireEvent.press(screen.getByText(ru.periodCustom));

    fireEvent.changeText(screen.getByLabelText(ru.periodFrom), '01.10.2026');
    fireEvent.changeText(screen.getByLabelText(ru.periodTo), '15.10.2026');
    await act(async () => {
      fireEvent.press(screen.getByText(ru.periodApply));
    });

    // Wait for "Ещё" button
    await waitFor(() => expect(screen.getByText(ru.more)).toBeTruthy());

    mockRequest.mockClear();
    await act(async () => {
      fireEvent.press(screen.getByText(ru.more));
    });

    await waitFor(() => {
      const pageCall = mockRequest.mock.calls.find(c =>
        typeof c[0] === 'string' && c[0].includes('cursor=cursor-token-123')
      );
      expect(pageCall).toBeTruthy();
      expect(pageCall[0]).toContain('date_from=');
      expect(pageCall[0]).toContain('date_to=');
    });
    screen.unmount();
  });

  it('dismissing PeriodSheet by backdrop cancel does not change period or trigger request', async () => {
    mockRequest.mockImplementation((path: string) => {
      if (path.includes('/transactions')) {
        return Promise.resolve({ items: [], next_cursor: null, has_more: false });
      }
      if (path.startsWith('/me/cards')) {
        return Promise.resolve([sampleCard]);
      }
      return Promise.resolve({});
    });

    const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const screen = render(
      <QueryClientProvider client={query}>
        <I18nProvider>
          <ActiveCardProvider>
            <HistoryScreen />
          </ActiveCardProvider>
        </I18nProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(ru.periodCustom)).toBeTruthy());
    await waitFor(() => expect(mockRequest).toHaveBeenCalledWith(expect.stringContaining('/transactions'), expect.anything()));

    mockRequest.mockClear();
    // Open sheet
    fireEvent.press(screen.getByText(ru.periodCustom));
    expect(screen.getByLabelText(ru.periodFrom)).toBeTruthy();

    // Cancel via backdrop
    fireEvent.press(screen.getByLabelText(ru.cancel));

    // Sheet closed, custom period still "Период…", no extra transactions request
    expect(screen.queryByLabelText(ru.periodFrom)).toBeNull();
    expect(screen.getByText(ru.periodCustom)).toBeTruthy();
    expect(mockRequest).not.toHaveBeenCalled();
    screen.unmount();
  });
});
