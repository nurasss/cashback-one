import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinesses } from '../api/queries';
import type {
  AgentKeyDisclosure,
  BusinessCreatedResponse,
  BusinessDetail,
  BusinessLegacyTier,
  ManagerAccessDisclosure,
} from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { ImageUploadField } from '../components/ImageUploadField';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function DialogFrame({ title, onClose, children, className }: {
  title: string; onClose: () => void; children: ReactNode; className?: string;
}) {
  const t = useAdminTranslation();
  const dialogRef = useRef<HTMLElement>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    restoreFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreFocus.current?.focus();
  }, []);
  const closeOnEscape = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') { event.preventDefault(); onClose(); }
    if (event.key === 'Tab') {
      const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]'
      );
      if (!controls?.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  };
  return <div className="mutation-backdrop">
    <section ref={dialogRef} tabIndex={-1} className={`mutation-dialog ${className ?? ''}`.trim()} role="dialog" aria-modal="true" aria-labelledby="mutation-title" onKeyDown={closeOnEscape}>
      <header className="mutation-heading">
        <h2 id="mutation-title">{title}</h2>
        <button
          className="mutation-dialog-close-btn"
          type="button"
          onClick={onClose}
          aria-label={t.mutations.closeDialog}
          title={t.mutations.close}
        >
          <span aria-hidden="true">✕</span>
          <span className="sr-only">{t.mutations.close}</span>
        </button>
      </header>
      {children}
    </section>
  </div>;
}

function isTier(value: unknown): value is BusinessLegacyTier {
  if (typeof value !== 'object' || value === null) return false;
  const tier = value as Record<string, unknown>;
  const decimal = (v: unknown) => (typeof v === 'string' || typeof v === 'number') && /^\d+(\.\d+)?$/.test(String(v));
  return Number.isInteger(tier.level) && decimal(tier.threshold) && decimal(tier.percent)
    && (tier.name === undefined || tier.name === null || typeof tier.name === 'string');
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toHexSwatch(value: string, fallback: string): string {
  const trimmed = value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    const [, r, g, b] = trimmed.toLowerCase();
    return `#${r}${r}${g}${g}${b}${b}`;
  }
  return fallback;
}

function formatLegacyTiersJson(tiers: BusinessLegacyTier[] | null): string {
  return JSON.stringify(tiers, null, 2);
}

type BusinessFormErrorField = 'name' | 'logo' | 'androidAppId' | 'prefixes' | 'colors' | 'tiers' | 'form';
interface BusinessFormError {
  field: BusinessFormErrorField;
  message: string;
}

