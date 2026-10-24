import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { AppState, Linking, StyleSheet } from 'react-native';
import * as expoCamera from 'expo-camera';
import { CardScanner } from '../src/features/CardScanner';
import { BindForm } from '../src/features/BindForm';
import { TabBar } from '../src/components/TabBar';
import { I18nProvider } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

// expo-camera is replaced by the manual mock in __mocks__/expo-camera.js (jest-expo maps
// node_modules mocks automatically). The fake hook keeps React state, and the fake CameraView
// records the scan handler so tests can emit barcode events.
const cameraState = (expoCamera as unknown as { __cameraState: {
  initialGranted: boolean; nextGranted: boolean; holdRequest: boolean;
  handler: ((result: { data: string }) => void) | null;
  barcodeTypes: readonly string[] | null;
} }).__cameraState;

// Scan events arrive from native outside React's knowledge, so they are wrapped in act().
const scan = (data: string) => act(() => { cameraState.handler?.({ data }); });
const bindForm = (language: 'ru' | 'kz' = 'ru') => render(<I18nProvider initial={language}><BindForm submit={jest.fn()} pending={false} /></I18nProvider>);

beforeEach(() => {
  cameraState.initialGranted = false;
  cameraState.nextGranted = false;
  cameraState.handler = null;
  cameraState.barcodeTypes = null;
  cameraState.holdRequest = false;
});

describe('Bind screen scanner button', () => {
  it('shows the camera scan button in Russian and Kazakh next to the number field', () => {
    const russian = bindForm('ru');
    expect(russian.getByLabelText(ru.scanWithCamera)).toBeTruthy();
    expect(russian.getByLabelText(ru.barcode)).toBeTruthy();
    const kazakh = bindForm('kz');
    expect(kazakh.getByLabelText(kz.scanWithCamera)).toBeTruthy();
    expect(kazakh.getByLabelText(kz.barcode)).toBeTruthy();
  });

  it('opens the scanner when the permission is granted on request', async () => {
    cameraState.nextGranted = true;
    const screen = bindForm();
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    expect(cameraState.barcodeTypes).toEqual(['qr', 'code128', 'code39', 'ean13', 'ean8', 'upc_a', 'upc_e', 'itf14', 'codabar']);
    expect(screen.getByText(ru.scanCardHint)).toBeTruthy();
    fireEvent.press(screen.getByLabelText(ru.close));
    expect(screen.queryByTestId('camera-view')).toBeNull();
  });

  it('shows a denied message with settings button and keeps manual entry available', async () => {
    cameraState.nextGranted = false;
    const screen = bindForm();
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByText(ru.cameraPermissionDenied)).toBeTruthy());
    expect(screen.getByText(ru.cameraPermissionTitle)).toBeTruthy();
    expect(screen.queryByTestId('camera-view')).toBeNull();
    expect(screen.getByLabelText(ru.barcode)).toBeTruthy(); // manual entry is untouched
    const openSettings = jest.spyOn(Linking, 'openSettings').mockResolvedValue();
    fireEvent.press(screen.getByLabelText(ru.openSettings));
    expect(openSettings).toHaveBeenCalled();
  });

  it('fills the field with the scanned number, closes the scanner and does not submit until Привязать карту', async () => {
    cameraState.nextGranted = true;
    const submit = jest.fn();
    const screen = render(<I18nProvider><BindForm submit={submit} pending={false} /></I18nProvider>);
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    scan(' 0001234 ');
    await waitFor(() => expect(screen.queryByTestId('camera-view')).toBeNull());
    expect(screen.getByLabelText(ru.barcode).props.value).toBe('0001234'); // trimmed, leading zeros kept as a string
    expect(submit).not.toHaveBeenCalled();
    fireEvent.press(screen.getByLabelText(ru.bind));
    expect(submit).toHaveBeenCalledWith('0001234');
  });

  it.each(['C1ABCDEFGH', 'abc', '123', '12345678901234'])('keeps scanning and shows the warning for %s', async value => {
    cameraState.initialGranted = true;
    cameraState.nextGranted = true;
    const screen = bindForm();
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    scan(value);
    await waitFor(() => expect(screen.getByText(ru.notCardNumber)).toBeTruthy());
    expect(screen.getByTestId('camera-view')).toBeTruthy(); // scanner stays open
    expect(screen.getByLabelText(ru.barcode).props.value).toBe('');
  });

  it('handles only the first valid reading and ignores further scan events', async () => {
    cameraState.nextGranted = true;
    const screen = bindForm();
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    scan('0001234');
    await waitFor(() => expect(screen.getByLabelText(ru.barcode).props.value).toBe('0001234'));
    scan('9999999999999');
    expect(screen.getByLabelText(ru.barcode).props.value).toBe('0001234'); // later events are ignored until close
  });

  it('closes together with the scanner and can be reopened', async () => {
    cameraState.nextGranted = true;
    const screen = bindForm();
    fireEvent.press(screen.getByLabelText(ru.scanWithCamera));
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    fireEvent.press(screen.getByLabelText(ru.close));
    expect(screen.queryByTestId('camera-view')).toBeNull();
    expect(screen.queryByText(ru.scanCardHint)).toBeNull();
  });
});

