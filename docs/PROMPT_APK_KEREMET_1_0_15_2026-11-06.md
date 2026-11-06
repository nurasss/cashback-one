# Промпт исполнителю приложения: сборка APK 1.0.15 — Keremet Bonus — 2026-11-06

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся по-русски.

## Контекст

После 1.0.14 принято и в main: новая иконка Keremet Bonus (вариант C) и круглый значок «k» в шапке главной (коммит после `045497a`, отчёт `reports/APP_KEREMET_ICON_V2_2026-11-06.md`). Собираем **только Keremet Bonus**: общее приложение Cashback One не изменилось, его не собирать.

Версия: **1.0.15 / versionCode 16** (общая в `app.json`; Cashback One 1.0.15 сейчас не собирается — это нормально). Подпись — тот же ключ. Разрешения и Firebase — как в `keremet-cashback-1.0.14.apk`. `CAMERA` не трогать.

## Шаги

1. `git pull --ff-only origin main`, `git status --short` (кроме `C:/`, `video/`, `reports/old-promo-cards-2026-11-06/`, `docs/tools/keremet-reset.zip` — пусто). `df -h /`: меньше 3 ГБ — СТОП. В `mobile/dist/` нет `keremet-cashback-1.0.15.apk`.
2. **Версия:** `mobile/app.json` — 1.0.15 / 16; `mobile/android/app/build.gradle` — `versionCode 16`, `versionName "1.0.15"`. Покажи `git diff mobile/app.json` и строки `build.gradle`.
3. До сборки: `npx jest --runInBand` (315 passed; одно падение — повтори один раз и покажи оба итога), `npx tsc --noEmit`, `npx eslint .`.
4. `mobile/scripts/build-client.sh keremet` → `mobile/dist/keremet-cashback-1.0.15.apk`. `processKeremetReleaseGoogleServices` выполнена. Gradle daemon остановить.
5. **Проверки:**
   - `aapt2 dump badging`: `kz.cashbackone.keremet`, «Keremet Bonus», versionCode 16, versionName 1.0.15, `arm64-v8a` и `armeabi-v7a`;
   - сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`;
   - разрешения равны `keremet-cashback-1.0.14.apk`;
   - `google_app_id` как в 1.0.14;
   - иконки: файлы `ic_launcher*` в APK **отличаются** от 1.0.14 и совпадают по содержимому с `mobile/clients/keremet/android/res/mipmap-*` (сравни SHA-256 распакованных PNG или опиши, как убедился); цвет фона адаптивной иконки `#F15173`;
   - картинка значка шапки есть в APK (`assets`/`res`, опиши где);
   - Hermes: `getClientConfig` → `"keremet"`, `DEMO_ENABLED` = false, API production;
   - размер и SHA-256.
6. `df -h /`, `git status --short`.

## Нельзя

Не публиковать, не менять `version.json`, лендинг, сервер, кабинет, код (кроме версии). Не собирать Cashback One. Прежние APK не трогать. Без commit/push.

## Отчёт

`reports/APK_KEREMET_1_0_15_BUILD.md`: сырой вывод шагов 1–6, что не проверено (иконка на настоящем лаунчере, установка поверх 1.0.14).
