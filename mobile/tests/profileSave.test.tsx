import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { TextInput } from 'react-native';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import { ApiError } from '../src/api/errors';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { errorMessages, ru } from '../src/i18n/ru';
import type { Profile } from '../src/types/api';

const mockRequest = jest.fn();
let mockFocusEffectCleanup: (() => void) | undefined;

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));
jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return {
    router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
    useFocusEffect: (cb: () => void | (() => void)) => {
      React.useEffect(() => {
        const cleanup = cb();
        mockFocusEffectCleanup = typeof cleanup === 'function' ? cleanup : undefined;
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

const patches = () => mockRequest.mock.calls.filter(call => call[1]?.method === 'PATCH');
const inputs = (screen: ReturnType<typeof render>) => screen.UNSAFE_getAllByType(TextInput).length;
const value = (screen: ReturnType<typeof render>, label: string) => screen.getByLabelText(label).props.value;

async function open(server: Profile = profile) {
  mockRequest.mockImplementation((path: string) =>
    path.startsWith('/me/profile') ? Promise.resolve(server) : Promise.reject(new Error(`unexpected ${path}`))
  );
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  const screen = render(
    <QueryClientProvider client={query}>
      <I18nProvider>
        <ActiveCardProvider>
          <ProfileScreen />
        </ActiveCardProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getByLabelText(ru.firstName)).toBeTruthy());
  return screen;
}

const sheetInput = (screen: ReturnType<typeof render>, label: string) => screen.getAllByLabelText(label).at(-1)!;

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
  mockFocusEffectCleanup = undefined;
});

it('profile has no save button, no IIN and no company', async () => {
  const screen = await open();
  expect(screen.queryByRole('button', { name: 'Сохранить' })).toBeNull();
  expect(screen.queryByLabelText('ИИН')).toBeNull();
  expect(screen.queryByLabelText('Компания')).toBeNull();
  expect(screen.queryByText('ИИН')).toBeNull();
  expect(screen.queryByText('Компания')).toBeNull();
  screen.unmount();
});

it('Done saves only the edited sheet field with a PATCH, closes the sheet and shows the new value', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.email));
  expect(inputs(screen)).toBe(3);
  fireEvent.changeText(sheetInput(screen, ru.email), '  aigerim@example.kz ');
  mockRequest.mockResolvedValueOnce({ ...profile, email: 'aigerim@example.kz' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(patches()).toHaveLength(1);
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { email: 'aigerim@example.kz' } });
  await waitFor(() => expect(inputs(screen)).toBe(2));
  expect(screen.getByLabelText(`${ru.email}: aigerim@example.kz`)).toBeTruthy();
  screen.unmount();
});

it('a failed save keeps the sheet open with the input and the error inside, and can be retried', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.address));
  fireEvent.changeText(sheetInput(screen, ru.address), 'ул. Абая 1');
  mockRequest.mockRejectedValueOnce(new ApiError('NETWORK_UNAVAILABLE'));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(inputs(screen)).toBe(3);
  expect(sheetInput(screen, ru.address).props.value).toBe('ул. Абая 1');
  expect(screen.getByText(errorMessages.NETWORK_UNAVAILABLE!)).toBeTruthy();
  expect(screen.getByRole('button', { name: ru.done }).props.accessibilityState.disabled).toBe(false);
  expect(screen.queryByText(ru.saved)).toBeNull();

  mockRequest.mockResolvedValueOnce({ ...profile, address: 'ул. Абая 1' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(patches()).toHaveLength(2);
  expect(patches()[1]![1].body).toEqual({ address: 'ул. Абая 1' });
  await waitFor(() => expect(inputs(screen)).toBe(2));
  expect(screen.queryByText(errorMessages.NETWORK_UNAVAILABLE!)).toBeNull();
  expect(screen.getByLabelText(`${ru.address}: ул. Абая 1`)).toBeTruthy();
  screen.unmount();
});

