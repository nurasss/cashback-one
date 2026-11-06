# Сборка APK 1.0.14 / versionCode 15 — Cashback One и Keremet Bonus — 2026-11-06

Без публикации, commit и push. Секреты не выводились.

## Шаги 1–3
- `git pull --ff-only origin main`: Already up to date. `git status`: `C:/`, `video/`, `reports/old-promo-cards-2026-11-06/` и два файла сверх списка — `docs/tools/keremet-reset.zip`, `reports/DEPLOY_BROADCAST_PUSH_2026-11-06.md`. Свободно 3,5 ГБ; APK 1.0.14 в `dist/` не было.
- Версия: `mobile/app.json` — `version` 1.0.14, `versionCode` 15; `mobile/android/app/build.gradle` (вне git) — `versionCode 15`, `versionName "1.0.14"`.
- `jest --runInBand`: 23 suites, **311 passed** (с предупреждением «Jest did not exit one second after…»). `tsc --noEmit`: чисто. `eslint .`: 0 ошибок, 1 предупреждение `react-hooks/exhaustive-deps` в `src/components/useKeyboardLift.ts:62`.

## Шаги 4–5
- Keremet: `build-client.sh keremet`, BUILD SUCCESSFUL 4m56s, `processKeremetReleaseGoogleServices` выполнена. После сборки свободно 2,5 ГБ (<3) — СТОП; владелец освободил место, сборка продолжена.
- Общий: `build-client.sh cashbackone`, BUILD SUCCESSFUL 30m17s (из них простой на медленном диске), `processCashbackoneReleaseGoogleServices` выполнена. Демоны Gradle остановлены; в конце свободно 4,2 ГБ.

## Шаг 6 — проверки
| | Keremet | Cashback One |
|---|---|---|
| файл | `mobile/dist/keremet-cashback-1.0.14.apk` | `mobile/dist/cashback-one-1.0.14.apk` |
| размер | 63 653 058 | 63 452 497 |
| SHA-256 | `5d7c3a73a0356e12a57c2130cd801e9e35fc088071d1ef997f9459b5fc73fe83` | `f9acb0d8b53e7aeff699b3954fe6d4527393c952299d4f128c12038f2df1db62` |
| пакет / label | `kz.cashbackone.keremet` / Keremet Bonus | `kz.cashbackone.mobile` / Cashback One |
| versionCode / Name | 15 / 1.0.14 | 15 / 1.0.14 |
| native-code | arm64-v8a, armeabi-v7a | arm64-v8a, armeabi-v7a |
| сертификат SHA-256 | `14afcbb5…cd63` (полностью совпал) | `14afcbb5…cd63` (полностью совпал) |
| разрешения vs 1.0.13 | diff пустой | diff пустой |
| `gcm_defaultSenderId` | `693902155886` | `693902155886` |
| `google_app_id` | `1:693902155886:android:1f667ed4a7db868bb2067f` | `1:693902155886:android:d0d86f1770025430b2067f` |
| иконки (17 файлов `ic_launcher*`, объединённый хеш) | = 1.0.13 (`4a3d1703817cd9b7…`) | = 1.0.13 (`c481426b7c505aed…`) |

google_app_id совпадает со значениями 1.0.13 (`reports/APK_1_0_13_BUILD.md` §6.4).

Hermes (`hermesc -b -dump-bytecode`, ошибок компилятора нет):
- `getClientConfig`: `LoadConstString r6, "keremet"` / `"cashbackone"` соответственно.
- `DEMO_ENABLED`: `LoadConstFalse r3` → `StoreNPToEnvironment r2, 3` перед `"https://demo.inva"…` (модуль `mockApi`), в обоих.
- Адрес `https://api.cashback-qr.poscenter.kz`: 1 вхождение в каждом.
- Маршрут `/bind`: в 1.0.13 строка была (1), в 1.0.14 — 0. `noCardTitle`: 1.0.13 — 4, 1.0.14 — 0.
- Плашка: ключ `noCardNotice` — 2 вхождения в каждом; текст «не найдена в базе магазина» в бандле хранится как UTF-16: 1.0.14 — 1 вхождение в обоих APK, в 1.0.13 — 0.

## Не проверено
Установка поверх 1.0.13 на телефоне; вид баннеров и акций с настоящими картинками; работа плашки на экране. Разрешение `CAMERA` не трогалось (по промпту).
