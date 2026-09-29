# TASK-006 Report

## Manual Bind API

Реализован эндпоинт ручной привязки существующей карты лояльности POSCENTER ONE к авторизованному клиенту по штрихкоду / QR-коду:

```http
POST /me/cards/bind
Authorization: Bearer <access_token>
```

Request payload:
```json
{
  "barcode": "0123456789012",
  "business_id": null
}
```

* `barcode` (string, required): 13-значный EAN-13 штрихкод.
* `business_id` (UUID, optional): идентификатор торговой сети / организации (бизнеса) для разрешения коллизий одинаковых штрихкодов в разных сетях.
* Successful response: `200 OK` с представлением `CustomerCardResponse` (единый DTO с `GET /me/cards/{id}`).
* Архитектурный принцип: сканирование камерой выполняется на клиенте (Mobile). Бэкенд получает только распознанную строку barcode.

---

## Barcode Validation

* Строгий контракт EAN-13:
  - Тип: исключительно строка (не преобразуется в `int`);
  - Длина: строго 13 цифр (`^\d{13}$`);
  - Ведущие нули сохраняются (`"0123456789012"`);
  - Внешние пробелы очищаются (`val.strip()`);
  - Внутренние пробелы, буквы, спецсимволы и нестроковые типы вызывают ошибку валидации `422 VALIDATION_ERROR`.
* Реализовано через Pydantic `@field_validator("barcode", mode="before")` в `BindCardRequest`.

---

## Business Resolution

1. Поиск производится **только** по существующим картам `cards` из зеркала POSCENTER ONE в активных организациях (`Business.status == "active"`). Бэкенд никогда не создает placeholder `Card`.
2. Если `business_id` передан:
   - Поиск строго по `Card.business_id == business_id AND Card.barcode == barcode`.
   - Если карта не найдена или бизнес неактивен, возвращается нейтральный `404 CARD_NOT_FOUND` (без раскрытия внутреннего статуса организации).
3. Если `business_id` опущен:
   - Ищутся все карты с этим barcode среди активных бизнесов.
   - Если найдена ровно 1 карта — выбирается она.
   - Если найдено 0 карт — возвращается `404 CARD_NOT_FOUND`.
   - Если найдено несколько карт — применяется алгоритм Prefix Resolution.

---

## Prefix Resolution

* Если несколько активных бизнесов имеют карты с одинаковым штрихкодом:
  - Анализируется массив `Business.barcode_prefixes`.
  - Учитываются только непустые строковые префиксы.
  - Префикс считается совпавшим, если `barcode.startswith(prefix)`.
* Если после фильтрации по префиксам остался ровно один бизнес — выбирается его карта.
* Если совпадений префиксов нет либо подходящих бизнесов несколько (коллизия):
  - Бэкенд **не выбирает** организацию наугад.
  - Возвращается контролируемый `409 BUSINESS_SELECTION_REQUIRED` с безопасным списком кандидатных бизнесов (`id`, `name`, `logo_url`, `colors`).
  - Приватные данные (балансы, телефоны, ФИО, агенты) в ответе полностью отсутствуют.
  - Мобильное приложение запрашивает выбор у пользователя и повторяет запрос с выбранным `business_id`.

---

## Phone Ownership Verification

1. После разрешения целевой карты `target_card` проверяется поле `card.phone`:
   - Если `card.phone IS NULL` — привязка запрещена, возвращается `409 CARD_ACTIVATION_REQUIRED`.
   - Если `card.phone` имеет невалидный формат — fail-closed, возвращается `409 CARD_BIND_NOT_ALLOWED`.
2. Телефон карты нормализуется в канонический формат E.164 (`normalize_phone`) и сравнивается с верифицированным телефоном текущего пользователя `current_user.phone`:
   - При совпадении (включая форматы `+7...`, `8...`, `7...`) привязка разрешается.
   - При несовпадении возвращается generic `409 CARD_BIND_NOT_ALLOWED` (`"This card cannot be linked to the current account."`).
3. Никакие персональные данные (номер телефона владельца, чужой номер) в текст ошибки не попадают.

---

## Activation Required Boundary

* Граница ответственности: карты, созданные в 1С без привязанного номера телефона (`card.phone IS NULL`), требуют отдельной процедуры подтверждения на кассе.
* В соответствии с ТЗ, процедура кассирской активации / выдачи временного кода еще не утверждена.
* Поэтому бэкенд возвращает контролируемый статус `409 CARD_ACTIVATION_REQUIRED`:
  ```json
  {
    "error": {
      "code": "CARD_ACTIVATION_REQUIRED",
      "message": "This card requires activation before it can be linked."
    }
  }
  ```
* Запись телефона в 1С, SMS OTP fallback или генерация псевдо-кодов активации исключены из текущего этапа.

---

## Existing Ownership

* Привязка существующей карты:
  - Если карта уже привязана к текущему пользователю и активна (`user_id == current_user.id`, `hidden_at IS NULL`) — запрос идемпотентен, возвращается `200 OK` с текущей картой без создания дублирующих строк в БД.
  - Если карта принадлежит другому пользователю (`user_id != current_user.id`) — возвращается generic `409 CARD_BIND_NOT_ALLOWED`. Перехват или кража чужой карты исключены.

---

## Manual Unhide

* Явное действие пользователя: повторный ввод/сканирование штрихкода собственной карты, которая ранее была мягко скрыта (`hidden_at IS NOT NULL`).
* Бэкенд выполняет `hidden_at = NULL`.
* Исходное время первой привязки `bound_at` и метод привязки `bind_method` сохраняются без изменений.
* Баланс, статус блокировки и зеркальные атрибуты карты не мутируют.
* Фоновая автопривязка `auto_bind_cards_by_phone` по-прежнему никогда не воскрешает скрытые карты.

