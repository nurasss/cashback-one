# Отчёт о публикации APK KeremEt (1.0.12) — 2026-11-06

**Дата:** 2026-11-06 (macOS).  
**Промпт:** `docs/PROMPT_APK_KEREMET_1_0_12_PUBLISH_2026-11-06.md`.  
**Статус:** **Успешно завершено.** Файл выложен на сайт отдельной ссылкой, все проверки пройдены.

---

## 1. Параметры опубликованного артефакта

| Параметр | Значение |
|---|---|
| Ссылка | `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.12.apk` |
| Имя файла | `keremet-cashback-1.0.12.apk` |
| Размер | **63 668 358 байт** (~60.7 МБ) |
| SHA-256 | **`fb1090049b81f337a88e7cbf8363ae8109164e7d974e9fca1a64c520d0003265`** |
| Content-Type | `application/vnd.android.package-archive` |
| Пакет приложения | `kz.cashbackone.keremet` |
| Версия / код | `1.0.12` / `13` |

---

## 2. Сырой вывод шагов

### 2.1. Шаг 1: Проверка диска и локального файла
```
$ df -h ~
Filesystem     Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s5  113Gi   94Gi  5.6Gi    95% 1525616 58983520    3%   /System/Volumes/Data

$ ls -ln mobile/dist/keremet-cashback-1.0.12.apk
-rw-r--r--@ 1 501  20  63668358 Nov  6 01:54 mobile/dist/keremet-cashback-1.0.12.apk

$ shasum -a 256 mobile/dist/keremet-cashback-1.0.12.apk
fb1090049b81f337a88e7cbf8363ae8109164e7d974e9fca1a64c520d0003265  mobile/dist/keremet-cashback-1.0.12.apk
```
- Свободное место: 5.6 ГБ.
- Размер и SHA-256 локального файла полностью совпали с эталонными.

### 2.2. Шаг 2 и 3: Подключение к FTPS и список файлов до загрузки
Подключение: TLS 1.2, проверка сертификата по `/etc/ssl/cert.pem`, `PROT P`, `TYPE I`, возврат в корень сессии перед операциями.

Список файлов в каталоге `app/` до загрузки (17 файлов):
```
Файл                                | Размер (байт)
-------------------------------------------------------
cashback-one-1.0.0.apk              | 51154351
cashback-one-1.0.1.apk              | 51154339
cashback-one-1.0.10.apk             | 68600435
cashback-one-1.0.11-test.apk        | 68601127
cashback-one-1.0.12.apk             | 69675373
cashback-one-1.0.2.apk              | 51160387
cashback-one-1.0.2.pre-ui.bak       | 51156475
cashback-one-1.0.2.round1.bak       | 51156327
cashback-one-1.0.3.apk              | 51167439
cashback-one-1.0.4.apk              | 51630551
cashback-one-1.0.5.apk              | 51630487
cashback-one-1.0.6.apk              | 62529495
cashback-one-1.0.7.apk              | 67778452
cashback-one-1.0.8.apk              | 67773772
cashback-one-1.0.9.apk              | 67951855
version.json                        | 169
```
Целевой файл `keremet-cashback-1.0.12.apk` до загрузки отсутствовал.

### 2.3. Шаг 4: Загрузка во временный файл, обратная проверка и переименование
```
Uploading to temporary name: .keremet-cashback-1.0.12.apk.upload-9466569f ...
Upload complete. Verifying size on server...
Remote size of .keremet-cashback-1.0.12.apk.upload-9466569f: 63668358
Downloading temporary file back for SHA-256 check...
Downloaded size: 63668358
Downloaded sha256: fb1090049b81f337a88e7cbf8363ae8109164e7d974e9fca1a64c520d0003265

Verification passed. Renaming .keremet-cashback-1.0.12.apk.upload-9466569f -> keremet-cashback-1.0.12.apk ...
Rename successful.
```

### 2.4. Шаг 5: Повторный список файлов в `app/` после загрузки
```
Файл                                | Размер (байт)
-------------------------------------------------------
cashback-one-1.0.0.apk              | 51154351
cashback-one-1.0.1.apk              | 51154339
cashback-one-1.0.10.apk             | 68600435
cashback-one-1.0.11-test.apk        | 68601127
cashback-one-1.0.12.apk             | 69675373
cashback-one-1.0.2.apk              | 51160387
cashback-one-1.0.2.pre-ui.bak       | 51156475
cashback-one-1.0.2.round1.bak       | 51156327
cashback-one-1.0.3.apk              | 51167439
cashback-one-1.0.4.apk              | 51630551
cashback-one-1.0.5.apk              | 51630487
cashback-one-1.0.6.apk              | 62529495
cashback-one-1.0.7.apk              | 67778452
cashback-one-1.0.8.apk              | 67773772
cashback-one-1.0.9.apk              | 67951855
keremet-cashback-1.0.12.apk         | 63668358
version.json                        | 169
```
- Добавлен ровно 1 файл: `keremet-cashback-1.0.12.apk` (размер 63 668 358 байт).
- Временных файлов нет.
- Все остальные файлы и их размеры остались без изменений.

### 2.5. Шаг 6: Проверка по HTTPS (`Cache-Control: no-cache`)
```
Downloading keremet-cashback-1.0.12.apk over HTTPS...
Status: 200
Content-Type: application/vnd.android.package-archive
Content-Length header: 63668358
Actual size: 63668358
Actual SHA-256: fb1090049b81f337a88e7cbf8363ae8109164e7d974e9fca1a64c520d0003265
```
Размер и SHA-256 скачанного файла побайтно совпали с локальным оригиналом.

### 2.6. Шаг 7: Сверка неизменности `version.json` и главной страницы
- `https://cashback-qr.poscenter.kz/app/version.json`:
  - До загрузки: `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b`
  - После загрузки: `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b`
  - Статус: **не изменился**.
- Главная страница `https://cashback-qr.poscenter.kz/`:
  - До загрузки: `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b`
  - После загрузки: `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b`
  - Статус: **не изменилась**.

---

## 3. Не проверено

Следующие проверки требуют реального физического Android-устройства:
1. Скачивание APK по ссылке непосредственно из мобильного браузера на телефон.
2. Установка приложения `Keremet Bonus` (`kz.cashbackone.keremet`) на телефон и прохождение авторизации по OTP.
3. Получение push-уведомлений в установленное приложение при кассовом списании.
