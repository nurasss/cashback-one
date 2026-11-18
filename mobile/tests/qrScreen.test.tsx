import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Alert, Linking } from 'react-native';
import Home from '../app/(app)/(tabs)/index';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import QrScreen from '../app/(app)/(tabs)/qr';
import StatusScreen from '../app/(app)/status';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { AppContent, Card, Profile } from '../src/types/api';

const mockRequest = jest.fn();
const mockRouterPush = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));
jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return {
    router: {
      push: (...args: unknown[]) => mockRouterPush(...args),
      replace: jest.fn(),
      navigate: jest.fn(),
      back: jest.fn(),
      canGoBack: () => true,
    },
    useFocusEffect: (cb: () => void | (() => void)) => {
      React.useEffect(() => {
        const cleanup = cb();
        return () => {
          if (typeof cleanup === 'function') cleanup();
        };
      }, [cb]);
    },
  };
});
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) {
    return React.createElement(Text, { testID: 'qr-payload' }, value);
  };
});

const card: Card = {
  id: 'card-id',
  barcode: '0123456789012',
  balance: '0.0000',
  is_blocked: false,
  updated_at: '2026-10-01T00:00:00Z',
  bound_at: '2026-10-01T00:00:00Z',
  bind_method: 'phone_auto',
  business: { id: 'b', name: 'Shop', branding: null },
  tier: null,
};
const second: Card = {
  ...card,
  id: 'card-2',
  barcode: '000123456',
  business: { id: 'b2', name: 'Market', branding: null },
};
const profile: Profile = {
  phone: '+77058344326',
  language: 'ru',
  first_name: null,
  last_name: null,
  email: null,
  gender: null,
  city: null,
  address: null,
  birth_date: null,
  iin: null,
  company: null,
};

function mountWith(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={query}>
      <I18nProvider initial={language}>
        <ActiveCardProvider>{element}</ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
  mockRouterPush.mockReset();
});

