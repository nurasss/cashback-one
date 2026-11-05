# Отчёт по задаче H: баннеры, акции и тексты магазина с сервера

**Дата:** 2026-11-05  
**Исполнитель:** Claude  
**Куратор проекта:** Antigravity  
**Статус:** Выполнено успешно, все проверки пройдены

---

## 1. Краткое резюме

В соответствии с `docs/PROMPT_APP_SERVER_CONTENT_2026-11-05.md` и планом перехода на клиентские сборки (`docs/ROADMAP_PER_CLIENT_2026-11-04.md`, п. 10):
- **Удалены зашитые данные магазинов и акций:** полностью удалены привязки к «КеремЕт», «In Plaza», `2gis.kz`, локальный файл `mobile/src/features/store.ts`, локальные арты `mobile/src/features/promotionsArtwork.ts` и 15 растровых PNG-файлов баннеров/акций из `mobile/assets/promotions/*`. Папка `mobile/assets` уменьшилась с **9.8 МБ до 3.8 МБ** (освобождено 6 МБ).
- **Интегрирован эндпоинт `GET /me/app-content`:** приложение запрашивает магазины и тексты для активной карты покупателя через React Query (`useAppContent(businessId)`), поддерживает заголовок `If-None-Match` с `ETag`, корректно обрабатывает `304 Not Modified`, скрывает блок при `404 CUSTOMER_RESOURCE_NOT_FOUND`.
- **Динамический блок магазина на главной (`StoreBlock`):** отображает вступительный текст `home_store_note_lead` (или нейтральный дефолтный текст без названия магазина при отсутствии) и список адресов активных магазинов в порядке `sort_order` на языке интерфейса (RU/KK). Адреса с `map_url` подчеркнуты и открывают карту по нажатию (`Linking.openURL`); адреса без ссылки выводятся как текст. Если магазинов нет — блок скрывается.
- **Динамический текст статуса:** экран «Мой статус» берет `balance_delay_note` из `app-content` на языке пользователя; если не задан — использует встроенный фоллбек.
- **Серверные баннеры и акции:** карусель на главной отображает только серверные баннеры (`kind: banner`), сетка предложений на главной и экран «Акции» отображают только серверные акции (`kind: offer`). При отсутствии данных секции скрываются без пустых рамок.
- **Офлайн-кеширование:** реализован модуль `mobile/src/storage/appCache.ts` на базе `@react-native-async-storage/async-storage` с двухуровневой схемой (синхронная in-memory память для мгновенного первого рендера без задержек + персистентное хранилище с привязкой ключей к пользователю и бизнесу). Приложение сохраняет ETag и тело ответа, при запуске без сети сразу рендерит сохранённые данные без блокирующих ошибок. При выходе из аккаунта или инвалидации сессии кеш полностью очищается через зарегистрированные хуки в `SessionProvider`.
- **Кеширование картинок:** установлен `expo-image` с `cachePolicy="memory-disk"`, обеспечивающий дисковое кеширование сетевых баннеров и промо-карточек для работы без интернета.
- **Сохранение окружения:** нативный каталог `mobile/android/` не изменялся (`expo prebuild` **не запускался**, работает Expo autolinking), версия осталась `1.0.11-test` (versionCode 12), push-код задачи C и правки 1.0.11-test не затронуты.

---

## 2. Новые зависимости

Установлены через `npx expo install`:
1. `@react-native-async-storage/async-storage@2.2.0` — стандартное персистентное key-value хранилище для кеширования JSON-ответов сервера (`app-content` и `promotions`) и их `ETag`. Не требует шифрования SecureStore, работает асинхронно, безопасно при больших объёмах данных.
2. `expo-image@~55.0.11` — компонент для эффективной загрузки изображений с поддержкой аппаратно-ускоренного рендеринга и встроенного дискового кеширования (`cachePolicy="memory-disk"`). Позволяет загружать сетевые баннеры и показывать их офлайн при отсутствии связи.

В `mobile/app.json` добавлен плагин `"expo-image"`. Нативные файлы в `mobile/android/` не изменялись.

---

