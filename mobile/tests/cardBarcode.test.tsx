import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, waitFor, within } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { Dimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import Home from '../app/(app)/(tabs)/index';
import QrScreen from '../app/(app)/(tabs)/qr';
import { ActiveCardProvider } from '../src/features/activeCard';
import { CardBarcode } from '../src/features/CardBarcode';
import { code128Bars, QUIET_ZONE_MODULES } from '../src/features/code128';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Card, Profile } from '../src/types/api';

const mockRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }) }));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: jest.fn(),
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) { return React.createElement(Text, { testID: 'qr-payload' }, value); };
});

const card: Card = { id: 'card-id', barcode: '0123456789012', balance: '0.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'b', name: 'Shop', branding: null }, tier: null };
const second: Card = { ...card, id: 'card-2', barcode: '000123456', business: { id: 'b2', name: 'Market', branding: null } };
const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const token = 'C1' + 'QRSTUVWX'.repeat(6);

function mountWith(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><I18nProvider initial={language}><ActiveCardProvider>{element}</ActiveCardProvider></I18nProvider></QueryClientProvider>);
}
function serve(routes: Record<string, unknown>) {
  mockRequest.mockImplementation((path: string) => {
    const match = Object.keys(routes).find(prefix => path.startsWith(prefix));
    return match ? Promise.resolve(routes[match]) : Promise.reject(new Error(`unexpected ${path}`));
  });
}
const qrReply = () => ({ token, expires_at: new Date(Date.now() + 60_000).toISOString(), ttl_seconds: 60 });
const barcodePath = (screen: ReturnType<typeof render>) => within(screen.getByTestId('card-barcode')).UNSAFE_getByType(Path);
const pathData = (screen: ReturnType<typeof render>) => barcodePath(screen).props.d as string;
// Read the drawn bars back out of the SVG path ("M{x} 0h{w}v{h}h-{w}z" per bar) in module units without quiet zone.
const drawnBars = (d: string) => Array.from(d.matchAll(/M(\d+) 0h(\d+)v\d+h-\d+z/g), m => ({ x: Number(m[1]) - QUIET_ZONE_MODULES, width: Number(m[2]) }));
beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });

describe('CardBarcode', () => {
  it('draws the Code 128 bars of the exact card number with the business name and a readable number', () => {
    const screen = render(<I18nProvider><CardBarcode card={card} /></I18nProvider>);
    expect(drawnBars(pathData(screen))).toEqual(code128Bars('0123456789012')!.bars);
    expect(screen.getByText('Shop')).toBeTruthy();
    expect(screen.getByText('0123456789012')).toBeTruthy(); // leading zero kept
    expect(screen.getByLabelText(/Штрихкод карты: Shop\. Номер карты 0 1 2 3 4 5 6 7 8 9 0 1 2/)).toBeTruthy();
  });

  it('uses a white background, black bars and full quiet zones inside the viewBox', () => {
    const screen = render(<I18nProvider><CardBarcode card={card} /></I18nProvider>);
    const { modules } = code128Bars('0123456789012')!;
    const bars = drawnBars(pathData(screen));
    expect(within(screen.getByTestId('card-barcode')).UNSAFE_getByType(Svg).props.viewBox).toBe(`0 0 ${modules + QUIET_ZONE_MODULES * 2} 96`);
    expect(barcodePath(screen).props.fill).toBe('#000000');
    expect(bars[0]!.x + QUIET_ZONE_MODULES).toBe(QUIET_ZONE_MODULES); // first bar starts after a full quiet zone
    const last = bars.at(-1)!;
    expect(last.x + last.width + QUIET_ZONE_MODULES).toBe(modules + QUIET_ZONE_MODULES); // and the stop bar ends before the right one
    expect(QUIET_ZONE_MODULES).toBeGreaterThanOrEqual(10);
    expect(JSON.stringify(screen.toJSON())).toContain('"backgroundColor":"#FFFFFF"');
  });

  it('fits a narrow screen without cropping the code', () => {
    const original = Dimensions.get('window');
    const setWindow = (width: number) => (Dimensions as unknown as { set: (value: unknown) => void }).set({ window: { ...original, width }, screen: { ...original, width } });
    setWindow(320);
    const screen = render(<I18nProvider><CardBarcode card={{ ...card, barcode: '123456789012345' }} /></I18nProvider>);
    try {
      const svgWidth = screen.getByTestId('card-barcode-svg').props.width as number;
      expect(svgWidth).toBeGreaterThan(0);
      expect(svgWidth).toBeLessThanOrEqual(320 - 80);
      expect(drawnBars(pathData(screen))).toEqual(code128Bars('123456789012345')!.bars);
      // at least one whole device pixel per module
      expect(svgWidth / (code128Bars('123456789012345')!.modules + QUIET_ZONE_MODULES * 2)).toBeGreaterThanOrEqual(1 / 3);
    } finally {
      screen.unmount();
      setWindow(original.width);
    }
  });

  it('draws nothing without a card or with an invalid number, and no code for a blocked card', () => {
    expect(render(<I18nProvider><CardBarcode card={undefined} /></I18nProvider>).toJSON()).toBeNull();
    for (const barcode of ['12345', '1234567890123456', '12a456', '']) {
      expect(render(<I18nProvider><CardBarcode card={{ ...card, barcode }} /></I18nProvider>).toJSON()).toBeNull();
    }
    const blocked = render(<I18nProvider><CardBarcode card={{ ...card, is_blocked: true }} /></I18nProvider>);
    expect(blocked.queryByTestId('card-barcode-svg')).toBeNull();
    expect(blocked.queryByText('0123456789012')).toBeNull();
    expect(blocked.getByText(ru.cardBlocked)).toBeTruthy();
    expect(blocked.getByText('Shop')).toBeTruthy();
  });
});

