# TASK-005-FIX Report

## Fixed Findings

В рамках данного PATCH устранены все замечания независимого ревью к реализации TASK-005:

1. **Card Updated Timestamp**: В схему `CustomerCardResponse` возвращено поле `updated_at: datetime` (timestamp последнего зеркального снимка карты из POSCENTER ONE). Заполнено в `GET /me/cards` и `GET /me/cards/{id}`.
2. **Atomic Soft-Hide**: Реализована атомарная операция скрытия карты на уровне СУБД (`UPDATE user_cards ... WHERE hidden_at IS NULL RETURNING id`). Устранена уязвимость race condition; при параллельных DELETE-запросах строго гарантируется ровно один ответ `204 No Content` и ответы `404 CARD_NOT_FOUND` для остальных, с полным исключением `500 Internal Server Error`.
3. **PII Logging**: Полностью удалены персональные данные (номер телефона, ФИО, user ID, токены) из логов сервиса автопривязки `auto_bind_cards_by_phone`. Логируется исключительно обезличенный `card_id`.
4. **Auto-Bind Ownership & Invariants**: Сохранение и подтверждение инварианта: карта не может быть украдена или перепривязана другому пользователю.
5. **Hidden Card Preservation**: Подтверждено тестами на уровне PostgreSQL: скрытая карта (`hidden_at IS NOT NULL`) никогда повторно не воскрешается при фоновом `auto_bind_cards_by_phone`.
6. **PostgreSQL Concurrency Suite**: Реализован и проверен полный набор из 5 интеграционных сценариев параллелизма на реальном PostgreSQL с использованием `asyncio.Barrier`:
   - `PG-WALLET-01`: параллельная автопривязка одним и тем же пользователем (несколько запросов с разных устройств/вкладок);
   - `PG-WALLET-02`: предотвращение кражи/перепривязки существующего чужого владельца;
   - `PG-WALLET-03`: параллельный атомарный soft-hide (10 итераций по 5 параллельных воркеров через `asyncio.Barrier(5)`, строго 1x204 и 4x404);
   - `PG-WALLET-04`: сохранение скрытого состояния карты при параллельной автопривязке;
   - `PG-WALLET-05`: детерминированная пагинация по keyset курсору при конкурентной вставке новых транзакций.
7. **Barcode Contract**: Приведен в соответствие 13-значный строковый формат штрихкода (EAN-13), с сохранением ведущего нуля (`"0123456789012"`). Документация `docs/CUSTOMER_API.md` и фикстуры тестов обновлены.
8. **Transaction Filter Specification**: Уточнено описание фильтра `type` в документации и docstring API: `type performs exact filtering by the canonical type received from ONE.`

---

## Card Updated Timestamp

* В схему `CustomerCardResponse` (`backend/app/schemas/wallet.py`) добавлено поле:
  ```python
  updated_at: datetime
  ```
* В `WalletService.get_customer_cards` и `WalletService.get_customer_card_detail` значение мапится напрямую из зеркальной сущности `Card.updated_at`.
* **Инвариант только для чтения (Read-Only)**: Операции в Customer API (включая soft-hide через `DELETE /me/cards/{id}`) мутируют только `user_cards.hidden_at` и никогда не изменяют `Card.updated_at`. Покрыто тестом `test_card_updated_at_preserved_on_soft_hide`.

---

## Atomic Soft Hide

* Предыдущая реализация soft-hide выполняла раздельные `SELECT ...` и `user_card.hidden_at = utcnow()`, что приводило к race conditions при параллельных запросах.
* В `WalletService.hide_customer_card` реализовано атомарное обновление через единый SQL-запрос с предикатом `hidden_at IS NULL`:
  ```python
  stmt = (
      update(UserCard)
      .where(
          UserCard.user_id == user.id,
          UserCard.card_id == card_id,
          UserCard.hidden_at.is_(None),
      )
      .values(hidden_at=utcnow())
      .returning(UserCard.id)
  )
  result = await session.execute(stmt)
  row = result.scalar_one_or_none()
  if row is None:
      raise CardNotFoundError()
  ```
* При параллельных запросах ровно один воркер обновляет строку и получает возвращенный `id`, возвращая `204 No Content`. Все остальные воркеры видят условие `hidden_at IS NULL` невыполненным, получают `None` и возвращают `404 CARD_NOT_FOUND`.

---

## PII Logging

* Из логгера `backend/app/services/wallet_service.py` удален вывод номеров телефонов (`user.phone`), ФИО, user ID и токенов.
* Сформировано безопасное сообщение:
  ```python
  logger.warning(
      "Auto-bind skipped because candidate card %s already has an owner",
      row.card_id,
  )
  ```
* Добавлен специализированный регрессионный тест `test_auto_bind_pii_not_in_logs`, перехватывающий логи через pytest `caplog` и проверяющий отсутствие любых следов телефона, user_id и токенов.

---

## Auto-Bind Ownership

