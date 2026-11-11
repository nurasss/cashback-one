export class ApiError extends Error {
  constructor(readonly code: string, readonly status = 0) {
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

export function errorFromResponse(status: number, payload: unknown): ApiError {
  const envelope = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  const candidate = envelope?.code;
  const code = typeof candidate === 'string' && /^[A-Z0-9_]{1,64}$/.test(candidate)
    ? candidate
    : status === 413
      ? 'FILE_TOO_LARGE'
      : status === 415
        ? 'UNSUPPORTED_MEDIA_TYPE'
        : status >= 500
          ? 'SERVER_UNAVAILABLE'
          : 'UNKNOWN_ERROR';
  return new ApiError(code, status);
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
  VALIDATION_ERROR: 'Проверьте заполненные поля.',
  ADMIN_PERIOD_TOO_LARGE: 'Выберите более короткий период.',
  ADMIN_INVALID_PERIOD: 'Проверьте даты периода.',
  FILE_TOO_LARGE: 'Файл слишком большой. Максимальный размер — 10 МБ.',
  VIDEO_TOO_LARGE: 'Размер видео превышает допустимый лимит 15 МБ.',
  VIDEO_DURATION_EXCEEDED: 'Длительность видео превышает допустимый лимит (не более 5 секунд).',
  VIDEO_HAS_AUDIO: 'Видео для заставки должно быть без аудиодорожки (звук запрещён).',
  VIDEO_UNSUPPORTED_CODEC: 'Поддерживается только видео с кодеком H.264 (avc1).',
  VIDEO_CORRUPTED: 'Видеофайл повреждён или не может быть декодирован.',
  VIDEO_VALIDATION_UNAVAILABLE: 'Серверная проверка видео временно недоступна. Попробуйте позже.',
  IMAGE_TOO_LARGE: 'Разрешение изображения слишком велико. Уменьшите картинку.',
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
  VALIDATION_ERROR: 'Толтырылған өрістерді тексеріңіз.',
  ADMIN_PERIOD_TOO_LARGE: 'Қысқарақ кезеңді таңдаңыз.',
  ADMIN_INVALID_PERIOD: 'Кезең күндерін тексеріңіз.',
  FILE_TOO_LARGE: 'Файл тым үлкен. Ең жоғары өлшемі — 10 МБ.',
  VIDEO_TOO_LARGE: 'Бейне өлшемі рұқсат етілген 15 МБ шегінен асты.',
  VIDEO_DURATION_EXCEEDED: 'Бейне ұзақтығы рұқсат етілген шектен асады (5 секундтан аспауы керек).',
  VIDEO_HAS_AUDIO: 'Қосымша заставкасына арналған бейнеде дыбыс болмауы керек (дыбысқа тыйым салынған).',
  VIDEO_UNSUPPORTED_CODEC: 'Тек H.264 (avc1) кодегі бар бейнеге қолдау көрсетіледі.',
  VIDEO_CORRUPTED: 'Бейне файл зақымдалған немесе оқу мүмкін емес.',
  VIDEO_VALIDATION_UNAVAILABLE: 'Серверлік бейне тексеру уақытша қолжетімсіз. Кейінірек көріңіз.',
  IMAGE_TOO_LARGE: 'Сурет өлшемі тым үлкен. Кескінді кішірейтіңіз.',
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

export function messageForError(error: unknown, locale: 'ru' | 'kk' = 'ru'): string {
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const dict = locale === 'kk' ? kkMessages : ruMessages;
  return dict[code] ?? dict.UNKNOWN_ERROR!;
}