## 3. Изменённые и удалённые файлы

### Удалённые файлы
1. `mobile/src/features/store.ts` (зашитая ссылка на 2ГИС магазина КеремЕт).
2. `mobile/src/features/promotionsArtwork.ts` (зашитые баннеры и промо-карточки).
3. `mobile/assets/promotions/*` (15 PNG-файлов баннеров и карточек, 6 МБ).

### Созданные файлы
1. `mobile/src/storage/appCache.ts` — модуль кеширования контента приложения и промо-акций (ETag, in-memory кэш, персистентное хранилище с изоляцией по `user_id` и `business_id`, методы `clearAppCache`, `loadAppContentCache`, `loadPromotionsCache`).
2. `mobile/tests/serverContentAndCache.test.tsx` — интеграционные тесты для ETag 304, 404, офлайн-режима, текстов статуса и очистки кеша.
3. `reports/APP_SERVER_CONTENT_2026-11-05.md` — данный отчёт.
4. `reports/app-server-content-2026-11-05/` — скриншоты главной и акций (RU и KK).

### Модифицированные файлы
1. `mobile/app.json` — добавлен плагин `expo-image`.
2. `mobile/package.json` и `mobile/package-lock.json` — добавлены `@react-native-async-storage/async-storage` и `expo-image`.
3. `mobile/src/types/api.ts` — добавлены типы `AppStoreItem`, `LocalizedText`, `CustomerAppTexts`, `AppContent`.
4. `mobile/src/api/client.ts` — расширен метод `requestWithMeta<T>` для возврата статуса ответа и заголовка `ETag`, поддержаны HTTP 304 (Not Modified) и HTTP 204 (No Content).
5. `mobile/src/api/app.ts` — добавлены хук `useAppContent(businessId)` и функции `fetchAppContentWithCache`, `fetchPromotionsWithCache` с поддержкой ETag и офлайн-фоллбека.
6. `mobile/src/auth/session.ts` — добавлен метод `getUserId()` для декодирования `sub` из JWT-токена доступа.
7. `mobile/src/auth/provider.tsx` — зарегистрирована очистка кеша (`clearAppCache()`) при `session.registerBeforeLogout` и `session.registerOnInvalidate`.
8. `mobile/src/components/useKeyboardLift.ts` — безопасный вызов `Keyboard.metrics?.()` для совместимости с web-demo.
9. `mobile/src/demo/mockApi.ts` — добавлен мок-эндпоинт `GET /me/app-content` с ETag/304, обновлены демо-акции без удалённых ассетов.
10. `mobile/src/i18n/ru.ts` и `mobile/src/i18n/kz.ts` — удалены `storeNoteLead` и `storeAddress`; добавлен нейтральный дефолтный текст `storeNoteDefaultLead`.
11. `mobile/src/features/home.tsx` — удалены `LOCAL_BANNERS`, `PERMANENT_OFFERS`, добавлен компонент `StoreBlock` (с сортировкой, ссылками на карту и нейтральным фоллбеком) и `ServerOffersGrid`; `BannerCarousel` переведён на `expo-image` и серверные баннеры.
12. `mobile/app/(app)/(tabs)/index.tsx` — на главной задействован `StoreBlock`, пустые секции карусели и акций скрываются.
13. `mobile/app/(app)/(tabs)/promotions.tsx` — только серверные акции, при отсутствии отображается нейтральное состояние `noPromotions`.
14. `mobile/app/(app)/promotion/[id].tsx` — удалён `ArtworkPromotionDetail`, рендерится деталка серверной акции.
15. `mobile/app/(app)/status.tsx` — текст задержки начисления берется из `appContent.app_texts.balance_delay_note` с фоллбеком на `t('balanceDelayNote')`.
16. `mobile/tests/setup.ts` — добавлены моки для `@react-native-async-storage/async-storage` и `expo-image`.
17. `mobile/tests/qrScreen.test.tsx` — тесты главной и статуса переведены на моки `/me/app-content` без упоминаний КеремЕт/2ГИС.
18. `mobile/tests/homeArtwork.test.tsx` — тесты карусели и сетки предложений с сервера.
19. `mobile/tests/promotionsArtwork.test.tsx` — тесты серверных акций.
20. `mobile/tests/flows.test.tsx` — обновлен переход при нажатии на карточку предложения на `/promotion/[id]`.

