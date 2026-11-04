# Отчёт по задаче G: Физические магазины и тексты приложения в кабинете (2026-11-04)

## 1. Контекст и цели

Задача выполнена в соответствии с `docs/PROMPT_BUSINESS_APP_CONTENT_2026-11-04.md` (Задача G) в развитие курса `docs/ROADMAP_PER_CLIENT_2026-11-04.md` (решение 10: тексты экранов и адреса физических точек продаж не зашиваются жестко в код мобильного приложения, а настраиваются бизнесом через кабинет администратора, передаются через API и кешируются на клиенте).

### Основные требования задачи:
1. **База данных и миграция:** Создать миграцию `0013_business_app_content` (следующую за `0012_push_devices`) с таблицей `business_stores`, колонкой `businesses.app_texts` (JSON, nullable) и корректным обратным откатом `downgrade`. Проверить двустороннее применение на реальном PostgreSQL 16.
2. **API кабинета администратора:** Эндпоинты `GET/POST /admin/businesses/{id}/stores`, `PATCH/DELETE /admin/businesses/{id}/stores/{store_id}`, `GET/PUT /admin/businesses/{id}/app-texts`. Все мутации логируются в `audit_log`, доступ строго разграничен (суперадмин — любой бизнес, менеджер — только свой, чужой бизнес возвращает HTTP 404).
3. **Безопасность ссылок на карты:** Поле `map_url` принимает только безопасные `https://` ссылки (2ГИС, Яндекс.Карты, Google Maps), отклоняя `http://`, схемы `javascript:`, `data:`, пробелы и некорректный синтаксис.
4. **API мобильного приложения:** Эндпоинт `GET /me/app-content?business_id=<uuid>` с проверкой привязки активной карты покупателя к бизнесу, поддержкой HTTP ETag и статуса `304 Not Modified`, заголовком `Cache-Control: private, max-age=300`. Документирован в `docs/CUSTOMER_API.md`.
5. **Кабинет администратора:** Раздел «Приложение» (`ContentPage.tsx` — вкладка `app` «Магазины и инфо» / «Дүкендер мен мәтіндер») и интеграция в детальную страницу бизнеса `BusinessDetailPage`. Полная поддержка языков RU и KK, модальные окна создания/редактирования/удаления магазинов, форма редактирования текстов с плейсхолдерами встроенных значений.
6. **Тесты и сборка:** Полное покрытие тестами бэкенда и кабинета, проверка чистоты linter/typecheck, production-сборка Vite.
7. **Скриншоты:** Захват экранов нового раздела в разрешении 1366px и 390px на двух языках (RU и KK) с тестовыми данными.

---

## 2. Изменённые и созданные файлы

### Бэкенд (`backend/`):
- `backend/migrations/versions/0013_business_app_content.py` *(новый)* — миграция Alembic: создание `business_stores` (индексы `ix_business_stores_business_id`, `ix_business_stores_active_sort`), добавление `app_texts` в `businesses`, обратимый `downgrade`.
- `backend/app/models/entities.py` — ORM-модель `BusinessStore` и связь в `Business` (`stores`, `app_texts: Mapped[dict | None]`).
- `backend/app/schemas/admin_content.py` — Pydantic-схемы `BusinessStoreAdminItem`, `BusinessStoreCreateRequest`, `BusinessStoreUpdateRequest`, `LocalizedAppText`, `AppTextsResponse`, `AppTextsUpdateRequest`, валидатор `_validate_map_url`.
- `backend/app/schemas/customer_app.py` — Pydantic-схемы `AppStoreItem`, `CustomerLocalizedText`, `CustomerAppTexts`, `CustomerAppContentResponse`.
- `backend/app/services/admin_content.py` — методы управления магазинами и текстами с бизнес-скоупингом и аудитом: `list_stores`, `create_store`, `update_store`, `delete_store`, `get_app_texts`, `update_app_texts`.
- `backend/app/api/admin.py` — роуты `/businesses/{business_id}/stores` и `/businesses/{business_id}/app-texts`.
- `backend/app/api/customer_app.py` — роут `GET /me/app-content` с расчетом ETag и 304.
- `backend/app/main.py` — добавление `"PUT"` в список разрешенных CORS-методов `allow_methods`.
- `backend/tests/test_business_app_content.py` *(новый)* — 4 комплексных теста полного жизненного цикла магазинов, текстов, безопасности ссылок, ETag/304 и скоупинга ролей.
- `backend/tests/test_admin_config.py` — обновление теста CORS-методов с учетом добавления PUT.

