# Публикация APK 1.0.11-test отдельной ссылкой — 2026-11-04

По поручению владельца APK 1.0.11-test выложен на сайт **отдельным файлом** для установки на телефон:
https://cashback-qr.poscenter.kz/app/cashback-one-1.0.11-test.apk

---

## 1. Параметры опубликованного артефакта

| Параметр | Значение |
|---|---|
| Файл | `mobile/dist/cashback-one-1.0.11-test.apk` |
| Размер | **68 601 127 байт** |
| SHA-256 | `1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754` |
| URL | `https://cashback-qr.poscenter.kz/app/cashback-one-1.0.11-test.apk` |
| HTTP Status | `HTTP/1.1 200 OK` |
| Content-Type | `application/vnd.android.package-archive` |
| Content-Length | `68601127` |

---

## 2. Сырой вывод шагов

### Шаг 1. Проверка места и локального файла
```text
$ df -h ~
Filesystem     Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s5  113Gi   93Gi  4.7Gi    96% 1510125 49344520    3%   /System/Volumes/Data

$ ls -l mobile/dist/cashback-one-1.0.11-test.apk
-rw-r--r--@ 1 nuras  staff  68601127 Nov  4 21:57 mobile/dist/cashback-one-1.0.11-test.apk

$ shasum -a 256 mobile/dist/cashback-one-1.0.11-test.apk
1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754  mobile/dist/cashback-one-1.0.11-test.apk
```
Размер (68 601 127 байт) и SHA-256 (`1fbb7c6c...`) полностью совпали с принятыми в `reports/APK_1_0_11_TEST_BUILD.md`.

### Шаг 2. Подключение FTPS
- Протокол: TLS 1.2 (`context.maximum_version = ssl.TLSVersion.TLSv1_2`), `PROT P`, `TYPE I`.
- Проверка сертификата включена (`cafile="/etc/ssl/cert.pem"`).
- Переход в каталог приложения: перед каждой сменой директории выполняется возврат в корень сессии (`ftp.cwd('/')`).
- Секреты доступа из `.env.hosting.local` не выводились и не сохранялись.

### Шаг 3. Список файлов `app/` до загрузки (14 файлов)
```text
cashback-one-1.0.0.apk             51154351 bytes
cashback-one-1.0.1.apk             51154339 bytes
cashback-one-1.0.2.apk             51160387 bytes
cashback-one-1.0.2.pre-ui.bak      51156475 bytes
cashback-one-1.0.2.round1.bak      51156327 bytes
cashback-one-1.0.3.apk             51167439 bytes
cashback-one-1.0.4.apk             51630551 bytes
cashback-one-1.0.5.apk             51630487 bytes
cashback-one-1.0.6.apk             62529495 bytes
cashback-one-1.0.7.apk             67778452 bytes
cashback-one-1.0.8.apk             67773772 bytes
cashback-one-1.0.9.apk             67951855 bytes
cashback-one-1.0.10.apk            68600435 bytes
version.json                            169 bytes
```
Файла `cashback-one-1.0.11-test.apk` до загрузки в каталоге не было.

### Шаг 4. Загрузка под временным именем, обратное скачивание и переименование
- Временное имя на FTPS: `.cashback-one-1.0.11-test.apk.upload-2ced4f1b`
- Размер загруженного файла на FTPS: `68601127` байт
- Обратное скачивание по FTPS во временный проверочный файл `/tmp/.cashback-one-1.0.11-test.apk.upload-2ced4f1b.verify`:
  - Размер скачанного: `68601127` байт
  - SHA-256 скачанного: `1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754`
  - Сверка: полное побайтовое совпадение с исходным локальным файлом.