describe('QR screen modes', () => {
  it('keeps the dynamic QR by default and never puts the card number into it', async () => {
    serve({ '/me/cards/card-id/qr': qrReply(), '/me/cards': [card] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload').props.children).toBe(token));
    expect(screen.queryByTestId('card-barcode')).toBeNull();
    screen.unmount();
  });

  it('shows a separate Code 128 for the selected card in barcode mode and the QR again on return', async () => {
    serve({ '/me/cards/card-id/qr': qrReply(), '/me/cards/card-2/qr': qrReply(), '/me/cards': [card, second] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByTestId('qr-payload')).toBeTruthy());
    fireEvent.press(screen.getByRole('button', { name: ru.modeBarcode }));
    expect(screen.queryByTestId('qr-payload')).toBeNull();
    expect(drawnBars(pathData(screen))).toEqual(code128Bars('0123456789012')!.bars);
    expect(screen.getAllByText('Shop').length).toBeGreaterThan(0);
    fireEvent.press(screen.getByRole('button', { name: 'Market' })); // choose the second card
    await waitFor(() => expect(screen.getByText('000123456')).toBeTruthy());
    expect(drawnBars(pathData(screen))).toEqual(code128Bars('000123456')!.bars);
    fireEvent.press(screen.getByRole('button', { name: ru.modeQr }));
    await waitFor(() => expect(screen.getByTestId('qr-payload').props.children).toBe(token));
    screen.unmount();
  });

  it('blocked card: no QR request and no barcode', async () => {
    serve({ '/me/cards': [{ ...card, is_blocked: true }] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.cardBlocked)).toBeTruthy());
    expect(mockRequest.mock.calls.some(call => String(call[0]).endsWith('/qr'))).toBe(false);
    fireEvent.press(screen.getByRole('button', { name: ru.modeBarcode }));
    expect(screen.queryByTestId('card-barcode-svg')).toBeNull();
    expect(screen.getByText(ru.cardBlocked)).toBeTruthy();
    screen.unmount();
  });

  it('no card: neither mode switch nor code', async () => {
    serve({ '/me/cards': [] });
    const screen = mountWith(<QrScreen />);
    await waitFor(() => expect(screen.getByText(ru.noCardTitle)).toBeTruthy());
    expect(screen.queryByRole('button', { name: ru.modeBarcode })).toBeNull();
    expect(screen.queryByTestId('card-barcode')).toBeNull();
    screen.unmount();
  });
});

describe('Balance delay note on the home screen', () => {
  const approved = 'Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные';
  const home = { '/me/cards': [card], '/me/profile': profile, '/me/promotions': { banners: [], offers: [], has_new: false } };

  it('shows the approved Russian text', async () => {
    serve(home);
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(approved)).toBeTruthy());
    expect(ru.balanceDelayNote).toBe(approved);
    screen.unmount();
  });

  it('shows the Kazakh equivalent when the language is Kazakh', async () => {
    serve({ ...home, '/me/profile': { ...profile, language: 'kz' } });
    const screen = mountWith(<Home />, 'kz');
    await waitFor(() => expect(screen.getByText(kz.balanceDelayNote)).toBeTruthy());
    expect(screen.queryByText(approved)).toBeNull();
    screen.unmount();
  });

  it('does not promise a time and no longer talks about closing a shift', () => {
    for (const text of [ru.balanceDelayNote, kz.balanceDelayNote]) {
      expect(text).not.toMatch(/24|48|час|сағат|смен/i);
    }
    expect(kz.balanceDelayNote).not.toBe(ru.balanceDelayNote);
  });

  it('is hidden when there is no card to update', async () => {
    serve({ ...home, '/me/cards': [] });
    const screen = mountWith(<Home />);
    await waitFor(() => expect(screen.getByText(ru.noCardTitle)).toBeTruthy());
    expect(screen.queryByText(approved)).toBeNull();
    screen.unmount();
  });
});
