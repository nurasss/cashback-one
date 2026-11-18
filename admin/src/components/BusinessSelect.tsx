import type { AllBusinessesResult } from '../api/queries';
import { messageForError } from '../api/errors';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

interface BusinessSelectProps {
  id?: string;
  ariaLabel?: string;
  value: string;
  onChange: (value: string) => void;
  allowAllLabel?: string;
  businesses: AllBusinessesResult;
}

export function BusinessSelect({
  id,
  ariaLabel,
  value,
  onChange,
  allowAllLabel,
  businesses,
}: BusinessSelectProps) {
  const { locale } = useLocale();
  const t = useAdminTranslation();

  const hasSelectedOption = !value || businesses.items.some(item => item.id === value);

  return (
    <div className="business-picker-wrap">
      <select
        id={id}
        aria-label={ariaLabel}
        value={value}
        onChange={event => onChange(event.target.value)}
      >
        {allowAllLabel !== undefined && <option value="">{allowAllLabel}</option>}
        {!hasSelectedOption && (
          <option value={value}>{t.content.selectedBusinessFallback}</option>
        )}
        {businesses.items.map(item => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>

      {businesses.isPending && (
        <span className="business-picker-status muted-copy" aria-live="polite">
          {t.mutations.agentLoadingBusinesses}
        </span>
      )}

      {!businesses.isPending && businesses.isLoadingMore && (
        <span className="business-picker-status muted-copy" aria-live="polite">
          {t.content.businessesLoadingMore(businesses.loadedCount)}
        </span>
      )}

      {businesses.isError && (
        <div className="business-picker-status business-picker-error" role="alert">
          <span>
            {businesses.loadedCount > 0
              ? t.content.businessesPartialError(businesses.loadedCount, messageForError(businesses.error, locale))
              : t.content.businessesLoadError(messageForError(businesses.error, locale))}
          </span>
          <button
            type="button"
            className="link-button"
            onClick={() => { void businesses.retry(); }}
          >
            {t.feedback.retry}
          </button>
        </div>
      )}
    </div>
  );
}