### Документация (`docs/`):
- `docs/CUSTOMER_API.md` — добавлен раздел 3.13 с описанием контракта `GET /me/app-content`, параметров, структуры ответа, заголовков ETag и кодов ошибок.

### Кабинет администратора (`admin/`):
- `admin/src/api/client.ts` — поддержка метода `'PUT'` в `RequestOptions`.
- `admin/src/api/types.ts` — TypeScript-интерфейсы `LocalizedText`, `BusinessStore`, `AppTexts`, `BusinessStoreInput`.
- `admin/src/api/queries.ts` — React Query хуки `useBusinessStores` и `useBusinessAppTexts`.
- `admin/src/features/BusinessAppContent.tsx` *(новый)* — UI-компонент управления магазинами и текстами приложения с модальными окнами, валидацией, переключателями и локализацией.
- `admin/src/pages/ContentPage.tsx` — добавление вкладки `'app'` («Магазины и инфо» / «Дүкендер мен мәтіндер») с фильтрацией бизнеса (для менеджера — жестко зафиксирован, для суперадмина — выбор из выпадающего списка).
- `admin/src/pages/BusinessesPage.tsx` — интеграция компонента `BusinessAppContent` в детальный просмотр бизнеса (`BusinessDetailPage`).
- `admin/src/i18n/admin.ts` — переводы всех новых UI-элементов на русский и казахский языки (`appContent`, `content.tabApp`, `content.selectBusinessHint`).
- `admin/tests/app-content.test.tsx` *(новый)* — 6 модульных тестов Vitest на рендеринг магазинов, текстов, модалок, переключение вкладок и скоупинг менеджера.

### Отчёты и скриншоты:
- `reports/BUSINESS_APP_CONTENT_2026-11-04.md` *(этот документ)*.
- `reports/business-app-content-2026-11-04/admin-app-content-ru-1366.png`
- `reports/business-app-content-2026-11-04/admin-app-content-ru-390.png`
- `reports/business-app-content-2026-11-04/admin-app-content-kk-1366.png`
- `reports/business-app-content-2026-11-04/admin-app-content-kk-390.png`

---

## 3. Проверки до правок (Baseline)

1. **Alembic последняя ревизия:**
   - `backend/migrations/versions/0012_push_devices.py` — проверена, является действующей `down_revision`.
2. **Бэкенд тесты (`backend/.venv/bin/pytest -q`):**
   - Вывод: `392 passed, 36 skipped, 4 warnings in 60.29s`
3. **Бэкенд линтер (`backend/.venv/bin/ruff check app`):**
   - Вывод: `All checks passed!`
4. **Бэкенд линтер (`backend/.venv/bin/ruff check .`):**
   - Вывод: `Found 2 errors` (ровно 2 известных baseline-замечания в `tests/test_barcode_contract.py`).
5. **Бэкенд mypy (`backend/.venv/bin/mypy app`):**
   - Вывод: `Found 16 errors in 2 files (checked 65 source files)` (только в `media_storage.py` и `image_service.py`).
6. **Кабинет Vitest (`admin/` -> `npx vitest run --maxWorkers=1`):**
   - Вывод: `Test Files 20 passed (20), Tests 163 passed (163) in 58.74s`