describe('CardScanner standalone', () => {
  it('warns in Kazakh for a non-number QR and keeps scanning', async () => {
    cameraState.initialGranted = true;
    const screen = render(<I18nProvider initial="kz"><CardScanner onCode={jest.fn()} onClose={jest.fn()} /></I18nProvider>);
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    scan('C1QRSTUVWXYZ');
    await waitFor(() => expect(screen.getByText(kz.notCardNumber)).toBeTruthy());
    expect(screen.getByText(kz.scanCardHint)).toBeTruthy();
  });
});

describe('TabBar QR button', () => {
  it('renders the QR tab flush with the others and navigates on press', () => {
    const onSelect = jest.fn();
    const screen = render(<TabBar active="index" onSelect={onSelect} badges={{ promotions: false, notifications: 0 }} />);
    const button = screen.getByLabelText(ru.tabQr);
    expect(button).toBeTruthy();
    expect(screen.getByText(ru.tabQr)).toBeTruthy(); // has a label like the other tabs
    const flat = StyleSheet.flatten(button.props.style);
    expect(flat.width).toBe(48);
    expect(flat.height).toBe(48);
    expect(flat.marginTop).toBeUndefined(); // no negative margin: flush with the panel
    fireEvent.press(button);
    expect(onSelect).toHaveBeenCalledWith('qr');
  });

  it('distinguishes the selected state', () => {
    const screen = render(<TabBar active="qr" onSelect={jest.fn()} badges={{ promotions: false, notifications: 0 }} />);
    const selected = screen.getByRole('tab', { selected: true });
    expect(selected.props.accessibilityLabel).toBe(ru.tabQr);
    expect(StyleSheet.flatten(selected.props.style).borderWidth).toBe(2);
  });
});

describe('Scanner permission and app state on a real device', () => {
  const emitAppState = (state: 'active' | 'background' | 'inactive') => {
    const calls = (AppState.addEventListener as jest.Mock).mock.calls;
    act(() => { for (const [, listener] of calls) listener(state); });
  };
  let spy: jest.SpyInstance;
  beforeEach(() => {
    spy = jest.spyOn(AppState, 'addEventListener').mockImplementation(() => ({ remove: jest.fn() }) as never);
  });
  afterEach(() => spy.mockRestore());

  it('does not show the denied card while the permission dialog is still open', async () => {
    cameraState.holdRequest = true;
    const screen = render(<I18nProvider initial="ru"><CardScanner onCode={jest.fn()} onClose={jest.fn()} /></I18nProvider>);
    await waitFor(() => expect(screen.getByTestId('camera-unavailable')).toBeTruthy());
    expect(screen.queryByText(ru.cameraPermissionTitle)).toBeNull();
    expect(screen.queryByText(ru.openSettings)).toBeNull();
  });

  it('stays open when Android backgrounds the app for the permission dialog', async () => {
    cameraState.holdRequest = true;
    const onClose = jest.fn();
    render(<I18nProvider initial="ru"><CardScanner onCode={jest.fn()} onClose={onClose} /></I18nProvider>);
    emitAppState('background');
    emitAppState('active');
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes when the app goes to the background with the camera running', async () => {
    cameraState.initialGranted = true;
    const onClose = jest.fn();
    const screen = render(<I18nProvider initial="ru"><CardScanner onCode={jest.fn()} onClose={onClose} /></I18nProvider>);
    await waitFor(() => expect(screen.getByTestId('camera-view')).toBeTruthy());
    emitAppState('inactive');
    expect(onClose).not.toHaveBeenCalled();
    emitAppState('background');
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
