# Промпт исполнителю приложения: приложение под клиента — задача I-app, 2026-11-05

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`, приложение `mobile/` (Expo 55, RN 0.83, Hermes). `mobile/android/` не в git и ведётся вручную, `expo prebuild` **не запускать**. Рабочее дерево с принятыми правками 1.0.12 (push, контент из кабинета) без коммита: не откатывать.

Решение владельца (`docs/ROADMAP_PER_CLIENT_2026-11-04.md`, задача I):
- у каждого клиента своё приложение: свой пакет, название, иконка, цвет и бизнес;
- код и сервер общие;
- **один ключ подписи для всех** клиентов (текущий `release.keystore`);
- общее приложение `kz.cashbackone.mobile` остаётся и работает как сейчас.

Сервер параллельно получает параметр `business_id` и выбор push-устройств по пакету (`docs/PROMPT_BACKEND_PER_CLIENT_APP_2026-11-05.md`). Его ещё нет на production: работай по описанию из этого промпта и проверяй моками.

## Задача

### 1. Настройки клиента в git

- `mobile/clients/<slug>/client.json`:
  - `slug`;
  - `android_app_id`;
  - `app_name` (`ru` и `kk`; на Android подпись под иконкой одна, взять `ru`, если не задан `android_label`);
  - `business_id` (UUID или `null` для общего приложения);
  - `primary_color`;
  - `scheme` (deep link).
- `mobile/clients/<slug>/android/res/…`: иконки `mipmap-*` и адаптивная иконка, `values/strings.xml` с `app_name`, цвета.
- Клиенты:
  - `cashbackone` — **общий**: все значения как сейчас, `business_id: null`;
  - `example` — **пример**: пакет `kz.cashbackone.example`, бизнес-заглушка `00000000-0000-0000-0000-000000000000`, иконка — копия текущей с другим цветом фона. Он нужен для тестов и проверки сборки. Его не публикуют.
- Схема проверки (`mobile/clients/schema` или проверка в тесте): формат пакета, UUID, цвет `#RRGGBB`, наличие всех плотностей иконок.

### 2. JS

- Клиент выбирается при сборке переменной `EXPO_PUBLIC_CLIENT` (по умолчанию `cashbackone`). Неизвестный slug — ошибка сборки или запуска, а не тихий откат на общий.
- `src/config/client.ts` отдаёт текущие настройки.
- Если `business_id` задан:
  - карты, QR, история, баланс, «Мой статус» и привязка карты работают только для карт этого бизнеса. На запросы из списка ниже добавить `?business_id=`, плюс фильтр на клиенте на случай старого сервера;
  - если у покупателя нет карты этого бизнеса, показать экран добавления карты, а не чужие карты;
  - `/me/app-content` запрашивать для бизнеса клиента, а не активной карты;
  - `PUT /me/push-token` отправлять `app_id` = `android_app_id` клиента (сейчас пакет берётся откуда-то, покажи откуда);
  - основной цвет темы взять из `primary_color`, если это укладывается в существующую тему без переделки экранов. Иначе СТОП и опиши, что нужно.
- Если `business_id: null`: поведение **побайтно как сейчас**, без нового параметра в запросах.
- Запросы с `business_id`: `/me/cards`, `/me/cards/bind`, `/me/promotions`, `/me/promotions/{id}`, `/me/promotions/seen`, `/me/notifications`, `/me/notifications/read`, `/me/badges`.
- Ключи кеша `appCache` уже включают бизнес. Проверь, что кеш разных клиентов на одном телефоне не пересекается (у каждого приложения своё хранилище, но проверь и логику).

### 3. Android без prebuild

- `mobile/android/app/build.gradle`: `productFlavors` (измерение `client`), по одному на каждого клиента из `mobile/clients/`. Для каждого задать:
  - `applicationId` из `client.json`;
  - `sourceSets.<slug>.res.srcDirs` на `../../clients/<slug>/android/res`, чтобы ресурсы лежали в git, а не в `android/`;
  - `resValue` и `manifestPlaceholders` для `scheme`.

  Ручные правки из прежних отчётов сохранить: подпись, версия, манифест с `tools:node="remove"`, `POST_NOTIFICATIONS`, google-services, иконка уведомлений. `namespace` оставить `kz.cashbackone.mobile`.
- Firebase: `google-services.json` ищется по flavor. Файл для пакетов клиентов владелец скачает позже, после добавления приложения в консоли Firebase. Сейчас:
  - общий flavor собирается с текущим файлом;
  - `example` — через `google-services.json` с `package_name` `kz.cashbackone.example`. Если его нет, отключи для этого flavor задачу google-services, пусть push у примера не работает. Опиши это.

  Содержимое `google-services.json` не выводить.
- Сборка: `assembleCashbackoneRelease` и `assembleExampleRelease` с тем же ключом подписи. Если имя задачи другое, покажи его.
- Список правок в `android/` построчно в отчёте. До правок скопируй `android/app/build.gradle` и манифест в `reports/per-client-2026-11-05/android-before/`.

### 4. Сборка без ручных шагов

`mobile/scripts/build-client.sh <slug>`. Без `git checkout`/`clean`, без `prebuild`, без удаления файлов. Порядок:
1. проверяет `client.json` и свободное место (меньше 3 ГБ — отказ);
2. задаёт `EXPO_PUBLIC_CLIENT`, `NODE_ENV=production`, `EXPO_PUBLIC_API_BASE_URL`;
3. убирает `EXPO_PUBLIC_DEMO` через `unset`;
4. загружает ключи из `~/.cashback-one-keys/keystore.env` через `set -a` в подоболочке;
5. собирает flavor;
6. копирует APK через `cp -n` в `mobile/dist/<slug>-<version>.apk`.

Версия общая из `app.json`. Если клиенту понадобится свой `versionCode`, опиши, как это сделать, но не делай.

## Тесты

- выбор клиента по `EXPO_PUBLIC_CLIENT`, неизвестный slug → ошибка;
- общий клиент: запросы без `business_id`, снимок поведения как до правок;
- клиент с бизнесом: все перечисленные запросы с `business_id`, чужие карты не видны даже от старого сервера, нет своей карты → экран добавления, `app-content` по бизнесу клиента, `push-token` с `app_id` клиента;
- проверка всех `client.json` в `mobile/clients/`.

## Что не менять

Сервер, `admin/`, агент, сайт, `version.json`, ключи, версию (1.0.12 / 13). Не публиковать APK, без commit/push.

## Проверки

Из `mobile/`, до правок и после: `npx jest --runInBand` (до правок 280 passed), `npx tsc --noEmit`, `npx eslint .`. Сборка `cashbackone` и `example` (свободно не меньше 3 ГБ, иначе собери только `example` и опиши). Для обоих APK:
- `aapt2 dump badging`: пакет, название, версия, архитектуры;
- сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`;
- разрешения равны 1.0.12;
- Hermes: demo выключен, адрес сервера на месте.

Для `cashbackone` бандл по смыслу как в 1.0.12: покажи строки `business_id` и отсутствие UUID примера. `git status` в конце.

## Отчёт

`reports/APP_PER_CLIENT_2026-11-05.md`. В нём:
- структура `mobile/clients/`;
- правки `android/` построчно;
- как добавить нового клиента по шагам для сисадмина: что дать (иконка, название, цвет, бизнес), какие команды запустить, что сделать в Firebase;
- сырой вывод проверок;
- что не проверено.
