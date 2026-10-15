# Wappi: отправка сообщений (исходящий WhatsApp)

Используется для одноразового кода входа и кода подтверждения списания на кассе.

```
POST {WAPPI_API_BASE_URL}/api/sync/message/send?profile_id={WAPPI_SENDER_PROFILE_ID или WAPPI_LOGIN_PROFILE_ID}
Authorization: {WAPPI_API_TOKEN}
Content-Type: application/json

{"recipient": "77001234567", "body": "Код для входа в приложение: 123456 ..."}
```

* Любой HTTP-статус ≥ 400 или сетевая ошибка → `503 WHATSAPP_DELIVERY_UNAVAILABLE`, код не сохраняется.
* Номер получателя и текст сообщения не пишутся в логи (кроме режима `log` для локальной разработки).
* Таймаут: `WAPPI_SEND_TIMEOUT_SECONDS` (10 с).

**Статус: NOT VERIFIED.** Адрес метода и формат тела взяты из публичной документации Wappi и должны быть проверены на рабочем профиле до запуска. Реализация — `backend/app/services/whatsapp_sender.py`.

Режимы `WHATSAPP_PROVIDER_MODE`: `disabled` (по умолчанию), `wappi`, `log` (только разработка, печатает код в лог сервера), `fake` (только тесты).