describe('QR screen', () => {
  it('shows the QR code containing card.barcode verbatim, including leading zeros', async () => {
    serve({ '/me/cards': [card] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload').props.children).toBe('0123456789012'));
    screen.unmount();

    const leadingZeroCard: Card = { ...card, id: 'card-zero', barcode: '0001' };
    serve({ '/me/cards': [leadingZeroCard] });
    const screen2 = mountWith(<QrScreen />);
    await waitFor(() => expect(screen2.getByTestId('qr-payload').props.children).toBe('0001'));
    screen2.unmount();
  });

  it('never requests /me/cards/{id}/qr from the QR screen', async () => {
    serve({ '/me/cards': [card] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload')).toBeTruthy());
    expect(mockRequest.mock.calls.some(call => String(call[0]).includes('/qr'))).toBe(false);
    screen.unmount();
  });

  it('has no card switcher chip row when customer has multiple cards', async () => {
    serve({ '/me/cards': [card, second] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload')).toBeTruthy());
    expect(screen.queryByRole('button', { name: 'Market' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Shop' })).toBeNull();
    expect(screen.queryByText('Market')).toBeNull();
    expect(screen.queryByText('Shop')).toBeNull();
    screen.unmount();
  });

  it('blocked card: shows cardBlocked and hides QR', async () => {
    serve({ '/me/cards': [{ ...card, is_blocked: true }] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.cardBlocked)).toBeTruthy());
    expect(screen.queryByTestId('qr-payload')).toBeNull();
    expect(mockRequest.mock.calls.some(call => String(call[0]).includes('/qr'))).toBe(false);
    screen.unmount();
  });

  it('no card: no code', async () => {
    serve({ '/me/cards': [] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.noCardNotice)).toBeTruthy());
    expect(screen.queryByTestId('qr-payload')).toBeNull();
    screen.unmount();
  });
});

describe('Home screen header and notes', () => {
  const mockAppContent: AppContent = {
    business_id: card.business.id,
    stores: [
      {
        id: 'store-1',
        title_ru: 'Супермаркет One',
        title_kk: 'One супермаркеті',
        address_ru: 'проспект Тауелсиздик, 4.',
        address_kk: 'Тәуелсіздік даңғылы, 4.',
        map_url: 'https://maps.example.com/firm/1',
        sort_order: 1,
      },
    ],
    app_texts: {
      home_store_note_lead: {
        ru: 'Вы можете потратить эти бонусы в супермаркете, по адресу: ',
        kk: 'Бұл бонустарды супермаркетте келесі мекенжай бойынша жұмсай аласыз: ',
      },
      balance_delay_note: null,
    },
    updated_at: '2026-11-04T12:00:00Z',
  };

  const home = {
    '/me/cards': [card],
    '/me/profile': profile,
    '/me/promotions': { banners: [], offers: [], has_new: false },
    '/me/app-content': mockAppContent,
  };

  it('tapping balance header navigates to /history', async () => {
    serve(home);
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.yourStatus)).toBeTruthy());
    const balanceButton = screen.getByRole('button', { name: new RegExp(ru.accrualHistory, 'i') });
    fireEvent.press(balanceButton);
    expect(mockRouterPush).toHaveBeenCalledWith('/history');
    screen.unmount();
  });

  // The pink address plate was removed from the home screen (owner decision 2026-11-10). Addresses, maps and distances live in the
  // stores section of the status screen, which the "where can I spend" link on Home opens.
  const waitForStoresLink = (screen: ReturnType<typeof mountWith>) => waitFor(() => {
    if (screen.queryByTestId('where-to-spend-link') === null) throw new Error('not yet: the stores link');
  });

  it('does not show the store addresses on the home screen in Russian (no plate, no legacy lead), the stores link stays', async () => {
    serve(home);
    const screen = mountWith(<Home />);
    await waitForStoresLink(screen);
    expect(screen.queryByTestId('store-block')).toBeNull();
    expect(screen.queryByText(mockAppContent.stores[0]!.address_ru)).toBeNull();
    expect(screen.queryByText(mockAppContent.app_texts.home_store_note_lead!.ru!, { exact: false })).toBeNull();
    expect(screen.queryByText(ru.balanceDelayNote)).toBeNull();
    expect(screen.getByText(ru.whereToSpendBonuses)).toBeTruthy();
    screen.unmount();
  });

  it('does not show the store addresses on the home screen in Kazakh either, the stores link stays', async () => {
    serve({ ...home, '/me/profile': { ...profile, language: 'kz' } });
    const screen = mountWith(<Home />, 'kz');
    await waitForStoresLink(screen);
    expect(screen.queryByTestId('store-block')).toBeNull();
    expect(screen.queryByText(mockAppContent.stores[0]!.address_kk)).toBeNull();
    expect(screen.queryByText(mockAppContent.app_texts.home_store_note_lead!.kk!, { exact: false })).toBeNull();
    expect(screen.queryByText(kz.balanceDelayNote)).toBeNull();
    expect(screen.getByText(kz.whereToSpendBonuses)).toBeTruthy();
    screen.unmount();
  });

  it('tapping the stores link opens the stores section of the status screen', async () => {
    serve(home);
    const screen = mountWith(<Home />);
    await waitForStoresLink(screen);
    fireEvent.press(screen.getByTestId('where-to-spend-link'));
    expect(mockRouterPush).toHaveBeenCalledWith({ pathname: '/status', params: { section: 'stores', at: expect.any(String) } });
    screen.unmount();
  });

  it('the stores section shows the address, and tapping the store opens its map URL', async () => {
    serve({ ...home, '/me/badges': { promotions_new: false, notifications_unread: 0 } });
    const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
    const screen = mountWith(<StatusScreen />);
    await waitFor(() => {
      if (screen.queryByTestId('status-store-item-store-1') === null) throw new Error('not yet: the store item');
    });
    expect(screen.getByText(mockAppContent.stores[0]!.address_ru)).toBeTruthy();
    fireEvent.press(screen.getByTestId('status-store-item-store-1'));
    expect(openUrlSpy).toHaveBeenCalledWith('https://maps.example.com/firm/1');
    openUrlSpy.mockRestore();
    screen.unmount();
  });

  it('does not crash and shows an Alert message if the map cannot be opened from the stores section', async () => {
    serve({ ...home, '/me/badges': { promotions_new: false, notifications_unread: 0 } });
    const openUrlSpy = jest.spyOn(Linking, 'openURL').mockRejectedValueOnce(new Error('Cannot open URL'));
    const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    const screen = mountWith(<StatusScreen />);
    await waitFor(() => {
      if (screen.queryByTestId('status-store-item-store-1') === null) throw new Error('not yet: the store item');
    });
    fireEvent.press(screen.getByTestId('status-store-item-store-1'));
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith(ru.app, ru.mapOpenFailed);
    });
    openUrlSpy.mockRestore();
    alertSpy.mockRestore();
    screen.unmount();
  });

  it('is hidden when there is no card', async () => {
    serve({ ...home, '/me/cards': [] });
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.noCardNotice)).toBeTruthy());
    expect(screen.queryByTestId('store-block')).toBeNull();
    screen.unmount();
  });
});

describe('Status screen', () => {
  const statusRoutes = {
    '/me/cards': [card],
    '/me/badges': { promotions_new: false, notifications_unread: 0 },
  };

  it('shows balanceDelayNote on the status screen when card is present', async () => {
    serve(statusRoutes);
    const screen = mountWith(<StatusScreen />);
    await waitFor(() => expect(screen.getByText(ru.balanceDelayNote)).toBeTruthy());
    screen.unmount();
  });

  it('hides balanceDelayNote on the status screen when no card', async () => {
    serve({ ...statusRoutes, '/me/cards': [] });
    const screen = mountWith(<StatusScreen />);
    await waitFor(() => expect(screen.getByText(ru.noCardNotice)).toBeTruthy());
    expect(screen.queryByText(ru.balanceDelayNote)).toBeNull();
    screen.unmount();
  });
});

describe('Profile screen links', () => {
  const profileRoutes = {
    '/me/profile': profile,
    '/me/cards': [card],
  };

  it('renders accrualHistory and the visible "Выход из аккаунта" row, but does NOT render myCards', async () => {
    serve(profileRoutes);
    const screen = mountWith(<ProfileScreen />);
    await waitFor(() => expect(screen.getByText(ru.accrualHistory)).toBeTruthy());
    expect(screen.queryByText(ru.myCards)).toBeNull();
    expect(screen.getByText(ru.logoutAccount)).toBeTruthy();
    expect(ru.logoutAccount).toBe('Выход из аккаунта');
    screen.unmount();
  });
});