7. **Кабинет typecheck (`npm run typecheck`):**
   - Вывод: 0 ошибок (`tsc --noEmit` exit 0).
8. **Кабинет lint (`npm run lint`):**
   - Вывод: 0 ошибок (`eslint .` exit 0).
9. **Кабинет build (`npm run build`):**
   - Вывод: сборка `dist/` успешно завершена за 579 мс.

---

## 4. Архитектурные решения

### 4.1. Хранение текстов: JSON-колонка `businesses.app_texts` vs отдельная таблица
- **Принятое решение:** Колонка `app_texts` типа `JSON` (в PostgreSQL `JSON`, в SQLite `JSON`) в таблице `businesses`.
- **Обоснование:**
  1. Отношение строго 1:1 к бизнесу. Количество настраиваемых текстовых блоков фиксировано и невелико (`home_store_note_lead`, `balance_delay_note`).
  2. Не требует дополнительных JOIN-ов при чтении бизнеса или контента приложения покупателя.
  3. Позволяет атомарно обновлять как отдельные ключи локализации (PATCH-семантика на уровне сервиса с объединением существующего словаря), так и всю конфигурацию целиком.
  4. При добавлении новых текстовых блоков в будущем не потребуется изменять схему БД через DDL миграции.

### 4.2. Размещение раздела в кабинете администратора
- **Принятое решение:** Создан универсальный переиспользуемый компонент `BusinessAppContent(businessId, businessName)`. Он внедрен в двух местах:
  1. В `ContentPage.tsx` в виде третьей вкладки `app` («Магазины и инфо» / «Дүкендер мен мәтіндер») рядом с «Акции и баннеры» и «Уведомления». Менеджер бизнеса видит свой магазин автоматически без селектора бизнеса; суперадминистратор выбирает бизнес из выпадающего списка.
  2. В `BusinessesPage.tsx` на странице детального просмотра конкретного бизнеса `BusinessDetailPage` (доступна суперадминистратору).
- **Обоснование:** Обеспечивает максимальное удобство для менеджеров магазина (весь клиентский контент собран на одной странице «Приложение») и суперадминистраторов (можно быстро настроить адреса и тексты прямо из карточки бизнеса в разделе «Бизнесы»).

### 4.3. Настройка CORS и метод PUT
- Ранее в `backend/app/main.py` параметр `allow_methods` ограничивался `["GET", "POST", "PATCH", "DELETE"]`.
- Для соответствия REST-семантике эндпоинта сохранения текстов `PUT /admin/businesses/{id}/app-texts` метод `"PUT"` добавлен в CORS `allow_methods`.
- Соответствующий тест preflight OPTIONS запросов в `backend/tests/test_admin_config.py` обновлен: метод `PUT` теперь проверяется на возвращение статуса `200 OK`, а недопустимый метод (например, `TRACE`) — на отказ `400 Bad Request`.

---

## 5. Формат API

### 5.1. Управление магазинами (Admin API)

- **Список магазинов:**
  ```http
  GET /admin/businesses/{business_id}/stores
  X-Admin-Request: 1
  Authorization: Bearer <token>
  ```
  *Ответ:* `200 OK`
  ```json
  [
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "business_id": "11111111-1111-1111-1111-111111111111",
      "title_ru": "Супермаркет «КеремЕт»",
      "title_kk": "«КеремЕт» супермаркеті",
      "address_ru": "проспект Тауелсиздик, 4",
      "address_kk": "Тәуелсіздік даңғылы, 4",
      "map_url": "https://2gis.kz/astana/firm/70000001103172202",
      "sort_order": 1,
      "is_active": true,
      "created_at": "2026-10-01T00:00:00Z",
      "updated_at": "2026-10-01T00:00:00Z"
    }
  ]
  ```

