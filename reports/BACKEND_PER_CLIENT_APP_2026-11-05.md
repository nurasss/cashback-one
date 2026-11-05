# Отчёт о реализации серверной поддержки клиентских Android-приложений (Task I-backend)

**Дата:** 2026-11-05  
**Исполнитель:** Gemini (backend, admin)  
**Куратор:** Antigravity  
**Статус:** Реализовано и проверено локально (SQLite + PostgreSQL 16 + Vitest + TypeScript)

---

## 1. Цель и контекст

Реализация серверной поддержки (Task I-backend) для разделения клиентских Android-приложений (multi-client / per-client Android apps) в экосистеме Cashback One:
1. Возможность привязки индивидуального идентификатора Android-пакета (`android_app_id`, например `kz.keremet.cashback`) к бизнесу.
2. Таргетирование push-уведомлений при подтверждении списания баллов на кассе (POS) с учётом `android_app_id` бизнеса и общего приложения `kz.cashbackone.mobile` (`PUSH_SHARED_APP_ID`).
3. Возврат машиночитаемой ошибки `CUSTOMER_NO_APP` на кассу, если у покупателя нет активного устройства с разрешённым приложением.
4. Поддержка опционального фильтра `business_id` в Customer API (карты, промо-акции, персональные уведомления, бейджи).
5. Отображение и редактирование `android_app_id` в панели управления (`admin/`) с разграничением прав (суперадмин — редактирование, менеджер бизнеса — только просмотр).
6. Актуализация спецификации `docs/CUSTOMER_API.md`.

---

## 2. Изменённые и созданные файлы

| Файл | Статус | Назначение |
|---|---|---|
| `backend/migrations/versions/0016_business_android_app_id.py` | Создан | Миграция Alembic: добавление `android_app_id` и `uq_businesses_android_app_id` в `businesses`. |
| `backend/app/schemas/common.py` | Изменён | Общий regex и валидатор `ANDROID_APP_ID_REGEX` (`^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$`). |
| `backend/app/schemas/customer_app.py` | Изменён | Использование общих констант regex для `DeviceRegisterRequest`. |
| `backend/app/models/entities.py` | Изменён | Поле `android_app_id` в модели `Business` и `UniqueConstraint("android_app_id", name="uq_businesses_android_app_id")`. |
| `backend/app/schemas/admin.py` | Изменён | Добавление `android_app_id` в `BusinessCreateRequest`, `BusinessUpdateRequest`, `BusinessListItem`. |
| `backend/app/services/admin_mutations.py` | Изменён | Поддержка `android_app_id` при создании/обновлении бизнеса, проверка уникальности с возвратом 422 HTTP при коллизии. |
| `backend/app/services/admin_queries.py` | Изменён | Вывод `android_app_id` в структуре `_business_item`. |
| `backend/app/api/admin.py` | Изменён | Разрешение чтения деталей бизнеса менеджером (`scope.business_id_for(business_id)`), сохранение суперадмин-прав на редактирование. |
| `backend/app/core/config.py` | Изменён | Настройка `PUSH_SHARED_APP_ID` (по умолчанию `"kz.cashbackone.mobile"`). |
| `backend/app/services/push_service.py` | Изменён | Таргетирование пушей (`resolve_allowed_app_ids`, `has_active_device`, `send_to_user`). |
| `backend/app/services/pos_service.py` | Изменён | Передача `business_id=pos_key.business_id` в вызовы `has_active_device` и `send_to_user`. |
| `backend/app/services/wallet_service.py` | Изменён | Фильтрация `get_customer_cards` по опциональному `business_id`. |
| `backend/app/services/content_service.py` | Изменён | Фильтрация по `business_id` в промо-акциях, уведомлениях, отметке о прочтении и счётчиках бейджей. |
| `backend/app/api/customer_app.py` | Изменён | Добавление query-параметра `business_id` в эндпоинты акций, уведомлений и бейджей. |
| `backend/app/api/customer_wallet.py` | Изменён | Добавление query-параметра `business_id` в `GET /me/cards` и `POST /me/cards/bind`. |
| `admin/src/api/types.ts` | Изменён | Добавление поля `android_app_id?: string | null` в тип `Business`. |
| `admin/src/i18n/admin.ts` | Изменён | Локализация RU и KK для отображения и редактирования Android App ID. |
| `admin/src/pages/BusinessesPage.tsx` | Изменён | Отображение `android_app_id` в карточке деталей бизнеса, безопасная навигация для менеджера. |
| `admin/src/features/AdminMutations.tsx` | Изменён | Поле ввода с валидацией и подсказкой в диалоге создания/редактирования бизнеса. |
| `admin/src/auth/RequireAdmin.tsx` | Изменён | Компонент `RequireBusinessDetailAccess` для доступа менеджера к деталям своей организации. |
| `admin/src/layout/AdminRoutes.tsx` | Изменён | Подключение `RequireBusinessDetailAccess` к маршруту `/admin/businesses/:id`. |
| `docs/CUSTOMER_API.md` | Изменён | Спецификация параметра `business_id` для 8 клиентских эндпоинтов и архитектурный раздел 3.14. |
| `backend/tests/test_migration_0016.py` | Создан | Тесты применения и отката миграции 0016 на SQLite и PostgreSQL 16 (с проверкой уникальности). |
| `backend/tests/test_push_per_client.py` | Создан | Тесты таргетинга пушей, изоляции приложений и возврата `CUSTOMER_NO_APP`. |
| `backend/tests/test_admin_business_app_id.py` | Создан | Тесты API админки (создание, редактирование, валидация формата, уникальность 422, права менеджера). |
| `backend/tests/test_customer_api_multi_client.py` | Создан | Интеграционные тесты скоупинга Customer API (карты, биндинг, промо-акции, уведомления, бейджи). |

