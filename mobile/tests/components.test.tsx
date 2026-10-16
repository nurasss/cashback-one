import { fireEvent, render } from '@testing-library/react-native';
import { ApiError } from '../src/api/errors';
import { TabBar } from '../src/components/TabBar';
import { ErrorNotice } from '../src/components/ui';
import { BindForm } from '../src/features/BindForm';
import { DynamicQr } from '../src/features/DynamicQr';
import { OfferCard, StatusCard } from '../src/features/home';
import { ru } from '../src/i18n/ru';
import type { CardQr, Promotion } from '../src/types/api';

jest.mock('react-native-qrcode-svg', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
  return function MockQr({ value }: { value: string }) { return React.createElement(Text, { testID: 'qr-payload' }, value); };
});
jest.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) }));

const token = 'C1' + 'ABCDEFGH'.repeat(6);
const qr = (expiresInMs: number): CardQr => ({ token, expires_at: new Date(Date.now() + expiresInMs).toISOString(), ttl_seconds: 60 });

it('tab bar shows Messages like the design and marks new promotions and notifications', () => {
  const onSelect = jest.fn();
  const screen = render(<TabBar active="index" onSelect={onSelect} badges={{ promotions: true, notifications: 3 }} />);
  expect(screen.getByText('Сообщения')).toBeTruthy();
  expect(screen.getByLabelText(`${ru.tabPromotions}. ${ru.newBadge}`)).toBeTruthy();
  expect(screen.getByLabelText(`${ru.tabNotifications}. ${ru.newBadge}`)).toBeTruthy();
  fireEvent.press(screen.getByLabelText(ru.tabQr));
  expect(onSelect).toHaveBeenCalledWith('qr');
});

it('tab bar without news shows plain labels', () => {
  const screen = render(<TabBar active="profile" onSelect={jest.fn()} badges={{ promotions: false, notifications: 0 }} />);
  expect(screen.getByLabelText(ru.tabPromotions)).toBeTruthy();
  expect(screen.getByLabelText(ru.tabNotifications)).toBeTruthy();
  expect(screen.getByRole('tab', { selected: true }).props.accessibilityLabel).toBe(ru.tabProfile);
});

it('dynamic QR encodes the server token, never the barcode, and hides expired tokens', () => {
  const screen = render(<DynamicQr qr={qr(60_000)} loading={false} failed={false} blocked={false} />);
  expect(screen.getByTestId('qr-payload').props.children).toBe(token);
  expect(screen.getByText(ru.showToCashier)).toBeTruthy();
  screen.rerender(<DynamicQr qr={qr(-1000)} loading={false} failed={false} blocked={false} />);
  expect(screen.queryByTestId('qr-payload')).toBeNull();
  screen.rerender(<DynamicQr qr={{ ...qr(60_000), token: '0123456789012' }} loading={false} failed={false} blocked={false} />);
  expect(screen.queryByTestId('qr-payload')).toBeNull();
  screen.rerender(<DynamicQr qr={qr(60_000)} loading={false} failed={false} blocked />);
  expect(screen.queryByTestId('qr-payload')).toBeNull();
  expect(screen.getByText(ru.cardBlocked)).toBeTruthy();
});

it('status card shows level and two-decimal balance like the design', () => {
  const onPress = jest.fn();
  const screen = render(<StatusCard tier={{ level: 1, name: null, percent: '3', max_percent: '12', spend_total: '0', next_level: 2, next_threshold: '350000', remaining: '350000' }} balance="0.0000" onPress={onPress} />);
  expect(screen.getByText('1')).toBeTruthy();
  expect(screen.getByText('0,00')).toBeTruthy();
  fireEvent.press(screen.getByRole('button'));
  expect(onPress).toHaveBeenCalled();
});

it('offer card shows badge and title', () => {
  const offer: Promotion = { id: 'p', business_id: null, kind: 'offer', title: 'Покупайте выгодно', subtitle: null, badge: 'Скидка на хиты', body: null, image_url: null, starts_at: null, ends_at: null, is_new: true };
  const onPress = jest.fn();
  const screen = render(<OfferCard offer={offer} index={0} onPress={onPress} />);
  fireEvent.press(screen.getByLabelText('Скидка на хиты. Покупайте выгодно'));
  expect(onPress).toHaveBeenCalled();
});

it('manual binding blocks invalid input and passes exact leading-zero string', () => {
  const submit = jest.fn(); const screen = render(<BindForm submit={submit} pending={false} />);
  fireEvent.changeText(screen.getByLabelText(ru.barcode), '123'); fireEvent.press(screen.getByRole('button', { name: ru.bind }));
  expect(screen.getByText(ru.invalidBarcode)).toBeTruthy(); expect(submit).not.toHaveBeenCalled();
  fireEvent.changeText(screen.getByLabelText(ru.barcode), '0123456789012'); fireEvent.press(screen.getByRole('button', { name: ru.bind }));
  expect(submit).toHaveBeenCalledWith('0123456789012');
});

it('network errors offer accessible retry without raw server message', () => {
  const retry = jest.fn(); const screen = render(<ErrorNotice error={new ApiError('NETWORK_UNAVAILABLE')} retry={retry} />);
  expect(screen.getByRole('alert')).toBeTruthy(); fireEvent.press(screen.getByRole('button', { name: ru.retry })); expect(retry).toHaveBeenCalled();
});
