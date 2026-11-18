import { useState, useEffect, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { privateKey, useAllBusinesses, useCard, useCards, useCardSearch, useCardTransactions, useUser, useUserTransactions } from '../api/queries';
import type { AdminTransaction, Card, CardUnbindResult, Page, PageQuery } from '../api/types';
import { BusinessSelect } from '../components/BusinessSelect';
import { DataTable } from '../components/DataTable';
import { CompactTableToggle, useCompactRows, useTableExpansion, type TableExpansion } from '../components/CompactTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, Pagination, StatusPill } from '../components/Feedback';
import { formatBalance, formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function OperationsPage() {
  const { view } = useAdminSession();
  const { setActiveBusiness } = useActiveBusiness();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [raw, setRaw] = useState('');
  const [businessId, setBusinessId] = useState('');
  const [criteria, setCriteria] = useState<{ barcode?: string; phone?: string; business_id?: string } | null>(null);
  const [cardListPage, setCardListPage] = usePage(25);
  const [cardSearchPage, setCardSearchPage] = usePage(25);
  const cardExpansion = useTableExpansion();

  const businesses = useAllBusinesses(
    view.status === 'authenticated' && view.admin.role === 'superadmin',
  );

  const adminRole = view.status === 'authenticated' ? view.admin.role : null;

  useEffect(() => {
    if (view.status !== 'authenticated' || adminRole !== 'superadmin') return;
    const selected = businessId ? businesses.items.find(b => b.id === businessId) : null;
    setActiveBusiness(selected ? {
      id: selected.id,
      name: selected.name,
      logo_url: selected.logo_url,
      android_app_id: selected.android_app_id,
    } : null);
  }, [businessId, businesses.items, view.status, adminRole, setActiveBusiness]);

  useEffect(() => {
    return () => {
      setActiveBusiness(null);
    };
  }, [setActiveBusiness]);

  const isSearchActive = criteria !== null;
  const isCardListActive = !isSearchActive;

  const cardList = useCards(
    businessId || undefined,
    cardListPage,
    isCardListActive,
  );

  const cardSearch = useCardSearch(
    criteria ?? {},
    cardSearchPage,
    isSearchActive,
  );

  useEffect(() => {
    const total = cardList.data?.total;
    if (total != null) {
      if (total === 0 && cardListPage.offset > 0) {
        setCardListPage(0);
      } else if (total > 0 && cardListPage.offset >= total) {
        const maxOffset = Math.floor((total - 1) / cardListPage.limit) * cardListPage.limit;
        setCardListPage(maxOffset);
      }
    }
  }, [cardList.data?.total, cardListPage.offset, cardListPage.limit, setCardListPage]);

  useEffect(() => {
    const total = cardSearch.data?.total;
    if (total != null) {
      if (total === 0 && cardSearchPage.offset > 0) {
        setCardSearchPage(0);
      } else if (total > 0 && cardSearchPage.offset >= total) {
        const maxOffset = Math.floor((total - 1) / cardSearchPage.limit) * cardSearchPage.limit;
        setCardSearchPage(maxOffset);
      }
    }
  }, [cardSearch.data?.total, cardSearchPage.offset, cardSearchPage.limit, setCardSearchPage]);

  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = raw.trim();
    if (!term) return;
    if (!/^[0-9+\s()-]+$/.test(term)) return;
    const digits = term.replace(/\D/g, '');
    if (digits.length < 4 || digits.length > 13) return;
    const isPureBarcode = /^[0-9]{4,13}$/.test(term);
    const next = {
      barcode: isPureBarcode ? term : digits,
      phone: term,
      ...(businessId ? { business_id: businessId } : {}),
    };
    setCriteria(next);
    setCardSearchPage(0);
  };

  const handleReset = () => {
    setRaw('');
    setCriteria(null);
    setCardListPage(0);
    setCardSearchPage(0);
  };

  const handleBusinessChange = (newBusId: string) => {
    setBusinessId(newBusId);
    setCardListPage(0);
    setCardSearchPage(0);
    if (criteria !== null) {
      setCriteria(prev => (prev ? { ...prev, business_id: newBusId || undefined } : null));
    }
  };

  const isSearching = isSearchActive && cardSearch.isFetching;
  const searchError = isSearchActive ? cardSearch.error : null;

  return (
    <div className="page-stack">
      <PageHeading
        title={t.operations.title}
        subtitle={
          view.status === 'authenticated' && view.admin.business
            ? t.operations.subtitleScope(view.admin.business.name)
            : t.operations.subtitleAll
        }
      />
      <section className="search-panel surface-card">
        <form className="search-form" onSubmit={search}>
          <label className="form-control search-input">
            <span>{t.operations.labelBarcode}</span>
            <input
              aria-label={t.operations.searchBarcodeAria}
              autoComplete="off"
              spellCheck={false}
              inputMode="tel"
              maxLength={64}
              value={raw}
              onChange={event => setRaw(event.target.value)}
              placeholder={t.operations.placeholderBarcode}
            />
          </label>
          {view.status === 'authenticated' && view.admin.role === 'superadmin' && (
            <div className="form-control business-select">
              <label htmlFor="operations-business">{t.operations.businessLabel}</label>
              <BusinessSelect
                id="operations-business"
                ariaLabel={t.operations.searchBusinessAria}
                value={businessId}
                onChange={handleBusinessChange}
                allowAllLabel={t.operations.allBusinesses}
                businesses={businesses}
              />
            </div>
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
                void cardSearch.refetch();
              }}
            />
          )}
          {cardSearch.isPending ? (
            <LoadingPage label={t.operations.loadingCards} />
          ) : cardSearch.data?.items.length === 0 && cardSearchPage.offset === 0 ? (
            <EmptyState title={t.operations.emptyCardsSearchTitle} detail={t.operations.emptyCardsSearchDetail} />
          ) : cardSearch.data ? (
            <CardResults
              expansion={cardExpansion}
              page={cardSearchPage}
              setPage={setCardSearchPage}
              rows={cardSearch.data.items}
              hasMore={cardSearch.data.has_more}
              total={cardSearch.data.total}
              locale={locale}
              t={t}
            />
          ) : null}
        </>
      )}

      {/* NO SEARCH ACTIVE: GENERAL CARDS LIST */}
      {!isSearchActive && (
        cardList.isPending ? (
          <LoadingPage label={t.operations.loadingCards} />
        ) : cardList.isError ? (
          <ErrorNotice error={cardList.error} retry={() => { void cardList.refetch(); }} />
        ) : cardList.data?.items.length === 0 && cardListPage.offset === 0 ? (
          <EmptyState title={t.operations.emptyCardsListTitle} detail={t.operations.emptyCardsListDetail} />
        ) : cardList.data ? (
          <CardResults
            expansion={cardExpansion}
            page={cardListPage}
            setPage={setCardListPage}
            rows={cardList.data.items}
            hasMore={cardList.data.has_more}
            total={cardList.data.total}
            locale={locale}
            t={t}
          />
        ) : null
      )}
    </div>
  );
}