---

## 3. Миграция 0016

Файл миграции: `backend/migrations/versions/0016_business_android_app_id.py`.
- **Родительская ревизия:** `0015_notification_redemption`.
- **Новое поле:** `android_app_id VARCHAR(255)`, `nullable=True`.
- **Ограничение:** `UniqueConstraint("android_app_id", name="uq_businesses_android_app_id")`.
- **Совместимость с СУБД:**
  - В PostgreSQL стандарт SQL-92/2008 допускает множественные `NULL` в уникальном ограничении (`UNIQUE (android_app_id)`). При попытке вставить два одинаковых не-NULL значения (`kz.keremet.cashback`) вызывается `IntegrityError`.
  - В SQLite уникальное ограничение также трактует каждое значение `NULL` как уникальное, допуская множественные `NULL`, но запрещая одинаковые не-NULL строки.
  - Использован `op.batch_alter_table("businesses")` для корректного применения как на PostgreSQL, так и на SQLite в тестах.
  - Метод `downgrade()` удаляет `uq_businesses_android_app_id` и колонку `android_app_id`.

---

## 4. Правило таргетинга пушей и обработка кассовых запросов

Реализовано в модуле `backend/app/services/push_service.py` и подключено к `backend/app/services/pos_service.py`:
1. Функция `resolve_allowed_app_ids(db, business_id)`:
   - Если `business_id is None`: разрешено только общее приложение `{PUSH_SHARED_APP_ID}` (`kz.cashbackone.mobile`).
   - Если у бизнеса **задан** `android_app_id`: разрешены `{business.android_app_id, PUSH_SHARED_APP_ID}`.
   - Если у бизнеса **не задан** `android_app_id` (`NULL`): разрешено только `{PUSH_SHARED_APP_ID}`.
2. Проверка активных устройств `has_active_device`:
   - Учитывает устройства пользователя, активные за последние `device_inactivity_days` (30 дней), с непустым `push_token`.
   - Если передан `business_id`, фильтрует устройства условием `Device.app_id.in_(allowed_app_ids)`.
3. Отправка `send_to_user`:
   - Если передан `business_id`, пуши отправляются только на устройства с разрешёнными `app_id`.
4. Кассовый вызов `/pos/redemptions`:
   - Перед созданием запроса на списание проверяется `has_active_device(db, user_id=user.id, business_id=pos_key.business_id)`.
   - Если у покупателя нет активных устройств с поддерживаемым приложением, сервер немедленно возвращает HTTP 409 с телом:
     ```json
     {
       "detail": "CUSTOMER_NO_APP",
       "message": "Customer has no active devices with supported app"
     }
     ```
   - Запрос подтверждения не создаётся, токены не расходуются, кассир сразу получает понятное сообщение.

---

## 5. Фильтрация Customer API по `business_id`

