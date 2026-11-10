# Согласованный контракт: Координаты магазинов и динамические статусы (с отдельным периодом оборота) — 2026-11-10

**Статус:** Уточнено по замечаниям куратора от 2026-11-10, готово для передачи Claude.
**Основание:** `docs/PROMPT_STATUSES_COORDINATES_CONTRACT_FIX_2026-11-10.md`, `docs/PROMPT_ADMIN_FINAL_REVISIONS_2026-11-09.md`, решения владельца.

---

## 1. Контракт координат магазинов (Business Store Coordinates)

### 1.1. База данных и модель (`business_stores`)
К таблице `business_stores` добавляются два поля:
- `latitude`: `Numeric(9, 6)`, nullable (диапазон `-90.000000` .. `+90.000000`)
- `longitude`: `Numeric(9, 6)`, nullable (диапазон `-180.000000` .. `+180.000000`)

### 1.2. Сериализация в API и типы данных
- В JSON REST API координаты отдаются строго как **JSON `number | null`** (число с плавающей точкой, `float`), **не как строки Decimal**.
- Старые магазины без координат сохраняются и отдают `null`.

### 1.3. Правила валидации (Admin API и Backend)
1. **Парная валидация:** либо оба поля заданы числами в допустимых диапазонах, либо оба равны `null`. Запрещено сохранять только широту без долготы или долготу без широты.
2. **Диапазоны:**
   - Широта (`latitude`): от `-90.0` до `+90.0`
   - Долгота (`longitude`): от `-180.0` до `+180.0`
3. **PATCH-валидация после слияния:** при частичном обновлении (`PATCH`) валидация парности и диапазонов проверяется на результирующем (merged) состоянии записи. Если передано только одно координатное поле, а второе уже есть в базе — результирующая пара должна быть валидной.
4. **Очистка координат:** для удаления координат из магазина передаётся явный `null` в оба поля: `{"latitude": null, "longitude": null}`.
5. Никаких платных геокодеров, внешних сетевых запросов и парсинга URL 2GIS/Google/Яндекс.

### 1.4. Admin CRUD API (`/admin/businesses/{id}/stores`)
- `GET /admin/businesses/{business_id}/stores`
  Возвращает список `BusinessStoreAdminItem` с `latitude: float | null`, `longitude: float | null`.
- `POST /admin/businesses/{business_id}/stores`
  Тело: `BusinessStoreCreateRequest`
  ```json
  {
    "title_ru": "Супермаркет №1",
    "title_kk": "№1 супермаркеті",
    "address_ru": "ул. Абая, 10",
    "address_kk": "Абай к-сі, 10",
    "map_url": "https://2gis.kz/...",
    "sort_order": 10,
    "is_active": true,
    "latitude": 43.238949,
    "longitude": 76.889709
  }
  ```
- `PATCH /admin/businesses/{business_id}/stores/{store_id}`
  Тело: `BusinessStoreUpdateRequest` (все поля опциональны).
- `DELETE /admin/businesses/{business_id}/stores/{store_id}`

### 1.5. Публичный endpoint контента: `GET /me/app-content`
> **Важно:** endpoint мобильного контента — именно **`GET /me/app-content`** (роутер `/me`, путь `/app-content`). Эндпоинт защищён и требует авторизации покупателя с Bearer-токеном (неавторизованный запрос возвращает HTTP 401 Unauthorized, гостевой доступ без токена к `/me` отклонён согласно архитектуре безопасности).

В объекте `stores: AppStoreItem[]` отдаются `latitude` и `longitude`:
```json
{
  "id": "c1f7a0b2-4d2a-44d8-b593-9c869e86a012",
  "title_ru": "Супермаркет на Абая",
  "title_kk": "Абай көшесіндегі супермаркет",
  "address_ru": "ул. Абая, 10",
  "address_kk": "Абай к-сі, 10",
  "map_url": "https://2gis.kz/almaty/...",
  "sort_order": 1,
  "latitude": 43.238949,
  "longitude": 76.889709
}
```
При отсутствии координат:
```json
  "latitude": null,
  "longitude": null
```

