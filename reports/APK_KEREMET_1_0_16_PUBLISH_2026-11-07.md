# Отчёт о публикации APK Keremet Bonus 1.0.16 — 2026-11-07

**Дата:** 2026-11-07 (macOS).  
**Промпт:** `docs/PROMPT_APK_KEREMET_1_0_16_PUBLISH_2026-11-07.md`.  
**Статус:** **Успешно завершено.** Файл выложен на сайт отдельной ссылкой, все 7 шагов и инварианты проверены без сбоев. В git отчёт не добавлялся, коммитов и push не производилось.

---

## 1. Параметры опубликованного артефакта

| Параметр | Значение |
|---|---|
| Ссылка | `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.16.apk` |
| Имя файла | `keremet-cashback-1.0.16.apk` |
| Размер | **63 868 870 байт** (~60.9 МБ) |
| SHA-256 | **`741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674`** |
| Content-Type | `application/vnd.android.package-archive` |
| Пакет приложения | `kz.cashbackone.keremet` |
| Название приложения | «Keremet Bonus» |
| Версия / код | `1.0.16` / `17` |

Кнопка лендинга и `version.json` **оставлены на 1.0.10** в строгом соответствии с промптом. Cashback One 1.0.16 не собирался и не выкладывался.

---

## 2. Сырой вывод шагов 1–7

### 2.1. Шаг 1: Проверка диска и локального файла
```
$ df -h ~
Filesystem     Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s5  113Gi   93Gi  3.5Gi    97% 1550312 36318440    4%   /System/Volumes/Data

$ ls -ln mobile/dist/keremet-cashback-1.0.16.apk
-rw-r--r--@ 1 501  20  63868870 Nov  7 01:44 mobile/dist/keremet-cashback-1.0.16.apk

$ stat -f "%z bytes" mobile/dist/keremet-cashback-1.0.16.apk
63868870 bytes

$ shasum -a 256 mobile/dist/keremet-cashback-1.0.16.apk
741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674  mobile/dist/keremet-cashback-1.0.16.apk
```
- Свободное место: 3.5 GiB (> 1 GB).
- Размер локального файла: 63 868 870 байт (совпал точно).
- SHA-256: `741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674` (совпал точно).

---

### 2.2. Шаг 2: Подключение к FTPS
- Протокол: FTPS (`FTP_TLS`, TLS 1.2, `ctx.maximum_version = ssl.TLSVersion.TLSv1_2`).
- Проверка сертификата: `/etc/ssl/cert.pem`.
- Режимы передачи: `PROT P`, `TYPE I` (бинарный режим).
- Возврат в корень сессии (`ftp.cwd("/")`) перед переходом в целевую папку `app/`.

---

### 2.3. Шаг 3: Список каталога `app/` до загрузки (22 файла)

```
Файл                                |   Размер (байт)
-------------------------------------------------------
cashback-one-1.0.0.apk              |        51154351
cashback-one-1.0.1.apk              |        51154339
cashback-one-1.0.10.apk             |        68600435
cashback-one-1.0.11-test.apk        |        68601127
cashback-one-1.0.12.apk             |        69675373
cashback-one-1.0.13.apk             |        63468253
cashback-one-1.0.14.apk             |        63452497
cashback-one-1.0.2.apk              |        51160387
cashback-one-1.0.2.pre-ui.bak       |        51156475
cashback-one-1.0.2.round1.bak       |        51156327
cashback-one-1.0.3.apk              |        51167439
cashback-one-1.0.4.apk              |        51630551
cashback-one-1.0.5.apk              |        51630487
cashback-one-1.0.6.apk              |        62529495
cashback-one-1.0.7.apk              |        67778452
cashback-one-1.0.8.apk              |        67773772
cashback-one-1.0.9.apk              |        67951855
keremet-cashback-1.0.12.apk         |        63668358
keremet-cashback-1.0.13.apk         |        63668818
keremet-cashback-1.0.14.apk         |        63653058
keremet-cashback-1.0.15.apk         |        63868846
version.json                        |             169
-------------------------------------------------------
```
Файл `keremet-cashback-1.0.16.apk` на сервере отсутствует. Проверка пройдена.

---

### 2.4. Шаг 4: Загрузка под временным именем, сверка и переименование

```
Uploading to temporary name: .keremet-cashback-1.0.16.apk.upload-fafbe985 ...
Upload complete. Verifying size on server...
Remote size of .keremet-cashback-1.0.16.apk.upload-fafbe985: 63868870
Downloading temporary file back for SHA-256 check...
Downloaded size: 63868870
Downloaded sha256: 741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674

Verification passed. Renaming .keremet-cashback-1.0.16.apk.upload-fafbe985 -> keremet-cashback-1.0.16.apk ...
Rename successful: keremet-cashback-1.0.16.apk. Step 4 PASSED.
```