- **Создание магазина:**
  ```http
  POST /admin/businesses/{business_id}/stores
  Content-Type: application/json

  {
    "title_ru": "Супермаркет «КеремЕт»",
    "title_kk": "«КеремЕт» супермаркеті",
    "address_ru": "проспект Тауелсиздик, 4",
    "address_kk": "Тәуелсіздік даңғылы, 4",
    "map_url": "https://2gis.kz/astana/firm/70000001103172202",
    "sort_order": 0,
    "is_active": true
  }
  ```
  *Ответ:* `201 Created`

- **Обновление магазина:**
  ```http
  PATCH /admin/businesses/{business_id}/stores/{store_id}
  Content-Type: application/json

  {
    "sort_order": 2,
    "is_active": false
  }
  ```
  *Ответ:* `200 OK`

- **Удаление магазина:**
  ```http
  DELETE /admin/businesses/{business_id}/stores/{store_id}
  ```
  *Ответ:* `204 No Content`

### 5.2. Управление текстами (Admin API)

- **Получение текстов:**
  ```http
  GET /admin/businesses/{business_id}/app-texts
  ```
  *Ответ:* `200 OK`
  ```json
  {
    "home_store_note_lead": {
      "ru": "Вы можете потратить эти баллы в супермаркете «КеремЕт»:",
      "kk": "Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:"
    },
    "balance_delay_note": {
      "ru": "Баллы начисляются после смены",
      "kk": "Ұпайлар ауысымнан кейін есептеледі"
    }
  }
  ```

- **Сохранение текстов:**
  ```http
  PUT /admin/businesses/{business_id}/app-texts
  Content-Type: application/json

  {
    "home_store_note_lead": {
      "ru": "Вы можете потратить эти баллы в супермаркете «КеремЕт»:",
      "kk": "Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:"
    },
    "balance_delay_note": {
      "ru": "Баллы начисляются после закрытия смены (2 раза в сутки)",
      "kk": "Ұпайлар ауысым жабылғаннан кейін есептеледі (тәулігіне 2 рет)"
    }
  }
  ```
  *Ответ:* `200 OK`

### 5.3. Контент приложения покупателя (Customer API)

- **Запрос:**
  ```http
  GET /me/app-content?business_id=11111111-1111-1111-1111-111111111111
  Authorization: Bearer <customer_token>
  If-None-Match: "3a9c7b..."
  ```
- **Заголовки ответа:**
  ```http
  HTTP/1.1 200 OK
  Content-Type: application/json
  ETag: "3a9c7b..."
  Cache-Control: private, max-age=300
  ```
  *Тело:*
  ```json
  {
    "business_id": "11111111-1111-1111-1111-111111111111",
    "stores": [
      {
        "id": "22222222-2222-2222-2222-222222222222",
        "title": {
          "ru": "Супермаркет «КеремЕт»",
          "kk": "«КеремЕт» супермаркеті"
        },
        "address": {
          "ru": "проспект Тауелсиздик, 4",
          "kk": "Тәуелсіздік даңғылы, 4"
        },
        "map_url": "https://2gis.kz/astana/firm/70000001103172202",
        "sort_order": 1
      }
    ],
    "app_texts": {
      "home_store_note_lead": {
        "ru": "Вы можете потратить эти баллы в супермаркете «КеремЕт»:",
        "kk": "Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:"
      },
      "balance_delay_note": {
        "ru": "Баллы начисляются после закрытия смены (2 раза в сутки)",
        "kk": "Ұпайлар ауысым жабылғаннан кейін есептеледі (тәулігіне 2 рет)"
      }
    },
    "updated_at": "2026-10-01T00:00:00Z"
  }
  ```
- При неизменном контенте возвращается `HTTP/1.1 304 Not Modified` с пустым телом.
- Если у покупателя нет активной карты данного бизнеса — возвращается `HTTP/1.1 403 Forbidden` (`{"detail": "NO_CARD_FOR_BUSINESS"}`).

---

## 6. Проверки после правок (Сырой вывод)

