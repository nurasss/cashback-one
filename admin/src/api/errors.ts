export type ConflictKind =
  | 'turnover_overlap'
  | 'level_exists'
  | 'priority_exists'
  | 'limit_reached';

export type ValidationHint =
  | 'starts_at_past'
  | 'ends_at_order'
  | 'invalid_year'
  | 'turnover_order';

export type SafeErrorField =
  | 'level'
  | 'min_turnover'
  | 'max_turnover'
  | 'percent'
  | 'starts_at'
  | 'ends_at'
  | 'sort_order'
  | 'image_url'
  | 'title'
  | 'name'
  | 'name_ru'
  | 'name_kk'
  | 'description_ru'
  | 'description_kk'
  | 'is_active';

export interface OverlapConflictItem {
  level?: number;
  name_ru?: string | null;
  name_kk?: string | null;
  min: string;
  max: string | null;
}

export interface LoyaltyScaleConflictItem {
  tier_id: string;
  other_tier_id: string;
  levels?: readonly [number, number];
  fields: readonly SafeErrorField[];
}

export interface SafeErrorDetail {
  reason?: string;
  periodMin?: string;
  periodMax?: string;
  currentVersion?: number;
  tierId?: string;
  tierIds?: readonly string[];
  conflictKind?: ConflictKind;
  overlapRange?: { min: string; max: string | null };
  overlapConflicts?: readonly OverlapConflictItem[];
  scaleConflicts?: readonly LoyaltyScaleConflictItem[];
  validationHint?: ValidationHint;
  fields?: readonly SafeErrorField[];
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    readonly status = 0,
    readonly detail?: SafeErrorDetail,
  ) {
    super(code);
    this.name = 'ApiError';
  }
}