Во все клиентские эндпоинты добавлен опциональный параметр запроса `business_id: UUID | None = None`:

| Метод и путь | Поведение без `business_id` | Поведение с `business_id` |
|---|---|---|
| `GET /me/cards` | Возвращает все привязанные карты пользователя всех бизнесов. | Возвращает только карты указанного бизнеса (`Card.business_id == business_id`). |
| `POST /me/cards/bind` | Привязывает карту по номеру. Если найдено несколько, привязывает первую активную. | Проверяет принадлежность карты указанному бизнесу. При несовпадении возвращает `404 Not Found`. |
| `GET /me/promotions` | Возвращает активные акции всех активных бизнесов. | Возвращает только активные акции указанного бизнеса. |
| `GET /me/promotions/{id}` | Возвращает детали акции (если бизнес активен). | Возвращает акцию только если её `business_id` совпадает с запрошенным. Иначе `404 Not Found`. |
| `POST /me/promotions/seen` | Отмечает просмотренными переданные `promotion_ids`. | Отмечает только те акции из переданного списка, которые принадлежат `business_id`. |
| `GET /me/notifications` | Возвращает персональные уведомления покупателя по всем бизнесам. | Возвращает уведомления только для указанного бизнеса (`Notification.business_id == business_id`). |
| `POST /me/notifications/read` | Отмечает прочитанными уведомления покупателя. | Отмечает прочитанными только те уведомления из списка, которые принадлежат указанному `business_id`. |
| `GET /me/badges` | Подсчитывает непросмотренные акции и непрочитанные уведомления по всей системе. | Подсчитывает счётчики только в разрезе переданного `business_id`. |

---

## 6. Панель управления (`admin/`) и безопасность

1. **Разграничение прав доступа:**
   - **Суперадмин (`is_superadmin=True`):** может просматривать и редактировать `android_app_id` бизнеса при создании и редактировании через диалог `BusinessEditorDialog`.
   - **Менеджер бизнеса (`role=business_manager`):** имеет доступ на чтение к странице деталей своего бизнеса (`/admin/businesses/:id`). Поле `android_app_id` отображается в режиме только для чтения («Идентификатор Android-приложения» / «Android қолданба идентификаторы»). Кнопки редактирования и удаления для менеджера скрыты; попытка отправки `PATCH /admin/businesses/{id}` блокируется сервером (HTTP 403 `Only superadmin can update businesses`).
2. **Валидация:**
   - Формат проверяется на клиенте и сервере регулярным выражением: `^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$`.
   - Пустая строка нормализуется в `null` (поле опциональное).
   - При попытке указать уже занятый другим бизнесом `android_app_id` сервер возвращает HTTP 422 с детализацией: `Android app ID already assigned to another business`.
3. **Локализация:**
   - Добавлены ключи `lineAndroidAppId`, `androidAppIdEmpty`, `businessAndroidAppId`, `businessAndroidAppIdHint`, `errBusinessAndroidAppId` в словари RU и KK (`admin/src/i18n/admin.ts`).

---

## 7. Результаты тестов и проверок

### 7.1 Сравнение Baseline и финала

| Компонент / Проверка | Baseline | После доработок | Разница |
|---|---|---|---|
| Backend `pytest` (SQLite default) | 427 passed, 36 skipped | **439 passed, 37 skipped** | +12 тестов passed |
| Backend `pytest -k postgres` | 37 passed, 426 deselected | **38 passed, 438 deselected** | +1 тест passed |
| Backend `ruff check app` | 0 errors | **0 errors** | Чисто |
| Backend `ruff check .` | 7 baseline errors (тесты контракта и pos) | **7 baseline errors** | Новых ошибок 0 |
| Backend `mypy app` | 16 legacy errors (`media_storage`, `image_service`) | **16 legacy errors** | Новых ошибок 0 |
| Admin `vitest` | 175 passed (22 test suites) | **175 passed (22 test suites)** | Без регрессий |
| Admin `tsc --noEmit` | Чисто | **Чисто** | 0 ошибок типов |
| Admin `vite build` | 531ms | **611ms** | Успешная production сборка |

### 7.2 Новые специализированные тесты бэкенда

