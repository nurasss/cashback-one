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
jest.mock('../src/auth/provider', () => ({ useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }) }));
jest.mock('expo-router', () => ({ router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true } }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const profile: Profile = { phone: '+77058344326', language: 'ru', first_name: null, last_name: null, email: null, gender: null, city: null, address: null, birth_date: null, iin: null, company: null };
const patches = () => mockRequest.mock.calls.filter(call => call[1]?.method === 'PATCH');
const inputs = (screen: ReturnType<typeof render>) => screen.UNSAFE_getAllByType(TextInput).length;

async function open(server: Profile = profile) {
  mockRequest.mockImplementation((path: string) => path.startsWith('/me/profile') ? Promise.resolve(server) : Promise.reject(new Error(`unexpected ${path}`)));
  const query = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  const screen = render(<QueryClientProvider client={query}><I18nProvider><ActiveCardProvider><ProfileScreen /></ActiveCardProvider></I18nProvider></QueryClientProvider>);
  await waitFor(() => expect(screen.getByLabelText(ru.firstName)).toBeTruthy());
  return screen;
}
const sheetInput = (screen: ReturnType<typeof render>, label: string) => screen.getAllByLabelText(label).at(-1)!;
beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });

it('Done saves only the edited field with a PATCH, closes the sheet and shows the new value', async () => {
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

it('editing again clears the previous save error', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.company));
  fireEvent.changeText(sheetInput(screen, ru.company), 'ТОО');
  mockRequest.mockRejectedValueOnce(new ApiError('SERVER_UNAVAILABLE', 503));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(screen.getByText(errorMessages.SERVER_UNAVAILABLE!)).toBeTruthy();
  fireEvent.changeText(sheetInput(screen, ru.company), 'ТОО Ромашка');
  expect(screen.queryByText(errorMessages.SERVER_UNAVAILABLE!)).toBeNull();
  screen.unmount();
});

it('a double press sends one PATCH, shows the saving state and ignores closing until it finishes', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.company));
  fireEvent.changeText(sheetInput(screen, ru.company), 'ТОО Ромашка');
  let resolve!: (value: Profile) => void;
  mockRequest.mockImplementationOnce(() => new Promise<Profile>(done => { resolve = done; }));
  const done = screen.getByRole('button', { name: ru.done });
  await act(async () => { fireEvent.press(done); fireEvent.press(done); });
  expect(patches()).toHaveLength(1);
  expect(screen.getByRole('button', { name: ru.saving }).props.accessibilityState.disabled).toBe(true);
  await act(async () => { fireEvent.press(screen.getByLabelText(ru.cancel)); }); // backdrop is ignored while saving
  expect(inputs(screen)).toBe(3);
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.saving })); });
  expect(patches()).toHaveLength(1);
  await act(async () => { resolve({ ...profile, company: 'ТОО Ромашка' }); });
  await waitFor(() => expect(inputs(screen)).toBe(2));
  expect(patches()).toHaveLength(1);
  expect(screen.getByLabelText(`${ru.company}: ТОО Ромашка`)).toBeTruthy();
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

it('an invalid value is rejected in the sheet and never sent', async () => {
  const screen = await open();
  fireEvent.press(screen.getByLabelText(ru.iin));
  fireEvent.changeText(sheetInput(screen, ru.iin), '12345');
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(screen.getByText(ru.invalidIin)).toBeTruthy();
  expect(patches()).toHaveLength(0);
  expect(inputs(screen)).toBe(3);
  screen.unmount();
});