export function isRetryableNetworkError(error: unknown): boolean {
  return error instanceof ApiError
    && (error.code === 'NETWORK_UNAVAILABLE' || error.code === 'REQUEST_TIMEOUT');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

const VALIDATION_FIELD_PATTERNS: ReadonlyArray<{ field: SafeErrorField; pattern: RegExp }> = [
  { field: 'level', pattern: /\blevel\b/i },
  { field: 'min_turnover', pattern: /\bmin_turnover\b/i },
  { field: 'max_turnover', pattern: /\bmax_turnover\b/i },
  { field: 'percent', pattern: /\bpercent\b/i },
  { field: 'starts_at', pattern: /\bstarts_at\b/i },
  { field: 'ends_at', pattern: /\bends_at\b/i },
  { field: 'sort_order', pattern: /\bsort_order\b/i },
  { field: 'image_url', pattern: /\bimage_url\b/i },
  { field: 'title', pattern: /\btitle\b/i },
  { field: 'name_ru', pattern: /\bname_ru\b/i },
  { field: 'name_kk', pattern: /\bname_kk\b/i },
  { field: 'description_ru', pattern: /\bdescription_ru\b/i },
  { field: 'description_kk', pattern: /\bdescription_kk\b/i },
  { field: 'is_active', pattern: /\bis_active\b/i },
  { field: 'name', pattern: /\bname\b/i },
];

const SAFE_ERROR_FIELDS = new Set<SafeErrorField>([
  'level',
  'min_turnover',
  'max_turnover',
  'percent',
  'starts_at',
  'ends_at',
  'sort_order',
  'image_url',
  'title',
  'name',
  'name_ru',
  'name_kk',
  'description_ru',
  'description_kk',
  'is_active',
]);

function filterSafeFields(raw: unknown): SafeErrorField[] {
  if (!Array.isArray(raw)) return [];
  const out = new Set<SafeErrorField>();
  for (const item of raw) {
    if (typeof item !== 'string') continue;
    const normalized = /^tiers\[\d+\]\.([a-z_]+)$/.exec(item)?.[1] ?? item;
    if (SAFE_ERROR_FIELDS.has(normalized as SafeErrorField)) {
      out.add(normalized as SafeErrorField);
    }
  }
  return [...out];
}

function parseScaleConflicts(rawConflicts: unknown): LoyaltyScaleConflictItem[] {
  if (!Array.isArray(rawConflicts)) return [];
  const items: LoyaltyScaleConflictItem[] = [];
  for (const entry of rawConflicts) {
    if (!isRecord(entry)) continue;
    const tierId = typeof entry.tier_id === 'string' ? entry.tier_id : '';
    const otherTierId = typeof entry.other_tier_id === 'string' ? entry.other_tier_id : '';
    if (!tierId || !otherTierId) continue;
    const rawLevels = entry.levels;
    const levels = Array.isArray(rawLevels)
      && rawLevels.length === 2
      && typeof rawLevels[0] === 'number'
      && typeof rawLevels[1] === 'number'
      ? ([rawLevels[0], rawLevels[1]] as const)
      : undefined;
    items.push({
      tier_id: tierId,
      other_tier_id: otherTierId,
      ...(levels ? { levels } : {}),
      fields: filterSafeFields(entry.fields),
    });
  }
  return items;
}

function parseStructuredConflicts(rawConflicts: unknown): OverlapConflictItem[] {
  if (!Array.isArray(rawConflicts)) return [];
  const items: OverlapConflictItem[] = [];
  for (const entry of rawConflicts) {
    if (!isRecord(entry)) continue;
    const min = typeof entry.min_turnover === 'string' || typeof entry.min_turnover === 'number'
      ? String(entry.min_turnover)
      : null;
    if (min === null) continue;
    const max = entry.max_turnover === null || entry.max_turnover === undefined
      ? null
      : typeof entry.max_turnover === 'string' || typeof entry.max_turnover === 'number'
        ? String(entry.max_turnover)
        : null;
    items.push({
      ...(typeof entry.level === 'number' ? { level: entry.level } : {}),
      name_ru: typeof entry.name_ru === 'string' ? entry.name_ru : null,
      name_kk: typeof entry.name_kk === 'string' ? entry.name_kk : null,
      min,
      max,
    });
  }
  return items;
}

function extractSafeDetail(
  code: string,
  rawMessage: string,
  envelope: Record<string, unknown> | null,
): SafeErrorDetail | undefined {
  const reason = typeof envelope?.reason === 'string' && /^[A-Z0-9_]{1,64}$/.test(envelope.reason)
    ? envelope.reason
    : undefined;

  if (code === 'CONFLICT') {
    const structuredConflicts = parseStructuredConflicts(envelope?.conflicts);
    const scaleConflicts = parseScaleConflicts(envelope?.conflicts);
    const structuredFields = filterSafeFields(envelope?.fields);

    if (reason === 'LOYALTY_SCALE_VERSION_CONFLICT') {
      const currentVersion =
        typeof envelope?.current_version === 'number' && Number.isInteger(envelope.current_version)
          ? envelope.current_version
          : undefined;
      return {
        reason,
        ...(currentVersion !== undefined ? { currentVersion } : {}),
      };
    }

    if (reason === 'LOYALTY_SCALE_RANGE_OVERLAP') {
      const unionFields = new Set<SafeErrorField>(structuredFields);
      for (const item of scaleConflicts) {
        for (const f of item.fields) unionFields.add(f);
      }
      if (unionFields.size === 0) {
        unionFields.add('min_turnover');
        unionFields.add('max_turnover');
      }
      return {
        reason,
        conflictKind: 'turnover_overlap',
        fields: [...unionFields],
        ...(scaleConflicts.length > 0 ? { scaleConflicts } : {}),
      };
    }

    if (reason === 'LOYALTY_TIER_RANGE_OVERLAP' || structuredConflicts.length > 0) {
      const first = structuredConflicts[0];
      return {
        ...(reason ? { reason } : {}),
        conflictKind: 'turnover_overlap',
        fields: structuredFields.length > 0 ? structuredFields : ['min_turnover', 'max_turnover'],
        ...(first ? { overlapRange: { min: first.min, max: first.max } } : {}),
        ...(structuredConflicts.length > 0 ? { overlapConflicts: structuredConflicts } : {}),
      };
    }

    if (rawMessage && /overlaps with tier/i.test(rawMessage)) {
      const rangeMatch = /\[([0-9]+(?:\.[0-9]+)?);\s*([0-9]+(?:\.[0-9]+)?|∞)\)\s*$/.exec(rawMessage);
      return {
        ...(reason ? { reason } : {}),
        conflictKind: 'turnover_overlap',
        fields: ['min_turnover', 'max_turnover'],
        ...(rangeMatch && rangeMatch[1]
          ? {
              overlapRange: {
                min: rangeMatch[1],
                max: rangeMatch[2] && rangeMatch[2] !== '∞' ? rangeMatch[2] : null,
              },
            }
          : {}),
      };
    }
    if (rawMessage && /tier with level \d+ already exists/i.test(rawMessage)) {
      return { ...(reason ? { reason } : {}), conflictKind: 'level_exists', fields: ['level'] };
    }
    if (rawMessage && /tier with priority \d+ already exists/i.test(rawMessage)) {
      return { ...(reason ? { reason } : {}), conflictKind: 'priority_exists' };
    }
    if (rawMessage && /maximum number of loyalty tiers reached/i.test(rawMessage)) {
      return { ...(reason ? { reason } : {}), conflictKind: 'limit_reached' };
    }
    return reason ? { reason } : undefined;
  }

  if (code === 'VALIDATION_ERROR') {
    const fields = new Set<SafeErrorField>(filterSafeFields(envelope?.fields));
    if (rawMessage) {
      for (const entry of VALIDATION_FIELD_PATTERNS) {
        if (entry.pattern.test(rawMessage)) {
          fields.add(entry.field);
        }
      }
    }

    let validationHint: ValidationHint | undefined;
    if (rawMessage && /starts_at cannot be in the past/i.test(rawMessage)) {
      validationHint = 'starts_at_past';
      fields.add('starts_at');
    } else if (rawMessage && /ends_at must be after starts_at/i.test(rawMessage)) {
      validationHint = 'ends_at_order';
      fields.add('ends_at');
    } else if (rawMessage && /четыр[её]х цифр/i.test(rawMessage)) {
      validationHint = 'invalid_year';
    } else if (rawMessage && /max_turnover must be greater than min_turnover/i.test(rawMessage)) {
      validationHint = 'turnover_order';
      fields.add('max_turnover');
    }

    const tierId = typeof envelope?.tier_id === 'string' ? envelope.tier_id : undefined;
    const tierIds = Array.isArray(envelope?.tier_ids)
      ? envelope.tier_ids.filter((id): id is string => typeof id === 'string' && id.length > 0)
      : undefined;

    if (!reason && !validationHint && fields.size === 0 && !tierId && (!tierIds || tierIds.length === 0)) {
      return undefined;
    }
    return {
      ...(reason ? { reason } : {}),
      ...(tierId ? { tierId } : {}),
      ...(tierIds && tierIds.length > 0 ? { tierIds } : {}),
      ...(validationHint ? { validationHint } : {}),
      ...(fields.size > 0 ? { fields: [...fields] } : {}),
    };
  }

  const periodMin = typeof envelope?.period_min === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(envelope.period_min)
    ? envelope.period_min
    : undefined;
  const periodMax = typeof envelope?.period_max === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(envelope.period_max)
    ? envelope.period_max
    : undefined;
  if (!reason && !periodMin && !periodMax) return undefined;
  return {
    ...(reason ? { reason } : {}),
    ...(periodMin ? { periodMin } : {}),
    ...(periodMax ? { periodMax } : {}),
  };
}

export function errorFromResponse(status: number, payload: unknown): ApiError {
  const envelope = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  const candidate = envelope?.code;
  const code = typeof candidate === 'string' && /^[A-Z0-9_]{1,64}$/.test(candidate)
    ? candidate
    : status === 409
      ? 'CONFLICT'
      : status === 413
        ? 'FILE_TOO_LARGE'
        : status === 415
          ? 'UNSUPPORTED_MEDIA_TYPE'
          : status >= 500
            ? 'SERVER_UNAVAILABLE'
            : 'UNKNOWN_ERROR';
  const rawMessage = typeof envelope?.message === 'string' ? envelope.message : '';
  const detail = extractSafeDetail(code, rawMessage, envelope);
  return new ApiError(code, status, detail);
}

const ruMessages: Record<string, string> = {
  CONFIG_MISSING: 'Сервис ещё не подключён. Обратитесь к администратору.',
  INVALID_API_URL: 'Не удалось настроить подключение к сервису.',
  INSECURE_TRANSPORT: 'Для сервиса требуется защищённое подключение HTTPS.',
  INVALID_CREDENTIALS: 'Неверный логин или пароль.',
  ADMIN_UNAUTHENTICATED: 'Сессия завершена. Войдите снова.',
  ADMIN_FORBIDDEN: 'У вашей учётной записи нет доступа к этому разделу.',
  ADMIN_RESOURCE_NOT_FOUND: 'Запись не найдена.',
  ADMIN_AGENT_REVOKED: 'Отключённому агенту нельзя менять ключ или ставить команды.',
  ADMIN_RESYNC_ALREADY_PENDING: 'Для агента уже есть активный запрос синхронизации.',
  ADMIN_CARD_ALREADY_UNBOUND: 'Карта уже отвязана.',
  ADMIN_RATE_LIMITED: 'Слишком много попыток. Попробуйте позже.',
  ADMIN_REQUEST_TOO_LARGE: 'Данные слишком большие. Уменьшите размер и повторите запрос.',
  ADMIN_CSRF_BLOCKED: 'Не удалось проверить запрос. Обновите страницу.',
  ADMIN_ORIGIN_FORBIDDEN: 'Подключение с этого адреса запрещено.',
  AUTH_RATE_LIMIT_UNAVAILABLE: 'Сервис входа временно недоступен.',
  CONFLICT: 'Конфликт с уже существующими данными. Проверьте значения и повторите.',
  VALIDATION_ERROR: 'Проверьте заполненные поля.',
  ADMIN_PERIOD_TOO_LARGE: 'Выберите более короткий период.',
  ADMIN_INVALID_PERIOD: 'Ошибка в указанном периоде: дата начала должна быть не позже даты окончания, а обе даты — не позже сегодняшнего дня по Астане.',
  FILE_TOO_LARGE: 'Файл слишком большой. Максимальный размер — 10 МиБ.',
  VIDEO_TOO_LARGE: 'Размер видео превышает допустимый лимит 15 МиБ.',
  VIDEO_DURATION_EXCEEDED: 'Длительность видео превышает допустимый лимит (не более 5 секунд).',
  VIDEO_HAS_AUDIO: 'Видео для заставки должно быть без аудиодорожки (звук запрещён).',
  VIDEO_UNSUPPORTED_CODEC: 'Поддерживается только видео с кодеком H.264 (avc1).',
  VIDEO_CORRUPTED: 'Видеофайл повреждён или не может быть декодирован.',
  VIDEO_VALIDATION_UNAVAILABLE: 'Серверная проверка видео временно недоступна. Попробуйте позже.',
  IMAGE_TOO_LARGE: 'Размер файла (до 5 МиБ для заставки) или разрешение изображения (до 40 Мп) слишком велики.',
  UNSUPPORTED_MEDIA_TYPE: 'Неподдерживаемый формат изображения. Загрузите JPEG, PNG, WebP или GIF.',
  MEDIA_STORAGE_ERROR: 'Не удалось сохранить изображение в хранилище. Попробуйте позже.',
  MEDIA_STORAGE_NOT_CONFIGURED: 'Хранилище медиафайлов ещё не настроено на сервере.',
  NETWORK_UNAVAILABLE: 'Нет соединения. Проверьте интернет и повторите запрос.',
  REQUEST_TIMEOUT: 'Сервер не ответил вовремя. Повторите запрос.',
  SERVER_UNAVAILABLE: 'Сервис временно недоступен. Попробуйте позже.',
  SESSION_CHANGED: 'Сессия изменилась. Обновите страницу.',
  INVALID_RESPONSE: 'Не удалось прочитать ответ сервера.',
  UNKNOWN_ERROR: 'Произошла ошибка. Повторите запрос.',
};

const kkMessages: Record<string, string> = {
  CONFIG_MISSING: 'Қызмет әлі қосылмаған. Әкімшіге хабарласыңыз.',
  INVALID_API_URL: 'Қызметке қосылуды баптау мүмкін болмады.',
  INSECURE_TRANSPORT: 'Қызмет үшін HTTPS қорғалған байланыс қажет.',
  INVALID_CREDENTIALS: 'Қате логин немесе құпиясөз.',
  ADMIN_UNAUTHENTICATED: 'Сессия аяқталды. Қайта кіріңіз.',
  ADMIN_FORBIDDEN: 'Тіркелгіңізде бұл бөлімге кіруге рұқсат жоқ.',
  ADMIN_RESOURCE_NOT_FOUND: 'Жазба табылмады.',
  ADMIN_AGENT_REVOKED: 'Өшірілген агенттің кілтін өзгертуге немесе оған команда беруге болмайды.',
  ADMIN_RESYNC_ALREADY_PENDING: 'Агент үшін белсенді синхрондау сұранысы бар.',
  ADMIN_CARD_ALREADY_UNBOUND: 'Карта байланысы бұрыннан ажыратылған.',
  ADMIN_RATE_LIMITED: 'Әрекеттер тым көп. Кейінірек қайталап көріңіз.',
  ADMIN_REQUEST_TOO_LARGE: 'Деректер көлемі тым үлкен. Өлшемін азайтып, қайталаңыз.',
  ADMIN_CSRF_BLOCKED: 'Сұранысты тексеру мүмкін болмады. Бетті жаңартыңыз.',
  ADMIN_ORIGIN_FORBIDDEN: 'Бұл мекенжайдан қосылуға тыйым салынған.',
  AUTH_RATE_LIMIT_UNAVAILABLE: 'Кіру қызметі уақытша қолжетімсіз.',
  CONFLICT: 'Қолданыстағы деректермен қайшылық. Мәндерді тексеріп қайталаңыз.',
  VALIDATION_ERROR: 'Толтырылған өрістерді тексеріңіз.',
  ADMIN_PERIOD_TOO_LARGE: 'Қысқарақ кезеңді таңдаңыз.',
  ADMIN_INVALID_PERIOD: 'Көрсетілген кезеңде қате бар: басталу күні аяқталу күнінен кеш болмауы, ал екі күн де Астана уақыты бойынша бүгіннен кеш болмауы тиіс.',
  FILE_TOO_LARGE: 'Файл тым үлкен. Ең жоғары өлшемі — 10 МиБ.',
  VIDEO_TOO_LARGE: 'Бейне өлшемі рұқсат етілген 15 МиБ шегінен асты.',
  VIDEO_DURATION_EXCEEDED: 'Бейне ұзақтығы рұқсат етілген шектен асады (5 секундтан аспауы керек).',
  VIDEO_HAS_AUDIO: 'Қосымша заставкасына арналған бейнеде дыбыс болмауы керек (дыбысқа тыйым салынған).',
  VIDEO_UNSUPPORTED_CODEC: 'Тек H.264 (avc1) кодегі бар бейнеге қолдау көрсетіледі.',
  VIDEO_CORRUPTED: 'Бейне файл зақымдалған немесе оқу мүмкін емес.',
  VIDEO_VALIDATION_UNAVAILABLE: 'Серверлік бейне тексеру уақытша қолжетімсіз. Кейінірек көріңіз.',
  IMAGE_TOO_LARGE: 'Файл өлшемі (заставка үшін 5 МиБ дейін) немесе сурет ажыратымдылығы (40 Мп дейін) тым үлкен.',
  UNSUPPORTED_MEDIA_TYPE: 'Суреттің қолдау көрсетілмейтін форматы. JPEG, PNG, WebP немесе GIF жүктеңіз.',
  MEDIA_STORAGE_ERROR: 'Суретті қоймаға сақтау мүмкін болмады. Кейінірек көріңіз.',
  MEDIA_STORAGE_NOT_CONFIGURED: 'Медиа файл қоймасы серверде әлі бапталмаған.',
  NETWORK_UNAVAILABLE: 'Байланыс жоқ. Интернетті тексеріп, қайталаңыз.',
  REQUEST_TIMEOUT: 'Сервер уақытында жауап бермеді. Қайталаңыз.',
  SERVER_UNAVAILABLE: 'Қызмет уақытша қолжетімсіз. Кейінірек көріңіз.',
  SESSION_CHANGED: 'Сессия өзгерді. Бетті жаңартыңыз.',
  INVALID_RESPONSE: 'Сервер жауабын оқу мүмкін болмады.',
  UNKNOWN_ERROR: 'Қате орын алды. Қайталап көріңіз.',
};

function formatNumericText(raw: string, locale: 'ru' | 'kk'): string {
  const num = Number(raw);
  if (!Number.isFinite(num)) return raw;
  return num.toLocaleString(locale === 'kk' ? 'kk-KZ' : 'ru-RU');
}

export function messageForError(error: unknown, locale: 'ru' | 'kk' = 'ru'): string {
  if (error instanceof ApiError) {
    const reason = error.detail?.reason;
    if (error.code === 'CONFLICT' && reason === 'LOYALTY_SCALE_VERSION_CONFLICT') {
      const ver = error.detail?.currentVersion;
      if (locale === 'kk') {
        return ver != null
          ? `Шкала серверде өзгертілген (өзекті нұсқа: v${ver}). Сақталмаған түзетулеріңіз сақталды — өзекті шкаланы жүктеп, қайта сақтаңыз.`
          : 'Шкала басқа сессияда өзгертілген. Өзекті шкаланы жүктеп, қайта сақтаңыз.';
      }
      return ver != null
        ? `Шкала статусов изменилась на сервере (актуальная версия: v${ver}). Ваши несохранённые правки сохранены в форме — загрузите актуальную шкалу и повторите сохранение.`
        : 'Шкала статусов была изменена в другой сессии. Загрузите актуальную шкалу и повторите сохранение.';
    }

    if (error.code === 'CONFLICT' && reason === 'LOYALTY_SCALE_RANGE_OVERLAP') {
      const pairs = (error.detail?.scaleConflicts ?? [])
        .map(item => (item.levels ? `#${item.levels[0]} ↔ #${item.levels[1]}` : ''))
        .filter(Boolean)
        .join(', ');
      return locale === 'kk'
        ? `Белсенді деңгейлердің айналым ауқымдары қиылысады${pairs ? ` (${pairs})` : ''}. Бөлектелген шектерді түзетіп, қайта сақтаңыз.`
        : `Диапазоны активных уровней пересекаются${pairs ? ` (${pairs})` : ''}. Исправьте выделенные границы оборота и повторите сохранение.`;
    }

    if (error.code === 'VALIDATION_ERROR' && reason) {
      if (reason === 'LOYALTY_SCALE_INVALID_RANGE') {
        return locale === 'kk'
          ? 'Айналым ауқымы қате: ең аз шек теріс болмауы тиіс, ал ең көп шек ең аздан қатаң түрде үлкен болуы керек.'
          : 'Некорректный диапазон оборота: минимальный порог не может быть отрицательным, а максимальный должен быть строго больше минимального.';
      }
      if (reason === 'LOYALTY_SCALE_INCOMPLETE') {
        return locale === 'kk'
          ? 'Шкалаға бизнестің барлық қолданыстағы деңгейлері қалдырылмай енгізілуі тиіс. Өзекті шкаланы жүктеп, қайталап көріңіз.'
          : 'В шкалу должны быть включены все существующие уровни бизнеса без пропусков. Загрузите актуальную шкалу и попробуйте снова.';
      }
      if (reason === 'LOYALTY_SCALE_UNKNOWN_TIER') {
        return locale === 'kk'
          ? 'Деңгейлердің бірі табылмады немесе бұл бизнеске тиесілі емес. Өзекті шкаланы жүктеңіз.'
          : 'Один из уровней не найден или больше не относится к этому бизнесу. Загрузите актуальную шкалу.';
      }
      if (reason === 'LOYALTY_SCALE_DUPLICATE_TIER') {
        return locale === 'kk'
          ? 'Шкала тізімінде қайталанатын деңгей табылды. Өзекті шкаланы жүктеп, қайта сақтаңыз.'
          : 'В списке шкалы обнаружен дублирующийся уровень. Загрузите актуальную шкалу и повторите сохранение.';
      }
    }

    if (error.code === 'CONFLICT' && error.detail?.conflictKind) {
      if (error.detail.conflictKind === 'turnover_overlap') {
        const conflicts = error.detail.overlapConflicts;
        if (conflicts && conflicts.length > 0) {
          const itemsText = conflicts
            .map(item => {
              const name = locale === 'kk'
                ? (item.name_kk || item.name_ru)
                : (item.name_ru || item.name_kk);
              const bounds = item.max !== null
                ? `[${formatNumericText(item.min, locale)}; ${formatNumericText(item.max, locale)})`
                : `[${formatNumericText(item.min, locale)}; ∞)`;
              return name ? `«${name}» ${bounds}` : bounds;
            })
            .join(', ');
          return locale === 'kk'
            ? `Айналым ауқымы басқа белсенді дәрежемен қиылысады: ${itemsText}. Алдымен қиылысатын дәрежені өзгертіңіз немесе өшіріңіз, не бос аралықты таңдаңыз.`
            : `Диапазон оборота пересекается с активным статусом: ${itemsText}. Сначала измените или отключите пересекающийся статус, либо выберите свободный интервал.`;
        }
        const range = error.detail.overlapRange;
        const formattedRange = range
          ? range.max !== null
            ? `${formatNumericText(range.min, locale)} – ${formatNumericText(range.max, locale)} ₸`
            : `${formatNumericText(range.min, locale)} ₸+`
          : '';
        return locale === 'kk'
          ? `Айналым ауқымы басқа белсенді дәрежемен${formattedRange ? ` (${formattedRange})` : ''} қиылысады. Алдымен қиылысатын дәрежені өзгертіңіз немесе өшіріңіз, не бос аралықты таңдаңыз.`
          : `Диапазон оборота пересекается с другим активным статусом${formattedRange ? ` (${formattedRange})` : ''}. Сначала измените или отключите пересекающийся статус, либо выберите свободный интервал.`;
      }
      if (error.detail.conflictKind === 'level_exists') {
        return locale === 'kk'
          ? 'Мұндай деңгей нөмірі бар дәреже бұрыннан бар.'
          : 'Статус с таким номером уровня уже существует.';
      }
      if (error.detail.conflictKind === 'priority_exists') {
        return locale === 'kk'
          ? 'Мұндай басымдығы бар дәреже бұрыннан бар.'
          : 'Статус с таким приоритетом уже существует.';
      }
      if (error.detail.conflictKind === 'limit_reached') {
        return locale === 'kk'
          ? 'Дәрежелердің ең көп санына жетті.'
          : 'Достигнуто максимальное количество статусов.';
      }
    }

    if (error.code === 'VALIDATION_ERROR' && error.detail?.validationHint) {
      if (error.detail.validationHint === 'starts_at_past') {
        return locale === 'kk'
          ? 'Көрсету басы өткен шақта болмауы керек. Болашақ күнді таңдаңыз немесе «Қазір бастау» режимін қосыңыз.'
          : 'Дата начала показа не может быть в прошлом. Выберите будущую дату или включите «Начать сейчас».';
      }
      if (error.detail.validationHint === 'ends_at_order') {
        return locale === 'kk'
          ? 'Көрсету соңы басталуынан қатаң түрде кейін болуы керек.'
          : 'Конец показа должен быть строго позже начала.';
      }
      if (error.detail.validationHint === 'invalid_year') {
        return locale === 'kk'
          ? 'Төрт таңбалы жылы бар дұрыс күнді көрсетіңіз (2000–2100).'
          : 'Укажите корректную дату с четырёхзначным годом (2000–2100).';
      }
      if (error.detail.validationHint === 'turnover_order') {
        return locale === 'kk'
          ? 'Максималды айналым минималды айналымнан үлкен болуы керек.'
          : 'Максимальный оборот должен быть строго больше минимального.';
      }
    }
  }

  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const dict = locale === 'kk' ? kkMessages : ruMessages;
  return dict[code] ?? dict.UNKNOWN_ERROR!;
}