### 6.1. Полный прогон тестов бэкенда (`backend/.venv/bin/pytest -q`)
```text
397 passed, 36 skipped, 4 warnings in 59.52s
```
*(+5 новых тестов: 4 в `test_business_app_content.py` + 1 в `test_admin_config.py`).*

### 6.2. Модульные тесты функционала (`pytest tests/test_business_app_content.py -v`)
```text
tests/test_business_app_content.py::test_superadmin_and_manager_store_lifecycle PASSED [ 25%]
tests/test_business_app_content.py::test_store_validation_and_url_security PASSED [ 50%]
tests/test_business_app_content.py::test_app_texts_lifecycle_and_validation PASSED [ 75%]
tests/test_business_app_content.py::test_customer_app_content_endpoint PASSED [100%]

============================== 4 passed in 1.66s ===============================
```

### 6.3. Тесты на временном кластере PostgreSQL 16 (`pytest -k postgres`)
```text
tests/test_config.py .                                                   [  2%]
tests/test_postgres_admin_security.py .......                            [ 21%]
tests/test_postgres_agent_sync_concurrency.py ....                       [ 32%]
tests/test_postgres_bind_concurrency.py ....                             [ 43%]
tests/test_postgres_customer_auth_concurrency.py ......                  [ 59%]
tests/test_postgres_model_smoke.py .                                     [ 62%]
tests/test_postgres_sms_concurrency.py ....                              [ 72%]
tests/test_postgres_wallet_concurrency.py ......                         [ 89%]
tests/test_postgres_wappi_concurrency.py ....                            [100%]

================ 37 passed, 396 deselected, 1 warning in 16.39s ================
```

### 6.4. Проверка миграций Alembic (PostgreSQL 16)
- **Upgrade head с 0001 до 0013:**
  ```text
  INFO  [alembic.runtime.migration] Running upgrade 0012_push_devices -> 0013_business_app_content, Business stores and localized app texts.
  ```
- **Downgrade -1 (откат до 0012):**
  ```text
  INFO  [alembic.runtime.migration] Running downgrade 0013_business_app_content -> 0012_push_devices, Business stores and localized app texts.
  ```
- **Повторный Upgrade head (до 0013):**
  ```text
  INFO  [alembic.runtime.migration] Running upgrade 0012_push_devices -> 0013_business_app_content, Business stores and localized app texts.
  ```
- Миграция полностью обратима, проверена на структуре PostgreSQL.

### 6.5. Линтер и mypy бэкенда
- **`backend/.venv/bin/ruff check app`**:
  ```text
  All checks passed!
  ```
- **`backend/.venv/bin/ruff check .`**:
  ```text
  Found 2 errors (только 2 baseline-ошибки в tests/test_barcode_contract.py).
  ```
- **`backend/.venv/bin/mypy app`**:
  ```text
  Found 16 errors in 2 files (только baseline-ошибки в media_storage.py и image_service.py; 0 новых ошибок).
  ```

### 6.6. Тесты кабинета Vitest (`admin/` -> `npx vitest run --maxWorkers=1`)
```text
Test Files  21 passed (21)
     Tests  169 passed (169)
  Start at  16:37:32
  Duration  63.01s (transform 1.17s, setup 4.48s, import 3.49s, tests 28.00s, environment 20.79s)
```
*(Все 21 файл тестов, включая 6 новых в `tests/app-content.test.tsx`, прошли успешно).*

### 6.7. Проверки TypeScript, ESLint и сборки в `admin/`
- **`npm run typecheck`**: exit code 0, 0 ошибок.
- **`npm run lint`**: exit code 0, 0 ошибок.
- **`npm run build`**: exit code 0, продакшен бандл собран без предупреждений.

### 6.8. Чистота git diff
- **`git diff --check`**: exit code 0, нет висячих пробелов и лишних строк в конце файлов.

---