---

## Foreign Owner Protection

* Инвариант уровня базы данных: `UNIQUE(user_cards.card_id)`.
* При попытке пользователя B привязать карту пользователя A:
  - Запрос отклоняется с кодом `409 CARD_BIND_NOT_ALLOWED`.
  - Владелец карты в таблице `user_cards` остается неизменным (User A).
  - Даже если карта пользователя A была скрыта (`hidden_at IS NOT NULL`), пользователь B не может завладеть ею.

---

## Blocked Cards

* Если `card.is_blocked == true`, но номер телефона совпадает с `current_user.phone`:
  - Привязка разрешается.
  - В ответе и кошельке карта отображается с атрибутом `"is_blocked": true`.
  - Customer API не разблокирует карту (источник истины — 1С/ONE).

---

## Concurrency

* Параллельные запросы привязки от одного пользователя (`POST /me/cards/bind`, 5 параллельных воркеров):
  - На уровне PostgreSQL используется `pg_insert(UserCard) ... on_conflict_do_nothing(index_elements=["card_id"])`.
  - Ровно 1 запись создается в `user_cards`.
  - 0 ошибок `IntegrityError`, 0 ошибок `HTTP 500`.
  - Все параллельные запросы возвращают `200 OK` с корректными данными карты.
* Параллельный manual unhide:
  - 5 параллельных запросов одновременно сбрасывают `hidden_at = NULL`.
  - В БД остается ровно 1 запись с `hidden_at IS NULL`, все 5 возвращают `200 OK`.

---

## PostgreSQL Tests

Интеграционный набор тестов в `backend/tests/test_postgres_bind_concurrency.py` проверен на реальном PostgreSQL 16 с использованием `asyncio.Barrier`:

| Тест | Описание | Результат |
|---|---|---|
| `PG-BIND-01` | 5 параллельных запросов привязки от одного пользователя для одной карты | PASSED |
| `PG-BIND-02` | Защита от кражи/перепривязки карты чужого владельца (User A -> User B) | PASSED |
| `PG-BIND-03` | 5 параллельных запросов unhide скрытой карты тем же владельцем | PASSED |
| `PG-BIND-04` | Изоляция одинакового штрихкода в двух разных бизнесах (prefix/business_id) | PASSED |

Общее время: **4 passed in 1.22s**.

Полный набор тестов PostgreSQL (`tests/test_postgres*`): **25 passed in 8.66s**.

---

## Regression Tests

* Unit / API тесты в `tests/test_customer_bind_card.py`: **17 passed**.
* Полный регрессионный тестовый набор (`pytest -v`): **151 passed, 25 skipped** (пропущены только тесты, требующие живого PostgreSQL, запущенные отдельно).
* Все существующие тесты (AUTH, AGENT SYNC, RATE LIMITING, WAPPI WEBHOOK, WALLET READ) полностью зеленые.

---

## Alembic

* Проверен полный цикл применения и отката миграций на PostgreSQL:
  ```bash
  alembic stamp base
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  alembic check
  ```
* Результат: **No new upgrade operations detected** (код возврата 0).
* Новая миграция `0007` не создавалась, так как модель данных Stage 1 (`UserCard`, `barcode_prefixes`, `hidden_at`, `bind_method`) полностью покрывает функциональность TASK-006.

---

## Ruff

* `ruff check app tests migrations`: **All checks passed!** (код возврата 0).

---

## Mypy

* `mypy app migrations`: **Success: no issues found in 38 source files** (код возврата 0).

---

## Compileall

* `python -m compileall app tests migrations`: успешно скомпилированы все модули (код возврата 0).

---

## Security / Privacy

1. **PII Sanitization**: Номера телефонов, ФИО, балансы и токены исключены из логов сервиса привязки.
2. **IDOR & Multi-Tenant Isolation**: При `CARD_BIND_NOT_ALLOWED` и `CARD_NOT_FOUND` не раскрываются данные чужих карт или существование неактивных организаций.
3. **Prefix Isolation**: Префиксы штрихкодов используются исключительно для разрешения тенанта и не считаются доказательством владения картой.

---

## Scope Exclusions

В соответствии с правилами строгого скоупа TASK-006 НЕ реализованы:
* Кассирская активация карт без телефона / временные коды активации;
* Запись телефона клиента в базу 1С;
* SMS OTP fallback flow;
* Мобильный интерфейс камеры / сканера QR;
* Административная панель;
* Windows Service агент / COM-соединитель;
* Интеграции Apple / Google Wallet.

---

## Known Limitations

* Карты без номера телефона (`phone IS NULL`) в POSCENTER ONE не могут быть привязаны до утверждения процедуры кассирской активации.

---

## Git Status

```text
On branch main
Changes to be committed:
  modified:   README.md
  modified:   backend/app/api/customer_wallet.py
  modified:   backend/app/core/errors.py
  modified:   backend/app/schemas/wallet.py
  modified:   backend/app/services/wallet_service.py
  new file:   backend/tests/test_customer_bind_card.py
  new file:   backend/tests/test_postgres_bind_concurrency.py
  modified:   docs/CUSTOMER_API.md
  new file:   TASK_006_REPORT.md
```

## Branch

`main`

## HEAD

`21e6ee9b83204c65b4eee2b4bac30b26ac104d9f`