export function BusinessEditorDialog({ business, onClose, onSaved }: {
  business?: BusinessDetail; onClose: () => void; onSaved: (managerAccess?: ManagerAccessDisclosure | null) => void;
}) {
  const { session } = useAdminSession();
  const { activeBusiness, setActiveBusiness } = useActiveBusiness();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState(business?.name ?? '');
  const [logoUrl, setLogoUrl] = useState(business?.logo_url ?? '');
  const [colorsObj, setColorsObj] = useState<Record<string, unknown> | null>(
    isPlainRecord(business?.colors) ? business.colors : null
  );
  const [colorsText, setColorsText] = useState(JSON.stringify(business?.colors ?? null, null, 2));
  const [prefixesList, setPrefixesList] = useState<string[] | null>(
    business ? (Array.isArray(business.barcode_prefixes) ? business.barcode_prefixes : null) : []
  );
  const [prefixDraft, setPrefixDraft] = useState('');
  const [prefixDraftError, setPrefixDraftError] = useState('');
  const [prefixesText, setPrefixesText] = useState(JSON.stringify(business?.barcode_prefixes ?? [], null, 2));
  const [androidAppId, setAndroidAppId] = useState(business?.android_app_id ?? '');
  const [status, setStatus] = useState<'active' | 'inactive'>(business?.status === 'inactive' ? 'inactive' : 'active');
  const [tiersList, setTiersList] = useState<BusinessLegacyTier[] | null>(
    Array.isArray(business?.loyalty_tiers) && business.loyalty_tiers.length > 0 ? business.loyalty_tiers : null
  );
  const [tiersText, setTiersText] = useState(formatLegacyTiersJson(business?.loyalty_tiers ?? null));
  const [formError, setFormError] = useState<BusinessFormError | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);

  useEffect(() => {
    if (!formError) return;
    const alertEl = formRef.current?.querySelector<HTMLElement>('[role="alert"]');
    if (typeof alertEl?.scrollIntoView === 'function') {
      alertEl.scrollIntoView({ block: 'center' });
    }
  }, [formError]);

  const clearFieldError = (field: BusinessFormErrorField) => {
    setFormError(current => (current?.field === field ? null : current));
  };

  const applyPrefixes = (next: string[] | null) => {
    setPrefixesList(next);
    setPrefixesText(JSON.stringify(next, null, 2));
    clearFieldError('prefixes');
    setPrefixDraftError('');
  };

  const handleAddPrefix = () => {
    const cleaned = prefixDraft.trim();
    if (!cleaned || cleaned.length > 32) {
      setPrefixDraftError(t.mutations.prefixErrEmpty);
      return;
    }
    const current = prefixesList ?? [];
    if (current.includes(cleaned)) {
      setPrefixDraftError(t.mutations.prefixErrDuplicate);
      return;
    }
    if (current.length >= 64) {
      setPrefixDraftError(t.mutations.prefixErrLimit);
      return;
    }
    applyPrefixes([...current, cleaned]);
    setPrefixDraft('');
  };

  const handleRemovePrefix = (prefixToRemove: string) => {
    if (!prefixesList) return;
    applyPrefixes(prefixesList.filter(item => item !== prefixToRemove));
  };

  const handleRawPrefixesChange = (raw: string) => {
    setPrefixesText(raw);
    clearFieldError('prefixes');
    try {
      const parsed: unknown = JSON.parse(raw || '[]');
      if (parsed === null) setPrefixesList(null);
      else if (Array.isArray(parsed) && parsed.every(value => typeof value === 'string')) {
        setPrefixesList(parsed);
      }
    } catch {
      // Keep user typing freely; submit validates JSON
    }
  };

  const applyColors = (next: Record<string, unknown> | null) => {
    const cleaned = next && Object.keys(next).length > 0 ? next : null;
    setColorsObj(cleaned);
    setColorsText(JSON.stringify(cleaned, null, 2));
    clearFieldError('colors');
  };

  const handleColorKeyChange = (key: 'primary' | 'accent', nextValue: string) => {
    const next: Record<string, unknown> = { ...(colorsObj ?? {}) };
    if (nextValue === '') delete next[key];
    else next[key] = nextValue;
    applyColors(next);
  };

  const handleRemoveExtraColorKey = (keyToRemove: string) => {
    if (!colorsObj) return;
    const next = { ...colorsObj };
    delete next[keyToRemove];
    applyColors(next);
  };

  const handleRawColorsChange = (raw: string) => {
    setColorsText(raw);
    clearFieldError('colors');
    try {
      const parsed: unknown = JSON.parse(raw || 'null');
      if (parsed === null || isPlainRecord(parsed)) {
        setColorsObj(parsed);
      }
    } catch {
      // Keep user typing freely; submit validates JSON
    }
  };

  const applyTiers = (next: BusinessLegacyTier[] | null) => {
    const normalized = next && next.length > 0 ? next : null;
    setTiersList(normalized);
    setTiersText(formatLegacyTiersJson(normalized));
    clearFieldError('tiers');
  };

  const handleAddLegacyTier = () => {
    const current = tiersList ?? [];
    if (current.length >= 10) return;
    const maxLevel = current.reduce((max, item) => Math.max(max, Number(item.level) || 0), 0);
    const nextThreshold = current.length === 0 ? '0' : '';
    applyTiers([...current, { level: maxLevel + 1, name: '', threshold: nextThreshold, percent: '0' }]);
  };

  const handleLegacyTierChange = (index: number, field: keyof BusinessLegacyTier, value: string) => {
    if (!tiersList) return;
    const next = tiersList.map((tier, idx) => {
      if (idx !== index) return tier;
      if (field === 'level') {
        const parsedLevel = Number.parseInt(value, 10);
        return { ...tier, level: Number.isFinite(parsedLevel) ? parsedLevel : tier.level };
      }
      if (field === 'name') {
        return { ...tier, name: value };
      }
      return { ...tier, [field]: value };
    });
    applyTiers(next);
  };

  const handleRemoveLegacyTier = (index: number) => {
    if (!tiersList) return;
    const remaining = tiersList.filter((_, idx) => idx !== index);
    applyTiers(remaining.length > 0 ? remaining : null);
  };

  const handleRawTiersChange = (raw: string) => {
    setTiersText(raw);
    clearFieldError('tiers');
    try {
      const parsed: unknown = JSON.parse(raw || 'null');
      if (parsed === null) setTiersList(null);
      else if (Array.isArray(parsed) && parsed.every(isTier)) setTiersList(parsed);
    } catch {
      // Keep user typing freely; submit validates JSON
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    const trimmedName = name.trim();
    if (!trimmedName || trimmedName.length > 255) {
      setFormError({ field: 'name', message: t.mutations.errBusinessName });
      return;
    }
    let normalizedLogo: string | null = null;
    if (logoUrl.trim()) {
      try {
        const parsed = new URL(logoUrl.trim());
        if (parsed.protocol !== 'https:' || !parsed.hostname || parsed.username || parsed.password || parsed.href.length > 1024) {
          throw new Error('invalid');
        }
        normalizedLogo = parsed.href;
      } catch {
        setFormError({ field: 'logo', message: t.mutations.errBusinessLogo });
        return;
      }
    }

    const trimmedAppId = androidAppId.trim();
    if (trimmedAppId) {
      const appIdRegex = /^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$/;
      if (!appIdRegex.test(trimmedAppId) || trimmedAppId.length > 255) {
        setFormError({ field: 'androidAppId', message: t.mutations.errBusinessAndroidAppId });
        return;
      }
    }

    let barcodePrefixes: string[] | null;
    try {
      const parsed: unknown = JSON.parse(prefixesText || '[]');
      if (parsed === null) barcodePrefixes = null;
      else if (Array.isArray(parsed) && parsed.every(value => typeof value === 'string')) {
        barcodePrefixes = parsed as string[];
        if (barcodePrefixes.length > 64 || barcodePrefixes.some(value => !value || value.trim() !== value || value.length > 32)) {
          throw new Error('invalid');
        }
      } else throw new Error('invalid');
    } catch {
      setFormError({ field: 'prefixes', message: t.mutations.errBusinessPrefixes });
      return;
    }

    let colors: Record<string, unknown> | null;
    try {
      const parsed: unknown = JSON.parse(colorsText || 'null');
      if (parsed === null) colors = null;
      else if (isPlainRecord(parsed)) colors = parsed;
      else throw new Error('invalid');
      if (new TextEncoder().encode(JSON.stringify(colors)).length > 8192) throw new Error('large');
    } catch {
      setFormError({ field: 'colors', message: t.mutations.errBusinessColors });
      return;
    }

    let loyaltyTiers: BusinessLegacyTier[] | null;
    try {
      const parsed: unknown = JSON.parse(tiersText || 'null');
      if (parsed === null) loyaltyTiers = null;
      else if (Array.isArray(parsed) && parsed.length > 0 && parsed.length <= 10) {
        const missingThreshold = parsed.some(
          item => typeof item === 'object' && item !== null && String((item as Record<string, unknown>).threshold ?? '').trim() === ''
        );
        if (missingThreshold) {
          setFormError({ field: 'tiers', message: t.mutations.errBusinessTierThreshold });
          return;
        }
        if (!parsed.every(isTier)) throw new Error('invalid');
        loyaltyTiers = parsed;
      } else throw new Error('invalid');
    } catch {
      setFormError({ field: 'tiers', message: t.mutations.errBusinessTiers });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: trimmedName,
        logo_url: normalizedLogo,
        colors,
        barcode_prefixes: barcodePrefixes,
        android_app_id: trimmedAppId || null,
        status,
        ...(business ? { loyalty_tiers: loyaltyTiers } : {}),
      };
      if (business) {
        const saved = await session.api.request<BusinessDetail>(`/admin/businesses/${encodeURIComponent(business.id)}`, {
          method: 'PATCH', body: payload,
        });
        session.syncBusiness?.(saved);
        if (activeBusiness?.id === saved.id) {
          setActiveBusiness({
            id: saved.id,
            name: saved.name,
            logo_url: saved.logo_url,
            android_app_id: saved.android_app_id,
          });
        }
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'business', business.id] });
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'businesses'] });
        onSaved();
      } else {
        const created = await session.api.request<BusinessCreatedResponse>('/admin/businesses', { method: 'POST', body: payload });
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'businesses'] });
        onSaved(created.manager_access);
      }
    } catch (mutationError) {
      setFormError({ field: 'form', message: messageForError(mutationError, locale) });
    } finally {
      setSaving(false);
    }
  };

  const primaryColor = typeof colorsObj?.primary === 'string' ? colorsObj.primary : '';
  const accentColor = typeof colorsObj?.accent === 'string' ? colorsObj.accent : '';
  const extraColorEntries = colorsObj
    ? Object.entries(colorsObj).filter(([key]) => key !== 'primary' && key !== 'accent')
    : [];

  return <DialogFrame title={business ? t.mutations.businessEditTitle : t.mutations.businessCreateTitle} onClose={onClose} className="mutation-dialog--wide business-editor-dialog">
    <form ref={formRef} className="mutation-form" onSubmit={event => { void submit(event); }}>
      <fieldset className="business-editor-fieldset">
        <legend>{t.mutations.sectionMain}</legend>
        <div className="mutation-form-row--two-col">
          <div className="form-control">
            <label htmlFor="business-name">{t.mutations.businessName}</label>
            <input
              id="business-name"
              value={name}
              maxLength={255}
              onChange={event => { setName(event.target.value); clearFieldError('name'); }}
              autoFocus
              required
            />
          </div>
          <div className="form-control">
            <label htmlFor="business-status">{t.mutations.businessStatus}</label>
            <select id="business-status" value={status} onChange={event => setStatus(event.target.value as 'active' | 'inactive')}>
              <option value="active">{t.mutations.statusActive}</option>
              <option value="inactive">{t.mutations.statusInactive}</option>
            </select>
          </div>
        </div>
        {formError?.field === 'name' && <p className="form-error" role="alert">{formError.message}</p>}

        <div className="form-control">
          <label htmlFor="business-logo">{t.mutations.businessLogo}</label>
          <ImageUploadField
            id="business-logo"
            value={logoUrl}
            onChange={nextLogo => { setLogoUrl(nextLogo); clearFieldError('logo'); }}
            purpose="logo"
            hint={t.mutations.businessLogoHint}
            onUploadingChange={setUploadingLogo}
            disabled={saving}
          />
        </div>
        {formError?.field === 'logo' && <p className="form-error" role="alert">{formError.message}</p>}

        <div className="form-control">
          <label htmlFor="business-android-app-id">{t.mutations.businessAndroidAppId}</label>
          <input
            id="business-android-app-id"
            value={androidAppId}
            maxLength={255}
            placeholder="kz.cashbackone.keremet"
            onChange={event => { setAndroidAppId(event.target.value); clearFieldError('androidAppId'); }}
            disabled={saving}
          />
          <small className="field-hint">{t.mutations.businessAndroidAppIdHint}</small>
        </div>
        {formError?.field === 'androidAppId' && <p className="form-error" role="alert">{formError.message}</p>}
      </fieldset>

      <fieldset className="business-editor-fieldset">
        <legend>{t.mutations.sectionPrefixes}</legend>
        <div className="form-control">
          <label htmlFor="business-prefix-draft">{t.mutations.prefixInputLabel}</label>
          <div className="business-prefix-add-row">
            <input
              id="business-prefix-draft"
              type="text"
              value={prefixDraft}
              maxLength={32}
              placeholder={t.mutations.prefixInputPlaceholder}
              onChange={event => { setPrefixDraft(event.target.value); setPrefixDraftError(''); }}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  handleAddPrefix();
                }
              }}
              disabled={saving}
            />
            <button type="button" className="button button-secondary" onClick={handleAddPrefix} disabled={saving}>
              {t.mutations.prefixAddBtn}
            </button>
            {prefixesList && prefixesList.length > 0 && (
              <button type="button" className="button button-secondary" onClick={() => applyPrefixes([])} disabled={saving}>
                {t.mutations.prefixClearAllBtn}
              </button>
            )}
          </div>
        </div>
        {prefixDraftError && <p className="field-error">{prefixDraftError}</p>}
        {prefixesList && prefixesList.length > 0 ? (
          <div className="business-prefix-chips">
            {prefixesList.map(prefix => (
              <span className="business-prefix-chip" key={prefix}>
                <span>{prefix}</span>
                <button
                  type="button"
                  className="business-prefix-chip-remove"
                  aria-label={t.mutations.prefixRemoveAria(prefix)}
                  onClick={() => handleRemovePrefix(prefix)}
                  disabled={saving}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p className="field-hint">{t.mutations.prefixEmptyHint}</p>
        )}
        <details className="business-raw-details">
          <summary>{t.mutations.rawJsonToggle}</summary>
          <div className="form-control">
            <label htmlFor="business-prefixes">{t.mutations.businessPrefixes}</label>
            <textarea id="business-prefixes" rows={3} value={prefixesText} onChange={event => handleRawPrefixesChange(event.target.value)} disabled={saving} />
          </div>
        </details>
        {formError?.field === 'prefixes' && <p className="form-error" role="alert">{formError.message}</p>}
      </fieldset>

      <fieldset className="business-editor-fieldset">
        <legend>{t.mutations.sectionColors}</legend>
        <div className="business-color-grid">
          <div className="form-control">
            <label htmlFor="business-color-primary">{t.mutations.colorPrimaryLabel}</label>
            <div className="business-color-input-row">
              <input
                id="business-color-primary-swatch"
                type="color"
                className="color-swatch-input"
                aria-label={t.mutations.colorPrimaryLabel}
                value={toHexSwatch(primaryColor, '#ff3a4d')}
                onChange={event => handleColorKeyChange('primary', event.target.value)}
                disabled={saving}
              />
              <input
                id="business-color-primary"
                type="text"
                value={primaryColor}
                placeholder="#ff3a4d"
                onChange={event => handleColorKeyChange('primary', event.target.value)}
                disabled={saving}
              />
              {primaryColor && (
                <button type="button" className="button button-secondary" onClick={() => handleColorKeyChange('primary', '')} disabled={saving}>
                  {t.mutations.colorClearBtn}
                </button>
              )}
            </div>
          </div>
          <div className="form-control">
            <label htmlFor="business-color-accent">{t.mutations.colorAccentLabel}</label>
            <div className="business-color-input-row">
              <input
                id="business-color-accent-swatch"
                type="color"
                className="color-swatch-input"
                aria-label={t.mutations.colorAccentLabel}
                value={toHexSwatch(accentColor, '#0f172a')}
                onChange={event => handleColorKeyChange('accent', event.target.value)}
                disabled={saving}
              />
              <input
                id="business-color-accent"
                type="text"
                value={accentColor}
                placeholder="#0f172a"
                onChange={event => handleColorKeyChange('accent', event.target.value)}
                disabled={saving}
              />
              {accentColor && (
                <button type="button" className="button button-secondary" onClick={() => handleColorKeyChange('accent', '')} disabled={saving}>
                  {t.mutations.colorClearBtn}
                </button>
              )}
            </div>
          </div>
        </div>
        {extraColorEntries.length > 0 && (
          <div>
            <p className="field-hint">{t.mutations.colorExtraKeysNote}</p>
            <div className="business-prefix-chips">
              {extraColorEntries.map(([key, val]) => (
                <span className="business-prefix-chip" key={key}>
                  <span>{key}: {typeof val === 'string' ? val : JSON.stringify(val)}</span>
                  <button
                    type="button"
                    className="business-prefix-chip-remove"
                    aria-label={t.mutations.colorRemoveKeyAria(key)}
                    onClick={() => handleRemoveExtraColorKey(key)}
                    disabled={saving}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
        <details className="business-raw-details">
          <summary>{t.mutations.rawJsonToggle}</summary>
          <div className="form-control">
            <label htmlFor="business-colors">{t.mutations.businessColors}</label>
            <textarea id="business-colors" rows={4} value={colorsText} onChange={event => handleRawColorsChange(event.target.value)} disabled={saving} />
          </div>
        </details>
        {formError?.field === 'colors' && <p className="form-error" role="alert">{formError.message}</p>}
      </fieldset>

      {business && (
        <fieldset className="business-editor-fieldset">
          <legend>{t.mutations.sectionLegacyTiers}</legend>
          <p className="field-hint">{t.mutations.legacyTiersNote}</p>
          {tiersList && tiersList.length > 0 ? (
            <div className="business-tier-list">
              {tiersList.map((tier, index) => (
                <div className="business-tier-card" key={`legacy-tier-${index}`}>
                  <div className="business-tier-grid">
                    <div className="form-control">
                      <label htmlFor={`legacy-tier-level-${index}`}>{t.mutations.legacyTierLevel}</label>
                      <input
                        id={`legacy-tier-level-${index}`}
                        type="number"
                        min={1}
                        step={1}
                        value={tier.level}
                        onChange={event => handleLegacyTierChange(index, 'level', event.target.value)}
                        disabled={saving}
                      />
                    </div>
                    <div className="form-control">
                      <label htmlFor={`legacy-tier-name-${index}`}>{t.mutations.legacyTierName}</label>
                      <input
                        id={`legacy-tier-name-${index}`}
                        type="text"
                        value={tier.name ?? ''}
                        onChange={event => handleLegacyTierChange(index, 'name', event.target.value)}
                        disabled={saving}
                      />
                    </div>
                    <div className="form-control">
                      <label htmlFor={`legacy-tier-threshold-${index}`}>{t.mutations.legacyTierThreshold}</label>
                      <input
                        id={`legacy-tier-threshold-${index}`}
                        type="text"
                        inputMode="decimal"
                        value={String(tier.threshold ?? '')}
                        placeholder={t.mutations.legacyTierThresholdPlaceholder}
                        aria-invalid={
                          formError?.field === 'tiers' && !/^\d+(\.\d+)?$/.test(String(tier.threshold ?? '').trim())
                            ? 'true'
                            : 'false'
                        }
                        onChange={event => handleLegacyTierChange(index, 'threshold', event.target.value)}
                        disabled={saving}
                      />
                    </div>
                    <div className="form-control">
                      <label htmlFor={`legacy-tier-percent-${index}`}>{t.mutations.legacyTierPercent}</label>
                      <input
                        id={`legacy-tier-percent-${index}`}
                        type="text"
                        inputMode="decimal"
                        value={String(tier.percent)}
                        onChange={event => handleLegacyTierChange(index, 'percent', event.target.value)}
                        disabled={saving}
                      />
                    </div>
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => handleRemoveLegacyTier(index)}
                      disabled={saving}
                    >
                      {t.mutations.legacyTierRemoveBtn}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="field-hint">{t.mutations.legacyTierEmpty}</p>
          )}
          <div className="business-inline-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={handleAddLegacyTier}
              disabled={saving || (tiersList?.length ?? 0) >= 10}
            >
              {t.mutations.legacyTierAddBtn}
            </button>
            {tiersList && tiersList.length > 0 && (
              <button
                type="button"
                className="button button-secondary"
                onClick={() => applyTiers(null)}
                disabled={saving}
              >
                {t.mutations.legacyTierClearBtn}
              </button>
            )}
          </div>
          <details className="business-raw-details">
            <summary>{t.mutations.rawJsonToggle}</summary>
            <div className="form-control">
              <label htmlFor="business-tiers">{t.mutations.businessTiers}</label>
              <textarea
                id="business-tiers"
                rows={4}
                value={tiersText}
                placeholder='[{"level": 1, "name": "Базовый", "threshold": "0", "percent": "3"}]'
                onChange={event => handleRawTiersChange(event.target.value)}
                disabled={saving}
              />
            </div>
          </details>
          {formError?.field === 'tiers' && <p className="form-error" role="alert">{formError.message}</p>}
        </fieldset>
      )}

      {formError?.field === 'form' && <p className="form-error" role="alert">{formError.message}</p>}
      <footer className="mutation-actions dialog-actions--left business-editor-footer">
        <button className="button button-primary" type="submit" disabled={saving || uploadingLogo}>{saving ? t.mutations.saving : business ? t.mutations.save : t.mutations.create}</button>
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving || uploadingLogo}>{t.mutations.cancel}</button>
      </footer>
    </form>
  </DialogFrame>;
}

export function AgentCreateDialog({ onClose, onCreated }: {
  onClose: () => void; onCreated: (disclosure: AgentKeyDisclosure) => void;
}) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const businesses = useBusinesses({ limit: 100, offset });
  const [businessId, setBusinessId] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!businessId) { setError(t.mutations.agentErrSelectBusiness); return; }
    setCreating(true);
    try {
      const disclosure = await session.api.request<AgentKeyDisclosure>('/admin/agents', {
        method: 'POST', body: { business_id: businessId },
      });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'agents'] });
      onCreated({ agent: disclosure.agent, api_key: disclosure.api_key });
    } catch (mutationError) {
      setError(messageForError(mutationError, locale));
    } finally {
      setCreating(false);
    }
  };

  return <DialogFrame title={t.mutations.agentCreateTitle} onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      <label htmlFor="agent-business">{t.mutations.agentBusiness}</label>
      {businesses.isPending ? <p>{t.mutations.agentLoadingBusinesses}</p> : businesses.isError ?
        <p className="form-error" role="alert">{messageForError(businesses.error, locale)}</p> :
        <select id="agent-business" value={businessId} onChange={event => setBusinessId(event.target.value)} required>
          <option value="">{t.mutations.agentSelectBusiness}</option>
          {businesses.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>}
      {(businesses.data?.has_more || offset > 0) && <div className="pagination-actions">
        <button className="button button-secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>{t.mutations.agentPrevBusinesses}</button>
        <button className="button button-secondary" type="button" disabled={!businesses.data?.has_more} onClick={() => setOffset(offset + 100)}>{t.mutations.agentNextBusinesses}</button>
      </div>}
      <p className="muted-copy">{t.mutations.agentApiKeyHint}</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-primary" type="submit" disabled={creating || businesses.isPending}>{creating ? t.mutations.creating : t.mutations.agentCreateSubmit}</button>
        <button className="button button-secondary" type="button" onClick={onClose} disabled={creating}>{t.mutations.cancel}</button>
      </footer>
    </form>
  </DialogFrame>;
}

export function AgentKeyDialog({ disclosure, title, onClose }: {
  disclosure: AgentKeyDisclosure; title?: string; onClose: () => void;
}) {
  const t = useAdminTranslation();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  const copy = async () => {
    setCopyError('');
    try {
      await navigator.clipboard.writeText(disclosure.api_key);
      setCopied(true);
    } catch {
      setCopyError(t.mutations.copyError);
    }
  };
  return <DialogFrame title={title ?? t.mutations.agentKeyTitleCreated} onClose={onClose}>
    <div className="mutation-form">
      <p>{t.mutations.agentKeyNotice}</p>
      <p className="muted-copy">{t.mutations.agentKeyInstallHint}</p>
      <p className="muted-copy">{t.mutations.agentInfo(disclosure.agent.business_name, disclosure.agent.id)}</p>
      <code className="secret-key" aria-label={t.mutations.agentApiKeyAria}>{disclosure.api_key}</code>
      {copyError && <p className="form-error" role="alert">{copyError}</p>}
      <footer className="mutation-actions">
        <button className="button button-primary" type="button" onClick={() => { void copy(); }}>{t.mutations.copyKeyBtn}</button>
        <button className="button button-secondary" type="button" onClick={() => { setCopied(false); onClose(); }}>{t.mutations.closeAndDismissBtn}</button>
      </footer>
      {copied && <p className="success-copy" role="status">{t.mutations.copied}</p>}
    </div>
  </DialogFrame>;
}

export function ManagerAccessDialog({ disclosure, title, onClose }: {
  disclosure: ManagerAccessDisclosure; title?: string; onClose: () => void;
}) {
  const t = useAdminTranslation();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');

  const origin = typeof window !== 'undefined' && window.location?.origin ? window.location.origin : '';
  const loginUrl = `${origin}/admin/login`;

  const copyAll = async () => {
    setCopyError('');
    setCopied(false);
    const fullText = t.mutations.copyAllTemplate(loginUrl, disclosure.login, disclosure.password);
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
    } catch {
      setCopyError(t.mutations.copyAllError);
    }
  };

  return <DialogFrame title={title ?? t.mutations.managerAccessTitle} onClose={onClose}>
    <div className="mutation-form">
      <p className="warning-copy" role="status">{t.mutations.managerWarning}</p>
      <label htmlFor="disclosure-url">{t.mutations.managerUrlLabel}</label>
      <code id="disclosure-url" className="secret-key" aria-label={t.mutations.managerUrlAria}>{loginUrl}</code>
      <label htmlFor="disclosure-login">{t.mutations.managerLoginLabel}</label>
      <code id="disclosure-login" className="secret-key" aria-label={t.mutations.managerLoginAria}>{disclosure.login}</code>
      <label htmlFor="disclosure-password">{t.mutations.managerPasswordLabel}</label>
      <code id="disclosure-password" className="secret-key" aria-label={t.mutations.managerPasswordAria}>{disclosure.password}</code>
      <footer className="mutation-actions manager-access-actions">
        <button className="button button-primary" type="button" onClick={() => { void copyAll(); }}>{t.mutations.copyAllBtn}</button>
      </footer>
      <div className="manager-access-status" aria-live="polite">
        {copyError ? <p className="form-error" role="alert">{copyError}</p> : copied ? <p className="success-copy">{t.mutations.copyAllCopied}</p> : null}
      </div>
    </div>
  </DialogFrame>;
}