it('choosing a gender saves just the gender; a failure keeps the sheet and allows another try', async () => {
  const screen = await open();
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  fireEvent.press(screen.getByLabelText(ru.gender));
  mockRequest.mockRejectedValueOnce(new ApiError('REQUEST_TIMEOUT'));
  await act(async () => { fireEvent.press(screen.getByRole('radio', { name: ru.female })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { gender: 'female' } });
  expect(screen.getByText(errorMessages.REQUEST_TIMEOUT!)).toBeTruthy();
  expect(screen.getByRole('radio', { name: ru.male })).toBeTruthy(); // the options are still on screen

  mockRequest.mockResolvedValueOnce({ ...profile, gender: 'male' });
  await act(async () => { fireEvent.press(screen.getByRole('radio', { name: ru.male })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { gender: 'male' } });
  await waitFor(() => expect(screen.getByLabelText(`${ru.gender}: ${ru.male}`)).toBeTruthy());
  expect(screen.getByLabelText(ru.firstName).props.value).toBe('Айгерим');
  screen.unmount();
});

it('unsaved first and last names are neither sent with a sheet field nor lost, and the general button saves them afterwards', async () => {
  const screen = await open();
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  fireEvent.press(screen.getByLabelText(ru.email));
  fireEvent.changeText(sheetInput(screen, ru.email), 'a@b.kz');
  // the server answers with its own copy of the profile, which does not know the typed names yet
  mockRequest.mockResolvedValueOnce({ ...profile, email: 'a@b.kz' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { email: 'a@b.kz' } });
  await waitFor(() => expect(inputs(screen)).toBe(2));
  expect(screen.getByLabelText(ru.firstName).props.value).toBe('Айгерим');
  expect(screen.getByLabelText(ru.lastName).props.value).toBe('Ахметова');

  mockRequest.mockResolvedValueOnce({ ...profile, email: 'a@b.kz', first_name: 'Айгерим', last_name: 'Ахметова' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(mockRequest).toHaveBeenLastCalledWith('/me/profile', { method: 'PATCH', auth: true, body: { first_name: 'Айгерим', last_name: 'Ахметова' } });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  expect(screen.getByLabelText(`${ru.email}: a@b.kz`)).toBeTruthy();
  screen.unmount();
});

it('a failed sheet save does not touch the typed names, and the general save does not overwrite text typed meanwhile', async () => {
  const screen = await open();
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Айгерим');
  fireEvent.press(screen.getByLabelText(ru.company));
  fireEvent.changeText(sheetInput(screen, ru.company), 'ТОО');
  mockRequest.mockRejectedValueOnce(new ApiError('NETWORK_UNAVAILABLE'));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.done })); });
  fireEvent.press(screen.getByLabelText(ru.cancel));
  expect(screen.getByLabelText(ru.firstName).props.value).toBe('Айгерим');
  expect(patches()).toHaveLength(1);

  // general save in flight while the last name is typed: only the sent field is taken from the answer
  let resolve!: (value: Profile) => void;
  mockRequest.mockImplementationOnce(() => new Promise<Profile>(done => { resolve = done; }));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  await act(async () => { resolve({ ...profile, first_name: 'Айгерим' }); });
  await waitFor(() => expect(screen.getByRole('button', { name: ru.save })).toBeTruthy());
  expect(screen.getByLabelText(ru.lastName).props.value).toBe('Ахметова');
  expect(screen.queryByText(ru.saved)).toBeNull(); // the last name typed meanwhile is still unsaved, so no success message
  screen.unmount();
});

// --- General save with a deferred PATCH: the answer must not overwrite what was typed while the request was in flight. ---
type Pending = { resolve: (value: Profile) => void; reject: (error: unknown) => void };
async function saveInFlight(screen: ReturnType<typeof render>, typed: Record<string, string>): Promise<Pending> {
  for (const [label, value] of Object.entries(typed)) fireEvent.changeText(screen.getByLabelText(label), value);
  let pending!: Pending;
  mockRequest.mockImplementationOnce(() => new Promise<Profile>((resolve, reject) => { pending = { resolve, reject }; }));
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  return pending;
}
const value = (screen: ReturnType<typeof render>, label: string) => screen.getByLabelText(label).props.value;

it('typing in the same first name while it is being saved keeps the new text, hides "saved" and sends it next', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.firstName]: 'Аня' });
  expect(patches()[0]![1].body).toEqual({ first_name: 'Аня' });
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна');
  await act(async () => { pending.resolve({ ...profile, first_name: 'Аня' }); });
  await waitFor(() => expect(screen.getByRole('button', { name: ru.save })).toBeTruthy());
  expect(value(screen, ru.firstName)).toBe('Анна');
  expect(screen.queryByText(ru.saved)).toBeNull();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(patches()).toHaveLength(2);
  expect(patches()[1]![1].body).toEqual({ first_name: 'Анна' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  expect(value(screen, ru.firstName)).toBe('Анна');
  screen.unmount();
});