function CardResults({
  expansion,
  page,
  setPage,
  rows,
  hasMore,
  total,
  locale,
  t,
}: {
  expansion: TableExpansion;
  page: PageQuery;
  setPage: (offset: number) => void;
  rows: Card[];
  hasMore: boolean;
  total?: number | null;
  locale: 'ru' | 'kk';
  t: ReturnType<typeof useAdminTranslation>;
}) {
  return (
    <DataTable<Card>
      expansion={expansion}
      page={{ ...page, has_more: hasMore, total }}
      onPage={setPage}
      rows={rows}
      rowKey={row => row.id}
      columns={[
        {
          key: 'barcode',
          title: t.operations.colCardAndOwner,
          render: row => {
            const ownerParts = [row.phone_masked, row.full_name].filter(Boolean);
            const ownerText = ownerParts.length > 0 ? ownerParts.join(' · ') : t.operations.notBound;
            return (
              <Link className="table-name mono-value" to={`/admin/cards/${encodeURIComponent(row.id)}`}>
                {row.barcode}
                <span>{ownerText}</span>
                <span>{row.business_name}</span>
              </Link>
            );
          },
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
          key: 'updated',
          title: t.operations.colCardUpdated,
          render: row => <time dateTime={row.updated_at}>{formatDate(row.updated_at, locale)}</time>,
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
  const [txPage, setTxPage] = usePage(25);
  const query = useCard(cardId);
  const txQuery = useCardTransactions(cardId, txPage);
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
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'card-transactions', card.id] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user-transactions'] }),
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
          <Detail label={t.operations.cardDataSource}>POSCENTER Cloud mirror</Detail>
          <Detail label={t.operations.cardUpdated}>
            <time dateTime={card.updated_at}>{formatDate(card.updated_at, locale)}</time>
          </Detail>
        </dl>
      </section>
      <TransactionsSection
        query={txQuery}
        page={txPage}
        setPage={setTxPage}
        locale={locale}
        t={t}
      />
    </div>
  );
}

export function UserDetailPage() {
  const { userId = '' } = useParams<{ userId: string }>();
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const [txPage, setTxPage] = usePage(25);
  const businessId =
    view.status === 'authenticated' && view.admin.role === 'superadmin'
      ? undefined
      : view.status === 'authenticated'
      ? view.admin.business?.id
      : undefined;
  const query = useUser(userId, businessId, page);
  const txQuery = useUserTransactions(userId, businessId, txPage);
  const compact = useCompactRows(query.data?.cards?.items ?? []);

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
        title={user.phone ?? t.operations.colUser}
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
        {(user.cards?.items?.length ?? 0) === 0 ? (
          <p className="table-empty">{t.operations.userCardsEmpty}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.operations.colCardAndOwner}</th>
                  <th>{t.businesses.colName}</th>
                  <th>{t.operations.colBalance}</th>
                  <th>{t.operations.colStatus}</th>
                </tr>
              </thead>
              <tbody id={compact.bodyId}>
                {compact.visibleRows.map(card => {
                  const ownerParts = [card.phone_masked, card.full_name].filter(Boolean);
                  return (
                    <tr key={card.id}>
                      <td>
                        <Link className="text-link mono-value" to={`/admin/cards/${encodeURIComponent(card.id)}`}>
                          {card.barcode}
                        </Link>
                        {ownerParts.length > 0 && (
                          <span className="cell-secondary">{ownerParts.join(' · ')}</span>
                        )}
                      </td>
                      <td>{card.business_name}</td>
                      <td>{formatBalance(card.balance)}</td>
                      <td>{card.is_blocked ? t.operations.blocked : t.operations.unblocked}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <CompactTableToggle {...compact} />
        {((user.cards?.items?.length ?? 0) > 0 || page.offset > 0) && compact.showPagination && (
          <div className="pagination">
            <span>{t.operations.userCardsPaged}</span>
            <div className="pagination-actions">
              <button
                className="button button-secondary"
                type="button"
                disabled={page.offset === 0}
                onClick={() => setPage(Math.max(0, page.offset - page.limit))}
              >
                {t.feedback.prevPage}
              </button>
              <button
                className="button button-secondary"
                type="button"
                disabled={!user.cards?.has_more}
                onClick={() => setPage(page.offset + page.limit)}
              >
                {t.feedback.nextPage}
              </button>
            </div>
          </div>
        )}
      </section>
      <TransactionsSection
        query={txQuery}
        page={txPage}
        setPage={setTxPage}
        showCardColumn
        locale={locale}
        t={t}
      />
    </div>
  );
}

function TransactionsSection({
  query,
  page,
  setPage,
  showCardColumn = false,
  locale,
  t,
}: {
  query: {
    isPending: boolean;
    isError: boolean;
    error: unknown;
    data?: Page<AdminTransaction>;
    refetch: () => Promise<unknown>;
  };
  page: PageQuery;
  setPage: (offset: number) => void;
  showCardColumn?: boolean;
  locale: 'ru' | 'kk';
  t: ReturnType<typeof useAdminTranslation>;
}) {
  const items = Array.isArray(query.data?.items) ? query.data.items : [];
  const hasMore = Boolean(query.data?.has_more);
  const compact = useCompactRows(items);

  return (
    <section className="surface-card">
      <div className="section-heading">
        <h2>{t.operations.transactionsTitle}</h2>
      </div>
      {query.isPending ? (
        <p className="table-empty">{t.operations.loadingTransactions}</p>
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      ) : items.length === 0 ? (
        <p className="table-empty">{t.operations.transactionsEmpty}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.operations.colTxDate}</th>
                {showCardColumn && <th>{t.operations.colCard}</th>}
                <th>{t.operations.colTxType}</th>
                <th className="align-right">{t.operations.colTxAmount}</th>
                <th className="align-right">{t.operations.colTxBalanceAfter}</th>
              </tr>
            </thead>
            <tbody id={compact.bodyId}>
              {compact.visibleRows.map(tx => {
                const isAccrual = tx.type === 'accrual';
                const isRedemption = tx.type === 'redemption';
                const tone = isAccrual ? 'positive' : isRedemption ? 'negative' : 'neutral';
                const typeLabel = isAccrual
                  ? t.operations.txTypeAccrual
                  : isRedemption
                  ? t.operations.txTypeRedemption
                  : tx.type;
                const cleanAmount = formatBalance(tx.amount.replace(/^[+-]/, ''));
                const sign = isAccrual
                  ? '+'
                  : isRedemption
                  ? '−'
                  : tx.amount.startsWith('-')
                  ? '−'
                  : '';
                return (
                  <tr key={tx.id}>
                    <td>
                      <time dateTime={tx.occurred_at}>{formatDate(tx.occurred_at, locale)}</time>
                    </td>
                    {showCardColumn && (
                      <td>
                        <Link className="table-name mono-value" to={`/admin/cards/${encodeURIComponent(tx.card_id)}`}>
                          {tx.barcode}
                          <span>{tx.business_name}</span>
                        </Link>
                      </td>
                    )}
                    <td>
                      <StatusPill tone={tone}>{typeLabel}</StatusPill>
                    </td>
                    <td className="align-right">
                      <span className="numeric-value">{`${sign}${cleanAmount}`}</span>
                    </td>
                    <td className="align-right">
                      <span className="numeric-value">{formatBalance(tx.balance_after)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <CompactTableToggle {...compact} />
      {(items.length > 0 || page.offset > 0) && compact.showPagination && (
        <Pagination
          page={{
            ...page,
            has_more: hasMore,
            total: query.data?.total ?? (!hasMore && items.length > 0 ? page.offset + items.length : undefined),
          }}
          onChange={setPage}
        />
      )}
    </section>
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