## 7. Снимки экрана (`reports/business-app-content-2026-11-04/`)

Сгенерированы 4 полностраничных скриншота на изолированном сервере с тестовыми данными без использования продакшена:
1. `admin-app-content-ru-1366.png` (523 КБ) — Десктоп 1366px, русский язык. Видны таблицы магазинов с адресом, ссылкой на 2ГИС, порядком и статусом, а также блоки редактирования текстов RU/KK.
2. `admin-app-content-ru-390.png` (311 КБ) — Мобильный экран 390px, русский язык. Адаптивная карточная сетка магазинов, кнопки управления и формы ввода текстов.
3. `admin-app-content-kk-1366.png` (534 КБ) — Десктоп 1366px, казахский язык («ФИЗИКАЛЫҚ ДҮКЕНДЕР», «Дүкен қосу», «ҚОЛДАНБА МӘТІНДЕРІ», «Мәтіндерді сақтау»).
4. `admin-app-content-kk-390.png` (320 КБ) — Мобильный экран 390px, казахский язык.

---

## 8. Инструкция для владельца для настройки пилота («КеремЕт»)

Для запуска данных пилота в продакшен владельцу необходимо выполнить следующие действия через кабинет администратора:

1. **Войти в кабинет** под учетной записью суперадминистратора или менеджера супермаркета «КеремЕт».
2. **Перейти в раздел «Приложение»** (меню слева) -> вкладка **«Магазины и инфо»**.
   *(Если вход под суперадминистратором — выбрать «Супермаркет «КеремЕт» в выпадающем списке бизнесов)*.
3. **Добавить физический магазин:**
   - Нажать кнопку **«Добавить магазин»**.
   - **Название (RU):** `Супермаркет «КеремЕт»`
   - **Название (KK):** `«КеремЕт» супермаркеті`
   - **Адрес (RU):** `проспект Тауелсиздик, 4`
   - **Адрес (KK):** `Тәуелсіздік даңғылы, 4`
   - **Ссылка на карту:** `https://2gis.kz/astana/firm/70000001103172202`
   - **Порядок отображения:** `1`
   - **Статус:** галочка «Активен (показывается покупателям)» включена.
   - Нажать **«Создать»**.
4. **Настроить тексты приложения:**
   - **Фраза перед адресом на главной (RU):** `Вы можете потратить эти баллы в супермаркете «КеремЕт»:`
   - **Фраза перед адресом на главной (KK):** `Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:`
   - **Текст о задержке баланса на экране статуса (RU):** `Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.`
   - **Текст о задержке баланса на экране статуса (KK):** `Баланс бірден жаңартылмайды. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі.`
   - Нажать кнопку **«Сохранить тексты»**.

---

## 9. Что не менялось и ограничения

- Папка `mobile/`, код агента 1С и лендинг **не изменялись**.
- Никаких авто-миграций данных пилота в коде миграции не создавалось (согласно правилу — данные вносятся владельцем через интерфейс).
- Production-деплой, `git commit` и `git push` не выполнялись.
- Все временные процессы (Vite dev, mock-сервер, кластер PostgreSQL 16) штатно остановлены и удалены.

---

## 10. Исправления вёрстки (по промпту от 2026-11-04)

### 10.1. Список изменённых файлов

