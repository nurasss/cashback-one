# SMS Provider Contract Specification (TASK-007)

Этот документ определяет контракт абстрактного провайдера доставки SMS для резервной аутентификации (SMS Fallback Authentication Core), семантику обработки сбоев, режим по умолчанию и рекомендации для будущей интеграции конкретного SMS-шлюза.

---

## 1. Статус реализации

> [!IMPORTANT]
> **REAL_SMS_PROVIDER = NOT IMPLEMENTED**
>
> В рамках TASK-007 реализовано исключительно ядро аутентификации (`SMS Fallback Authentication Core`) и контракт провайдера (`SmsProvider` Protocol). Реальный SMS-шлюз (SMSC, Twilio, KazInfoTech или иной оператор) **НЕ подключен**.
> Бэкенд готов к интеграции внешнего вендорного адаптера без изменения доменной логики.

---

## 2. Интерфейс провайдера (`SmsProvider` Protocol)

Провайдер доставки определяется как асинхронный протокол Python в модуле `app/services/sms_provider.py`:

```python
from typing import Protocol

class SmsProvider(Protocol):
    """Abstract SMS delivery provider interface."""

    async def send_otp(self, phone: str, code: str) -> None:
        """Send a one-time verification code to recipient phone number.

        Args:
            phone: Customer phone number in normalized E.164 format (e.g. '+77011234567').
            code: 6-digit verification code string (e.g. '123456').

        Raises:
            AppError: If a controlled application error should be returned directly.
            Exception: Any transport or vendor exception, which will trigger DB rollback
                       and a 503 SMS_DELIVERY_UNAVAILABLE response.
        """
        ...
```

---

## 3. Режимы работы (`SMS_PROVIDER_MODE`)

Режим выбирается через переменную окружения `SMS_PROVIDER_MODE`:

| Режим (`SMS_PROVIDER_MODE`) | Класс провайдера | Разрешенные окружения | Назначение и поведение |
|---|---|---|---|
| `disabled` (по умолчанию) | `DisabledSmsProvider` | `development`, `production`, `test` | Безопасный режим по умолчанию, когда внешний вендор не подключен. При обращении к `/auth/sms/request` немедленно возвращает `503 Service Unavailable` (`SMS_PROVIDER_NOT_CONFIGURED`) до изменения счетчиков rate limiter и создания OTP в БД. |
| `fake` | `FakeSmsProvider` | **Только `test`** | In-memory тестовый fake для юнит/интеграционных тестов. Включение `fake` в `development` или `production` строго запрещено и приводит к немедленной ошибке конфигурации (`ValidationError` fail-fast). |
| `<vendor>` (будущее расширение) | VendorAdapter | `development`, `production`, `test` | Будущий адаптер конкретного вендора (например, SMSC, Mobizon, Twilio). Любые неизвестные значения `SMS_PROVIDER_MODE` вызывают fail-fast на старте приложения. |

---

## 4. Обработка сбоев и откат транзакций БД

Инварианты обработки сбоев:
1. Запись `OtpCode` в базу данных и физический вызов `sms_provider.send_otp()` выполняются до фиксации транзакции (`commit`).
2. **Provider failure before DB commit:** если отправка завершается ошибкой (сетевой таймаут, исключение провайдера, режим `disabled`), транзакция базы данных **немедленно откатывается (`await session.rollback()`)**. В БД не остается ни одной активной или незавершенной записи OTP.
3. Клиент получает контролируемый ответ:
   - `503 Service Unavailable` (`code: "SMS_PROVIDER_NOT_CONFIGURED"`) — если режим `disabled`;
   - `503 Service Unavailable` (`code: "SMS_DELIVERY_UNAVAILABLE"`) — при сбое шлюза/транспорта.

---

## 5. Delivery Consistency / Failure Boundary

> [!WARNING]
> **Cross-system distributed atomicity is technically not possible between PostgreSQL and an external SMS Gateway.**
>
> База данных PostgreSQL не может откатить внешнюю SMS, если сообщение уже принято или отправлено оператором связи.

### Четкие границы гарантий:
* **Сбой до фиксации в БД (Provider Exception $\rightarrow$ DB Rollback):**
  Если вызов `send_otp` выбросил исключение, сессия БД гарантированно откатывается. В таблице `otp_codes` не возникает фантомных активных кодов, клиент получает 503.
* **Успех провайдера с последующим сбоем фиксации БД (Provider Success $\rightarrow$ Commit Failure):**
  Если SMS-шлюз успешно принял/доставил SMS, но последующий `await session.commit()` завершился сбоем (разрыв связи с PostgreSQL, таймаут диска и т.п.), внешняя доставка не может быть автоматически отозвана.
* **Требования к будущему production-адаптеру:**
  1. Вызов внешнего SMS API должен иметь жесткий сетевой таймаут (Connect/Read timeout, например 3–5 секунд).
  2. Ошибки транспорта и таймауты маппятся в HTTP 503 (`SMS_DELIVERY_UNAVAILABLE`).
  3. Адаптер должен учитывать сценарии неопределенного исхода (ambiguous outcome / network split) и по возможности передавать идемпотентный ключ запроса (`request_id` / `idempotency_key`), поддерживаемый API провайдера.
  4. При необходимости строгой сверки статусов доставки в последующих задачах может быть внедрен паттерн transactional outbox / delivery reconciliation.

---

## 6. Безопасность кода и PII

1. **Открытый OTP-код:**
   - 6-значный цифровой код (`^\d{6}$`), генерируемый криптографически стойким генератором `secrets.choice`.
   - Открытый код передается исключительно в метод `send_otp(phone, code)`.
   - Открытый код **никогда** не сохраняется в базе данных.
   - Открытый код **никогда** не выводится в логи приложения.
2. **Хранение в БД:**
   - В поле `otp_codes.code_hash` сохраняется только криптографический HMAC-SHA256 дайджест: `HMAC-SHA256(SMS_OTP_HASH_KEY, f"{normalized_phone}:{otp}")`.
   - Проверка осуществляется в постоянное время (`hmac.compare_digest`).
   - `SMS_OTP_HASH_KEY` является отдельным обязательным секретом в production/development (минимум 32 символа, без fallback на WhatsApp secret).
3. **Хэширование PII для Rate Limiter:**
   - В ключах Redis для ограничения частоты запросов не используется открытый номер телефона; используется односторонний SHA-256 fingerprint (`phone_fingerprint`).

---

## 7. Руководство по подключению реального SMS-адаптера

При реализации интеграции в следующих итерациях:
1. Создать класс-адаптер (например, `SmscProvider` или `TwilioProvider`), реализующий протокол `SmsProvider`:
   ```python
   async def send_otp(self, phone: str, code: str) -> None:
       # Вызов внешнего HTTP API SMS-шлюза с таймаутом
       # В случае сетевых сбоев/4xx/5xx от шлюза выбросить исключение (например, SmsDeliveryError)
   ```
2. Зарегистрировать валидный идентификатор вендора в enum/validation `Settings` в `app/core/config.py`.
3. Зарегистрировать провайдер в фабрике зависимостей `app/services/sms_provider.py`:
   ```python
   def get_sms_provider() -> SmsProvider:
       if settings.sms_provider_mode == "fake":
           if settings.app_env.lower() != "test":
               raise AppError(status_code=503, code="SMS_PROVIDER_NOT_CONFIGURED")
           return get_fake_sms_provider()
       if settings.sms_provider_mode == "smsc":
           return SmscProvider(...)
       return DisabledSmsProvider()
   ```
