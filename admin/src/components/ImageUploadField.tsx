import { useRef, useState, type ChangeEvent } from 'react';
import { useAdminSession } from '../auth/provider';
import { useLocale } from '../i18n/LocaleContext';
import { adminErrorMessage, useAdminTranslation } from '../i18n/admin';
import type { ImageUploadResponse } from '../api/types';
import { IconUpload } from './Icons';

export interface ImageUploadFieldProps {
  id: string;
  value: string;
  onChange: (url: string) => void;
  purpose: 'promotion' | 'logo';
  onUploadingChange?: (uploading: boolean) => void;
  disabled?: boolean;
  placeholder?: string;
}

const MAX_CLIENT_BYTES = 10 * 1024 * 1024;
const ACCEPTED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);

export function ImageUploadField({
  id,
  value,
  onChange,
  purpose,
  onUploadingChange,
  disabled = false,
  placeholder,
}: ImageUploadFieldProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const [meta, setMeta] = useState<{ width: number; height: number; bytes: number } | null>(null);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Reset input value so re-selecting same file works
    event.target.value = '';
    if (!file) return;

    if (file.size > MAX_CLIENT_BYTES) {
      setError(t.imageUpload.clientTooLarge);
      return;
    }

    if (file.type && !ACCEPTED_MIME_TYPES.has(file.type.toLowerCase())) {
      setError(t.imageUpload.invalidType);
      return;
    }

    setError(null);
    setUploading(true);
    onUploadingChange?.(true);

    try {
      const formData = new FormData();
      formData.append('purpose', purpose);
      formData.append('file', file, file.name);

      const res = await session.api.request<ImageUploadResponse>('/admin/media/images', {
        method: 'POST',
        body: formData,
        timeoutMs: 60_000,
      });

      onChange(res.url);
      setPreviewError(false);
      setMeta({ width: res.width, height: res.height, bytes: res.bytes });
      setError(null);
    } catch (uploadError) {
      setError(adminErrorMessage(uploadError, locale));
    } finally {
      setUploading(false);
      onUploadingChange?.(false);
    }
  };

  const handleClear = () => {
    onChange('');
    setPreviewError(false);
    setMeta(null);
    setError(null);
  };

  const hasValue = Boolean(value && value.trim());

  return (
    <div className="image-upload-field">
      <div className="image-upload-controls">
        <input
          id={id}
          type="url"
          value={value}
          maxLength={1024}
          placeholder={placeholder ?? t.imageUpload.urlPlaceholder}
          onChange={e => {
            onChange(e.target.value);
            setPreviewError(false);
            setMeta(null);
            setError(null);
          }}
          disabled={disabled || uploading}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          data-testid={`${id}-file-input`}
        />
        <button
          type="button"
          className="button button-secondary image-upload-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          data-testid={`${id}-upload-button`}
        >
          <IconUpload />
          <span>{uploading ? t.imageUpload.uploading : hasValue ? t.imageUpload.change : t.imageUpload.button}</span>
        </button>
      </div>

      {hasValue && (
        <div className="image-upload-preview-card" data-testid={`${id}-preview-card`}>
          {!previewError && (
            <img
              key={value.trim()}
              src={value.trim()}
              alt={t.imageUpload.previewAlt}
              className="image-upload-thumb"
              referrerPolicy="no-referrer"
              loading="lazy"
              onError={() => setPreviewError(true)}
            />
          )}
          <div className="image-upload-info">
            <span className="image-upload-info-url" title={value}>{value}</span>
            {meta && (
              <span className="image-upload-info-meta">
                {t.imageUpload.dimensionsLabel(meta.width, meta.height)} · {t.imageUpload.sizeLabel(Math.round(meta.bytes / 1024))}
              </span>
            )}
          </div>
          <button
            type="button"
            className="image-upload-clear-btn"
            onClick={handleClear}
            disabled={disabled || uploading}
            title={t.imageUpload.remove}
            aria-label={t.imageUpload.remove}
          >
            ✕
          </button>
        </div>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
