import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { AppState, Linking, Modal, Platform } from 'react-native';
import {
  fetchVersionInfo,
  getCurrentVersionCode,
  parseVersionInfo,
  updateDecision,
  VERSION_INFO_URL,
  type VersionInfo,
} from '../src/features/appUpdate';
import { UpdateNotice } from '../src/features/UpdateNotice';
import { I18nProvider } from '../src/i18n';
import { ru } from '../src/i18n/ru';

interface MockExpoGlobal {
  __mockExpoConfig?: { android?: { versionCode?: number } } | null;
}

const mockGlobal = globalThis as unknown as MockExpoGlobal;

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    get expoConfig() {
      const g = globalThis as unknown as MockExpoGlobal;
      return g.__mockExpoConfig !== undefined
        ? g.__mockExpoConfig
        : { android: { versionCode: 10 } };
    },
  },
}));

describe('parseVersionInfo', () => {
  const valid: VersionInfo = {
    latest_version: '1.0.10',
    latest_version_code: 11,
    min_version_code: 1,
    download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
  };

  it('parses valid version info', () => {
    expect(parseVersionInfo(valid)).toEqual(valid);
  });

  it('rejects HTML string', () => {
    expect(parseVersionInfo('<!DOCTYPE html><html><body>Error</body></html>')).toBeNull();
  });

  it('rejects null and undefined', () => {
    expect(parseVersionInfo(null)).toBeNull();
    expect(parseVersionInfo(undefined)).toBeNull();
  });

  it('rejects array', () => {
    expect(parseVersionInfo([valid])).toBeNull();
  });

  it('rejects missing fields', () => {
    expect(parseVersionInfo({ latest_version: '1.0.10' })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version: undefined })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version_code: undefined })).toBeNull();
    expect(parseVersionInfo({ ...valid, min_version_code: undefined })).toBeNull();
    expect(parseVersionInfo({ ...valid, download_url: undefined })).toBeNull();
  });

  it('rejects invalid version format', () => {
    expect(parseVersionInfo({ ...valid, latest_version: '1.0' })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version: 'v1.0.10' })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version: '1.0.10-beta' })).toBeNull();
  });

  it('rejects fractional and negative codes', () => {
    expect(parseVersionInfo({ ...valid, latest_version_code: 1.5 })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version_code: -1 })).toBeNull();
    expect(parseVersionInfo({ ...valid, latest_version_code: 0 })).toBeNull();
    expect(parseVersionInfo({ ...valid, min_version_code: 2.2 })).toBeNull();
    expect(parseVersionInfo({ ...valid, min_version_code: -5 })).toBeNull();
    expect(parseVersionInfo({ ...valid, min_version_code: 0 })).toBeNull();
  });

  it('rejects when min is greater than latest', () => {
    expect(parseVersionInfo({ ...valid, min_version_code: 12, latest_version_code: 11 })).toBeNull();
  });

  it('rejects http:// download URL', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'http://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
      }),
    ).toBeNull();
  });

  it('rejects other domain', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://evil.com/app/cashback-one-1.0.10.apk',
      }),
    ).toBeNull();
  });

  it('rejects evil domain subdomain attack', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz.evil.example/app/cashback-one-1.0.0.apk',
      }),
    ).toBeNull();
  });

  it('rejects URL with credentials / @ attack', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz@evil.example/app/cashback-one-1.0.0.apk',
      }),
    ).toBeNull();
  });

  it('rejects extra path in download URL', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz/app/sub/cashback-one-1.0.0.apk',
      }),
    ).toBeNull();
  });

  it('rejects different filename in download URL', () => {
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-two-1.0.0.apk',
      }),
    ).toBeNull();
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.0.apk.exe',
      }),
    ).toBeNull();
    expect(
      parseVersionInfo({
        ...valid,
        download_url: 'https://cashback-qr.poscenter.kz/app/other.apk',
      }),
    ).toBeNull();
  });
});

describe('updateDecision', () => {
  const info: VersionInfo = {
    latest_version: '1.0.10',
    latest_version_code: 10,
    min_version_code: 5,
    download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
  };

  it('returns none if info or currentCode is empty/invalid', () => {
    expect(updateDecision(null, 5)).toBe('none');
    expect(updateDecision(info, null)).toBe('none');
    expect(updateDecision(info, undefined)).toBe('none');
    expect(updateDecision(info, 0)).toBe('none');
    expect(updateDecision(info, -1)).toBe('none');
  });

  it('returns required when currentCode < min_version_code', () => {
    expect(updateDecision(info, 4)).toBe('required');
    expect(updateDecision(info, 1)).toBe('required');
  });

  it('returns optional when currentCode >= min_version_code and currentCode < latest_version_code', () => {
    expect(updateDecision(info, 5)).toBe('optional'); // boundary: equals min
    expect(updateDecision(info, 9)).toBe('optional');
  });

  it('returns none when currentCode >= latest_version_code', () => {
    expect(updateDecision(info, 10)).toBe('none'); // boundary: equals latest
    expect(updateDecision(info, 11)).toBe('none'); // above latest
  });

  it('handles case when min equals latest', () => {
    const strictInfo: VersionInfo = { ...info, min_version_code: 10, latest_version_code: 10 };
    expect(updateDecision(strictInfo, 9)).toBe('required');
    expect(updateDecision(strictInfo, 10)).toBe('none');
    expect(updateDecision(strictInfo, 11)).toBe('none');
  });
});