it('cancelling sends nothing and leaves the value unchanged', async () => {
  const screen = await open({ ...profile, address: 'Старый адрес' });
  fireEvent.press(screen.getByLabelText(`${ru.address}: Старый адрес`));
  fireEvent.changeText(sheetInput(screen, ru.address), 'Другой адрес');
  fireEvent.press(screen.getByLabelText(ru.cancel));
  expect(inputs(screen)).toBe(2);
  expect(patches()).toHaveLength(0);
  expect(screen.getByLabelText(`${ru.address}: Старый адрес`)).toBeTruthy();
  screen.unmount();
});

it('an unchanged value closes the sheet without a request', async () => {
  const screen = await open({ ...profile, email: 'a@b.kz' });
  fireEvent.press(screen.getByLabelText(`${ru.email}: a@b.kz`));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(patches()).toHaveLength(0);
  expect(inputs(screen)).toBe(2);
  screen.unmount();
});

it('empty values go to the API as null, also for the birth date', async () => {
  const screen = await open({ ...profile, email: 'a@b.kz', birth_date: '1990-02-01' });
  fireEvent.press(screen.getByLabelText(`${ru.email}: a@b.kz`));
  fireEvent.changeText(sheetInput(screen, ru.email), '   ');
  mockRequest.mockResolvedValueOnce({ ...profile, birth_date: '1990-02-01' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { email: null } });
  await waitFor(() => expect(inputs(screen)).toBe(2));

  fireEvent.press(screen.getByLabelText(`${ru.birthDate}: 01.02.1990`));
  fireEvent.changeText(sheetInput(screen, ru.birthDate), '');
  mockRequest.mockResolvedValueOnce({ ...profile });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { birth_date: null } });
  screen.unmount();
});

it('an invalid email is rejected in the sheet and never sent', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.email));
  fireEvent.changeText(sheetInput(screen, ru.email), 'bad-email');
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(screen.getByText(ru.invalidEmail)).toBeTruthy();
  expect(patches()).toHaveLength(0);
  expect(inputs(screen)).toBe(3);
  screen.unmount();
});

it('birth date sheet applies mask and rejects date under 18 with birthDateUnder18', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.birthDate));
  // Mask formatting test:
  fireEvent.changeText(sheetInput(screen, ru.birthDate), '01012020');
  expect(sheetInput(screen, ru.birthDate).props.value).toBe('01.01.2020');

  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(screen.getByText(ru.birthDateUnder18)).toBeTruthy();
  expect(patches()).toHaveLength(0);

  // Invalid date 31.02:
  fireEvent.changeText(sheetInput(screen, ru.birthDate), '31021990');
  expect(sheetInput(screen, ru.birthDate).props.value).toBe('31.02.1990');
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(screen.getByText(ru.invalidDate)).toBeTruthy();
  expect(patches()).toHaveLength(0);

  screen.unmount();
});

it('first name auto-saves after 800ms debounce', async () => {
  jest.useFakeTimers();
  const screen = await open();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Айгерим' });

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  expect(patches()).toHaveLength(0);

  act(() => { jest.advanceTimersByTime(700); });
  expect(patches()).toHaveLength(0);

  await act(async () => { jest.advanceTimersByTime(200); });
  expect(patches()).toHaveLength(1);
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { first_name: 'Айгерим' } });

  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  jest.useRealTimers();
  screen.unmount();
});

it('first name auto-saves immediately on blur', async () => {
  const screen = await open();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Дамир' });

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Дамир');
  expect(patches()).toHaveLength(0);

  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(1);
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { first_name: 'Дамир' } });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('first name auto-saves immediately when leaving screen (focus effect cleanup)', async () => {
  const screen = await open();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Рустам' });

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Рустам');
  expect(patches()).toHaveLength(0);

  await act(async () => {
    if (mockFocusEffectCleanup) mockFocusEffectCleanup();
  });
  expect(patches()).toHaveLength(1);
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { first_name: 'Рустам' } });
  screen.unmount();
});

