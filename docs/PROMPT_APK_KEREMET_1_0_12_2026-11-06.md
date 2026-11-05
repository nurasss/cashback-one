# Промпт исполнителю приложения: сборка APK KeremEt с push — 2026-11-06

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся по-русски.

## Контекст

Задача I-app и имя файла приняты (коммиты `2b43de4`, `a0955ed`). Первая сборка KeremEt была без Firebase и переименована куратором в `mobile/dist/keremet-cashback-1.0.12.no-push.apk` (не трогать).

Куратор положил `google-services.json` для `kz.cashbackone.keremet` из проекта **`cashback-one-loyalty`** (тот же проект, что у общего приложения и ключа сервера):
- `mobile/android/app/src/keremet/google-services.json` (права 600, папка `android/` вне git);
- копия `~/.cashback-one-keys/google-services.keremet.json`;
- SHA-256 начинается с `cd4a39921e669e3e`.

**Содержимое файла не выводить.** Разрешено вывести только `project_id` и список `package_name`.

Сервер задачи I выкачен (alembic `0016`), push на production включён (`fcm`).

## Шаги

1. `git pull --ff-only origin main`, `git status --short` (кроме `C:/` и `video/` — пусто). `df -h /`: меньше 3 ГБ — СТОП.
2. SHA-256 файла из п. «Контекст» совпадает. `project_id` = `cashback-one-loyalty`, среди `package_name` есть `kz.cashbackone.keremet`. Иначе СТОП.
3. До сборки: `npx jest --runInBand` (301 passed), `npx tsc --noEmit`, `npx eslint .`.
4. Сборка: `mobile/scripts/build-client.sh keremet`. В выводе Gradle задача `processKeremetReleaseGoogleServices` **выполнена**, а не `SKIPPED`. Если пропущена — СТОП.
5. Результат `mobile/dist/keremet-cashback-1.0.12.apk`. Проверки:
   - `aapt2 dump badging`: пакет `kz.cashbackone.keremet`, `versionCode` 13, `versionName` 1.0.12, label «Keremet Bonus», `arm64-v8a` и `armeabi-v7a`;
   - сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`;
   - разрешения равны `keremet-cashback-1.0.12.no-push.apk` (с заменой пакета в динамическом разрешении);
   - `aapt2 dump resources`: ресурс `google_app_id` есть и равен `mobilesdk_app_id` клиента `kz.cashbackone.keremet` из файла; `gcm_defaultSenderId` = номер проекта `cashback-one-loyalty`. Выведи только эти два значения;
   - Hermes (как в `reports/APP_PER_CLIENT_2026-11-05.md`, разбор `hermesc -dump-bytecode`): `getClientConfig` подставляет `"keremet"`, `DEMO_ENABLED` = false в модуле `mockApi`, адрес `https://api.cashback-qr.poscenter.kz`;
   - размер и SHA-256.
6. Gradle daemon остановить, `df -h /` после.

## Нельзя

Не публиковать APK и не загружать на сайт, не менять `version.json`, лендинг, сервер, кабинет. Не менять код, `build.gradle`, манифест, версию. Не трогать другие APK в `dist/`. Без commit/push.

## Отчёт

`reports/APK_KEREMET_1_0_12_BUILD.md`: сырой вывод шагов 1–6 без секретов, что не проверено (установка на телефон, получение push, код списания на кассе).
