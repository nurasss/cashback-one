import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, usePosKeys } from '../api/queries';
import type { PosKey, PosKeyDisclosure } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { StatusPill } from '../components/Feedback';
import { DialogFrame } from './AdminMutations';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';
import { formatDate } from '../utils/format';

interface PosKeyCreateDialogProps {
  businessId: string;
  onClose: () => void;
  onCreated: (disclosure: PosKeyDisclosure) => void;
}

export function PosKeyCreateDialog({
  businessId,
  onClose,
  onCreated,
}: PosKeyCreateDialogProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) {
      setError(t.posKeys.nameRequired);
      return;
    }
    setError('');
    setCreating(true);
    try {
      const res = await session.api.request<PosKeyDisclosure>(
        `/admin/businesses/${encodeURIComponent(businessId)}/pos-keys`,
        {
          method: 'POST',
          body: { name: cleanName },
        }
      );
      onCreated(res);
    } catch (err) {
      setError(messageForError(err, locale));
    } finally {
      setCreating(false);
    }
  };

  return (
    <DialogFrame title={t.posKeys.createTitle} onClose={onClose}>
      <form className="mutation-form" onSubmit={handleSubmit}>
        <label className="field-block">
          <span className="field-label">{t.posKeys.createNameLabel}</span>
          <input
            className="input-text"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t.posKeys.createNamePlaceholder}
            maxLength={100}
            autoFocus
          />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <footer className="mutation-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={creating}>
            {t.posKeys.cancelBtn}
          </button>
          <button className="button button-primary" type="submit" disabled={creating}>
            {creating ? t.posKeys.creatingSubmitBtn : t.posKeys.createSubmitBtn}
          </button>
        </footer>
      </form>
    </DialogFrame>
  );
}

interface PosKeyDialogProps {
  disclosure: PosKeyDisclosure;
  onClose: () => void;
}

export function PosKeyDialog({ disclosure, onClose }: PosKeyDialogProps) {
  const t = useAdminTranslation();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');

  const copy = async () => {
    setCopyError('');
    try {
      await navigator.clipboard.writeText(disclosure.api_key);
      setCopied(true);
    } catch {
      setCopyError(t.posKeys.copyError);
    }
  };

  return (
    <DialogFrame title={t.posKeys.keyDialogTitle} onClose={onClose}>
      <div className="mutation-form">
        <p>{t.posKeys.keyDialogNotice}</p>
        <p className="muted-copy">{t.posKeys.keyDialogHint}</p>
        <p className="muted-copy">
          <strong>{disclosure.pos_key.name}</strong>
        </p>
        <code className="secret-key" aria-label={t.posKeys.keyAriaLabel}>
          {disclosure.api_key}
        </code>
        {copyError && <p className="form-error" role="alert">{copyError}</p>}
        <footer className="mutation-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => {
              setCopied(false);
              onClose();
            }}
          >
            {t.posKeys.closeBtn}
          </button>
          <button className="button button-primary" type="button" onClick={() => { void copy(); }}>
            {t.posKeys.copyBtn}
          </button>
        </footer>
        {copied && <p className="success-copy" role="status">{t.posKeys.copied}</p>}
      </div>
    </DialogFrame>
  );
}

interface PosKeyRevokeDialogProps {
  posKey: PosKey;
  onClose: () => void;
  onRevoked: () => void;
}

export function PosKeyRevokeDialog({ posKey, onClose, onRevoked }: PosKeyRevokeDialogProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [error, setError] = useState('');
  const [revoking, setRevoking] = useState(false);

  const handleRevoke = async () => {
    setError('');
    setRevoking(true);
    try {
      await session.api.request<PosKey>(
        `/admin/pos-keys/${encodeURIComponent(posKey.id)}/revoke`,
        { method: 'POST' }
      );
      onRevoked();
    } catch (err) {
      setError(messageForError(err, locale));
    } finally {
      setRevoking(false);
    }
  };

  return (
    <DialogFrame title={t.posKeys.revokeBtn} onClose={onClose}>
      <div className="mutation-form">
        <p>{t.posKeys.confirmRevoke(posKey.name)}</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <footer className="mutation-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={revoking}>
            {t.posKeys.cancelBtn}
          </button>
          <button
            className="button button-destructive"
            type="button"
            onClick={() => { void handleRevoke(); }}
            disabled={revoking}
          >
            {revoking ? t.posKeys.revoking : t.posKeys.revokeBtn}
          </button>
        </footer>
      </div>
    </DialogFrame>
  );
}