describe('fetchVersionInfo', () => {
  it('returns parsed info on valid response without authorization header', async () => {
    const raw = {
      latest_version: '1.0.10',
      latest_version_code: 11,
      min_version_code: 1,
      download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
    };
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => raw,
    });
    const result = await fetchVersionInfo(fetcher as never);
    expect(result).toEqual(raw);
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe(VERSION_INFO_URL);
    expect(options.headers).toEqual({ 'Cache-Control': 'no-cache' });
    expect(options.headers.Authorization).toBeUndefined();
  });

  it('returns null on 200 with HTML without throwing', async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON at position 0');
      },
    });
    const result = await fetchVersionInfo(fetcher as never);
    expect(result).toBeNull();
  });

  it('returns null on 500 without throwing', async () => {
    const fetcher = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'internal error' }),
    });
    const result = await fetchVersionInfo(fetcher as never);
    expect(result).toBeNull();
  });

  it('returns null on network error without throwing', async () => {
    const fetcher = jest.fn().mockRejectedValue(new Error('Network connection failed'));
    const result = await fetchVersionInfo(fetcher as never);
    expect(result).toBeNull();
  });

  it('returns null on timeout without throwing', async () => {
    const fetcher = jest.fn().mockRejectedValue(new DOMException('The user aborted a request.', 'AbortError'));
    const result = await fetchVersionInfo(fetcher as never);
    expect(result).toBeNull();
  });
});

function setExpoConfig(config: { android?: { versionCode?: number } } | null) {
  mockGlobal.__mockExpoConfig = config;
}

describe('getCurrentVersionCode', () => {
  afterEach(() => {
    setExpoConfig({ android: { versionCode: 10 } });
  });

  it('returns versionCode if positive integer', () => {
    setExpoConfig({ android: { versionCode: 10 } });
    expect(getCurrentVersionCode()).toBe(10);
  });

  it('returns null if not number or missing', () => {
    setExpoConfig({ android: { versionCode: undefined } });
    expect(getCurrentVersionCode()).toBeNull();

    setExpoConfig(null);
    expect(getCurrentVersionCode()).toBeNull();

    setExpoConfig({ android: { versionCode: -5 } });
    expect(getCurrentVersionCode()).toBeNull();

    setExpoConfig({ android: { versionCode: 2.5 } });
    expect(getCurrentVersionCode()).toBeNull();
  });
});

