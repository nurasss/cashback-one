# Промпт исполнителю приложения: сборка APK 1.0.16 — Keremet Bonus — 2026-11-07

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся по-русски.

## Контекст

После 1.0.15 принято и в main (`6c409f0`, отчёт `reports/APP_HISTORY_COLORS_2026-11-07.md`): в истории начисления зелёные, списания красные, склад не показывается; так же окрашены уведомления о начислении и списании. Собираем **только Keremet Bonus**, Cashback One не собирать.

Версия: **1.0.16 / versionCode 17** (общая в `app.json`). Подпись — тот же ключ. Разрешения, Firebase и иконки — как в `keremet-cashback-1.0.15.apk`. `CAMERA` не трогать.

## Шаги

1. `git pull --ff-only origin main`, `git status --short` (кроме `C:/`, `video/`, `reports/old-promo-cards-2026-11-06/`, `docs/tools/keremet-reset.zip` — пусто). `df -h /`: меньше 3 ГБ — СТОП. В `mobile/dist/` нет `keremet-cashback-1.0.16.apk`.
2. **Версия:** `mobile/app.json` — 1.0.16 / 17; `mobile/android/app/build.gradle` — `versionCode 17`, `versionName "1.0.16"`. Покажи `git diff mobile/app.json` и строки `build.gradle`.
3. До сборки: `npx jest --runInBand` (317 passed; одно падение — повтори один раз и покажи оба итога), `npx tsc --noEmit`, `npx eslint .`.
4. `mobile/scripts/build-client.sh keremet` → `mobile/dist/keremet-cashback-1.0.16.apk`. `processKeremetReleaseGoogleServices` выполнена. Gradle daemon остановить.
5. **Проверки:**
   - `aapt2 dump badging`: `kz.cashbackone.keremet`, «Keremet Bonus», versionCode 17, versionName 1.0.16, `arm64-v8a` и `armeabi-v7a`;
   - сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`;
   - разрешения равны `keremet-cashback-1.0.15.apk`;
   - `google_app_id` как в 1.0.15;
   - иконки `ic_launcher*` **совпадают** с 1.0.15 (читай файлы прямо из zip, а не распаковкой: на Mac `res/zR.png` и `res/zr.png` совпадают без учёта регистра); фон адаптивной иконки `#F15173`;
   - Hermes: `getClientConfig` → `"keremet"`, `DEMO_ENABLED` = false (в модуле `mockApi`), API production; в байткоде есть `#E8F5EC` (новый `softSuccess`);
   - размер и SHA-256.
6. `df -h /`, `git status --short`.

## Нельзя

Не публиковать, не менять `version.json`, лендинг, сервер, кабинет, код (кроме версии). Не собирать Cashback One. Прежние APK не трогать. Без commit/push.

## Отчёт

`reports/APK_KEREMET_1_0_16_BUILD.md`: сырой вывод шагов 1–6, что не проверено (установка поверх 1.0.15, вид истории на телефоне).
