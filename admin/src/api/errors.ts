export class ApiError extends Error {
  constructor(readonly code: string, readonly status = 0) {
    super(code);
    this.name = 'ApiError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function errorFromResponse(status: number, payload: unknown): ApiError {
  const envelope = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  const candidate = envelope?.code;
  const code = typeof candidate === 'string' && /^[A-Z0-9_]{1,64}$/.test(candidate)
    ? candidate
    : status >= 500 ? 'SERVER_UNAVAILABLE' : 'UNKNOWN_ERROR';
  return new ApiError(code, status);
}

const messages: Record<string, string> = {
  CONFIG_MISSING: 'Сервис ещё не подключён. Обратитесь к администратору.',
  INVALID_API_URL: 'Не удалось настроить подключение к сервису.',
  INSECURE_TRANSPORT: 'Для сервиса требуется защищённое подключение HTTPS.',
  INVALID_CREDENTIALS: 'Неверный логин или пароль.',
  ADMIN_UNAUTHENTICATED: 'Сессия завершена. Войдите снова.',
  ADMIN_FORBIDDEN: 'У вашей учётной записи нет доступа к этому разделу.',
  ADMIN_RESOURCE_NOT_FOUND: 'Запись не найдена.',
  ADMIN_RATE_LIMITED: 'Слишком много попыток. Попробуйте позже.',
  ADMIN_CSRF_BLOCKED: 'Не удалось проверить запрос. Обновите страницу.',
  ADMIN_ORIGIN_FORBIDDEN: 'Подключение с этого адреса запрещено.',
  AUTH_RATE_LIMIT_UNAVAILABLE: 'Сервис входа временно недоступен.',
  VALIDATION_ERROR: 'Проверьте заполненные поля.',
  ADMIN_PERIOD_TOO_LARGE: 'Выберите более короткий период.',
  ADMIN_INVALID_PERIOD: 'Проверьте даты периода.',
  NETWORK_UNAVAILABLE: 'Нет соединения. Проверьте интернет и повторите запрос.',
  REQUEST_TIMEOUT: 'Сервер не ответил вовремя. Повторите запрос.',
  SERVER_UNAVAILABLE: 'Сервис временно недоступен. Попробуйте позже.',
  SESSION_CHANGED: 'Сессия изменилась. Обновите страницу.',
  INVALID_RESPONSE: 'Не удалось прочитать ответ сервера.',
  UNKNOWN_ERROR: 'Произошла ошибка. Повторите запрос.',
};

export function messageForError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  return messages[code] ?? messages.UNKNOWN_ERROR!;
}