---

## 4. Проверка на отсутствие зашитых упоминаний (grep)

### Grep до правок
В исходном коде присутствовали:
- Ключи `storeNoteLead`, `storeAddress` в `ru.ts`/`kz.ts`.
- `STORE_MAP_URL` с ссылкой на 2ГИС в `store.ts`.
- `LOCAL_BANNERS`, `PERMANENT_OFFERS`, `ArtworkPromotionDetail` в `promotionsArtwork.ts`.
- Текстовые вхождения «КеремЕт», «In Plaza» в тестах и компонентах.

### Grep после правок
Команда:
```bash
git grep -i -E "керемет|in plaza|2gis|promotionsartwork" mobile/src mobile/app mobile/tests
```
**Результат:** Код возврата 1 (пустой вывод, 0 совпадений по всему проекту).

Проверка удаления ключей локализации:
```bash
git grep -E "storeNoteLead|storeAddress" mobile/src mobile/app
```
**Результат:** найдены только имена классов CSS `styles.storeAddress` и `styles.storeAddressPlain` в `home.tsx`. Сами ключи локализации полностью удалены.

---

## 5. Тексты для проверки владельцем (RU и KK)

### 1. Нейтральный фоллбек вступительного текста магазина (`storeNoteDefaultLead`)
Используется на главной странице, если сервер вернул список магазинов, но поле `app_texts.home_store_note_lead` не заполнено:
- **RU:** `Вы можете потратить баллы по адресу: `
- **KK:** `Ұпайларды мына мекенжай бойынша жұмсай аласыз: `

### 2. Фоллбек текста задержки начисления (`balanceDelayNote`)
Используется на экране «Мой статус», если поле `app_texts.balance_delay_note` не заполнено на сервере (встроенные строки из словарей `ru.ts`/`kz.ts`):
- **RU:** `Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.`
- **KK:** `Баланс бірден жаңартылмайды. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі.`

### 3. Тексты мока в demo-режиме (`mobile/src/demo/mockApi.ts`)
- **`home_store_note_lead`:**
  - RU: `Вы можете потратить эти баллы в супермаркетах сети по адресу: `
  - KK: `Сіз бұл ұпайларды желі супермаркеттерінде келесі мекенжай бойынша жұмсай аласыз: `
- **`balance_delay_note`:**
  - RU: `Баллы за покупки начисляются и обновляются после закрытия кассовой смены`
  - KK: `Сатып алулар үшін ұпайлар кассалық ауысым жабылғаннан кейін есептеледі және жаңартылады`
- **Магазины demo:**
  - Магазин 1:
    - `title_ru`: `Супермаркет POSCENTER, ТЦ «Астана Молл»`
    - `title_kk`: `POSCENTER супермаркеті, «Астана Молл» СОО`
    - `address_ru`: `проспект Тауелсиздик, 34`
    - `address_kk`: `Тәуелсіздік даңғылы, 34`
    - `map_url`: `https://maps.google.com/?q=51.143,71.472` (ссылка активна)
  - Магазин 2:
    - `title_ru`: `Мини-маркет POSCENTER`
    - `title_kk`: `POSCENTER шағын маркеті`
    - `address_ru`: `улица Достык, 12`
    - `address_kk`: `Достық көшесі, 12`
    - `map_url`: `null` (выводится обычным текстом без подчеркивания)

---

## 6. Сырой вывод проверок

### Тесты Jest до правок (baseline)
```
Test Suites: 21 passed, 21 total
Tests:       271 passed, 271 total
Snapshots:   0 total
Time:        16.326 s
```

