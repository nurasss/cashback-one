import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { useAdminSession } from '../auth/provider';
import { privateKey, useBusinesses, useCard, useCards, useCardSearch, useUser, useUserSearch } from '../api/queries';
import type { AdminUser, Card, CardUnbindResult, PageQuery } from '../api/types';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatBalance, formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function OperationsPage() {
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [mode, setMode] = useState<'barcode' | 'phone'>('barcode');
  const [raw, setRaw] = useState('');
  const [businessId, setBusinessId] = useState('');
  const [criteria, setCriteria] = useState<{ barcode?: string; phone?: string; business_id?: string } | null>(null);
  const [cardListPage, setCardListPage] = usePage(25);
  const [cardSearchPage, setCardSearchPage] = usePage(25);
  const [userPage, setUserPage] = usePage(25);

  const businesses = useBusinesses(
    { limit: 100, offset: 0 },
    view.status === 'authenticated' && view.admin.role === 'superadmin',
  );

  const isSearchActive = criteria !== null;
  const isCardListActive = !isSearchActive && mode === 'barcode';

  const cardList = useCards(
    businessId || undefined,
    cardListPage,
    isCardListActive,
  );

  const cardSearch = useCardSearch(
    criteria ?? {},
    cardSearchPage,
    isSearchActive && mode === 'barcode',
  );

  const userSearch = useUserSearch(
    { phone: criteria?.phone ?? '', ...(criteria?.business_id ? { business_id: criteria.business_id } : {}) },
    userPage,
    isSearchActive && mode === 'phone',
  );

  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = raw.trim();
    if (!term) return;
    if (mode === 'barcode' && !/^[0-9]{6,15}$/.test(term)) return;
    if (mode === 'phone' && term.replace(/\D/g, '').length < 7) return;
    const next = {
      ...(mode === 'barcode' ? { barcode: term } : { phone: term }),
      ...(businessId ? { business_id: businessId } : {}),
    };
    setCriteria(next);
    setCardSearchPage(0);
    setUserPage(0);
  };

  const handleReset = () => {
    setMode('barcode');
    setRaw('');
    setCriteria(null);
    setCardListPage(0);
    setCardSearchPage(0);
    setUserPage(0);
  };

  const handleBusinessChange = (newBusId: string) => {
    setBusinessId(newBusId);
    setCardListPage(0);
    setCardSearchPage(0);
    setUserPage(0);
    if (criteria !== null) {
      setCriteria(prev => (prev ? { ...prev, business_id: newBusId || undefined } : null));
    }
  };

  const handleTabChange = (newMode: 'barcode' | 'phone') => {
    setMode(newMode);
    setRaw('');
    setCriteria(null);
    setCardListPage(0);
    setCardSearchPage(0);
    setUserPage(0);
  };

  const isSearching = isSearchActive && (mode === 'barcode' ? cardSearch.isFetching : userSearch.isFetching);
  const searchError = isSearchActive ? (mode === 'barcode' ? cardSearch.error : userSearch.error) : null;

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow={t.operations.eyebrow}
        title={t.operations.title}
        subtitle={
          view.status === 'authenticated' && view.admin.business
            ? t.operations.subtitleScope(view.admin.business.name)
            : t.operations.subtitleAll
        }
      />
      <section className="search-panel surface-card">
        <div className="search-tabs" role="tablist" aria-label={t.operations.title}>
          <button
            className={mode === 'barcode' ? 'search-tab selected' : 'search-tab'}
            type="button"
            role="tab"
            aria-selected={mode === 'barcode'}
            onClick={() => handleTabChange('barcode')}
          >
            {t.operations.tabBarcode}
          </button>
          <button
            className={mode === 'phone' ? 'search-tab selected' : 'search-tab'}
            type="button"
            role="tab"
            aria-selected={mode === 'phone'}
            onClick={() => handleTabChange('phone')}
          >
            {t.operations.tabPhone}
          </button>
        </div>
        <form className="search-form" onSubmit={search}>
          <label className="form-control search-input">
            <span>{mode === 'barcode' ? t.operations.labelBarcode : t.operations.labelPhone}</span>
            <input
              aria-label={mode === 'barcode' ? t.operations.searchBarcodeAria : t.operations.searchPhoneAria}
              autoComplete="off"
              spellCheck={false}
              inputMode={mode === 'barcode' ? 'numeric' : 'tel'}
              maxLength={mode === 'barcode' ? 64 : 32}
              value={raw}
              onChange={event => setRaw(event.target.value)}
              placeholder={mode === 'barcode' ? t.operations.placeholderBarcode : t.operations.placeholderPhone}
            />
          </label>
          {view.status === 'authenticated' && view.admin.role === 'superadmin' && (
            <label className="form-control">
              <span>{t.operations.businessLabel}</span>
              <select
                aria-label={t.operations.searchBusinessAria}
                value={businessId}
                onChange={event => handleBusinessChange(event.target.value)}
              >
                <option value="">{t.operations.allBusinesses}</option>
                {businesses.data?.items.map(business => (
                  <option key={business.id} value={business.id}>
                    {business.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button className="button button-primary" type="submit" disabled={isSearching || !raw.trim()}>
            {isSearching ? t.operations.searchingBtn : t.operations.searchBtn}
          </button>
          {(isSearchActive || raw.trim().length > 0) && (
            <button className="button button-secondary" type="button" onClick={handleReset}>
              {t.operations.resetBtn}
            </button>
          )}
        </form>
        <p className="search-hint">
          {isSearchActive ? t.operations.searchHintActive : t.operations.searchHintDefault}
        </p>
      </section>

      {/* SEARCH ACTIVE */}
      {isSearchActive && (
        <>
          {searchError && (
            <ErrorNotice
              error={searchError}
              retry={() => {
                if (mode === 'barcode') void cardSearch.refetch();
                else void userSearch.refetch();
              }}
            />
          )}
          {mode === 'barcode' ? (
            cardSearch.isPending ? (
              <LoadingPage label={t.operations.loadingCards} />
            ) : cardSearch.data?.items.length === 0 && cardSearchPage.offset === 0 ? (
              <EmptyState title={t.operations.emptyCardsSearchTitle} detail={t.operations.emptyCardsSearchDetail} />
            ) : cardSearch.data ? (
              <CardResults
                page={cardSearchPage}
                setPage={setCardSearchPage}
                rows={cardSearch.data.items}
                hasMore={cardSearch.data.has_more}
                locale={locale}
                t={t}
              />
            ) : null
          ) : (
            userSearch.isPending ? (
              <LoadingPage label={t.operations.loadingUsers} />
            ) : userSearch.data?.items.length === 0 && userPage.offset === 0 ? (
              <EmptyState title={t.operations.emptyUsersSearchTitle} detail={t.operations.emptyUsersSearchDetail} />
            ) : userSearch.data ? (
              <UserResults
                page={userPage}
                setPage={setUserPage}
                rows={userSearch.data.items}
                hasMore={userSearch.data.has_more}
                locale={locale}
                t={t}
              />
            ) : null
          )}
        </>
      )}

      {/* NO SEARCH ACTIVE: GENERAL CARDS LIST (or PHONE PROMPT) */}
      {!isSearchActive && (
        mode === 'barcode' ? (
          cardList.isPending ? (
            <LoadingPage label={t.operations.loadingCards} />
          ) : cardList.isError ? (
            <ErrorNotice error={cardList.error} retry={() => { void cardList.refetch(); }} />
          ) : cardList.data?.items.length === 0 && cardListPage.offset === 0 ? (
            <EmptyState title={t.operations.emptyCardsListTitle} detail={t.operations.emptyCardsListDetail} />
          ) : cardList.data ? (
            <CardResults
              page={cardListPage}
              setPage={setCardListPage}
              rows={cardList.data.items}
              hasMore={cardList.data.has_more}
              locale={locale}
              t={t}
            />
          ) : null
        ) : (
          <EmptyState
            title={t.operations.phonePromptTitle}
            detail={t.operations.phonePromptDetail}
          />
        )
      )}
    </div>
  );
}

function CardResults({
  page,
  setPage,
  rows,
  hasMore,
  locale,
  t,
}: {
  page: PageQuery;
  setPage: (offset: number) => void;
  rows: Card[];
  hasMore: boolean;
  locale: 'ru' | 'kk';
  t: ReturnType<typeof useAdminTranslation>;
}) {
  return (
    <DataTable<Card>
      page={{ ...page, has_more: hasMore }}
      onPage={setPage}
      rows={rows}
      rowKey={row => row.id}
      columns={[
        {
          key: 'barcode',
          title: t.operations.colCard,
          render: row => (
            <Link className="table-name mono-value" to={`/admin/cards/${encodeURIComponent(row.id)}`}>
              {row.barcode}
              <span>{row.business_name}</span>
            </Link>
          ),
        },
        {
          key: 'balance',
          title: t.operations.colBalance,
          render: row => <span className="numeric-value">{formatBalance(row.balance)}</span>,
          align: 'right',
        },
        {
          key: 'status',
          title: t.operations.colStatus,
          render: row => (
            <StatusPill tone={row.is_blocked ? 'negative' : 'positive'}>
              {row.is_blocked ? t.operations.blocked : t.operations.unblocked}
            </StatusPill>
          ),
        },
        {
          key: 'owner',
          title: t.operations.colOwner,
          render: row =>
            row.bind_method && row.phone_masked ? (
              <span>{row.phone_masked}</span>
            ) : (
              <span className="muted-copy">{t.operations.notBound}</span>
            ),
        },
        {
          key: 'updated',
          title: t.operations.colCardUpdated,
          render: row => <time dateTime={row.updated_at}>{formatDate(row.updated_at, locale)}</time>,
        },
      ]}
    />
  );
}

function UserResults({
  page,
  setPage,
  rows,
  hasMore,
  locale,
  t,
}: {
  page: PageQuery;
  setPage: (offset: number) => void;
  rows: AdminUser[];
  hasMore: boolean;
  locale: 'ru' | 'kk';
  t: ReturnType<typeof useAdminTranslation>;
}) {
  return (
    <DataTable<AdminUser>
      page={{ ...page, has_more: hasMore }}
      onPage={setPage}
      rows={rows}
      rowKey={row => row.id}
      columns={[
        {
          key: 'phone',
          title: t.operations.colUser,
          render: row => (
            <Link className="table-name" to={`/admin/users/${encodeURIComponent(row.id)}`}>
              {row.phone_masked ?? t.operations.notSpecified}
              <span>{t.operations.colUserLanguage(row.language)}</span>
            </Link>
          ),
        },
        {
          key: 'cards',
          title: t.operations.colCardsInBiz,
          render: row => <span className="numeric-value">{row.business_cards_count}</span>,
          align: 'right',
        },
        {
          key: 'created',
          title: t.operations.colRegistered,
          render: row => <time dateTime={row.created_at}>{formatDate(row.created_at, locale)}</time>,
        },
      ]}
    />
  );
}

export function CardDetailPage() {
  const { view, session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const { cardId = '' } = useParams<{ cardId: string }>();
  const query = useCard(cardId);
  const [unbindBusy, setUnbindBusy] = useState(false);
  const [unbindError, setUnbindError] = useState('');
  const [unbindResult, setUnbindResult] = useState<CardUnbindResult['status'] | null>(null);

  if (query.isPending) return <LoadingPage label={t.operations.loadingCards} />;
  if (query.isError || !query.data) {
    return (
      <div className="page-stack">
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      </div>
    );
  }
  const card = query.data;
  const canUnbind =
    view.status === 'authenticated' && (view.admin.role === 'superadmin' || view.admin.role === 'business_manager');

  const submitUnbind = async () => {
    const maskedCustomer = card.phone_masked ?? t.operations.notSpecified;
    const warning = t.operations.unbindConfirm(card.business_name, maskedCustomer, card.barcode);
    if (!window.confirm(warning)) return;
    setUnbindBusy(true);
    setUnbindError('');
    setUnbindResult(null);
    try {
      const result = await session.api.request<CardUnbindResult>(
        `/admin/cards/${encodeURIComponent(card.id)}/unbind`,
        { method: 'POST', body: {} }
      );
      setUnbindResult(result.status);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'card', card.id] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'card-search'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'cards'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user-search'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'business', card.business_id] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'dashboard'] }),
      ]);
    } catch (error) {
      setUnbindError(messageForError(error, locale));
    } finally {
      setUnbindBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow={t.operations.cardDetailEyebrow}
        title={card.business_name}
        subtitle={t.operations.cardDetailSubtitle}
        actions={
          <>
            {canUnbind && (
              <button
                className="button button-danger"
                type="button"
                disabled={unbindBusy || !card.bind_method}
                onClick={() => { void submitUnbind(); }}
              >
                {unbindBusy ? t.operations.unbindingBtn : t.operations.unbindBtn}
              </button>
            )}
            <Link className="button button-secondary" to="/admin/operations">
              {t.operations.backToSearchResults}
            </Link>
          </>
        }
      />
      {unbindError && <p className="form-error" role="alert">{unbindError}</p>}
      {unbindResult && (
        <p className="success-copy" role="status">
          {unbindResult === 'unbound' ? t.operations.unbindSuccess : t.operations.unbindAlready}
        </p>
      )}
      <section className="surface-card">
        <dl className="detail-list">
          <Detail label={t.operations.cardBarcode}>
            <span className="mono-value">{card.barcode}</span>
          </Detail>
          <Detail label={t.operations.cardBalance}>
            <strong className="numeric-value">{formatBalance(card.balance)}</strong>
          </Detail>
          <Detail label={t.operations.cardStatus}>
            <StatusPill tone={card.is_blocked ? 'negative' : 'positive'}>
              {card.is_blocked ? t.operations.blocked : t.operations.unblocked}
            </StatusPill>
          </Detail>
          <Detail label={t.operations.cardPhone}>{card.phone_masked ?? t.operations.notSpecified}</Detail>
          <Detail label={t.operations.cardCustomer}>{card.full_name ?? t.operations.notSpecified}</Detail>
          <Detail label={t.operations.cardOwnerLang}>{card.owner_language ?? t.operations.noActiveProfile}</Detail>
          <Detail label={t.operations.cardBindMethod}>{card.bind_method ?? t.operations.notBound}</Detail>
          <Detail label={t.operations.cardBoundAt}>
            {card.bound_at ? formatDate(card.bound_at, locale) : '—'}
          </Detail>
          <Detail label={t.operations.cardHidden}>
            {card.hidden_at ? formatDate(card.hidden_at, locale) : t.operations.no}
          </Detail>
          <Detail label={t.operations.cardDataSource}>POSCENTER Cloud mirror</Detail>
          <Detail label={t.operations.cardUpdated}>
            <time dateTime={card.updated_at}>{formatDate(card.updated_at, locale)}</time>
          </Detail>
        </dl>
      </section>
    </div>
  );
}

export function UserDetailPage() {
  const { userId = '' } = useParams<{ userId: string }>();
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const businessId =
    view.status === 'authenticated' && view.admin.role === 'superadmin'
      ? undefined
      : view.status === 'authenticated'
      ? view.admin.business?.id
      : undefined;
  const query = useUser(userId, businessId, page);

  if (query.isPending) return <LoadingPage label={t.operations.loadingUsers} />;
  if (query.isError || !query.data) {
    return (
      <div className="page-stack">
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      </div>
    );
  }
  const user = query.data;

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow={t.operations.userDetailEyebrow}
        title={user.phone ?? t.operations.colUser}
        subtitle={t.operations.userDetailSubtitle}
        actions={
          <Link className="button button-secondary" to="/admin/operations">
            {t.operations.backToSearch}
          </Link>
        }
      />
      <section className="surface-card">
        <dl className="detail-list">
          <Detail label={t.operations.userPhone}>{user.phone ?? t.operations.notSpecified}</Detail>
          <Detail label={t.operations.userLang}>{user.language}</Detail>
          <Detail label={t.operations.userCreated}>
            <time dateTime={user.created_at}>{formatDate(user.created_at, locale)}</time>
          </Detail>
        </dl>
      </section>
      <section className="surface-card">
        <div className="section-heading">
          <h2>{t.operations.cardsInScope}</h2>
        </div>
        {user.cards.items.length === 0 ? (
          <p className="table-empty">{t.operations.userCardsEmpty}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.operations.colCard}</th>
                  <th>{t.businesses.colName}</th>
                  <th>{t.operations.colBalance}</th>
                  <th>{t.operations.cardBindMethod}</th>
                  <th>{t.operations.colStatus}</th>
                </tr>
              </thead>
              <tbody>
                {user.cards.items.map(card => (
                  <tr key={card.id}>
                    <td>
                      <Link className="text-link mono-value" to={`/admin/cards/${encodeURIComponent(card.id)}`}>
                        {card.barcode}
                      </Link>
                    </td>
                    <td>{card.business_name}</td>
                    <td>{formatBalance(card.balance)}</td>
                    <td>{card.bind_method ?? '—'}</td>
                    <td>{card.is_blocked ? t.operations.blocked : t.operations.unblocked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {user.cards.items.length > 0 && (
          <div className="pagination">
            <span>{t.operations.userCardsPaged}</span>
            <div className="pagination-actions">
              <button
                className="button button-secondary"
                disabled={page.offset === 0}
                onClick={() => setPage(Math.max(0, page.offset - page.limit))}
              >
                {t.feedback.prevPage}
              </button>
              <button
                className="button button-secondary"
                disabled={!user.cards.has_more}
                onClick={() => setPage(page.offset + page.limit)}
              >
                {t.feedback.nextPage}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="detail-line">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