* Сохраняется инвариант `one card -> at most one user` благодаря ограничению БД `uq_user_cards_card_id`.
* При совпадении номера телефона пользователя с картой, уже принадлежащей другому клиенту, привязка пропускается (`ON CONFLICT (card_id) DO NOTHING` + предикат исключения чужих карт).
* Сценарий проверен на PostgreSQL в `test_pg_wallet_02_foreign_existing_owner_cannot_be_stolen`.

---

## Hidden Card Preservation

* Если клиент скрыл карту (`hidden_at IS NOT NULL`), фоновый процесс `auto_bind_cards_by_phone` при последующих обращениях к `GET /me/cards` проверяет существование привязки в `user_cards` (независимо от значения `hidden_at`) и никогда повторно не делает карту видимой.
* Проверено на PostgreSQL в `test_pg_wallet_04_hidden_card_not_resurrected_by_auto_bind`.

---

## PostgreSQL Concurrency

Проверено на локальном экземпляре PostgreSQL (`poscenter_loyalty_test`) с использованием `asyncio.Barrier` для обеспечения реального одновременного входа корутин:

| ID | Описание теста | Результат |
|---|---|---|
| `PG-WALLET-01` | Параллельная автопривязка карт при одновременных запросах от одного пользователя | PASSED |
| `PG-WALLET-02` | Защита от перехвата карты чужого владельца (IDOR/Theft protection) | PASSED |
| `PG-WALLET-02` (aux) | Параллельная автопривязка из конкурирующих сессий | PASSED |
| `PG-WALLET-03` | Конкурентный soft-hide (10 итераций x 5 параллельных запросов через `asyncio.Barrier(5)`, строго 1x204, 4x404, 0x500) | PASSED |
| `PG-WALLET-04` | Сохранение скрытого состояния карты при параллельной автопривязке | PASSED |
| `PG-WALLET-05` | Детерминированность keyset-пагинации при параллельной вставке транзакций | PASSED |

Время выполнения: **6 passed in 2.32s**.

---

## Barcode Contract

* Штрихкод строго стандартизирован как 13-значная строка формата EAN-13, сохраняющая ведущие нули (например, `"0123456789012"`).
* В тесты добавлен `test_card_barcode_leading_zero_preserved`, проверяющий целостность строкового типа и сохранение ведущего нуля в ответах API.
* Документация в `docs/CUSTOMER_API.md` и фикстуры тестов обновлены.

---

## Regression Tests

* **Полный unit-набор тестов**:
  - `pytest -v`: **134 passed, 21 skipped in 11.96s** (все non-DB тесты, 21 PostgreSQL-специфичный тест пропускается при отсутствии переменной `POSTGRES_TEST_URL`).
* **Полный PostgreSQL-набор тестов**:
  - `POSTGRES_TEST_URL="..." pytest -v tests/test_postgres*`: **21 passed in 6.57s** (включая PG-SYNC, PG-AUTH, PG-WAPPI и PG-WALLET).

---

## Alembic

* Проверен полный цикл миграций на PostgreSQL:
  - `alembic upgrade head`: успешно (0001 -> 0006).
  - `alembic downgrade -1`: успешно (0006 -> 0005).
  - `alembic upgrade head`: успешно (0005 -> 0006).
  - `alembic check`: **No new upgrade operations detected** (код возврата 0).
* Пустая миграция 0007 не создавалась, так как схема БД для данного патча осталась полностью неизменной.

---

## Ruff

* `ruff check app tests migrations`:
  - **All checks passed!** (код возврата 0).

---

## Mypy

* `mypy app migrations`:
  - **Success: no issues found in 38 source files** (код возврата 0).

---

## Compileall

* `python -m compileall app tests migrations`:
  - Все исходные файлы скомпилированы успешно, синтаксических ошибок нет (код возврата 0).

---

## Security Checks

1. **IDOR / Ownership Isolation**: Любые запросы к чужим или скрытым картам (`/me/cards/{id}`, `/me/cards/{id}/transactions`, `DELETE /me/cards/{id}`) возвращают `404 CARD_NOT_FOUND` без утечки факта существования карты.
2. **Zero PII Leakage**: Логирование автопривязки не содержит персональных данных.
3. **Read-Only Invariant**: Customer API не имеет прав на модификацию баланса, статуса блокировки или времени обновления карты (`cards.updated_at`).

---

## Deviations

Отклонений от требований ТЗ (`TZ_loyalty_app_v1.1`) и скоупа патча нет.

---

## Known Limitations

* Привязка карт по QR/штрихкоду и активационному коду вручную покупателем отложена до TASK-006 в строгом соответствии с планом разработки.

---

## Git Status

```text
On branch main
Changes to be committed:
  modified:   README.md
  modified:   backend/app/api/customer_wallet.py
  modified:   backend/app/schemas/wallet.py
  modified:   backend/app/services/wallet_service.py
  modified:   backend/tests/test_auto_bind.py
  modified:   backend/tests/test_customer_wallet.py
  modified:   backend/tests/test_postgres_wallet_concurrency.py
  modified:   docs/CUSTOMER_API.md
  new file:   TASK_005_FIX_REPORT.md
```

## Branch

`main`

## HEAD

`a885fdddc8c9d00b08c1e2e284f9f3993c7e687e`
