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

export function DialogFrame({ title, onClose, children }: {
  title: string; onClose: () => void; children: ReactNode;
}) {
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
        <button className="button button-secondary" type="button" onClick={onClose} aria-label="Закрыть окно">Закрыть</button>
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
      setError('Введите название длиной до 255 символов.');
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
        setError('Логотип должен быть HTTPS URL без встроенных учётных данных.');
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
      setError('Цвета должны быть JSON-объектом не больше 8 KiB или null.');
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
      setError('Префиксы должны быть JSON-массивом строк, [] или null.');
      return;
    }

    let loyaltyTiers: LoyaltyTier[] | null;
    try {
      const parsed: unknown = JSON.parse(tiersText || 'null');
      if (parsed === null) loyaltyTiers = null;
      else if (Array.isArray(parsed) && parsed.length > 0 && parsed.length <= 10 && parsed.every(isTier)) loyaltyTiers = parsed;
      else throw new Error('invalid');
    } catch {
      setError('Уровни должны быть JSON-массивом до 10 объектов {level, name, threshold, percent} или null.');
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
      setError(messageForError(mutationError));
    } finally {
      setSaving(false);
    }
  };

  return <DialogFrame title={business ? 'Изменить бизнес' : 'Создать бизнес'} onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      <label htmlFor="business-name">Название</label>
      <input id="business-name" value={name} maxLength={255} onChange={event => setName(event.target.value)} autoFocus required />
      <label htmlFor="business-logo">Логотип (HTTPS URL или пусто)</label>
      <input id="business-logo" type="url" value={logoUrl} maxLength={1024} onChange={event => setLogoUrl(event.target.value)} />
      <label htmlFor="business-colors">Цвета (ограниченный JSON object)</label>
      <textarea id="business-colors" rows={5} value={colorsText} onChange={event => setColorsText(event.target.value)} />
      <label htmlFor="business-prefixes">Префиксы barcode (JSON array; пустой список допустим)</label>
      <textarea id="business-prefixes" rows={3} value={prefixesText} onChange={event => setPrefixesText(event.target.value)} />
      {business && <><label htmlFor="business-tiers">Уровни лояльности (JSON: level, name, threshold — сумма покупок, percent — % баллов)</label>
      <textarea id="business-tiers" rows={6} value={tiersText} placeholder='[{"level": 1, "name": "Базовый", "threshold": "0", "percent": "3"}]' onChange={event => setTiersText(event.target.value)} /></>}
      <label htmlFor="business-status">Статус</label>
      <select id="business-status" value={status} onChange={event => setStatus(event.target.value as 'active' | 'inactive')}>
        <option value="active">Активен</option><option value="inactive">Неактивен</option>
      </select>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>Отмена</button>
        <button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Сохраняем…' : business ? 'Сохранить' : 'Создать'}</button>
      </footer>
    </form>
  </DialogFrame>;
}

export function AgentCreateDialog({ onClose, onCreated }: {
  onClose: () => void; onCreated: (disclosure: AgentKeyDisclosure) => void;
}) {
  const { session } = useAdminSession();
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const businesses = useBusinesses({ limit: 100, offset });
  const [businessId, setBusinessId] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!businessId) { setError('Выберите бизнес.'); return; }
    setCreating(true);
    try {
      const disclosure = await session.api.request<AgentKeyDisclosure>('/admin/agents', {
        method: 'POST', body: { business_id: businessId },
      });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'agents'] });
      // The disclosure bypasses query/mutation caches and is passed only to transient component state.
      onCreated({ agent: disclosure.agent, api_key: disclosure.api_key });
    } catch (mutationError) {
      setError(messageForError(mutationError));
    } finally {
      setCreating(false);
    }
  };

  return <DialogFrame title="Создать агента" onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      <label htmlFor="agent-business">Бизнес</label>
      {businesses.isPending ? <p>Загружаем список бизнесов…</p> : businesses.isError ?
        <p className="form-error" role="alert">{messageForError(businesses.error)}</p> :
        <select id="agent-business" value={businessId} onChange={event => setBusinessId(event.target.value)} required>
          <option value="">Выберите бизнес</option>
          {businesses.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>}
      {businesses.data?.has_more && <div className="pagination-actions">
        <button className="button button-secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Предыдущие бизнесы</button>
        <button className="button button-secondary" type="button" onClick={() => setOffset(offset + 100)}>Следующие бизнесы</button>
      </div>}
      <p className="muted-copy">Ключ API будет показан один раз после создания.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={creating}>Отмена</button>
        <button className="button button-primary" type="submit" disabled={creating || businesses.isPending}>{creating ? 'Создаём…' : 'Создать агента'}</button>
      </footer>
    </form>
  </DialogFrame>;
}

export function AgentKeyDialog({ disclosure, title = 'Ключ агента создан', onClose }: {
  disclosure: AgentKeyDisclosure; title?: string; onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  const copy = async () => {
    setCopyError('');
    try {
      await navigator.clipboard.writeText(disclosure.api_key);
      setCopied(true);
    } catch {
      setCopyError('Не удалось скопировать. Выделите ключ вручную.');
    }
  };
  return <DialogFrame title={title} onClose={onClose}>
    <div className="mutation-form">
      <p>Ключ будет показан только один раз. Сохраните его сейчас.</p>
      <p className="muted-copy">Агент: {disclosure.agent.business_name} · {disclosure.agent.id}</p>
      <code className="secret-key" aria-label="Одноразовый API key">{disclosure.api_key}</code>
      {copyError && <p className="form-error" role="alert">{copyError}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={() => { setCopied(false); onClose(); }}>Закрыть и удалить ключ</button>
        <button className="button button-primary" type="button" onClick={() => { void copy(); }}>Скопировать ключ</button>
      </footer>
      {copied && <p className="success-copy" role="status">Скопировано.</p>}
    </div>
  </DialogFrame>;
}

export function ManagerAccessDialog({ disclosure, title = 'Доступ клиента к админке', onClose }: {
  disclosure: ManagerAccessDisclosure; title?: string; onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');

  const copyAll = async () => {
    setCopyError('');
    const fullText = `Ссылка: ${disclosure.login_url}\nЛогин: ${disclosure.login}\nПароль: ${disclosure.password}`;
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
    } catch {
      setCopyError('Не удалось скопировать. Выделите данные вручную.');
    }
  };

  return <DialogFrame title={title} onClose={onClose}>
    <div className="mutation-form">
      <p className="warning-copy" role="status">Пароль показан один раз и не сохраняется. Передайте клиенту безопасным способом.</p>
      <label htmlFor="disclosure-url">Ссылка для входа</label>
      <code id="disclosure-url" className="secret-key" aria-label="Ссылка для входа">{disclosure.login_url}</code>
      <label htmlFor="disclosure-login">Логин</label>
      <code id="disclosure-login" className="secret-key" aria-label="Логин менеджера">{disclosure.login}</code>
      <label htmlFor="disclosure-password">Пароль</label>
      <code id="disclosure-password" className="secret-key" aria-label="Пароль менеджера">{disclosure.password}</code>
      {copyError && <p className="form-error" role="alert">{copyError}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose}>Закрыть</button>
        <button className="button button-primary" type="button" onClick={() => { void copyAll(); }}>Скопировать всё</button>
      </footer>
      {copied && <p className="success-copy" role="status">Скопировано в буфер обмена.</p>}
    </div>
  </DialogFrame>;
}