### 1.6. TypeScript контракт для Claude (`mobile/src/types/api.ts`)
```typescript
export interface AppStoreItem {
  id: string;
  title_ru: string;
  title_kk: string;
  address_ru: string;
  address_kk: string;
  map_url: string | null;
  sort_order: number;
  latitude?: number | null;
  longitude?: number | null;
}
```

### 1.7. Поведение в приложении (Claude)
- Расстояние вычисляется по формуле гаверсинуса (по прямой) между координатами пользователя и `(latitude, longitude)` магазина. Подпись в UI: «По прямой».
- Использовать **только foreground location** и только по прямому действию пользователя (открытие вкладки магазинов). Без фонового отслеживания, без холодного старта.
- Координаты пользователя **никогда не передаются на бэкенд**.
- При отсутствии координат у магазина (`null`), отказе в доступе или выключенной геолокации: показывать адрес и «Расстояние недоступно» (не показывать 0 км).

---

## 2. Контракт динамических статусов (с отдельным периодом оборота)

### 2.1. Принцип модели: отдельный период у каждого уровня
Каждый уровень шкалы лояльности имеет **собственный период скользящего окна оборота** `turnover_period_months` (положительное целое число календарных месяцев от 1 до 36).

Начальные условия магазина Keremet:
- Уровень 1: 0 .. <100 000 ₸, **6 месяцев**, 2%, «Нет-нет заглядывает»
- Уровень 2: 100 000 .. <200 000 ₸, **6 месяцев**, 3%, «Продуктовый эксперт»
- Уровень 3: >= 200 000 ₸, **6 месяцев**, 4%, «Шоппинг-босс»

При этом кабинет позволяет настраивать независимые периоды для любого бизнеса (например, Уровень 1 — 3 мес, Уровень 2 — 6 мес, Уровень 3 — 12 мес).

### 2.2. Таблица БД: `business_loyalty_tiers`
- `id`: `UUID` (PK, default uuid4)
- `business_id`: `UUID` (FK -> `businesses.id`, ON DELETE CASCADE, NOT NULL)
- `level`: `Integer` (порядковый номер: 1, 2, 3...)
- `priority`: `Integer` (приоритет уровня: уникален в пределах бизнеса, большее число = выше приоритет; по умолчанию равен `level`)
- `name_ru`: `String(120)` (название на русском)
- `name_kk`: `String(120)` (название на казахском, по умолчанию совпадает с русским или заполняется менеджером)
- `description_ru`: `Text`, nullable
- `description_kk`: `Text`, nullable
- `image_url`: `String(1024)`, nullable (ссылка на загруженную через кабинет картинку, scoped к бизнесу)
- `turnover_period_months`: `Integer` (от 1 до 36 календарных месяцев)
- `min_turnover`: `Numeric(14, 2)` (нижняя граница, включительно, `>= 0.00`)
- `max_turnover`: `Numeric(14, 2)`, nullable (верхняя граница, исключительно; `null` = без верхней границы)
- `percent`: `Numeric(5, 2)` (процент кэшбэка, от `0.00` до `100.00`)
- `is_active`: `Boolean` (default True)
- `created_at`: `DateTime(timezone=True)`
- `updated_at`: `DateTime(timezone=True)`

**Ограничения целостности:**
- `UNIQUE(business_id, level)`
- `UNIQUE(business_id, priority)`
- `CHECK(turnover_period_months >= 1 AND turnover_period_months <= 36)`
- `CHECK(min_turnover >= 0)`
- `CHECK(max_turnover IS NULL OR max_turnover > min_turnover)`
- `CHECK(percent >= 0 AND percent <= 100)`

### 2.2.1. Миграция схемы БД
- Идентификатор Alembic: `0019_coords_and_loyalty_tiers` (down revision: `0018_business_splash_config`).
- Длина ревизии — 29 символов (строго <= 32 символов для совместимости с `alembic_version.version_num VARCHAR(32)` на PostgreSQL).
- Проверена двусторонним прогоном `upgrade 0019 -> downgrade 0018 -> upgrade 0019` на реальном PostgreSQL 16.

