import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import * as ImagePicker from 'expo-image-picker';
import { manipulateAsync } from 'expo-image-manipulator';
import { Alert, Image } from 'react-native';
import ProfileScreen from '../app/(app)/(tabs)/profile';
import { ApiError } from '../src/api/errors';
import { ActiveCardProvider } from '../src/features/activeCard';
import { Avatar } from '../src/features/profile';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import type { Profile } from '../src/types/api';

const mockRequest = jest.fn();

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: mockRequest }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));

jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useFocusEffect: (cb: () => void | (() => void)) => {
    const React = jest.requireActual<typeof import('react')>('react');
    React.useEffect(() => {
      const cleanup = cb();
      return () => {
        if (typeof cleanup === 'function') cleanup();
      };
    }, [cb]);
  },
}));

jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(),
}));

jest.mock('expo-image-manipulator', () => ({
  manipulateAsync: jest.fn((uri: string) =>
    Promise.resolve({ uri: `${uri}-manipulated.jpg`, width: 512, height: 512 })
  ),
  SaveFormat: { JPEG: 'jpeg', PNG: 'png', WEBP: 'webp' },
}));

const testProfile: Profile = {
  phone: '+77019998877',
  language: 'ru',
  first_name: 'Азамат',
  last_name: 'Бек',
  email: null,
  gender: null,
  city: null,
  address: null,
  birth_date: null,
  iin: null,
  company: null,
  avatar_url: null,
};

async function openScreen(server: Profile = testProfile) {
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

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
});

it('Avatar shows initials when no avatar_url is provided', () => {
  const screen = render(
    <I18nProvider>
      <Avatar initials="АБ" avatarUrl={null} />
    </I18nProvider>
  );
  expect(screen.getByText('АБ')).toBeTruthy();
  expect(screen.UNSAFE_queryByType(Image)).toBeNull();
});

it('Avatar shows Image when avatar_url is provided and hides initials', () => {
  const screen = render(
    <I18nProvider>
      <Avatar initials="АБ" avatarUrl="https://cdn.example.kz/avatars/test.webp" />
    </I18nProvider>
  );
  const img = screen.UNSAFE_getByType(Image);
  expect(img.props.source).toEqual({ uri: 'https://cdn.example.kz/avatars/test.webp' });
  expect(screen.queryByText('АБ')).toBeNull();
});

it('Avatar falls back to initials if Image fires onError', () => {
  const screen = render(
    <I18nProvider>
      <Avatar initials="АБ" avatarUrl="https://cdn.example.kz/avatars/corrupt.webp" />
    </I18nProvider>
  );
  const img = screen.UNSAFE_getByType(Image);
  fireEvent(img, 'error');
  expect(screen.getByText('АБ')).toBeTruthy();
  expect(screen.UNSAFE_queryByType(Image)).toBeNull();
});

it('clicking Avatar when no photo exists directly launches image picker without Alert', async () => {
  const screen = await openScreen({ ...testProfile, avatar_url: null });
  const alertSpy = jest.spyOn(Alert, 'alert');

  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({ canceled: true });

  const avatarBtn = screen.getByLabelText(ru.avatarChange);
  await act(async () => {
    fireEvent.press(avatarBtn);
  });

  expect(alertSpy).not.toHaveBeenCalled();
  expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith({
    mediaTypes: ['images'],
    allowsEditing: true,
    aspect: [1, 1],
  });
  screen.unmount();
});

it('canceling photo selection sends no request and changes nothing', async () => {
  const screen = await openScreen({ ...testProfile, avatar_url: null });
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({ canceled: true, assets: null });

  await act(async () => {
    fireEvent.press(screen.getByLabelText(ru.avatarChange));
  });

  expect(mockRequest).not.toHaveBeenCalledWith(expect.stringContaining('/me/avatar'), expect.anything());
  screen.unmount();
});

it('successful image selection manipulates to 512x512 JPEG, sends FormData with auth token, and updates profile', async () => {
  const screen = await openScreen({ ...testProfile, avatar_url: null });
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({
    canceled: false,
    assets: [{ uri: 'file:///local/cache/photo.png', width: 1200, height: 1200 }],
  });

  const newAvatarUrl = 'https://cashback-qr.poscenter.kz/media/avatars/new123.webp';
  mockRequest.mockResolvedValueOnce({ ...testProfile, avatar_url: newAvatarUrl });

  await act(async () => {
    fireEvent.press(screen.getByLabelText(ru.avatarChange));
  });

  // Verify manipulation: resize to width 512, compress 0.8, format JPEG
  expect(manipulateAsync).toHaveBeenCalledWith(
    'file:///local/cache/photo.png',
    [{ resize: { width: 512 } }],
    { compress: 0.8, format: 'jpeg' }
  );

  // Verify upload request
  const uploadCall = mockRequest.mock.calls.find(call => call[0] === '/me/avatar' && call[1]?.method === 'POST');
  expect(uploadCall).toBeTruthy();
  expect(uploadCall[1].auth).toBe(true);
  expect(uploadCall[1].body).toBeInstanceOf(FormData);

  // Verify avatar updated on screen
  await waitFor(() => {
    const img = screen.UNSAFE_getByType(Image);
    expect(img.props.source).toEqual({ uri: newAvatarUrl });
  });
  screen.unmount();
});

it('failed upload leaves previous photo intact and displays error notice', async () => {
  const oldUrl = 'https://cashback-qr.poscenter.kz/media/avatars/old.webp';
  const screen = await openScreen({ ...testProfile, avatar_url: oldUrl });

  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValueOnce({
    canceled: false,
    assets: [{ uri: 'file:///local/large.jpg' }],
  });
  mockRequest.mockRejectedValueOnce(new ApiError('FILE_TOO_LARGE', 413));

  await act(async () => {
    // With photo present, press triggers Alert
    fireEvent.press(screen.getByLabelText(ru.avatarChange));
  });

  // Old photo is still displayed
  expect(screen.UNSAFE_getByType(Image).props.source).toEqual({ uri: oldUrl });
  screen.unmount();
});

it('clicking Avatar when photo exists shows Alert with Change and Delete options, and Delete clears avatar', async () => {
  const currentUrl = 'https://cashback-qr.poscenter.kz/media/avatars/current.webp';
  const screen = await openScreen({ ...testProfile, avatar_url: currentUrl });
  const alertSpy = jest.spyOn(Alert, 'alert');

  await act(async () => {
    fireEvent.press(screen.getByLabelText(ru.avatarChange));
  });

  expect(alertSpy).toHaveBeenCalledWith(
    ru.avatarChange,
    undefined,
    expect.arrayContaining([
      expect.objectContaining({ text: ru.avatarChange }),
      expect.objectContaining({ text: ru.avatarDelete }),
      expect.objectContaining({ text: ru.cancel }),
    ])
  );

  // Trigger Delete button callback from Alert
  const buttons = alertSpy.mock.calls[0]![2]!;
  const deleteBtn = buttons.find(b => b.text === ru.avatarDelete);
  expect(deleteBtn).toBeTruthy();

  mockRequest.mockResolvedValueOnce({ ...testProfile, avatar_url: null });
  await act(async () => {
    deleteBtn!.onPress!();
  });

  // DELETE request sent
  expect(mockRequest).toHaveBeenCalledWith('/me/avatar', { method: 'DELETE', auth: true });

  // Initials returned, Image gone
  await waitFor(() => {
    expect(screen.getByText('АБ')).toBeTruthy();
    expect(screen.UNSAFE_queryByType(Image)).toBeNull();
  });
  screen.unmount();
});