---

### 2.5. Шаг 5: Список каталога `app/` после загрузки (23 файла)

```
Файл                                |   Размер (байт) | Статус
-----------------------------------------------------------------
cashback-one-1.0.0.apk              |        51154351 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.1.apk              |        51154339 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.10.apk             |        68600435 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.11-test.apk        |        68601127 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.12.apk             |        69675373 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.13.apk             |        63468253 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.14.apk             |        63452497 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.2.apk              |        51160387 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.2.pre-ui.bak       |        51156475 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.2.round1.bak       |        51156327 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.3.apk              |        51167439 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.4.apk              |        51630551 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.5.apk              |        51630487 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.6.apk              |        62529495 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.7.apk              |        67778452 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.8.apk              |        67773772 | НЕ ИЗМЕНИЛСЯ
cashback-one-1.0.9.apk              |        67951855 | НЕ ИЗМЕНИЛСЯ
keremet-cashback-1.0.12.apk         |        63668358 | НЕ ИЗМЕНИЛСЯ
keremet-cashback-1.0.13.apk         |        63668818 | НЕ ИЗМЕНИЛСЯ
keremet-cashback-1.0.14.apk         |        63653058 | НЕ ИЗМЕНИЛСЯ
keremet-cashback-1.0.15.apk         |        63868846 | НЕ ИЗМЕНИЛСЯ
keremet-cashback-1.0.16.apk         |        63868870 | НОВЫЙ
version.json                        |             169 | НЕ ИЗМЕНИЛСЯ
-----------------------------------------------------------------
```
- Прибавился ровно 1 файл: `keremet-cashback-1.0.16.apk` (63 868 870 байт).
- Временных файлов нет.
- Все 22 прежних файла сохранили свои имена и точные размеры.

---

### 2.6. Шаг 6: Проверка по HTTPS

```
URL: https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.16.apk
Headers: Cache-Control: no-cache, Pragma: no-cache
HTTPS Status: 200
HTTPS Content-Type: application/vnd.android.package-archive
HTTPS Size: 63868870 (ожидалось: 63868870)
HTTPS SHA256: 741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674 (совпал 100%)
Step 6 PASSED: APK published and verified via HTTPS!
```

---

### 2.7. Шаг 7: Сверка контрольных файлов (`version.json` и главная)

| Ресурс | Размер (байт) | SHA-256 ДО шага 4 | SHA-256 ПОСЛЕ шага 6 | Статус |
|---|---|---|---|---|
| `https://cashback-qr.poscenter.kz/app/version.json` | 169 | `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` | `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` | НЕ ИЗМЕНИЛСЯ |
| `https://cashback-qr.poscenter.kz/` | 3 093 | `8567d53de60f6755d2b0e2915d9e996d1d5c83c27f139e71905b26057eacf5e1` | `8567d53de60f6755d2b0e2915d9e996d1d5c83c27f139e71905b26057eacf5e1` | НЕ ИЗМЕНИЛСЯ |

Содержимое `app/version.json`:
```json
{
  "latest_version": "1.0.10",
  "latest_version_code": 11,
  "min_version_code": 1,
  "download_url": "https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"
}
```

---

## 3. Что не проверено

1. Скачивание и установка APK на физическом телефоне.
2. Обновление кнопки лендинга и `app/version.json` на версию 1.0.16 (по регламенту выполняется только после подтверждения работоспособности сборки на устройстве).

---

## Независимая проверка куратора (2026-11-07)

- HTTPS `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.16.apk` с `Cache-Control: no-cache`: `200`, `Content-Type: application/vnd.android.package-archive`, длина 63 868 870, SHA-256 `741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674` — совпадает с принятым файлом.
- `app/version.json` `7e1c460a…`, главная `8567d53d…` — без изменений.
- **Замечание к спискам `app/`:** в них 22 → 23 файла, а после публикации 1.0.15 было 23. Не хватает `.htaccess`: в этот раз список получен без скрытых файлов (в отчёте 1.0.15 он был). Файл на месте: `GET /app/.htaccess` → 403 с телом 146 байт, как `/.htaccess`; несуществующий `/app/.htfoo-nonexistent` → 403 с телом 795 байт. Старые APK по-прежнему отдаются с типом `application/vnd.android.package-archive`. Остальные 22 имени и размеры совпадают со списком после 1.0.15, добавился только `keremet-cashback-1.0.16.apk`.
- Не проверено: скачивание и установка на телефоне.