1. **`tests/test_migration_0016.py`** (2 теста: SQLite + PostgreSQL 16):
   - Проверка применения миграции `0016_business_android_app_id` (добавление колонки `android_app_id` и констрейнта).
   - Проверка успешного отката `downgrade()` (удаление констрейнта и колонки).
   - Проверка уникальности: успешная вставка нескольких записей с `android_app_id = NULL` и вызов `IntegrityError` при дублировании не-NULL значения (`kz.app.one`).
2. **`tests/test_push_per_client.py`** (3 теста):
   - `test_resolve_allowed_app_ids`: проверка формирования белого списка приложений для общего бизнеса, бизнеса с индивидуальным ID и системных запросов.
   - `test_push_targeting_three_devices`: проверка сценария с 3 устройствами одного пользователя (Keremet `kz.keremet.cashback`, Общее `kz.cashbackone.mobile`, Стороннее `kz.other.app`). Списание на кассе Керемет отправляет пуш только на устройства Керемет и Общее, игнорируя стороннее.
   - `test_push_targeting_customer_no_app`: при попытке списания на кассе бизнеса Керемет, когда у пользователя установлено только стороннее приложение, касса мгновенно получает HTTP 409 `CUSTOMER_NO_APP`.
3. **`tests/test_admin_business_app_id.py`** (4 теста):
   - `test_superadmin_can_create_business_with_android_app_id`: создание бизнеса суперадмином с `android_app_id`.
   - `test_business_android_app_id_invalid_format_returns_422`: валидация формата пакета (ошибки при неверных символах, ведущих цифрах).
   - `test_business_android_app_id_uniqueness`: возврат HTTP 422 при попытке назначить дублирующий `android_app_id`.
   - `test_manager_access_to_android_app_id`: менеджер видит `android_app_id` своего бизнеса в `GET /admin/businesses/{id}`, но не может изменить его через `PATCH /admin/businesses/{id}` (HTTP 403).
4. **`tests/test_customer_api_multi_client.py`** (4 теста):
   - `test_get_cards_with_and_without_business_id`: фильтрация карт покупателя по бизнесу.
   - `test_bind_card_foreign_business_returns_404_not_found`: запрет привязки карты чужого бизнеса при указании `business_id`.
   - `test_promotions_and_detail_with_and_without_business_id`: фильтрация списка и деталей промо-акций.
   - `test_notifications_and_badges_with_and_without_business_id`: фильтрация уведомлений и расчёта бейджей.

---

## 8. Процедура выкатки (Rollout) на production

Для применения изменений на production-сервере (`kz-vps`):

1. **Git Pull на сервере:**
   ```bash
   cd /opt/cashback-one
   git pull --ff-only origin main
   ```
2. **Применение миграции базы данных:**
   ```bash
   docker compose exec -T cashback-backend alembic upgrade head
   ```
   *Примечание:* Миграция безопасна для работающей базы, добавляет `nullable` колонку без блокировок существующих строк и создаёт уникальный индекс.
3. **Перезапуск контейнера бэкенда:**
   ```bash
   docker compose restart cashback-backend
   ```
4. **Деплой админки:**
   - Сборка `npm run build` в `admin/`.
   - Синхронизация файлов `dist/` на хостинг через FTPS (сначала assets, затем `index.html`).
5. **Настройка бизнеса «Керемет»:**
   - В панели суперадмина открыть редактирование бизнеса «Супермаркет Керемет» (или через CLI/SQL).
   - Задать в поле «Идентификатор Android-приложения»: `kz.keremet.cashback`.
   - Сохранить изменения.
6. **Совместимость:**
   - Старые версии клиентских приложений (1.0.1–1.0.12) работают с общим ID `kz.cashbackone.mobile` и не передают `business_id` — для них поведение остаётся прежним (полная обратная совместимость).
   - Новое индивидуальное приложение `kz.keremet.cashback` при регистрации устройства передаёт свой `app_id` и во всех запросах передаёт `business_id` супермаркета Керемет.

---

## 9. Что не проверялось / ограничения

1. **Реальная отправка пушей через FCM:** в тестах использовался мок `FakePushSender` (настоящие ключи Google FCM не вызывались).
2. **Физические устройства Android:** регистрация реального FCM токена из сборки APK не проводилась в рамках серверной задачи.
3. **Агент 1С:** агент и модуль интеграции с 1С намеренно не затрагивались в соответствии с требованиями изоляции.
4. **Коммиты и деплой:** в соответствии с инструкцией изменения не коммитились в git и не отправлялись на боевой сервер.
