# Промпт исполнителю приложения: имя файла APK по клиенту — 2026-11-05

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся по-русски.

## Контекст

Задача I-app принята (коммит `2b43de4`, отчёт `reports/APP_PER_CLIENT_2026-11-05.md`). `mobile/scripts/build-client.sh` копирует APK в `mobile/dist/<slug>-<version>.apk`. Владелец хочет для KeremEt имя **`keremet-cashback-<version>.apk`**. Собранный ранее файл куратор уже переименовал в `mobile/dist/keremet-cashback-1.0.12.apk`.

## Что сделать

1. В `mobile/clients/<slug>/client.json` необязательное поле `apk_name`, латиница в нижнем регистре, цифры и дефис (`^[a-z0-9]+(-[a-z0-9]+)*$`):
   - `keremet`: `"keremet-cashback"`;
   - `cashbackone`: `"cashback-one"` (как у прежних файлов `cashback-one-1.0.x.apk`);
   - `example`: поле не задавать.
2. `build-client.sh`: имя файла `mobile/dist/<apk_name>-<version>.apk`, если поле есть, иначе `<slug>-<version>.apk`. Чтение поля — тем же способом, каким скрипт уже читает `client.json`. Остальное в скрипте не менять: `cp -n`, проверка места, ключи, `unset EXPO_PUBLIC_DEMO`.
3. Проверка формата `apk_name` там же, где проверяются остальные поля `client.json` (схема или тест).
4. Тесты: формат поля; для `keremet` скрипт вычисляет `keremet-cashback-<version>.apk`, для `example` — `example-<version>.apk`. Вычисление имени проверить без сборки: например, режим скрипта `--print-apk-name` или отдельная функция. Опиши, что выбрал.

## Нельзя

APK не собирать (на Mac мало места). Не менять версию, `android/`, код приложения, сервер. Не трогать файлы в `mobile/dist/`. Без commit/push.

## Проверки и отчёт

`npx jest --runInBand` (до правок 296 passed), `npx tsc --noEmit`, `npx eslint .`, `bash -n scripts/build-client.sh`, вывод вычисленного имени для трёх клиентов. Раздел «Имя файла APK» в конце `reports/APP_PER_CLIENT_2026-11-05.md`: `git diff`, сырой вывод проверок.
