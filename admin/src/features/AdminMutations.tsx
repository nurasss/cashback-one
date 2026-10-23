import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinesses } from '../api/queries';
import type {
  AgentKeyDisclosure,
  BusinessCreatedResponse,
  BusinessDetail,
  LoyaltyTier,
  ManagerAccessDisclosure,
} from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function DialogFrame({ title, onClose, children }: {
  title: string; onClose: () => void; children: ReactNode;
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
    <section ref={dialogRef} tabIndex={-1} className="mutation-dialog" role="dialog" aria-modal="true" aria-labelledby="mutation-title" onKeyDown={closeOnEscape}>
      <header className="mutation-heading"><h2 id="mutation-title">{title}</h2>
        <button className="button button-secondary" type="button" onClick={onClose} aria-label={t.mutations.closeDialog}>{t.mutations.close}</button>
      </header>
      {children}
    </section>
  </div>;
}

function isTier(value: unknown): value is LoyaltyTier {
  if (typeof value !== 'object' || value === null) return false;
  const tier = value as Record<string, unknown>;
  const decimal = (v: unknown) => (typeof v === 'string' || typeof v === 'number') && /^\d+(\.\d+)?$/.test(String(v));
  return Number.isInteger(tier.level) && decimal(tier.threshold) && decimal(tier.percent)
    && (tier.name === undefined || tier.name === null || typeof tier.name === 'string');
}

export function BusinessEditorDialog({ business, onClose, onSaved }: {
  business?: BusinessDetail; onClose: () => void; onSaved: (managerAccess?: ManagerAccessDisclosure | null) => void;
}) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState(business?.name ?? '');
  const [logoUrl, setLogoUrl] = useState(business?.logo_url ?? '');
  const [colorsText, setColorsText] = useState(JSON.stringify(business?.colors ?? null, null, 2));
  const [prefixesText, setPrefixesText] = useState(JSON.stringify(business?.barcode_prefixes ?? [], null, 2));
  const [status, setStatus] = useState<'active' | 'inactive'>(business?.status === 'inactive' ? 'inactive' : 'active');
  const [tiersText, setTiersText] = useState(JSON.stringify(business?.loyalty_tiers ?? null, null, 2));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const trimmedName = name.trim();
    if (!trimmedName || trimmedName.length > 255) {
      setError(t.mutations.errBusinessName);
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
        setError(t.mutations.errBusinessLogo);
        return;
      }
    }
    let colors: Record<string, unknown> | null;
    try {
      const parsed: unknown = JSON.parse(colorsText || 'null');
      if (parsed === null) colors = null;
      else if (typeof parsed === 'object' && !Array.isArray(parsed)) colors = parsed as Record<string, unknown>;
      else throw new Error('invalid');
      if (new TextEncoder().encode(JSON.stringify(colors)).length > 8192) throw new Error('large');
    } catch {
      setError(t.mutations.errBusinessColors);
      return;
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
      setError(t.mutations.errBusinessPrefixes);
      return;
    }

    let loyaltyTiers: LoyaltyTier[] | null;
    try {
      const parsed: unknown = JSON.parse(tiersText || 'null');
      if (parsed === null) loyaltyTiers = null;
      else if (Array.isArray(parsed) && parsed.length > 0 && parsed.length <= 10 && parsed.every(isTier)) loyaltyTiers = parsed;
      else throw new Error('invalid');
    } catch {
      setError(t.mutations.errBusinessTiers);
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: trimmedName,
        logo_url: normalizedLogo,
        colors,
        barcode_prefixes: barcodePrefixes,
        status,
        ...(business ? { loyalty_tiers: loyaltyTiers } : {}),
      };
      if (business) {
        await session.api.request<BusinessDetail>(`/admin/businesses/${encodeURIComponent(business.id)}`, {
          method: 'PATCH', body: payload,
        });
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'business', business.id] });
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'businesses'] });
        onSaved();
      } else {
        const created = await session.api.request<BusinessCreatedResponse>('/admin/businesses', { method: 'POST', body: payload });
        await queryClient.invalidateQueries({ queryKey: [...privateKey, 'businesses'] });
        onSaved(created.manager_access);
      }
    } catch (mutationError) {
      setError(messageForError(mutationError, locale));
    } finally {
      setSaving(false);
    }
  };

  return <DialogFrame title={business ? t.mutations.businessEditTitle : t.mutations.businessCreateTitle} onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      <label htmlFor="business-name">{t.mutations.businessName}</label>
      <input id="business-name" value={name} maxLength={255} onChange={event => setName(event.target.value)} autoFocus required />
      <label htmlFor="business-logo">{t.mutations.businessLogo}</label>
      <input id="business-logo" type="url" value={logoUrl} maxLength={1024} onChange={event => setLogoUrl(event.target.value)} />
      <label htmlFor="business-colors">{t.mutations.businessColors}</label>
      <textarea id="business-colors" rows={5} value={colorsText} onChange={event => setColorsText(event.target.value)} />
      <label htmlFor="business-prefixes">{t.mutations.businessPrefixes}</label>
      <textarea id="business-prefixes" rows={3} value={prefixesText} onChange={event => setPrefixesText(event.target.value)} />
      {business && <><label htmlFor="business-tiers">{t.mutations.businessTiers}</label>
      <textarea id="business-tiers" rows={6} value={tiersText} placeholder='[{"level": 1, "name": "Базовый", "threshold": "0", "percent": "3"}]' onChange={event => setTiersText(event.target.value)} /></>}
      <label htmlFor="business-status">{t.mutations.businessStatus}</label>
      <select id="business-status" value={status} onChange={event => setStatus(event.target.value as 'active' | 'inactive')}>
        <option value="active">{t.mutations.statusActive}</option><option value="inactive">{t.mutations.statusInactive}</option>
      </select>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>{t.mutations.cancel}</button>
        <button className="button button-primary" type="submit" disabled={saving}>{saving ? t.mutations.saving : business ? t.mutations.save : t.mutations.create}</button>
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
      {businesses.data?.has_more && <div className="pagination-actions">
        <button className="button button-secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>{t.mutations.agentPrevBusinesses}</button>
        <button className="button button-secondary" type="button" onClick={() => setOffset(offset + 100)}>{t.mutations.agentNextBusinesses}</button>
      </div>}
      <p className="muted-copy">{t.mutations.agentApiKeyHint}</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={creating}>{t.mutations.cancel}</button>
        <button className="button button-primary" type="submit" disabled={creating || businesses.isPending}>{creating ? t.mutations.creating : t.mutations.agentCreateSubmit}</button>
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
      <p className="muted-copy">{t.mutations.agentInfo(disclosure.agent.business_name, disclosure.agent.id)}</p>
      <code className="secret-key" aria-label={t.mutations.agentApiKeyAria}>{disclosure.api_key}</code>
      {copyError && <p className="form-error" role="alert">{copyError}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={() => { setCopied(false); onClose(); }}>{t.mutations.closeAndDismissBtn}</button>
        <button className="button button-primary" type="button" onClick={() => { void copy(); }}>{t.mutations.copyKeyBtn}</button>
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
      {copyError && <p className="form-error" role="alert">{copyError}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose}>{t.mutations.close}</button>
        <button className="button button-primary" type="button" onClick={() => { void copyAll(); }}>{t.mutations.copyAllBtn}</button>
      </footer>
      {copied && <p className="success-copy" role="status">{t.mutations.copyAllCopied}</p>}
    </div>
  </DialogFrame>;
}