### 2.2.2. Правила валидации интервалов оборота (Turnover Range Validation)
Интервалы оборота проверяются как полуоткрытые `[min_turnover, max_turnover)`:
1. **Строго в пределах одного бизнеса и одного периода `turnover_period_months`:**
   - Интервалы статусов с **одинаковым** периодом оборота не должны пересекаться. Пересечение вызывает ошибку `409 CONFLICT`.
   - Граничные касания разрешены (например, `[0, 100000)` и `[100000, 200000)` являются корректными смежными интервалами).
   - Статусы с **разными** периодами оборота (например, 3 мес и 6 мес) или статусы разных бизнесов могут иметь одинаковые числовые диапазоны без конфликта.
2. При `PATCH` валидация выполняется на объединённом (merged) состоянии с учётом исключения текущего редактируемого статуса.

### 2.2.3. Валидация изображений статусов (Scoped Media Validation)
1. Разрешены только относительные медиа-пути внутри `/media/business-assets/` или абсолютные URL доверенного API хоста (`SAFE_MEDIA_PATH_REGEX`).
2. Внешние произвольные ссылки и SSRF строго запрещены (`422 VALIDATION_ERROR`).
3. Картинка обязана принадлежать тому же бизнесу (`business_id`), для которого создаётся/редактируется статус. Попытка прикрепить изображение чужого бизнеса отклоняется с кодом `403 FORBIDDEN`.
4. Несуществующий медиафайл отклоняется с кодом `404 NOT_FOUND`.
5. При ошибке валидации картинки в `PATCH` статус не изменяется, старое валидное изображение остаётся нетронутым.

### 2.3. Публичный каталог шкалы: `GET /me/app-content`
Каталог отдаётся в общем контенте приложения. Он содержит **только общую шкалу магазина** и **не содержит персональных данных, чеков или выбранного уровня конкретного покупателя**:
```json
{
  "business_id": "b1a2c3d4-...",
  "stores": [ ... ],
  "app_texts": { ... },
  "splash": { ... },
  "loyalty_tiers": [
    {
      "id": "e5b8c3a1-1111-...",
      "level": 1,
      "priority": 1,
      "name_ru": "Нет-нет заглядывает",
      "name_kk": "Нет-нет заглядывает",
      "description_ru": "Стартовый уровень кэшбэка",
      "description_kk": "Бастапқы кэшбэк деңгейі",
      "image_url": "https://api.cashback-qr.poscenter.kz/media/tiers/e5b8c3a1.webp",
      "turnover_period_months": 6,
      "min_turnover": "0.00",
      "max_turnover": "100000.00",
      "percent": "2.00"
    },
    {
      "id": "f6a9d4b2-2222-...",
      "level": 2,
      "priority": 2,
      "name_ru": "Продуктовый эксперт",
      "name_kk": "Продуктовый эксперт",
      "description_ru": "Повышенный кэшбэк",
      "description_kk": "Жоғары кэшбэк",
      "image_url": "https://api.cashback-qr.poscenter.kz/media/tiers/f6a9d4b2.webp",
      "turnover_period_months": 6,
      "min_turnover": "100000.00",
      "max_turnover": "200000.00",
      "percent": "3.00"
    },
    {
      "id": "a7b0e5c3-3333-...",
      "level": 3,
      "priority": 3,
      "name_ru": "Шоппинг-босс",
      "name_kk": "Шоппинг-босс",
      "description_ru": "Максимальный кэшбэк на всё",
      "description_kk": "Барлық сатып алуларға максималды кэшбэк",
      "image_url": "https://api.cashback-qr.poscenter.kz/media/tiers/a7b0e5c3.webp",
      "turnover_period_months": 6,
      "min_turnover": "200000.00",
      "max_turnover": null,
      "percent": "4.00"
    }
  ],
  "loyalty_tiers_version": 1,
  "updated_at": "2026-11-10T00:00:00Z"
}
```

### 2.4. Версионирование и инвалидация кеша
- В таблицу `businesses` добавляется `loyalty_tiers_version: Integer` (начинается с 1).
- При любой мутации статуса (создание, изменение, удаление, смена порядка/активности) бэкенд инкрементирует `loyalty_tiers_version` и обновляет `updated_at` бизнеса.
- Это гарантирует корректную работу `If-Modified-Since` и сброс локального кеша `app-content` на мобильных клиентах.

