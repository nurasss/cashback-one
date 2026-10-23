import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ImageUploadField } from '../src/components/ImageUploadField';
import { LocaleProvider, LOCALE_STORAGE_KEY } from '../src/i18n/LocaleContext';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function TestHarness({
  initialUrl = '',
  purpose = 'promotion' as 'promotion' | 'logo',
  onUploadingChange,
}: {
  initialUrl?: string;
  purpose?: 'promotion' | 'logo';
  onUploadingChange?: (uploading: boolean) => void;
}) {
  const [url, setUrl] = useState(initialUrl);

  return (
    <LocaleProvider>
      <AdminProvider>
        <ImageUploadField
          id="test-image"
          value={url}
          onChange={setUrl}
          purpose={purpose}
          onUploadingChange={onUploadingChange}
        />
      </AdminProvider>
    </LocaleProvider>
  );
}

function setupFetchMock(
  handler?: (url: string, init?: RequestInit) => Response | Promise<Response>,
) {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/admin/auth/refresh')) {
      return json(200, {
        access_token: 'fixture-access',
        token_type: 'bearer',
        expires_in: 900,
      });
    }
    if (url.endsWith('/admin/me')) {
      return json(200, {
        admin: { id: 'admin-1', login: 'super', role: 'superadmin', business: null },
      });
    }
    if (handler) {
      return handler(url, init);
    }
    return json(404, { error: { code: 'NOT_FOUND' } });
  });

  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.localStorage.clear();
});

