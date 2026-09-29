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
            Exception: Any transport or vendor exception, which will trigger atomic DB rollback
                       and a 503 SMS_DELIVERY_UNAVAILABLE response.
        """
        ...
```

---

## 3. Режимы работы (`SMS_PROVIDER_MODE`)

Режим выбирается через переменную окружения `SMS_PROVIDER_MODE`:

| Режим (`SMS_PROVIDER_MODE`) | Класс провайдера | Назначение и поведение |
|---|---|---|
| `disabled` (по умолчанию) | `DisabledSmsProvider` | Безопасный режим по умолчанию для сред, где вендор еще не подключен. При вызове `/auth/sms/request` выбрасывает контролируемый `AppError(status_code=503, code="SMS_PROVIDER_NOT_CONFIGURED")`. |
| `fake` | `FakeSmsProvider` | In-memory тестовый провайдер для автоматизированных тестов. Сохраняет отправленные коды в `sent_messages` и поддерживает флаг `fail_next` для симуляции сбоев сети/провайдера. |
| `<vendor>` (будущее расширение) | VendorAdapter | Адаптер конкретного вендора (например, SMSC, Mobizon, Twilio). |

---

## 4. Атомарность и обработка сбоев доставки

Инвариант безопасности:
1. Запись `OtpCode` в базу данных и физическая отправка через провайдер происходят в рамках одной транзакции с отложенной фиксацией (`commit`).
2. Провайдер вызывается **до** `await session.commit()`.
3. Если отправка завершается ошибкой (сетевой таймаут, ошибка провайдера, `DisabledSmsProvider`), транзакция базы данных **немедленно откатывается (`await session.rollback()`)**.
4. В базе данных **не создается ни одной активной/повисшей OTP-записи**, если доставка не удалась.
5. Клиент получает контролируемый ответ:
   - `503 Service Unavailable` (`code: "SMS_PROVIDER_NOT_CONFIGURED"`) — если режим `disabled`;
   - `503 Service Unavailable` (`code: "SMS_DELIVERY_UNAVAILABLE"`) — при сбое шлюза/транспорта.

---

## 5. Безопасность кода и PII

1. **Открытый OTP-код:**
   - 6-значный цифровой код (`^\d{6}$`), генерируемый криптографически стойким генератором `secrets.choice`.
   - Открытый код передается исключительно в метод `send_otp(phone, code)`.
   - Открытый код **никогда** не сохраняется в базе данных.
   - Открытый код **никогда** не выводится в логи приложения.
2. **Хранение в БД:**
   - В поле `otp_codes.code_hash` сохраняется только криптографический HMAC-SHA256 дайджест: `HMAC-SHA256(SMS_OTP_HASH_KEY, f"{normalized_phone}:{otp}")`.
   - Проверка осуществляется в постоянное время (`hmac.compare_digest`).
3. **Хэширование PII для Rate Limiter:**
   - В ключах Redis для ограничения частоты запросов не используется открытый номер телефона; используется односторонний SHA-256 fingerprint (`phone_fingerprint`).

---

## 6. Руководство по подключению реального SMS-адаптера

При реализации интеграции в следующих итерациях:
1. Создать класс-адаптер (например, `SmscProvider` или `TwilioProvider`), реализующий метод:
   ```python
   async def send_otp(self, phone: str, code: str) -> None:
       # Вызов внешнего HTTP API SMS-шлюза
       # В случае 4xx/5xx от шлюза выбросить исключение (например, SmsDeliveryError)
   ```
2. Зарегистрировать провайдер в фабрике зависимостей `app/services/sms_provider.py`:
   ```python
   def get_sms_provider() -> SmsProvider:
       if settings.sms_provider_mode == "fake":
           return get_fake_sms_provider()
       if settings.sms_provider_mode == "smsc":
           return SmscProvider(...)
       return DisabledSmsProvider()
   ```
3. Конфигурация кредов шлюза (API key, sender name) должна валидироваться в `app/core/config.py` при `sms_provider_mode == "<vendor>"`.