### Тесты Jest после правок
```
PASS tests/homeArtwork.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/flows.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/components.test.tsx
PASS tests/avatar.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/wallet.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/push.test.tsx
PASS tests/transport.test.ts
PASS tests/core.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/keyboardLift.test.ts
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/session.test.ts

Test Suites: 21 passed, 21 total
Tests:       277 passed, 277 total
Snapshots:   0 total
Time:        19.586 s
Ran all test suites.
```
*(Прирост тестов: +6 новых интеграционных тестов кеша и контента, общее число 277 passed)*

### Проверка типов TypeScript (`npx tsc --noEmit`)
```
Exit code: 0
(Вывод пуст — 0 ошибок типизации)
```

### Проверка линтером (`npx eslint .`)
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```
*(0 ошибок, 1 давнее предупреждение в хуке клавиатуры)*

### Проверка форматирования Git (`git diff --check`)
```
Exit code: 0
(Вывод пуст — 0 ошибок форматирования / trailing whitespace)
```

### Размер папки ассетов (`du -sh mobile/assets`)
```
3.8M	mobile/assets
```
*(Размер сократился с 9.8M до 3.8M)*

---

## 7. Скриншоты Web Demo

Снимки интерфейса сохранены в директории `reports/app-server-content-2026-11-05/`:
- `home-ru.png`: Главный экран (RU) — отображаются карусель баннеров, блок магазинов с подчёркнутой ссылкой на Тәуелсіздік 34 и текстовым адресом Достық 12, сетка «Горячие предложения».
- `home-kk.png`: Главный экран (KK) — отображаются казахский вступительный текст магазина («Сіз бұл ұпайларды желі супермаркеттерінде келесі мекенжай бойынша жұмсай аласыз: »), казахские адреса («Тәуелсіздік даңғылы, 34», «Достық көшесі, 12»), заголовок «Ыстық ұсыныстар» и навигационные вкладки («Басты», «Акциялар», «Менің QR-кодым», «Хабарламалар»).
- `promotions-ru.png`: Экран «Акции» (RU) — список серверных предложений с бейджами.
- `promotions-kk.png`: Экран «Акции» (KK) — заголовок «Акциялар», список акций с сервера.

---

## 8. Чеклист для владельца: что заполнить в кабинете до выпуска клиентского APK

До сборки APK под конкретного клиента владелец должен заполнить в админ-панели следующие данные бизнеса:

1. **Магазины (`/admin/stores` или карточка бизнеса):**
   - Название RU и KK (например, «Супермаркет на Абая»).
   - Адрес RU и KK (например, «пр. Абая, 150» / «Абай даңғылы, 150»).
   - Ссылка на карту `map_url` (ссылка на 2ГИС, Яндекс.Карты или Google Maps). Если ссылки нет, оставить пустой — адрес отобразится как текст без перехода.
   - Порядок сортировки `sort_order` (1, 2, 3...).
   > *Если магазины не добавлены, блок адресов на главной странице приложения будет автоматически скрыт.*

2. **Тексты приложения (`app_texts` в настройках бизнеса):**
   - `home_store_note_lead` (RU и KK) — вступительный текст перед списком адресов на главной странице (например: «Вы можете потратить накопленные баллы в наших супермаркетах по адресам: »).
   - `balance_delay_note` (RU и KK) — пояснение под балансом на экране «Мой статус» (например: «Баллы начисляются после закрытия кассовой смены»).

3. **Баннеры карусели (`promotions` с типом `banner`):**
   - Загрузить изображения баннеров (соотношение сторон ~16:9).
   - Указать заголовки и подзаголовки.
   > *Если баннеров нет, карусель на главной странице скрывается.*

4. **Акции и предложения (`promotions` с типом `offer`):**
   - Загрузить изображения акций.
   - Заполнить бейджи («Скидка недели», «Кешбэк 10%»), заголовки и подробные описания.
   > *Если акций нет, блок «Горячие предложения» на главной странице скрывается, а на экране «Акции» выводится нейтральное сообщение об отсутствии активных акций.*

---

## 9. Что не проверялось

- Установка на физический Android-смартфон (сборка APK не проводилась, версия приложения сохранена `1.0.11-test` / 12).
- Нативное поведение дискового кеша картинок `expo-image` на реальном мобильном устройстве без интернета (в браузерном demo проверен HTTP/localStorage кэш, в unit-тестах Jest используется мок).
- Привязка жесткого `business_id` под сборку конкретного клиента (задача I — отдельный этап).

---

## 10. Исправления после приёмки

По замечаниям куратора из `docs/PROMPT_APP_SERVER_CONTENT_FIXES_2026-11-05.md`:

### 1. Что изменено
1. **Гарантированное чтение AsyncStorage при холодном старте (`mobile/src/api/app.ts`):**
   - В начало функций `fetchPromotionsWithCache` и `fetchAppContentWithCache` добавлен вызов `await initAppCache()`.
   - Теперь при холодном старте без интернета кешированные данные гарантированно вычитываются из `AsyncStorage` в память до выполнения сетевого запроса, предотвращая показ экрана с ошибкой.
2. **Атомарность и устойчивость к гонкам `clearAppCache()` (`mobile/src/storage/appCache.ts`):**
   - Введён счётчик поколения `cacheGeneration`.
   - `initAppCache()` проверяет поколение кеша перед чтением и при сохранении каждой записи.
   - `clearAppCache()` инкрементирует `cacheGeneration`, очищает `memoryCache`, дожидается завершения незавершённого `initPromise` (`await inFlight`), повторно очищает `memoryCache`, удаляет ключи из `AsyncStorage` и сбрасывает `initPromise = null`.
   - Это гарантирует, что если `clearAppCache()` вызван параллельно с незавершённой инициализацией кеша, устаревшие данные пользователя не останутся в памяти после выхода.
3. **Исправление описания текста задержки в отчёте:**
   - В разделе 5.2 отчёта исправлен текст встроенного фоллбека на фактические строки из `ru.ts`/`kz.ts`:
     - RU: `Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.`
     - KK: `Баланс бірден жаңартылмайды. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі.`
   - Сами словари `ru.ts` и `kz.ts` оставлены без изменений.
4. **Тесты устойчивости кеша (`mobile/tests/serverContentAndCache.test.tsx`):**
   - Добавлены 3 теста в suite `Cold start and concurrency race safety`:
     - Холодный старт при отказе сети (данные только в `AsyncStorage`, изолированный модуль `jest.isolateModules`): проверяет возврат сохранённых `app-content` и `promotions`.
     - Холодный старт с ETag и ответом `304 Not Modified`: проверяет отправку `If-None-Match` из `AsyncStorage` и возврат сохранённых данных.
     - Гонка `clearAppCache()` во время незавершённого `initAppCache()` (через заблокированный промис `AsyncStorage.multiGet`): проверяет, что после завершения обоих промисов память гарантированно пуста.

### 2. Сырой вывод проверок

#### `npx jest --runInBand`
```
PASS tests/serverContentAndCache.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/flows.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/avatar.test.tsx
PASS tests/wallet.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/push.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/components.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/core.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 21 passed, 21 total
Tests:       280 passed, 280 total
Snapshots:   0 total
Time:        19.953 s, estimated 20 s
Ran all test suites.
```

#### `npx tsc --noEmit`
```
Exit code: 0
(Вывод пуст — 0 ошибок типизации)
```

#### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

#### `git diff --check`
```
Exit code: 0
(Вывод пуст — 0 ошибок форматирования / пробелов)
```

#### `git diff --stat -- src/storage src/api tests`
```
 mobile/src/api/app.ts                   | 119 +++++++++++-
 mobile/src/api/client.ts                |  21 ++-
 mobile/tests/flows.test.tsx             |  11 +-
 mobile/tests/homeArtwork.test.tsx       | 312 ++++++++++++--------------------
 mobile/tests/promotionsArtwork.test.tsx | 145 +++++----------
 mobile/tests/qrScreen.test.tsx          | 264 ++++++++++++++++++++++-----
 mobile/tests/setup.ts                   |  23 +++
 7 files changed, 541 insertions(+), 354 deletions(-)
```
*(Файлы `mobile/src/storage/appCache.ts` и `mobile/tests/serverContentAndCache.test.tsx` созданы в задаче H и находятся в рабочем дереве)*

