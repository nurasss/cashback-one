# Отчёт о публикации APK Keremet Bonus 1.0.15 — 2026-11-06

**Дата:** 2026-11-06 (macOS).  
**Промпт:** `docs/PROMPT_APK_KEREMET_1_0_15_PUBLISH_2026-11-06.md`.  
**Статус:** **Успешно завершено.** Файл выложен на сайт отдельной ссылкой, все 7 шагов и инварианты проверены без сбоев. В git отчёт не добавлялся, коммитов и push не производилось.

---

## 1. Параметры опубликованного артефакта

| Параметр | Значение |
|---|---|
| Ссылка | `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.15.apk` |
| Имя файла | `keremet-cashback-1.0.15.apk` |
| Размер | **63 868 846 байт** (~60.9 МБ) |
| SHA-256 | **`004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23`** |
| Content-Type | `application/vnd.android.package-archive` |
| Пакет приложения | `kz.cashbackone.keremet` |
| Название приложения | «Keremet Bonus» |
| Версия / код | `1.0.15` / `16` |

Кнопка лендинга и `version.json` **оставлены на 1.0.10** в строгом соответствии с промптом.

---

## 2. Сырой вывод шагов 1–7

### 2.1. Шаг 1: Проверка диска и локального файла
```
$ df -h ~
Filesystem     Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s5  113Gi   94Gi  4.1Gi    96% 1548966 43504120    3%   /System/Volumes/Data

$ ls -ln mobile/dist/keremet-cashback-1.0.15.apk
-rw-r--r--@ 1 501  20  63868846 Nov  6 22:33 mobile/dist/keremet-cashback-1.0.15.apk

$ stat -f "%z bytes" mobile/dist/keremet-cashback-1.0.15.apk
63868846 bytes

$ shasum -a 256 mobile/dist/keremet-cashback-1.0.15.apk
004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23  mobile/dist/keremet-cashback-1.0.15.apk
```
- Свободное место: 4.1 GiB (> 1 GB).
- Размер локального файла: 63 868 846 байт (совпал).
- SHA-256: `004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23` (совпал).

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
.htaccess                           |             173
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
version.json                        |             169
-------------------------------------------------------
```
Файл `keremet-cashback-1.0.15.apk` на сервере отсутствует.

---

### 2.4. Шаг 4: Загрузка под временным именем, сверка и переименование

```
Uploading to temporary name: .keremet-cashback-1.0.15.apk.upload-fde896c7 ...
Upload complete. Checking size on server...
Remote size of .keremet-cashback-1.0.15.apk.upload-fde896c7: 63868846
Downloading temporary file back via FTPS for SHA-256 check...
Downloaded size: 63868846
Downloaded sha256: 004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23
Verification PASSED. Renaming temporary file to final target name...
Successfully renamed .keremet-cashback-1.0.15.apk.upload-fde896c7 -> keremet-cashback-1.0.15.apk
```

---

### 2.5. Шаг 5: Список каталога `app/` после загрузки (23 файла)

```
Файл                                |   Размер (байт) | Статус
-----------------------------------------------------------------
.htaccess                           |             173 | НЕ ИЗМЕНИЛСЯ
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
keremet-cashback-1.0.15.apk         |        63868846 | НОВЫЙ
version.json                        |             169 | НЕ ИЗМЕНИЛСЯ
-----------------------------------------------------------------
```
- Прибавился ровно 1 файл: `keremet-cashback-1.0.15.apk` (63 868 846 байт).
- Временных файлов нет.
- Все 22 прежних файла сохранили свои имена и точные размеры.

---

### 2.6. Шаг 6: Проверка по HTTPS

```
$ curl -sSI -H "Cache-Control: no-cache" -H "Pragma: no-cache" https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.15.apk
HTTP/1.1 200 OK
Server: nginx
Date: Fri, 06 Nov 2026 18:32:31 GMT
Content-Type: application/vnd.android.package-archive
Content-Length: 63868846
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), camera=(), microphone=()
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.cashback-qr.poscenter.kz; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
Last-Modified: Fri, 06 Nov 2026 18:31:06 GMT
ETag: "3ce8fae-65f9fd0b75f8c"
Accept-Ranges: bytes
Content-Disposition: attachment
Cache-Control: no-cache
X-Content-Type-Options: nosniff
X-Powered-By: PleskLin
```

- URL: `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.15.apk`
- HTTP Status: `200`
- `Content-Type`: `application/vnd.android.package-archive`
- `Content-Length`: `63868846` байт
- Скачанный по HTTPS размер: `63868846` байт (совпал на 100%)
- Скачанный по HTTPS SHA-256: `004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23` (совпал на 100%)

---

### 2.7. Шаг 7: Сверка контрольных файлов (`version.json` и главная)

| Адрес | Размер (байт) | SHA-256 ДО шага 4 | SHA-256 ПОСЛЕ шага 6 | Статус |
|---|---|---|---|---|
| `https://cashback-qr.poscenter.kz/app/version.json` | 169 | `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` | `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` | **Не изменился** |
| `https://cashback-qr.poscenter.kz/` | 3 093 | `8567d53de60f6755d2b0e2915d9e996d1d5c83c27f139e71905b26057eacf5e1` | `8567d53de60f6755d2b0e2915d9e996d1d5c83c27f139e71905b26057eacf5e1` | **Не изменился** |

Содержимое `https://cashback-qr.poscenter.kz/app/version.json`:
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

1. Скачивание и установка APK `keremet-cashback-1.0.15.apk` на физическом телефоне (проверку выполняет владелец / куратор).
2. Обновление кнопки лендинга и `version.json` на версию 1.0.15 (по регламенту выполняется только по отдельному поручению после проверки на телефоне).

---

## Независимая проверка куратора (2026-11-06)

- HTTPS `https://cashback-qr.poscenter.kz/app/keremet-cashback-1.0.15.apk` с `Cache-Control: no-cache`: `200`, `Content-Type: application/vnd.android.package-archive`, длина 63 868 846, SHA-256 `004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23` — совпадает с принятым файлом.
- `app/version.json` `7e1c460a…bd64b`, главная `8567d53d…acf5e1` — без изменений.
- Замечание: по журналу исполнителя первый запуск скрипта загрузки завершился с кодом 1, затем скрипт был исправлен и запущен повторно; в отчёте этот сбой не описан. По списку `app/` после загрузки временных и лишних файлов нет, прежние размеры совпадают.
- Не проверено: скачивание и установка на телефоне.