### 2.5. Приватный статус карты: `GET /me/cards` и `GET /me/cards/{id}`
Персональный статус карты отдаётся **строго в авторизованном карточном API**.
К объекту карты добавляется аддитивное поле `loyalty_status`:

```json
{
  "id": "c1f7a0b2-...",
  "barcode": "2000000001234",
  "balance": "1500.00",
  "is_blocked": false,
  "tier": {
    "level": 1,
    "name": "Нет-нет заглядывает",
    "percent": "2.00",
    "max_percent": "4.00",
    "spend_total": null
  },
  "loyalty_status": {
    "known": false,
    "reason": "unconfirmed",
    "tier_id": null,
    "level": null,
    "percent": null,
    "turnover_amount": null,
    "coverage_months": null,
    "calculated_at": null,
    "program_version": 1
  }
}
```

**Значения `reason`:**
- `"unconfirmed"` — оборот покупок за требуемые окна ещё не подтверждён агентом/1С (текущее состояние Keremet).
- `"stale"` — расчёт устарел (данные старше допустимого TTL обновления).
- `"no_match"` — подтверждённый оборот не попадает ни в один из диапазонов.
- `null` — статус успешно подтверждён (`known: true`).

### 2.6. Правило расчёта и защита неполного покрытия (Coverage Rule)
> **Критическое правило:** если у покупателя подтверждены покупки за $K$ месяцев (например, за 6 месяцев), но существует более приоритетный уровень $T_{\text{high}}$, требующий окно $M > K$ месяцев (например, 12 месяцев), **нельзя** преждевременно выбирать нижний уровень, считая верхний недостигнутым.
> Либо имеется подтверждённое покрытие чеков для всех окон уровней, способных повлиять на выбор, либо `known: false`, `reason: 'unconfirmed'`.
> Неизвестный оборот **никогда не приравнивается к 0**.

**Стабильный tie-break при совпадении условий разных окон:**
1. Наивысший `priority`
2. При равном `priority` — наибольший `level`
3. При равном `level` — наименьший `id` (детерминированная стабильность)

### 2.7. TypeScript контракты для Claude (`mobile/src/types/api.ts`)
```typescript
export interface AppLoyaltyTier {
  id: string;
  level: number;
  priority: number;
  name_ru: string;
  name_kk: string;
  description_ru: string | null;
  description_kk: string | null;
  image_url: string | null;
  turnover_period_months: number;
  min_turnover: string; // Строка Decimal, e.g. "0.00", "100000.00"
  max_turnover: string | null; // e.g. "200000.00" или null
  percent: string; // e.g. "2.00", "3.00", "4.00"
}

export interface CardLoyaltyStatus {
  known: boolean;
  reason: 'unconfirmed' | 'stale' | 'no_match' | null;
  tier_id: string | null;
  level: number | null;
  percent: string | null;
  turnover_amount: string | null;
  coverage_months: number | null;
  calculated_at: string | null;
  program_version: number;
}

export interface Card {
  id: string;
  barcode: string;
  balance: string;
  is_blocked: boolean;
  updated_at: string;
  bound_at: string;
  bind_method: string;
  business: {
    id: string;
    name: string;
    branding: {
      logo_url: string | null;
      primary_color: string | null;
      accent_color: string | null;
    } | null;
  };
  tier?: Tier | null; // Сохраняется для старых версий приложения
  loyalty_status?: CardLoyaltyStatus | null; // Новый безопасный контракт статуса
}

export interface AppContent {
  business_id: string;
  stores: AppStoreItem[];
  app_texts: CustomerAppTexts;
  splash?: CustomerAppSplashConfig;
  loyalty_tiers?: AppLoyaltyTier[];
  loyalty_tiers_version?: number;
  updated_at: string;
}
```

### 2.8. Статус интеграции с кассой и агентом
- Редактор статусов в кабинете и каталог в `/me/app-content` являются информационно-презентационными.
- Создание или изменение уровней в кабинете **не меняет автоматически правила начисления бонусов в 1С / Cash**.
- Поле `CardLoyaltyStatus.known` на бэкенде остаётся `false` (`reason: 'unconfirmed'`), пока не будет полностью реализован и принят сбор данных из 1C через агент по заданию `docs/PROMPT_AGENT_PURCHASE_TURNOVER_2026-11-09.md`.
