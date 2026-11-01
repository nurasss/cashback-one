import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import Login from '../app/login';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';

const mockRequest = jest.fn();
const mockAccept = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: mockAccept, logout: jest.fn() } }),
}));
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('../src/storage/secure', () => ({
  deviceId: jest.fn(() => Promise.resolve('test-device-id')),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
});

it('login button inactive on invalid number, hints invalidPhone on non-7 first digit, requests code with +7XXXXXXXXXX and code_length: 4', async () => {
  const screen = render(<I18nProvider><Login /></I18nProvider>);

  const phoneInput = screen.getByLabelText(ru.phone);
  const requestButton = screen.getByRole('button', { name: ru.requestCode });

  // 1. Initial state: +7 on screen, button disabled
  expect(phoneInput.props.value).toBe('+7');
  expect(requestButton.props.accessibilityState.disabled).toBe(true);

  // 2. Partial input (less than 10 digits): button still disabled
  fireEvent.changeText(phoneInput, '+7 701 123');
  expect(phoneInput.props.value).toBe('+7 701 123');
  expect(requestButton.props.accessibilityState.disabled).toBe(true);
  expect(screen.queryByText(ru.invalidPhone)).toBeNull();

  // 3. 10 digits but first digit is not 7 (e.g. 601 123 45 67):
  fireEvent.changeText(phoneInput, '+7 601 123 45 67');
  expect(phoneInput.props.value).toBe('+7 601 123 45 67');
  expect(requestButton.props.accessibilityState.disabled).toBe(true);
  expect(screen.getByText(ru.invalidPhone)).toBeTruthy();

  // 4. Valid 10 digits starting with 7:
  fireEvent.changeText(phoneInput, '+7 701 123 45 67');
  expect(phoneInput.props.value).toBe('+7 701 123 45 67');
  expect(requestButton.props.accessibilityState.disabled).toBe(false);
  expect(screen.queryByText(ru.invalidPhone)).toBeNull();

  // 5. Click request code -> sends +77011234567 and code_length: 4
  mockRequest.mockResolvedValueOnce({ status: 'sent', expires_in: 300 });
  await act(async () => {
    fireEvent.press(requestButton);
  });
  expect(mockRequest).toHaveBeenLastCalledWith('/auth/whatsapp/request', {
    method: 'POST',
    body: {
      phone: '+77011234567',
      device_id: 'test-device-id',
      code_length: 4,
    },
  });

  // 6. Verification code step: 4-digit code required
  await waitFor(() => expect(screen.getByLabelText(ru.code)).toBeTruthy());
  const codeInput = screen.getByLabelText(ru.code);
  const verifyButton = screen.getByRole('button', { name: ru.verify });

  // Disabled on empty or less than 4 digits:
  expect(verifyButton.props.accessibilityState.disabled).toBe(true);
  fireEvent.changeText(codeInput, '123');
  expect(verifyButton.props.accessibilityState.disabled).toBe(true);

  // Active on exactly 4 digits:
  fireEvent.changeText(codeInput, '1234');
  expect(verifyButton.props.accessibilityState.disabled).toBe(false);

  // Submit verification:
  const tokens = { access_token: 'acc', refresh_token: 'ref', token_type: 'bearer', expires_in: 900 };
  mockRequest.mockResolvedValueOnce(tokens);
  await act(async () => {
    fireEvent.press(verifyButton);
  });
  expect(mockRequest).toHaveBeenLastCalledWith('/auth/whatsapp/verify', {
    method: 'POST',
    body: {
      phone: '+77011234567',
      device_id: 'test-device-id',
      code: '1234',
    },
  });
  expect(mockAccept).toHaveBeenCalledWith(tokens);

  screen.unmount();
});