export function BusinessPosKeys({ businessId }: { businessId: string }) {
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const keysQuery = usePosKeys(businessId);

  const [createOpen, setCreateOpen] = useState(false);
  const [disclosure, setDisclosure] = useState<PosKeyDisclosure | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<PosKey | null>(null);

  const handleCreated = (newDisclosure: PosKeyDisclosure) => {
    setCreateOpen(false);
    setDisclosure(newDisclosure);
    void queryClient.invalidateQueries({ queryKey: [...privateKey, 'pos-keys', businessId] });
  };

  const handleRevoked = () => {
    setRevokeTarget(null);
    void queryClient.invalidateQueries({ queryKey: [...privateKey, 'pos-keys', businessId] });
  };

  return (
    <section className="surface-card pos-keys-section">
      <div className="section-heading">
        <div>
          <h2>{t.posKeys.sectionTitle}</h2>
          <p className="muted-copy">{t.posKeys.sectionSubtitle}</p>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => setCreateOpen(true)}
        >
          {t.posKeys.addBtn}
        </button>
      </div>

      {keysQuery.isPending ? (
        <p className="loading-copy">{t.posKeys.loading}</p>
      ) : keysQuery.isError ? (
        <p className="form-error">{messageForError(keysQuery.error, locale)}</p>
      ) : !keysQuery.data || keysQuery.data.length === 0 ? (
        <p className="table-empty">{t.posKeys.empty}</p>
      ) : (
        <>
          {/* Desktop/Tablet Table view */}
          <div className="table-wrap pos-keys-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.posKeys.colName}</th>
                  <th>{t.posKeys.colCreated}</th>
                  <th>{t.posKeys.colLastUsed}</th>
                  <th>{t.posKeys.colStatus}</th>
                  <th className="align-right">{t.posKeys.colActions}</th>
                </tr>
              </thead>
              <tbody>
                {keysQuery.data.map(key => (
                  <tr key={key.id}>
                    <td>
                      <strong>{key.name}</strong>
                    </td>
                    <td>
                      <time dateTime={key.created_at}>{formatDate(key.created_at, locale)}</time>
                    </td>
                    <td>
                      {key.last_used_at ? (
                        <time dateTime={key.last_used_at}>{formatDate(key.last_used_at, locale)}</time>
                      ) : (
                        <span className="muted-copy">{t.posKeys.neverUsed}</span>
                      )}
                    </td>
                    <td>
                      <StatusPill tone={key.status === 'active' ? 'positive' : 'neutral'}>
                        {key.status === 'active' ? t.posKeys.statusActive : t.posKeys.statusRevoked}
                      </StatusPill>
                    </td>
                    <td className="align-right">
                      {key.status === 'active' && (
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => setRevokeTarget(key)}
                        >
                          {t.posKeys.revokeBtn}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards view (<= 640px) */}
          <div className="pos-keys-cards">
            {keysQuery.data.map(key => (
              <div key={key.id} className="pos-key-card">
                <div className="pos-key-card-header">
                  <strong>{key.name}</strong>
                  <StatusPill tone={key.status === 'active' ? 'positive' : 'neutral'}>
                    {key.status === 'active' ? t.posKeys.statusActive : t.posKeys.statusRevoked}
                  </StatusPill>
                </div>
                <div className="pos-key-card-meta">
                  <span className="muted-copy">{t.posKeys.colCreated}: </span>
                  <time dateTime={key.created_at}>{formatDate(key.created_at, locale)}</time>
                </div>
                <div className="pos-key-card-meta">
                  <span className="muted-copy">{t.posKeys.colLastUsed}: </span>
                  {key.last_used_at ? (
                    <time dateTime={key.last_used_at}>{formatDate(key.last_used_at, locale)}</time>
                  ) : (
                    <span className="muted-copy">{t.posKeys.neverUsed}</span>
                  )}
                </div>
                {key.status === 'active' && (
                  <div className="pos-key-card-actions">
                    <button
                      className="link-button"
                      type="button"
                      onClick={() => setRevokeTarget(key)}
                    >
                      {t.posKeys.revokeBtn}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {createOpen && (
        <PosKeyCreateDialog
          businessId={businessId}
          onClose={() => setCreateOpen(false)}
          onCreated={handleCreated}
        />
      )}

      {disclosure && (
        <PosKeyDialog
          disclosure={disclosure}
          onClose={() => setDisclosure(null)}
        />
      )}

      {revokeTarget && (
        <PosKeyRevokeDialog
          posKey={revokeTarget}
          onClose={() => setRevokeTarget(null)}
          onRevoked={handleRevoked}
        />
      )}
    </section>
  );
}