it('typing in the same last name while it is being saved keeps the new text and sends it next', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.lastName]: 'Ахметов' });
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  await act(async () => { pending.resolve({ ...profile, last_name: 'Ахметов' }); });
  await waitFor(() => expect(screen.getByRole('button', { name: ru.save })).toBeTruthy());
  expect(value(screen, ru.lastName)).toBe('Ахметова');
  expect(screen.queryByText(ru.saved)).toBeNull();
  mockRequest.mockResolvedValueOnce({ ...profile, last_name: 'Ахметова' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(patches()[1]![1].body).toEqual({ last_name: 'Ахметова' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('typing in both names while saving keeps both and the next save sends both', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.firstName]: 'Аня', [ru.lastName]: 'Ахметов' });
  expect(patches()[0]![1].body).toEqual({ first_name: 'Аня', last_name: 'Ахметов' });
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна');
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  await act(async () => { pending.resolve({ ...profile, first_name: 'Аня', last_name: 'Ахметов' }); });
  await waitFor(() => expect(screen.getByRole('button', { name: ru.save })).toBeTruthy());
  expect([value(screen, ru.firstName), value(screen, ru.lastName)]).toEqual(['Анна', 'Ахметова']);
  expect(screen.queryByText(ru.saved)).toBeNull();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна', last_name: 'Ахметова' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(patches()[1]![1].body).toEqual({ first_name: 'Анна', last_name: 'Ахметова' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('typing in another field while saving keeps it, hides "saved" and sends only that field next', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.firstName]: 'Аня' });
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  await act(async () => { pending.resolve({ ...profile, first_name: 'Аня' }); });
  await waitFor(() => expect(screen.getByRole('button', { name: ru.save })).toBeTruthy());
  expect([value(screen, ru.firstName), value(screen, ru.lastName)]).toEqual(['Аня', 'Ахметова']);
  expect(screen.queryByText(ru.saved)).toBeNull();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Аня', last_name: 'Ахметова' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(patches()[1]![1].body).toEqual({ last_name: 'Ахметова' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});

it('untouched fields take the server normalization and "saved" is shown', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.firstName]: '  Аня ', [ru.lastName]: 'Ахметова' });
  expect(patches()[0]![1].body).toEqual({ first_name: 'Аня', last_name: 'Ахметова' });
  await act(async () => { pending.resolve({ ...profile, first_name: 'Аня', last_name: 'АХМЕТОВА' }); });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  expect([value(screen, ru.firstName), value(screen, ru.lastName)]).toEqual(['Аня', 'АХМЕТОВА']);
  expect(patches()).toHaveLength(1);
  screen.unmount();
});

it('a failed save keeps what was typed before and during the request, shows no "saved" and the next save sends it', async () => {
  const screen = await open();
  const pending = await saveInFlight(screen, { [ru.firstName]: 'Аня' });
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна');
  fireEvent.changeText(screen.getByLabelText(ru.lastName), 'Ахметова');
  await act(async () => { pending.reject(new ApiError('NETWORK_UNAVAILABLE')); });
  await waitFor(() => expect(screen.getByText(errorMessages.NETWORK_UNAVAILABLE!)).toBeTruthy());
  expect([value(screen, ru.firstName), value(screen, ru.lastName)]).toEqual(['Анна', 'Ахметова']);
  expect(screen.queryByText(ru.saved)).toBeNull();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна', last_name: 'Ахметова' });
  await act(async () => { fireEvent.press(screen.getByRole('button', { name: ru.save })); });
  expect(patches()[1]![1].body).toEqual({ first_name: 'Анна', last_name: 'Ахметова' });
  await waitFor(() => expect(screen.getByText(ru.saved)).toBeTruthy());
  screen.unmount();
});