describe('UpdateNotice dialog flow and component', () => {
  const originalPlatform = Platform.OS;
  let emitAppState: (state: 'active' | 'background' | 'inactive') => void;
  let appStateSpy: jest.SpyInstance;

  beforeEach(() => {
    Platform.OS = 'android';
    setExpoConfig({ android: { versionCode: 10 } });
    const listeners: ((state: string) => void)[] = [];
    appStateSpy = jest.spyOn(AppState, 'addEventListener').mockImplementation((_, listener) => {
      listeners.push(listener as never);
      return {
        remove: () => {
          const index = listeners.indexOf(listener as never);
          if (index !== -1) listeners.splice(index, 1);
        },
      } as never;
    });
    emitAppState = (state) => {
      act(() => {
        for (const l of listeners) l(state);
      });
    };
  });

  afterEach(() => {
    Platform.OS = originalPlatform;
    setExpoConfig({ android: { versionCode: 10 } });
    appStateSpy.mockRestore();
    jest.restoreAllMocks();
  });

  it('shows nothing when there is no update', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.9',
        latest_version_code: 10,
        min_version_code: 1,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.9.apk',
      }),
    } as never);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).toHaveBeenCalled();
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
  });

  it('shows optional dialog with text and both buttons when update is optional', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.10',
        latest_version_code: 11,
        min_version_code: 1,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
      }),
    } as never);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    expect(screen.getByText(ru.updateBody)).toBeTruthy();
    expect(screen.getByText(ru.updateNow)).toBeTruthy();
    expect(screen.getByText(ru.updateLater)).toBeTruthy();
  });

  it('calls Linking.openURL with correct link and closes dialog on "Обновить" in optional mode', async () => {
    const downloadUrl = 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk';
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.10',
        latest_version_code: 11,
        min_version_code: 1,
        download_url: downloadUrl,
      }),
    } as never);

    const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    await act(async () => {
      fireEvent.press(screen.getByText(ru.updateNow));
    });

    expect(openUrlSpy).toHaveBeenCalledWith(downloadUrl);
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
  });

  it('handles "Позже", suppresses background check within 6h, refetches after 6h but keeps optional dismissed', async () => {
    let checkCount = 0;
    jest.spyOn(global, 'fetch').mockImplementation(async () => {
      checkCount++;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          latest_version: '1.0.10',
          latest_version_code: 11,
          min_version_code: 1,
          download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
        }),
      } as never;
    });

    const nowSpy = jest.spyOn(Date, 'now').mockReturnValue(1_000_000_000);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());
    expect(checkCount).toBe(1);

    // Click "Позже"
    act(() => {
      fireEvent.press(screen.getByText(ru.updateLater));
    });
    expect(screen.queryByText(ru.updateTitle)).toBeNull();

    // Return from background 1 hour later (< 6 hours)
    nowSpy.mockReturnValue(1_000_000_000 + 1 * 60 * 60 * 1000);
    emitAppState('active');
    expect(checkCount).toBe(1); // not called again
    expect(screen.queryByText(ru.updateTitle)).toBeNull();

    // Return from background 7 hours later (>= 6 hours)
    nowSpy.mockReturnValue(1_000_000_000 + 7 * 60 * 60 * 1000);
    emitAppState('active');
    await act(async () => {
      await Promise.resolve();
    });
    expect(checkCount).toBe(2); // refetched
    expect(screen.queryByText(ru.updateTitle)).toBeNull(); // remains dismissed because it is still optional
  });

  it('shows required dialog when return from background becomes required after previous "Позже"', async () => {
    let mode: 'optional' | 'required' = 'optional';
    jest.spyOn(global, 'fetch').mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          latest_version: '1.0.10',
          latest_version_code: 11,
          min_version_code: mode === 'optional' ? 1 : 11,
          download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
        }),
      } as never;
    });

    const nowSpy = jest.spyOn(Date, 'now').mockReturnValue(1_000_000_000);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    // Dismiss optional
    act(() => {
      fireEvent.press(screen.getByText(ru.updateLater));
    });
    expect(screen.queryByText(ru.updateTitle)).toBeNull();

    // Background transition after 6 hours with required update
    mode = 'required';
    nowSpy.mockReturnValue(1_000_000_000 + 7 * 60 * 60 * 1000);
    emitAppState('active');

    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());
    expect(screen.getByText(ru.updateRequiredBody)).toBeTruthy();
    expect(screen.getByText(ru.updateNow)).toBeTruthy();
    expect(screen.queryByText(ru.updateLater)).toBeNull(); // No "Позже" button in required mode
  });

  it('required mode: hardware back button does not close dialog, and dialog stays open on update press', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.10',
        latest_version_code: 11,
        min_version_code: 11, // current is 10 -> required
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
      }),
    } as never);

    const openUrlSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    // Hardware back button via Modal onRequestClose
    const modal = screen.UNSAFE_getByType(Modal);
    act(() => {
      modal.props.onRequestClose();
    });
    // Dialog must stay open!
    expect(screen.getByText(ru.updateTitle)).toBeTruthy();

    // Press "Обновить"
    await act(async () => {
      fireEvent.press(screen.getByText(ru.updateNow));
    });
    expect(openUrlSpy).toHaveBeenCalled();
    // In required mode, dialog still stays open!
    expect(screen.getByText(ru.updateTitle)).toBeTruthy();
  });

  it('optional mode: hardware back button closes dialog like "Позже"', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.10',
        latest_version_code: 11,
        min_version_code: 1,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
      }),
    } as never);

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    const modal = screen.UNSAFE_getByType(Modal);
    act(() => {
      modal.props.onRequestClose();
    });
    // Must close!
    expect(screen.queryByText(ru.updateTitle)).toBeNull();
  });

  it('openURL error does not crash app and dialog remains open', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        latest_version: '1.0.10',
        latest_version_code: 11,
        min_version_code: 1,
        download_url: 'https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk',
      }),
    } as never);

    jest.spyOn(Linking, 'openURL').mockRejectedValue(new Error('Cannot open URL'));

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await waitFor(() => expect(screen.getByText(ru.updateTitle)).toBeTruthy());

    await act(async () => {
      fireEvent.press(screen.getByText(ru.updateNow));
    });

    // Dialog stays open despite error
    expect(screen.getByText(ru.updateTitle)).toBeTruthy();
  });

  it('does not fetch on web platform', async () => {
    Platform.OS = 'web';
    const fetchSpy = jest.spyOn(global, 'fetch');

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.toJSON()).toBeNull();
  });

  it('does not fetch when demo is enabled', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');

    const screen = render(<I18nProvider initial="ru"><UpdateNotice demoEnabled /></I18nProvider>);
    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.toJSON()).toBeNull();
  });

  it('does not fetch when versionCode is missing / not configured', async () => {
    setExpoConfig(null);
    const fetchSpy = jest.spyOn(global, 'fetch');

    const screen = render(<I18nProvider initial="ru"><UpdateNotice /></I18nProvider>);
    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.toJSON()).toBeNull();
  });
});