- Переименование на сервере: `.cashback-one-1.0.11-test.apk.upload-2ced4f1b` → `cashback-one-1.0.11-test.apk`.
- Временный файл скачивания удален.
- *Примечание по вспомогательному скрипту:* вызов `nlst()` переводит канал управления в режим ASCII (`TYPE A`), из-за чего последующий опрос `size()` вернул ошибку `550 SIZE not allowed in ASCII mode`. Скрипт скорректирован вызовом `voidcmd('TYPE I')` перед опросом размеров.

### Шаг 5. Повторный список `app/` после загрузки (15 файлов)
```text
cashback-one-1.0.0.apk             51154351 bytes
cashback-one-1.0.1.apk             51154339 bytes
cashback-one-1.0.10.apk            68600435 bytes
cashback-one-1.0.11-test.apk       68601127 bytes   <--- ДОБАВЛЕН
cashback-one-1.0.2.apk             51160387 bytes
cashback-one-1.0.2.pre-ui.bak      51156475 bytes
cashback-one-1.0.2.round1.bak      51156327 bytes
cashback-one-1.0.3.apk             51167439 bytes
cashback-one-1.0.4.apk             51630551 bytes
cashback-one-1.0.5.apk             51630487 bytes
cashback-one-1.0.6.apk             62529495 bytes
cashback-one-1.0.7.apk             67778452 bytes
cashback-one-1.0.8.apk             67773772 bytes
cashback-one-1.0.9.apk             67951855 bytes
version.json                            169 bytes
```
Прибавился ровно 1 файл (`cashback-one-1.0.11-test.apk`), временных файлов нет, размеры и имена всех остальных файлов не изменились.

### Шаг 6. Скачивание по HTTPS и проверка
```text
$ curl -v -H "Cache-Control: no-cache" https://cashback-qr.poscenter.kz/app/cashback-one-1.0.11-test.apk -o /tmp/downloaded-1.0.11-test.apk
< HTTP/1.1 200 OK
< Content-Type: application/vnd.android.package-archive
< Content-Length: 68601127

$ ls -l /tmp/downloaded-1.0.11-test.apk
-rw-r--r--@ 1 nuras  wheel  68601127 Nov  4 22:05 /tmp/downloaded-1.0.11-test.apk

$ shasum -a 256 /tmp/downloaded-1.0.11-test.apk mobile/dist/cashback-one-1.0.11-test.apk
1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754  /tmp/downloaded-1.0.11-test.apk
1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754  mobile/dist/cashback-one-1.0.11-test.apk
```
`Content-Type: application/vnd.android.package-archive`, длина `68601127` байт и SHA-256 полностью совпадают. Временный скачанный файл удален.

### Шаг 7. Проверка неизменности `version.json` и главной страницы

#### До загрузки (до шага 4):
```text
$ curl -s -H "Cache-Control: no-cache" https://cashback-qr.poscenter.kz/app/version.json | shasum -a 256
7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b  -

$ curl -s -H "Cache-Control: no-cache" https://cashback-qr.poscenter.kz/ | shasum -a 256
c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d  -
```

#### После загрузки (после шага 6):
```text
$ curl -s -H "Cache-Control: no-cache" https://cashback-qr.poscenter.kz/app/version.json | shasum -a 256
7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b  -

$ curl -s -H "Cache-Control: no-cache" https://cashback-qr.poscenter.kz/ | shasum -a 256
c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d  -
```
Хеши `version.json` и главной страницы идентичны до и после загрузки (не изменялись).

---

## 3. Соблюдение ограничений

- `app/version.json` не менялся;
- Главная страница (`index.html`), кнопка лендинга, `.htaccess`, другие APK, каталоги `demo/`, `media/` не изменялись;
- Файл `cashback-one-1.0.11-test.no-api.apk` на сервер не загружался;
- Без публикации в GitHub Releases, без commit и push, без изменений исходного кода репозитория.

---

## 4. Не проверено

- Скачивание APK по ссылке на физический Android-смартфон;
- Установка APK `1.0.11-test` поверх версии 1.0.10 на физическом устройстве.
