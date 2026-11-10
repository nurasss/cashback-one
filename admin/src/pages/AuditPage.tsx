import { useAdminSession } from '../auth/provider';
import { useAudit } from '../api/queries';
import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { useTableExpansion } from '../components/CompactTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

function StateView({
  label,
  value,
  isSuperadmin,
  locale,
}: {
  label: string;
  value: Record<string, unknown> | null;
  isSuperadmin: boolean;
  locale: 'ru' | 'kk';
}) {
  if (!value) return <span className="muted-copy">—</span>;
  if (!isSuperadmin) {
    const summary = summarizeAuditState(value, locale);
    return summary ? <span>{summary}</span> : <span className="muted-copy">—</span>;
  }
  return (
    <details className="audit-state">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function summarizeAuditState(value: Record<string, unknown> | null, locale: 'ru' | 'kk'): string | null {
  if (!value) return null;
  const parts: string[] = [];
  if (value.title_ru || value.title_kk) {
    const title = (locale === 'kk' ? (value.title_kk || value.title_ru) : (value.title_ru || value.title_kk)) as string;
    if (title) parts.push(title);
  } else if (value.title && typeof value.title === 'string') {
    parts.push(value.title);
  } else if (value.name && typeof value.name === 'string') {
    parts.push(value.name);
  }
  if (value.percent !== undefined && value.percent !== null) {
    parts.push(`${value.percent}%`);
  }
  if (value.address && typeof value.address === 'string') {
    parts.push(value.address);
  }
  if (value.barcode && typeof value.barcode === 'string') {
    parts.push(`№ ${value.barcode}`);
  }
  if (value.phone && typeof value.phone === 'string') {
    parts.push(value.phone);
  }
  if (parts.length > 0) return parts.join(', ');
  return null;
}

function describeAuditAction(action: string, locale: 'ru' | 'kk', isSuperadmin = false): string {
  const dict: Record<string, { ru: string; kk: string }> = {
    promotion_created: { ru: 'Создана публикация', kk: 'Жарияланым жасалды' },
    promotion_updated: { ru: 'Изменена акция / баннер', kk: 'Акция / баннер өзгертілді' },
    promotion_deleted: { ru: 'Удалена акция / баннер', kk: 'Акция / баннер жойылды' },
    store_created: { ru: 'Добавлен магазин', kk: 'Дүкен қосылды' },
    store_updated: { ru: 'Изменён адрес магазина', kk: 'Дүкен мекенжайы өзгертілді' },
    store_deleted: { ru: 'Удалён магазин', kk: 'Дүкен жойылды' },
    loyalty_tier_created: { ru: 'Создан статус лояльности', kk: 'Адалдық дәрежесі жасалды' },
    loyalty_tier_updated: { ru: 'Изменён статус лояльности', kk: 'Адалдық дәрежесі өзгертілді' },
    loyalty_tier_deleted: { ru: 'Удалён статус лояльности', kk: 'Адалдық дәрежесі жойылды' },
    business_created: { ru: 'Создан бизнес', kk: 'Бизнес жасалды' },
    business_updated: { ru: 'Обновлены настройки бизнеса', kk: 'Бизнес баптаулары жаңартылды' },
    business_manager_created: { ru: 'Создан управляющий', kk: 'Басқарушы жасалды' },
    business_manager_password_reset: { ru: 'Сброшен пароль управляющего', kk: 'Басқарушы құпия сөзі қалпына келтірілді' },
    business_app_texts_updated: { ru: 'Обновлены тексты приложения', kk: 'Қолданба мәтіндері жаңартылды' },
    business_splash_updated: { ru: 'Обновлены настройки заставки', kk: 'Заставка баптаулары жаңартылды' },
    business_splash_uploaded: { ru: 'Загружена заставка', kk: 'Заставка жүктелді' },
    image_uploaded: { ru: 'Загружена картинка', kk: 'Сурет жүктелді' },
    media_uploaded: { ru: 'Загружен медиафайл', kk: 'Медиа файл жүктелді' },
    agent_created: { ru: 'Создан агент', kk: 'Агент жасалды' },
    agent_registered: { ru: 'Зарегистрирован агент', kk: 'Агент тіркелді' },
    agent_rekeyed: { ru: 'Перевыпущен ключ агента', kk: 'Агент кілті қайта шығарылды' },
    agent_key_rotated: { ru: 'Сменён ключ агента', kk: 'Агент кілті ауыстырылды' },
    agent_revoked: { ru: 'Отозван агент', kk: 'Агент кері қайтарылды' },
    agent_full_resync_requested: { ru: 'Запрошена полная синхронизация', kk: 'Толық синхрондау сұралды' },
    pos_key_created: { ru: 'Создан кассовый ключ', kk: 'Касса кілті жасалды' },
    pos_key_revoked: { ru: 'Отозван кассовый ключ', kk: 'Касса кілті кері қайтарылды' },
    card_unbound: { ru: 'Отвязана карта', kk: 'Карта ажыратылды' },
    notification_created: { ru: 'Создана рассылка', kk: 'Хабарлама жасалды' },
    notification_deleted: { ru: 'Удалена рассылка', kk: 'Хабарлама жойылды' },
  };

  const item = dict[action];
  if (item) return item[locale];
  if (!isSuperadmin) {
    return locale === 'kk' ? 'Жүйедегі басқа әрекет' : 'Другое действие в системе';
  }
  const humanized = action.replace(/_/g, ' ');
  return locale === 'kk' ? `Жүйелік әрекет (${humanized})` : `Системное действие (${humanized})`;
}

function describeAuditEntity(entity: string, locale: 'ru' | 'kk'): string {
  const dict: Record<string, { ru: string; kk: string }> = {
    promotion: { ru: 'Акция / баннер', kk: 'Акция / баннер' },
    business_store: { ru: 'Магазин', kk: 'Дүкен' },
    business_loyalty_tier: { ru: 'Статус лояльности', kk: 'Адалдық дәрежесі' },
    business: { ru: 'Бизнес', kk: 'Бизнес' },
    admin_user: { ru: 'Пользователь', kk: 'Пайдаланушы' },
    agent_command: { ru: 'Команда агента', kk: 'Агент командасы' },
    business_splash_asset: { ru: 'Заставка', kk: 'Заставка' },
    pos_key: { ru: 'Кассовый ключ', kk: 'Касса кілті' },
    card: { ru: 'Карта', kk: 'Карта' },
    agent: { ru: 'Агент', kk: 'Агент' },
    image: { ru: 'Изображение', kk: 'Сурет' },
    notification: { ru: 'Рассылка', kk: 'Хабарлама' },
  };
  const item = dict[entity];
  if (item) return item[locale];
  return entity.replace(/_/g, ' ');
}

function getAuditTargetName(item: AuditItem): string | null {
  const state = item.after_state ?? item.before_state;
  if (!state || typeof state !== 'object') return null;
  const val = (state as Record<string, unknown>).title ??
    (state as Record<string, unknown>).name ??
    (state as Record<string, unknown>).title_ru ??
    (state as Record<string, unknown>).title_kk ??
    (state as Record<string, unknown>).barcode ??
    (state as Record<string, unknown>).key_prefix ?? null;
  if (val && typeof val === 'string') {
    return val;
  }
  return null;
}

export function AuditPage() {
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const expansion = useTableExpansion();
  const query = useAudit(page);
  const isManager = view.status === 'authenticated' && view.admin.role === 'business_manager';
  const isSuperadmin = view.status === 'authenticated' && view.admin.role === 'superadmin';

  return (
    <div className="page-stack">
      <PageHeading
        title={t.audit.title}
        subtitle={
          isManager
            ? t.audit.subtitleScope(view.admin.business?.name ?? '')
            : t.audit.subtitleAll
        }
      />
      <p className="data-note">
        <StatusPill tone="warning">{t.audit.readOnlyBadge}</StatusPill> {t.audit.note}
      </p>
      {query.isPending ? (
        <LoadingPage label={t.audit.loading} />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      ) : query.data?.items.length === 0 && page.offset === 0 ? (
        <EmptyState title={t.audit.emptyTitle} detail={t.audit.emptyDetail} />
      ) : query.data ? (
        <DataTable<AuditItem>
          expansion={expansion}
          page={{ ...page, has_more: query.data.has_more }}
          onPage={setPage}
          rows={query.data.items}
          rowKey={row => row.id}
          columns={[
            {
              key: 'created',
              title: t.audit.colDateTime,
              render: row => <time dateTime={row.created_at}>{formatDate(row.created_at, locale)}</time>,
            },
            { key: 'actor', title: t.audit.colActor, render: row => <span className="cell-primary">{row.actor}</span> },
            {
              key: 'action',
              title: t.audit.colAction,
              render: row => {
                const target = getAuditTargetName(row);
                return (
                  <div>
                    <strong>{describeAuditAction(row.action, locale, isSuperadmin)}</strong>
                    {target && (
                      <div className="muted-copy" style={{ fontSize: '0.8125rem' }}>
                        «{target}»
                      </div>
                    )}
                  </div>
                );
              },
            },
            {
              key: 'entity',
              title: t.audit.colEntity,
              render: row => <span>{describeAuditEntity(row.entity, locale)}</span>,
            },
            { key: 'before', title: t.audit.colBefore, render: row => <StateView label={t.audit.stateShow} value={row.before_state} isSuperadmin={isSuperadmin} locale={locale} /> },
            { key: 'after', title: t.audit.colAfter, render: row => <StateView label={t.audit.stateShow} value={row.after_state} isSuperadmin={isSuperadmin} locale={locale} /> },
          ]}
        />
      ) : null}
    </div>
  );
}