describe('ImageUploadField component', () => {
  it('renders initial empty state with upload button and URL input', async () => {
    setupFetchMock();
    render(<TestHarness />);

    const input = await screen.findByRole('textbox');
    expect(input).toHaveValue('');
    expect(screen.getByTestId('test-image-upload-button')).toHaveTextContent('Загрузить файл');
  });

  it('renders with existing URL, showing preview card and "Заменить файл"', async () => {
    setupFetchMock();
    const existingUrl = 'https://cashback-qr.poscenter.kz/media/promotions/existing123.webp';
    render(<TestHarness initialUrl={existingUrl} />);

    const input = await screen.findByRole('textbox');
    expect(input).toHaveValue(existingUrl);
    expect(screen.getByTestId('test-image-upload-button')).toHaveTextContent('Заменить файл');
    expect(screen.getByTestId('test-image-preview-card')).toBeInTheDocument();
  });

  it('rejects file larger than 10 MB on client side without network request', async () => {
    const fetchMock = setupFetchMock();
    render(<TestHarness />);

    const fileInput = await screen.findByTestId('test-image-file-input');
    // 11 MB dummy file
    const largeFile = new File(['a'.repeat(1024)], 'large.jpg', { type: 'image/jpeg' });
    Object.defineProperty(largeFile, 'size', { value: 11 * 1024 * 1024 });

    fireEvent.change(fileInput, { target: { files: [largeFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Файл превышает 10 МБ. Выберите файл меньшего размера.',
    );

    // Verify no upload network request was sent
    const uploadCalls = vi.mocked(fetchMock).mock.calls.filter(([url]) =>
      String(url).endsWith('/admin/media/images'),
    );
    expect(uploadCalls).toHaveLength(0);
  });

  it('rejects unsupported MIME types on client side without network request', async () => {
    const fetchMock = setupFetchMock();
    render(<TestHarness />);

    const fileInput = await screen.findByTestId('test-image-file-input');
    const pdfFile = new File(['%PDF-1.4'], 'document.pdf', { type: 'application/pdf' });

    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Поддерживаются только форматы JPEG, PNG, WebP и GIF.',
    );

    const uploadCalls = vi.mocked(fetchMock).mock.calls.filter(([url]) =>
      String(url).endsWith('/admin/media/images'),
    );
    expect(uploadCalls).toHaveLength(0);
  });

  it('performs successful upload and updates form state with preview and size info', async () => {
    const uploadingStates: boolean[] = [];
    const fetchMock = setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(200, {
          url: 'https://cashback-qr.poscenter.kz/media/promotions/abc12345def67890.webp',
          width: 1200,
          height: 600,
          bytes: 46080,
        });
      }
      return json(404, {});
    });

    render(<TestHarness onUploadingChange={u => uploadingStates.push(u)} />);

    const fileInput = await screen.findByTestId('test-image-file-input');
    const testFile = new File([new Uint8Array([0xff, 0xd8, 0xff])], 'banner.jpg', {
      type: 'image/jpeg',
    });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(
        screen.getByDisplayValue(
          'https://cashback-qr.poscenter.kz/media/promotions/abc12345def67890.webp',
        ),
      ).toBeInTheDocument();
    });

    // Check size label (46080 bytes = 45 KB) and dimensions
    expect(screen.getByText('1200 × 600 px · 45 КБ')).toBeInTheDocument();

    // Verify upload notified onUploadingChange: true -> false
    expect(uploadingStates).toEqual([true, false]);

    // Verify FormData was sent with purpose
    const uploadCall = vi
      .mocked(fetchMock)
      .mock.calls.find(([url]) => String(url).endsWith('/admin/media/images'));
    expect(uploadCall).toBeDefined();
    const body = uploadCall?.[1]?.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get('purpose')).toBe('promotion');
  });

  it('displays user-friendly error when server returns 413 FILE_TOO_LARGE', async () => {
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(413, {
          error: { code: 'FILE_TOO_LARGE', message: 'Payload too large.' },
        });
      }
      return json(404, {});
    });

    render(<TestHarness />);
    const fileInput = await screen.findByTestId('test-image-file-input');
    const testFile = new File(['data'], 'big.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Файл слишком большой. Максимальный размер — 10 МБ.',
    );
  });

  it('displays user-friendly error when server returns 415 UNSUPPORTED_MEDIA_TYPE', async () => {
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(415, {
          error: { code: 'UNSUPPORTED_MEDIA_TYPE', message: 'Unsupported format.' },
        });
      }
      return json(404, {});
    });

    render(<TestHarness />);
    const fileInput = await screen.findByTestId('test-image-file-input');
    const testFile = new File(['not an image'], 'corrupt.jpg', { type: 'image/jpeg' });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Неподдерживаемый формат изображения. Загрузите JPEG, PNG, WebP или GIF.',
    );
  });

  it('displays user-friendly error when storage fails (502 MEDIA_STORAGE_ERROR)', async () => {
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(502, {
          error: { code: 'MEDIA_STORAGE_ERROR', message: 'FTPS failure.' },
        });
      }
      return json(404, {});
    });

    render(<TestHarness />);
    const fileInput = await screen.findByTestId('test-image-file-input');
    const testFile = new File(['data'], 'img.jpg', { type: 'image/jpeg' });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Не удалось сохранить изображение в хранилище. Попробуйте позже.',
    );
  });

  it('displays user-friendly error when storage is unconfigured (503 MEDIA_STORAGE_NOT_CONFIGURED)', async () => {
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(503, {
          error: {
            code: 'MEDIA_STORAGE_NOT_CONFIGURED',
            message: 'FTPS not configured.',
          },
        });
      }
      return json(404, {});
    });

    render(<TestHarness />);
    const fileInput = await screen.findByTestId('test-image-file-input');
    const testFile = new File(['data'], 'img.jpg', { type: 'image/jpeg' });

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Хранилище медиафайлов ещё не настроено на сервере.',
    );
  });

  it('allows manual typing in text input and clearing value with clear button', async () => {
    const user = userEvent.setup();
    setupFetchMock();
    render(<TestHarness />);

    const input = await screen.findByRole('textbox');
    await user.type(input, 'https://example.com/logo.png');
    expect(input).toHaveValue('https://example.com/logo.png');

    // Preview card is visible
    expect(screen.getByTestId('test-image-preview-card')).toBeInTheDocument();

    // Click clear button
    const clearBtn = screen.getByRole('button', { name: 'Удалить изображение' });
    await user.click(clearBtn);

    expect(input).toHaveValue('');
    expect(screen.queryByTestId('test-image-preview-card')).not.toBeInTheDocument();
  });

  it('displays Kazakh localization when locale is kk', async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, 'kk');
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        return json(503, {
          error: { code: 'MEDIA_STORAGE_NOT_CONFIGURED', message: 'not configured' },
        });
      }
      return json(404, {});
    });

    render(<TestHarness />);

    // In KK, button is "Файлды жүктеу"
    expect(await screen.findByText('Файлды жүктеу')).toBeInTheDocument();

    // Trigger error
    const fileInput = screen.getByTestId('test-image-file-input');
    fireEvent.change(fileInput, {
      target: { files: [new File([''], 'test.png', { type: 'image/png' })] },
    });

    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Медиа файл қоймасы серверде әлі бапталмаған.',
    );
  });

  it('resets preview error state and shows preview again after a new upload', async () => {
    let uploadCount = 0;
    setupFetchMock((url, init) => {
      if (url.endsWith('/admin/media/images') && init?.method === 'POST') {
        uploadCount++;
        return json(200, {
          url: `https://cashback-qr.poscenter.kz/media/promotions/img_${uploadCount}.webp`,
          width: 800,
          height: 600,
          bytes: 32000,
        });
      }
      return json(404, {});
    });

    render(<TestHarness initialUrl="https://example.com/broken-image.jpg" />);

    // Initial image exists in preview
    let img = await screen.findByRole('img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('referrerPolicy', 'no-referrer');
    expect(img).toHaveAttribute('loading', 'lazy');

    // Simulate image error event
    fireEvent.error(img);

    // img should be removed on error
    expect(screen.queryByRole('img')).not.toBeInTheDocument();

    // Now upload a new valid image
    const fileInput = screen.getByTestId('test-image-file-input');
    const newFile = new File(['valid'], 'fresh.png', { type: 'image/png' });
    fireEvent.change(fileInput, { target: { files: [newFile] } });

    // After upload completes, preview image is visible again!
    img = await screen.findByRole('img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute(
      'src',
      'https://cashback-qr.poscenter.kz/media/promotions/img_1.webp',
    );
    expect(img).toHaveAttribute('referrerPolicy', 'no-referrer');
  });
});
