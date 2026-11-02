import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import { ActiveCardProvider } from '../src/features/activeCard';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import type { Profile } from '../src/types/api';

const mockRequest = jest.fn();

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

const defaultProfile: Profile = {
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

async function mountProfile(server: Profile = defaultProfile) {
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
  await waitFor(() => expect(screen.getByLabelText(new RegExp(`^${ru.city}`))).toBeTruthy());
  return screen;
}

describe('City custom input', () => {
  beforeEach(() => {
    mockRequest.mockClear();
  });

  it('saves standard city selected from list', async () => {
    const screen = await mountProfile();
    fireEvent.press(screen.getByLabelText(ru.city));

    mockRequest.mockResolvedValueOnce({ ...defaultProfile, city: ru.cityOption1 });
    await act(async () => {
      fireEvent.press(screen.getByRole('radio', { name: ru.cityOption1 }));
    });

    expect(mockRequest).toHaveBeenCalledWith('/me/profile', {
      method: 'PATCH',
      auth: true,
      body: { city: ru.cityOption1 },
    });
    screen.unmount();
  });

  it('opens custom text input when selecting "Другой город", shows error on short input, saves trimmed valid input with max length 100', async () => {
    const screen = await mountProfile();
    fireEvent.press(screen.getByLabelText(ru.city));

    // Select "Другой город"
    await act(async () => {
      fireEvent.press(screen.getByRole('radio', { name: ru.cityOption22 }));
    });

    // Sheet switches to custom input mode
    const textInput = screen.getByPlaceholderText(ru.cityCustomPh);
    expect(textInput).toBeTruthy();
    expect(textInput.props.maxLength).toBe(100);

    // Try submitting short text (< 2 chars)
    fireEvent.changeText(textInput, 'A');
    mockRequest.mockClear();
    await act(async () => {
      fireEvent.press(screen.getByText(ru.done));
    });

    expect(screen.getByText(ru.invalidCity)).toBeTruthy();
    expect(mockRequest).not.toHaveBeenCalled();

    // Enter valid city with spaces around
    fireEvent.changeText(textInput, '  Темиртау  ');
    mockRequest.mockResolvedValueOnce({ ...defaultProfile, city: 'Темиртау' });

    await act(async () => {
      fireEvent.press(screen.getByText(ru.done));
    });

    expect(mockRequest).toHaveBeenCalledWith('/me/profile', {
      method: 'PATCH',
      auth: true,
      body: { city: 'Темиртау' },
    });
    screen.unmount();
  });

  it('keeps input empty when user previously had "Алматы" and selects "Другой город"', async () => {
    const screen = await mountProfile({ ...defaultProfile, city: ru.cityOption1 });
    fireEvent.press(screen.getByLabelText(new RegExp(`^${ru.city}`)));

    await act(async () => {
      fireEvent.press(screen.getByRole('radio', { name: ru.cityOption22 }));
    });

    const textInput = screen.getByPlaceholderText(ru.cityCustomPh);
    expect(textInput.props.value).toBe('');
    screen.unmount();
  });

  it('marks "Другой город" selected when already saved, and tapping it opens empty field without triggering save', async () => {
    const screen = await mountProfile({ ...defaultProfile, city: ru.cityOption22 });
    fireEvent.press(screen.getByLabelText(new RegExp(`^${ru.city}`)));

    const option = screen.getByRole('radio', { name: ru.cityOption22 });
    expect(option.props.accessibilityState.selected).toBe(true);

    mockRequest.mockClear();
    await act(async () => {
      fireEvent.press(option);
    });

    expect(mockRequest).not.toHaveBeenCalled();
    const textInput = screen.getByPlaceholderText(ru.cityCustomPh);
    expect(textInput.props.value).toBe('');
    screen.unmount();
  });
});