1. **`admin/src/features/BusinessAppContent.tsx`**:
   - Интегрированы хуки `useTableExpansion`, `useCompactRows` и компонент `CompactTableToggle` из `../components/CompactTable` по аналогии с другими таблицами кабинета («Акции и баннеры», «Карты»).
   - Обернута таблица магазинов в `.table-wrap` со стандартным паттерном строк кабинета и кнопкой переключения компактного режима.
   - Убраны красные верхние надзаголовки `.panel-kicker` («ФИЗИЧЕСКИЕ МАГАЗИНЫ», «ТЕКСТЫ В ПРИЛОЖЕНИИ»); заменены на стандартные `.section-heading` с `<h2>` и `<p className="muted-copy">`.
   - В ячейках таблицы выводится только активный язык интерфейса: RU при RU (`store.title_ru`, `store.address_ru`), KK при KK (`store.title_kk || store.title_ru`, `store.address_kk || store.address_ru`). Вторичный язык доступен только в модальном диалоге редактирования/создания.
   - Кнопки действий форматированы как `.pagination-actions .link-button`.
   - Форма текстов приложения обернута в `.app-texts-form`, блоки fieldset — в `.app-texts-fieldset`, поля ввода — в `.app-text-textarea`, кнопка сохранения — в `.app-texts-submit`.

2. **`admin/src/styles/admin.css`**:
   - Для полосы вкладок `.search-tabs` добавлены правила горизонтальной прокрутки внутри контейнера без переполнения страницы: `overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; scrollbar-width: thin;`, для `.search-tab`: `flex-shrink: 0; white-space: nowrap;`.
   - Для предотвращения расширения колонок CSS Grid добавлен сброс минимальной ширины: `.page-stack { min-width: 0; width: 100%; max-width: 100%; } .page-stack > * { min-width: 0; max-width: 100%; }`.
   - Для текстовых полей `.app-text-textarea` задан стандартный шрифт кабинета: `font-family: inherit; font-size: 13px; line-height: 1.5; width: 100%; max-width: 100%; box-sizing: border-box; min-width: 0;`.
   - Добавлены классы `.app-texts-form`, `.app-texts-fieldset`, `.app-texts-submit`.
   - В медиа-запрос `@media (max-width: 760px)` добавлены правила адаптивности для карточек и полей: `.surface-card { min-width: 0; max-width: 100%; box-sizing: border-box; padding: 16px 14px; }`, `.app-texts-fieldset { padding: 12px; }`, `.app-texts-submit { width: 100%; }`.

### 10.2. Сырой вывод проверок до и после правок

#### До внесения правок вёрстки:
- **`npx vitest run --maxWorkers=1`**:
  ```text
  Test Files  21 passed (21)
       Tests  169 passed (169)
    Start at  16:54:10
    Duration  172.82s (transform 3.48s, setup 7.72s, import 12.01s, tests 70.83s, environment 58.74s)
  ```
- **`npm run typecheck`**: `exit code 0` (0 ошибок).
- **`npm run lint`**: `exit code 0` (0 ошибок).
- **`npm run build`**: `exit code 0` (dist/ собрался за 812 ms).

#### После внесения правок вёрстки:
- **`npx vitest run --maxWorkers=1`**:
  ```text
  Test Files  21 passed (21)
       Tests  169 passed (169)
    Start at  17:09:45
    Duration  64.06s (transform 1.13s, setup 4.70s, import 3.51s, tests 27.60s, environment 21.65s)
  ```
- **`npm run typecheck`**: `exit code 0` (0 ошибок).
- **`npm run lint`**: `exit code 0` (0 ошибок).
- **`npm run build`**:
  ```text
  vite v6.4.1 building for production...
  transforming...
  ✓ 2056 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   1.44 kB │ gzip:   0.69 kB
  dist/assets/index-BtA4R52_.css   36.85 kB │ gzip:   7.38 kB
  dist/assets/index-CVz5i7pW.js   563.36 kB │ gzip: 164.71 kB
  ✓ built in 844ms
  ```
- **`git diff --check`**: `exit code 0` (нет висячих пробелов и проблем с окончаниями строк).

### 10.3. Измерения в браузере: `scrollWidth` / `innerWidth` и шрифты

Проверены 8 состояний страницы (4 разрешения x 2 языка) на локальном сервере с тестовыми данными. Перед каждым измерением выполнялась чистая перезагрузка страницы на целевой ширине.

