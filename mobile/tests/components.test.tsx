import { render, fireEvent } from '@testing-library/react-native';
import { WalletList } from '../src/features/WalletList';
import { BindForm } from '../src/features/BindForm';
import { CardQr } from '../src/features/CardQr';
import { ErrorNotice } from '../src/components/ui';
import { ApiError } from '../src/api/errors';
import type { Card } from '../src/types/api';
import { ru } from '../src/i18n/ru';
jest.mock('react-native-qrcode-svg', () => { const React = jest.requireActual<typeof import('react')>('react'); const { Text } = jest.requireActual<typeof import('react-native')>('react-native'); return function MockQr({ value }: { value: string }) { return React.createElement(Text, { testID: 'qr-payload' }, value); }; });
const card: Card = { id: 'card', barcode: '0123456789012', balance: '50.0000', is_blocked: false, updated_at: '2026-10-01T00:00:00Z', bound_at: '2026-10-01T00:00:00Z', bind_method: 'phone_auto', business: { id: 'business', name: 'Магазин', branding: null } };
it('wallet empty state has bind CTA and is not an error', () => {
  const bind = jest.fn(); const screen = render(<WalletList cards={[]} bind={bind} open={jest.fn()} refreshing={false} refresh={jest.fn()} />);
  expect(screen.getByText(ru.emptyTitle)).toBeTruthy(); fireEvent.press(screen.getByRole('button', { name: ru.bind })); expect(bind).toHaveBeenCalled();
});
it('wallet populated state shows real DTO balance barcode and opens card', () => {
  const open = jest.fn(); const screen = render(<WalletList cards={[card]} bind={jest.fn()} open={open} refreshing={false} refresh={jest.fn()} />);
  expect(screen.getByText('50')).toBeTruthy(); expect(screen.getByText(card.barcode)).toBeTruthy();
  fireEvent.press(screen.getByRole('button', { name: /Магазин/ })); expect(open).toHaveBeenCalledWith(card.id);
});
it('manual binding blocks invalid input and passes exact leading-zero string', () => {
  const submit = jest.fn(); const screen = render(<BindForm submit={submit} pending={false} />);
  fireEvent.changeText(screen.getByLabelText(ru.barcode), '123'); fireEvent.press(screen.getByRole('button', { name: ru.bind }));
  expect(submit).not.toHaveBeenCalled(); expect(screen.getByText(ru.invalidBarcode)).toBeTruthy();
  fireEvent.changeText(screen.getByLabelText(ru.barcode), card.barcode); fireEvent.press(screen.getByRole('button', { name: ru.bind })); expect(submit).toHaveBeenCalledWith(card.barcode);
});
it('QR component forwards the exact barcode to QR encoder', () => { const screen = render(<CardQr barcode={card.barcode} />); expect(screen.getByTestId('qr-payload').props.children).toBe(card.barcode); });
it('invalid QR never renders an encoder', () => { const screen = render(<CardQr barcode="123" />); expect(screen.queryByTestId('qr-payload')).toBeNull(); expect(screen.getByText(ru.qrInvalid)).toBeTruthy(); });
it('network errors offer accessible retry without raw server message', () => {
  const retry = jest.fn(); const screen = render(<ErrorNotice error={new ApiError('NETWORK_UNAVAILABLE')} retry={retry} />);
  expect(screen.getByRole('alert')).toBeTruthy(); fireEvent.press(screen.getByRole('button', { name: ru.retry })); expect(retry).toHaveBeenCalled();
});
