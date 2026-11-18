# CANDIDATE (rework1) — контракт безопасного содержания событий журнала (`promotion`, `notification`, `app_texts_updated`)

**Статус документа:**
- **Часть 1** (`promotion_*`, `notification_*`, `app_texts_updated`) — **РЕАЛИЗОВАНО в изолированном backend-кандидате `rework1`**: [`backend-audit-content-rework1-candidate.tgz`](file:///Users/nuras/Desktop/cashback-one/reports/admin-audit-content-rework-2026-11-16/backend/rework1/backend-audit-content-rework1-candidate.tgz) (`157 920` байт, SHA-256 `db86f0f3274e4970755ebff420b1de4e08731866de444cfb1ae3247a2dc2b5fc`) поверх принятой базы [`backend-scale-audit-candidate.tgz`](file:///Users/nuras/Desktop/cashback-one/reports/admin-eleven-items-finish-2026-11-16/backend-rework1/backend-scale-audit-candidate.tgz) (`SHA-256 b7e03da17cfc92143073d8f5519e7f66d79ee3f966d874baf4dc5c6a9b731b10`). Не выложено в production, ожидает приёмки.
- **Часть 2** (`business_splash_updated`, расширение/редакция `media_uploaded`) — **ТОЛЬКО ПРЕДЛОЖЕНИЯ (НЕ РЕАЛИЗОВАНО, НЕ В ALLOWLIST)**. `business_splash_updated` по-прежнему отдаёт `before_state: null`, `after_state: null`; `media_uploaded.url` не изменялся.

Базовый контракт шкалы и tier/store-проекций ([ADMIN_SCALE_AUDIT_PACKAGE_REWORK_2026-11-16.md](file:///Users/nuras/Desktop/cashback-one/reports/ADMIN_SCALE_AUDIT_PACKAGE_REWORK_2026-11-16.md), [ADMIN_SCALE_EDITOR_CONTRACT_CANDIDATE_2026-11-16.md](file:///Users/nuras/Desktop/cashback-one/docs/ADMIN_SCALE_EDITOR_CONTRACT_CANDIDATE_2026-11-16.md)) сохранён без изменений.

---

## Часть 1. Реализованные поля в кандидате `rework1` (`GET /admin/audit` → `items[]`)

Поля верхнего уровня элемента журнала не менялись:
`id`, `actor`, `admin_user_id`, `business_id`, `action`, `entity`, `before_state`, `after_state`, `created_at`.

### 1.1. Акции и баннеры (`promotion_created`, `promotion_updated`, `promotion_deleted`)

- `entity`: `"promotion"`
- **Сохранены прежние поля:**
  - `promotion_id`: UUID-строка акции/баннера;
  - `business_id`: UUID-строка бизнеса (для глобальных акций `AuditLog.business_id = null` ключ `business_id` внутри `before_state`/`after_state` не добавляется);
  - `kind`: `"banner" | "offer"`;
  - `is_active`: `boolean`.
- **Добавлены в writer (`_promotion_state`) и projector (`_project_promotion_fields`):**
  - `title`: `string` (1…120 символов, обрезаны пробелы по краям; проходит через `_safe_audit_value` — значения с `password=`/`token=`/`secret=`/`user:pass@`, префиксами токенов `agk_`/`pos_`/`rfr_`/`adm_rfr_`/`Bearer`/`eyJ…` и query-параметрами HTTPS URL редактируются на `[REDACTED]`; строка длиннее 120 символов или не-строка отбрасывается);
  - `starts_at`: UTC ISO-8601 (`"YYYY-MM-DDTHH:MM:SS+00:00"`) или явный `null` (если ключ присутствовал в снимке со значением `None`); **отсутствующий исторический ключ остаётся отсутствующим**, а **невалидное/переполняющее строковое значение в историческом JSON (например `9999-12-31T23:59:59-01:00` или `1000-01-01T00:00:00+23:59`) молча опускается, не превращаясь в `null`**;
  - `ends_at`: UTC ISO-8601 (`"YYYY-MM-DDTHH:MM:SS+00:00"`) или явный `null` по тем же правилам;
  - `sort_order`: `integer` в диапазоне `-1000..1000` (`bool` и строки отвергаются).
- **Валидация крайних дат на входе (`_PromotionFields.validate_4_digit_year`, `_normalize_promotion_dt`):** проверяются оба года (`parsed.year` и `as_utc(parsed).year` в `1000..9999`) внутри `try ... except (ValueError, OverflowError)` — переполнение/выход из 4 цифр после приведения к UTC возвращает HTTP `422` (`VALIDATION_ERROR`), не HTTP `500` и без частичной записи в БД/аудит.
- **Никогда не включаются:** `subtitle`, `badge`, `body`, `description`, `image_url`, `created_at`, `updated_at`, телефоны, токены, внутренние и произвольные JSON-поля.
- **Семантика доступа:** глобальные акции (`business_id = null`) видны в `GET /admin/audit` **только** `superadmin`; `business_manager` видит события **только** своего бизнеса и не видит глобальные/чужие события. Старые записи в `audit_log` по текущему содержимому таблицы `promotions` не достраиваются.

#### Примеры `promotion_*`

Создание акции бизнеса (с явными датами в UTC, переданными в `+05:00`, и порядком):
```json
{
  "action": "promotion_created",
  "entity": "promotion",
  "business_id": "11111111-1111-1111-1111-111111111111",
  "before_state": null,
  "after_state": {
    "promotion_id": "22222222-2222-2222-2222-222222222222",
    "business_id": "11111111-1111-1111-1111-111111111111",
    "kind": "offer",
    "title": "Осенняя скидка 10%",
    "starts_at": "2026-11-20T05:00:00+00:00",
    "ends_at": "2026-11-30T18:59:59+00:00",
    "sort_order": 5,
    "is_active": true
  }
}
```

Редактирование акции и очистка дат до `null` (`PATCH` с `starts_at: null, ends_at: null`):
```json
{
  "action": "promotion_updated",
  "entity": "promotion",
  "before_state": {
    "promotion_id": "22222222-2222-2222-2222-222222222222",
    "business_id": "11111111-1111-1111-1111-111111111111",
    "kind": "offer",
    "title": "Зимняя скидка 15%",
    "starts_at": "2026-11-22T05:00:00+00:00",
    "ends_at": "2026-11-30T18:59:59+00:00",
    "sort_order": 12,
    "is_active": false
  },
  "after_state": {
    "promotion_id": "22222222-2222-2222-2222-222222222222",
    "business_id": "11111111-1111-1111-1111-111111111111",
    "kind": "offer",
    "title": "Зимняя скидка 15%",
    "starts_at": null,
    "ends_at": null,
    "sort_order": 12,
    "is_active": false
  }
}
```

Историческое событие, записанное до доработки (отсутствующие ключи остаются отсутствующими):
```json
{
  "action": "promotion_updated",
  "entity": "promotion",
  "before_state": {
    "promotion_id": "44444444-4444-4444-4444-444444444444",
    "business_id": "11111111-1111-1111-1111-111111111111",
    "kind": "offer",
    "is_active": true
  },
  "after_state": {
    "promotion_id": "44444444-4444-4444-4444-444444444444",
    "business_id": "11111111-1111-1111-1111-111111111111",
    "kind": "offer",
    "is_active": true
  }
}
```

---

### 1.2. Рассылки (`notification_created`, `notification_deleted`)

- `entity`: `"notification"`
- **Разрешённые поля:**
  - `notification_id`: UUID-строка рассылки;
  - `business_id`: UUID-строка бизнеса (для глобальной рассылки с `AuditLog.business_id = null` ключ `business_id` внутри снимка не добавляется);
  - `kind`: `"info"`;
  - `title`: `string` (1…120 символов, секрето-фильтр через `_clean_str`; если в снимке `targeted_user: true`, `title` **не выдаётся**);
  - `targeted_user`: `boolean` (`false` для массовых рассылок);
  - `scheduled_at`: UTC ISO-8601 или явный `null` (если ключ присутствовал; крайние/битые даты опускаются);
  - `push_sent_at`: UTC ISO-8601 или явный `null`;
  - `push_devices`: неотрицательное целое число (`int`, не `bool`), если была попытка немедленной отправки;
  - `push_delivered`: неотрицательное целое число (`int`, не `bool`), если была попытка немедленной отправки.
- Входной валидатор `NotificationCreateRequest.validate_scheduled_at` также безопасно перехватывает `(ValueError, OverflowError)` и проверяет год до и после `as_utc`, возвращая HTTP `422`.
- **Никогда не включаются:** `body` (текст сообщения), `user_id`, `phone`, `redemption_id`, токены устройств, списки получателей и любые ПДн.
- **Семантика доступа:** глобальные рассылки (`business_id = null`) видны только `superadmin`; `business_manager` видит только рассылки своего бизнеса.

---

### 1.3. Тексты приложения (`app_texts_updated`) — РЕАЛИЗОВАНО по решению владельца (`OWNER_AUDIT_TEXT_VISIBILITY_2026-11-16.md`)

При сохранении через `PUT /admin/businesses/{business_id}/app-texts` нормальные тексты продолжают сохраняться и читаться через `Business.app_texts`, но в `audit_log` и в `GET /admin/audit` записываются и отдаются **только метаданные блоков и языков без самих текстов**.

- `action`: `"app_texts_updated"`, `entity`: `"business_app_texts"`.
- **Закрытый набор блоков (`_APP_TEXT_BLOCKS`):** `["home_text", "home_store_note_lead", "balance_delay_note"]`.
- **Закрытый набор языков (`_APP_TEXT_LOCALES`):** `["ru", "kk"]`.
- **Закрытый набор пар (`changed_locales`):** `{"home_text.ru", "home_text.kk", "home_store_note_lead.ru", "home_store_note_lead.kk", "balance_delay_note.ru", "balance_delay_note.kk"}`.
- **Поля `before_state`:**
  - `<block>`: `{"ru": boolean, "kk": boolean}` для каждого из трёх закрытых блоков (истинно, если обрезанный от пробелов текст не пуст);
  - `configured_fields`: отсортированный список блоков из закрытого набора, у которых заполнен хотя бы один язык (`ru` или `kk`).
- **Поля `after_state`:**
  - `<block>`: `{"ru": boolean, "kk": boolean}` для каждого из трёх закрытых блоков;
  - `configured_fields`: отсортированный список настроенных блоков после сохранения;
  - `changed_fields`: отсортированный список блоков, в которых реально изменилось хотя бы одно строковое значение (`before[block][lang] != after[block][lang]`, включая замену непустого текста `A` на непустой текст `B`);
  - `changed_locales`: отсортированный список изменившихся пар `<block>.<lang>`.
- **No-op `PUT /app-texts`:** существующее поведение создания строки `AuditLog` сохранено; при отсутствии реальных текстовых отличий возвращаются пустые списки `"changed_fields": []`, `"changed_locales": []` (фиктивные изменения не выдумываются).
- **Строгий projector (`_project_app_texts_state`):** на чтении/записи принимает в `<block>.<lang>` **только строгий `bool`**, фильтрует и дедуплицирует `configured_fields`/`changed_fields`/`changed_locales` по закрытым множествам, сохраняет явные пустые списки `[]`, а произвольные строки, отрывки текстов, неизвестные блоки и неизвестные языки (`en` и др.) отбрасывает.
- **Исторические записи:** бекфилл не делается; старые записи с `null`/`null` или сырыми небулевыми строками остаются `null`/`null` на чтении в `GET /admin/audit`.
- **Доступ:** `business_manager` видит события только своего `business_id`; `superadmin` видит все бизнесы; чужой менеджер не видит чужих событий (и получает `404` при попытке `PUT`).

#### Примеры `app_texts_updated`

Первое заполнение (`home_text.ru`):
```json
{
  "action": "app_texts_updated",
  "entity": "business_app_texts",
  "business_id": "11111111-1111-1111-1111-111111111111",
  "before_state": {
    "home_text": { "ru": false, "kk": false },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": false },
    "configured_fields": []
  },
  "after_state": {
    "home_text": { "ru": true, "kk": false },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": false },
    "configured_fields": ["home_text"],
    "changed_fields": ["home_text"],
    "changed_locales": ["home_text.ru"]
  }
}
```

Замена непустого текста `A` на другой непустой текст `B` в `home_text.ru` (булевы флаги присутствия остались `true` → `true`, но изменение зафиксировано):
```json
{
  "action": "app_texts_updated",
  "entity": "business_app_texts",
  "business_id": "11111111-1111-1111-1111-111111111111",
  "before_state": {
    "home_text": { "ru": true, "kk": true },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": true },
    "configured_fields": ["balance_delay_note", "home_text"]
  },
  "after_state": {
    "home_text": { "ru": true, "kk": true },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": true },
    "configured_fields": ["balance_delay_note", "home_text"],
    "changed_fields": ["home_text"],
    "changed_locales": ["home_text.ru"]
  }
}
```

Очистка локали `home_text.kk` и всего блока `balance_delay_note`:
```json
{
  "action": "app_texts_updated",
  "entity": "business_app_texts",
  "before_state": {
    "home_text": { "ru": true, "kk": true },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": true },
    "configured_fields": ["balance_delay_note", "home_text"]
  },
  "after_state": {
    "home_text": { "ru": true, "kk": false },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": false },
    "configured_fields": ["home_text"],
    "changed_fields": ["balance_delay_note", "home_text"],
    "changed_locales": ["balance_delay_note.kk", "home_text.kk"]
  }
}
```

Сохранение без фактических изменений (no-op):
```json
{
  "action": "app_texts_updated",
  "entity": "business_app_texts",
  "before_state": {
    "home_text": { "ru": true, "kk": false },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": false },
    "configured_fields": ["home_text"]
  },
  "after_state": {
    "home_text": { "ru": true, "kk": false },
    "home_store_note_lead": { "ru": false, "kk": false },
    "balance_delay_note": { "ru": false, "kk": false },
    "configured_fields": ["home_text"],
    "changed_fields": [],
    "changed_locales": []
  }
}
```

---

### 1.4. Рекомендации для UI (`AuditPage.tsx`) при работе с Частью 1

1. Поля `title`, `starts_at`, `ends_at`, `sort_order`, `kind`, `is_active` у `promotion_*` выводятся как обычный текст (не HTML).
2. Различайте **явный `null`** у `starts_at`/`ends_at`/`scheduled_at`/`push_sent_at` и **отсутствующий ключ** в историческом/отброшенном снимке (не показывать отсутствующий ключ как «очищено»).
3. Для `notification_*` отобразите подписи `title`, `scheduled_at`, `push_sent_at`, `push_devices`, `push_delivered` и `kind="info"` без `rawDetails` для менеджера.
4. Для `app_texts_updated` используйте `changed_fields` и `changed_locales` для списка изменённых блоков и языков, `configured_fields` и булевые `<block>.{ru,kk}` для статуса заполнения, а при `changed_fields: []` — нейтральную пометку вроде «Без фактических изменений». Для исторических строк с `null`/`null` сохраняйте аккуратный fallback без раскрытия `rawDetails`.

---

## Часть 2. НЕ РЕАЛИЗОВАНО — оставшиеся предложения (не в allowlist)

> **Важно:** перечисленные ниже контракты **НЕ включены** в allowlist кандидата `rework1`. `business_splash_updated` по-прежнему возвращает `before_state: null` и `after_state: null`. `media_uploaded.url` сохранён без изменений.

### 2.1. Предложение для `business_splash_updated` (`entity: "business_splash"`) — НЕ РЕАЛИЗОВАНО

- Предлагаемые безопасные поля без `media_url` и токена `version`:
  `enabled` (`boolean`), `media_type` (`"image" | "video" | null`), `width` (`int | null`), `height` (`int | null`), `duration_seconds` (`float | null`), `file_size` (`int | null`), `media_configured` (`boolean`), `media_changed` (`boolean` в `after_state`).
- Открытый вопрос перед реализацией: выравнивание имени поля `duration_seconds` (backend) vs `duration_sec` (UI `AuditPage.tsx`).

### 2.2. Уточнение по `media_uploaded` (`entity: "media"` / `"splash_media"`) — НЕ МЕНЯЛОСЬ

- В текущем коде (не изменялось в `rework1`): при загрузке изображения `promotion`/`logo` сохраняется `purpose`, `bytes`, `width`, `height`, `url`; при загрузке splash через `POST /admin/media/splash` поля `purpose="splash"`, `media_type`, `duration_seconds` отбрасываются проектором, а `url` остаётся доступным.
- Предложение к отдельной приёмке: допустить метаданные `purpose="splash"`, `media_type`, `duration_seconds` и решить, оставлять ли `url` в `media_uploaded`.