| Язык | Целевая ширина | `window.innerWidth` | `document.documentElement.scrollWidth` | Горизонтальная прокрутка (`scrollWidth <= innerWidth`) | Шрифт textarea (`font-family` / `font-size`) | Статус бокового меню (1366 px) |
|---|---|---|---|---|---|---|
| **RU** | 320 px | 320 px | 320 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **RU** | 390 px | 390 px | 390 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **RU** | 768 px | 768 px | 768 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **RU** | 1366 px | 1366 px | 1366 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | Ширина: 260px, фон: `rgb(15, 23, 42)`, логотип цел |
| **KK** | 320 px | 320 px | 320 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **KK** | 390 px | 390 px | 390 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **KK** | 768 px | 768 px | 768 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | — |
| **KK** | 1366 px | 1366 px | 1366 px | **Нет (true)** | `Roboto, system-ui, ...` / 13px | Ширина: 260px, фон: `rgb(15, 23, 42)`, логотип цел |

### 10.4. Расследование дефекта бокового меню на 1366 px (Пункт 2)

- **Причина:** Дефект на предыдущем снимке `admin-app-content-kk-1366.png` (обрыв фона бокового меню на ~150px) являлся **артефактом изменения размера окна в Chromium/DevTools без перезагрузки страницы**. При последовательном программном вызове `resize_page` со значения 390px до 1366px без перезагрузки страницы Chromium сохранил внутренние области отсечения (clip-path / composite layers) от мобильного представления.
- **Доказательство:**
  1. В исходном коде кабинета (`AdminShell.tsx`, `admin.css`) структура сайдбара строго фиксирована:
     ```css
     .admin-shell { display: grid; grid-template-columns: 260px 1fr; }
     .sidebar { width: 260px; background: var(--navy); } /* var(--navy) = #0f172a */
     ```
  2. При чистой загрузке страницы сразу на ширине 1366 px (как для RU, так и для KK) вычисленные стили сайдбара:
     - `sidebarWidth: 260px`
     - `sidebarBackground: "rgb(15, 23, 42)"` (#0f172a)
     - Логотип `poscenter.kz` полностью отображается без разрезов.
     - Пункты меню («Бизнестер», «Агенттер», «Карталар мен клиенттер») отображаются белым текстом строго на тёмно-синем фоне сайдбара и не заходят на белую область контента.
  3. Дефект полностью отсутствует при соблюдении правила «перезагрузка страницы перед каждым снимком на целевой ширине».

### 10.5. Обновлённые снимки экрана (`reports/business-app-content-2026-11-04/`)

Все 8 снимков пересняты с чистой перезагрузкой страницы и сохранены в отчёте:
1. `admin-app-content-ru-320.png` (332 689 байт) — Мобильный 320 px, русский язык. Без горизонтального скролла (`scrollWidth: 320`), таблица с компактным переключателем, поля Roboto 13px.
2. `admin-app-content-ru-390.png` (555 442 байт) — Мобильный 390 px, русский язык. Карточки, поля и кнопка точно в границах экрана (`scrollWidth: 390`).
3. `admin-app-content-ru-768.png` (457 515 байт) — Планшет 768 px, русский язык.
4. `admin-app-content-ru-1366.png` (521 403 байт) — Десктоп 1366 px, русский язык. Сайдбар 260 px, логотип цел.
5. `admin-app-content-kk-320.png` (334 661 байт) — Мобильный 320 px, казахский язык. Без горизонтального скролла (`scrollWidth: 320`).
6. `admin-app-content-kk-390.png` (566 377 байт) — Мобильный 390 px, казахский язык. Без горизонтального скролла (`scrollWidth: 390`).
7. `admin-app-content-kk-768.png` (466 265 байт) — Планшет 768 px, казахский язык.
8. `admin-app-content-kk-1366.png` (540 936 байт) — Десктоп 1366 px, казахский язык. Сайдбар 260 px цел, фон сплошной тёмно-синий, текст пунктов не выходит за пределы.