it('typing during in-flight PATCH does not overwrite new input and sends it in next request', async () => {
  const screen = await open();
  let resolveInFlight!: (val: Profile) => void;
  mockRequest.mockImplementationOnce(() => new Promise<Profile>(resolve => { resolveInFlight = resolve; }));

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Аня');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(1);
  expect(patches()[0]![1].body).toEqual({ first_name: 'Аня' });

  // Type new text while request is in flight
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна');

  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна' });
  await act(async () => {
    resolveInFlight({ ...profile, first_name: 'Аня' });
  });

  // Text on screen is preserved
  expect(value(screen, ru.firstName)).toBe('Анна');

  // Trigger save for new text
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(2);
  expect(patches()[1]![1].body).toEqual({ first_name: 'Анна' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('failed auto-save keeps typed text and shows ErrorNotice', async () => {
  const screen = await open();
  mockRequest.mockRejectedValueOnce(new ApiError('NETWORK_UNAVAILABLE'));

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });

  expect(value(screen, ru.firstName)).toBe('Айгерим');
  expect(screen.getByText(errorMessages.NETWORK_UNAVAILABLE!)).toBeTruthy();
  expect(screen.queryByText(ru.saved)).toBeNull();

  // Retry saves text
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Айгерим' });
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(2);
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('queued save during in-flight PATCH uses fresh profile from query and sends latest state', async () => {
  const screen = await open({ ...profile, first_name: 'A' });
  let resolveInFlight!: (val: Profile) => void;
  mockRequest.mockImplementationOnce(() => new Promise<Profile>(resolve => { resolveInFlight = resolve; }));

  // 1. User types 'AB' and triggers blur
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'AB');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(1);
  expect(patches()[0]![1].body).toEqual({ first_name: 'AB' });

  // 2. While request is in flight, user reverts name to 'A' and triggers blur (queued)
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'A');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });

  // 3. First request completes, returning AB as the current server profile
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'A' });
  await act(async () => {
    resolveInFlight({ ...profile, first_name: 'AB' });
  });

  // 4. Queued save must have compared 'A' with fresh server state 'AB' and sent PATCH with 'A'
  expect(patches()).toHaveLength(2);
  expect(patches()[1]![1].body).toEqual({ first_name: 'A' });
  screen.unmount();
});

it('auto-save does not eat trailing space and preserves typed space for next character', async () => {
  jest.useFakeTimers();
  const screen = await open();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна' });

  // User types 'Анна '
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна ');
  expect(patches()).toHaveLength(0);

  // 800ms debounce fires PATCH
  await act(async () => { jest.advanceTimersByTime(800); });
  expect(patches()).toHaveLength(1);
  expect(patches()[0]![1].body).toEqual({ first_name: 'Анна' });

  // Server returned 'Анна', but input on screen must preserve trailing space 'Анна '
  expect(value(screen, ru.firstName)).toBe('Анна ');

  // Next typed character gives 'Анна М'
  fireEvent.changeText(screen.getByLabelText(ru.firstName), `${value(screen, ru.firstName)}М`);
  expect(value(screen, ru.firstName)).toBe('Анна М');

  // Test no-extra-patch on blur when current.trim() matches server:
  const screen2 = await open({ ...profile, first_name: 'Анна' });
  fireEvent.changeText(screen2.getByLabelText(ru.firstName), 'Анна ');
  await act(async () => { fireEvent(screen2.getByLabelText(ru.firstName), 'blur'); });
  expect(patches()).toHaveLength(1); // no extra PATCH because 'Анна '.trim() === 'Анна'.trim()
  jest.useRealTimers();
  screen.unmount();
  screen2.unmount();
});

it('focus and blur without changes does not show saved and does not send PATCH', async () => {
  const screen = await open({ ...profile, first_name: 'Азамат' });
  fireEvent(screen.getByLabelText(ru.firstName), 'focus');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });

  expect(patches()).toHaveLength(0);
  expect(screen.queryByText(ru.saved)).toBeNull();
  screen.unmount();
});
