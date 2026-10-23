# Локальный POS-сервис динамического QR — 2026-10-23

## Итог: СТОП на проверке mypy до правок

`docs/PROMPT_AGENT_POS_QR_2026-10-23.md` прочитан целиком (122 строки). Тесты агента и ruff прошли. В `agent/pyproject.toml` настроен strict mypy; пакет доступен в существующем `backend/.venv`. Его проверка до правок завершилась кодом 1: 10 ошибок в 4 файлах. Среди них есть ошибки типов, не связанные с платформой. По обязательному правилу «Упало или неожиданно — СТОП» исходники не изменялись, исправления и повторные прогоны не выполнялись.

## Изменения по файлам

- Создан только этот отчёт — `reports/AGENT_POS_QR_2026-10-23.md`.
- `agent/`, существующие тесты и фикстуры, packaging, runtime, SQLite/HMAC/курсоры/ACL не изменялись.
- Документ интеграции и пример BSL не создавались: реализация остановлена до правок.
- Конфиги клиента и `.env*` не читались и не изменялись; облако, VPS, установленная служба и ONE не затрагивались.
- Зависимости не устанавливались, venv не создавался, EXE/установщик не собирались; commit/push не выполнялись.
- `admin/`, `backend/`, `mobile/` не изменялись. Существующий Python из `backend/.venv` использован только как среда проверок.

## Контракт (требование, ещё не реализовано)

Касса → HTTP по LAN с отдельным `X-Pos-Token` → агент → облако с `X-Agent-Key`. Ключ агента кассе не передаётся.

- По умолчанию POS-сервис выключен; при включении пароль кассы не короче 32 символов, CIDR allowlist, хост/порт и тайм-аут проверяются.
- `POST /v1/qr/resolve`, `application/json`, до 1 КБ, `{"token":"C1..."}` → только `{"barcode":"..."}` со строковым номером и ведущими нулями.
- `GET /v1/health` с тем же паролем → `{"status":"ok"}`, без обращения к облаку.
- CIDR → пароль через compare_digest → ограничения частоты → локальный QR-шаблон → облако без повторов.
- Ошибки: `403 POS_FORBIDDEN`, `401 POS_UNAUTHORIZED`, `429 POS_RATE_LIMITED`, `400 QR_TOKEN_MALFORMED`, `413` для большого тела; облако 422 → `422 QR_TOKEN_INVALID`, 401/403 → `502 AGENT_NOT_AUTHORIZED`, тайм-аут → `504 CLOUD_TIMEOUT`, сеть → `503 CLOUD_UNAVAILABLE`, прочее → `502 CLOUD_ERROR`.
- Формат ошибки: `{"error":{"code":"...","message":"..."}}`, короткое сообщение по-русски; секреты и полные QR/номера в логи не попадают.
- Стандартный ThreadingHTTPServer, отдельный daemon-поток, независимость от синхронизации, остановка вместе с runtime; `status` без секретов.

Это описание заданного контракта, **не результат реализации или интеграционного теста**.

## Сырые выводы проверок

Рабочий каталог всех shell-команд: `/Users/nuras/Desktop/cashback-one`.

### Исходное состояние Git

`git status --short`, код выхода **0**:

```text
?? C:/
?? docs/PROMPT_AGENT_POS_QR_2026-10-23.md
```

Вложенные инструкции проверены инструментом glob: `**/AGENTS.md` внутри `agent/`, включая скрытые каталоги. Ответ `No files found`; это не shell-команда, код выхода неприменим.

### Baseline pytest

`PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q -ra`, код выхода **0**, тайм-аут инструмента 360000 мс:

```text
................................ssssssssssssss.......................... [ 35%]
.............................ssss..s.................................... [ 70%]
....................................................ssss...              [100%]
=========================== short test summary info ============================
SKIPPED [1] agent/tests/test_installer_config.py:52: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [1] agent/tests/test_installer_config.py:113: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [5] agent/tests/test_installer_config.py:206: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [7] agent/tests/test_installer_config.py:278: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [1] agent/tests/test_one_mapping.py:23: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:55: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:63: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:73: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:93: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_windows_service.py:62: Windows only test
SKIPPED [3] agent/tests/test_windows_service.py:84: Windows only test
180 passed, 23 skipped in 14.58s
```

Список skip: 14 проверок установщика без ISCC, 5 проверок без внешнего Stage 0 mapping, 4 Windows-only проверки службы. Они не исправлялись и не объявляются пройденными.

### Baseline ruff

`backend/.venv/bin/python -m ruff check agent`, код выхода **0**:

```text
All checks passed!
```

### Доступность mypy

`backend/.venv/bin/python -c 'import importlib.util; print("mypy_available=" + str(importlib.util.find_spec("mypy") is not None))'`, код выхода **0**:

```text
mypy_available=True
```

### Baseline mypy — причина остановки

`PYTHONPATH=agent/src backend/.venv/bin/python -m mypy --config-file agent/pyproject.toml agent/src`, код выхода **1**:

```text
agent/src/poscenter_loyalty_agent/stage0/data_profile.py:415: error: Dict entry 0 has incompatible type "str": "str"; expected "str": "dict[str, int]"  [dict-item]
agent/src/poscenter_loyalty_agent/stage0/data_profile.py:415: note: Error code "dict-item" not covered by "type: ignore[return-value]" comment
agent/src/poscenter_loyalty_agent/one_com_source.py:512: error: Argument 1 to "convert_one_datetime" has incompatible type "Any | None"; expected "datetime"  [arg-type]
agent/src/poscenter_loyalty_agent/dry_run.py:108: error: Unexpected keyword argument "next_check_in_seconds" for "HeartbeatResult"  [call-arg]
agent/src/poscenter_loyalty_agent/dry_run.py:219: error: Incompatible types in assignment (expression has type "SourceBatch[TransactionSyncItem]", variable has type "SourceBatch[CardSyncItem]")  [assignment]
agent/src/poscenter_loyalty_agent/dry_run.py:222: error: Argument "transactions" to "TransactionsSyncPayload" has incompatible type "list[CardSyncItem]"; expected "list[TransactionSyncItem]"  [arg-type]
agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "OpenKey"  [attr-defined]
agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "HKEY_CURRENT_USER"  [attr-defined]
agent/src/poscenter_loyalty_agent/dry_run.py:273: error: Module has no attribute "QueryValueEx"  [attr-defined]
agent/src/poscenter_loyalty_agent/windows_service.py:120: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_name_"  [attr-defined]
agent/src/poscenter_loyalty_agent/windows_service.py:121: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_args_"  [attr-defined]
Found 10 errors in 4 files (checked 29 source files)
```

Не все ошибки платформенные: в частности, ошибки типов коллекций и payload в `stage0/data_profile.py` и `dry_run.py`. Существующий mypy не объявляется зелёным. Никаких type-ignore, изменений фикстур или исправлений вне задачи не внесено.

## Не проверено / не выполнено

- Сам POS-сервис, настройки и status: не реализованы.
- Новые тесты POS, ограничения частоты, проверка пароля/CIDR/QR, лимит тела, логи и изоляция: не реализованы и не проверены.
- Ручной Mac-запуск с подменённым облаком и curl: не выполнен.
- Итоговая регрессия после правок: не выполнялась, правок кода нет.
- Windows-служба и совместный lifecycle: не проверены на Windows.
- Windows Firewall: команда не выполнялась, правило не создавалось.
- Реальная касса и пример BSL: не проверены; пример пока не создан.
- Реальное облако: не вызывалось.
- EXE/установщик и комплектность PyInstaller: не собирались и не проверялись.

## План следующего шага для куратора

1. Принять решение по baseline mypy: отдельное разрешение продолжить с зафиксированными 10 существующими ошибками либо отдельная задача на их исправление. Самостоятельно обходить СТОП нельзя.
2. После разрешения реализовать текущий промпт, выполнить локальные mock-тесты и curl, создать инструкцию и BSL-пример; независимая приёмка куратора.
3. Отдельная задача на Windows: сборка EXE и установщика, проверка включения нового модуля в сборку без ослабления защиты конфигов и состояния.
4. На тестовом Windows-компьютере, по отдельному разрешению: защищённая копия конфига и состояния, обновление агента с POS выключенным; затем включение POS с отдельным паролем кассы и узким CIDR/IP allowlist. Ключ агента кассе не передавать.
5. Настроить Windows Firewall: входящий TCP 8765, только Private, RemoteIP — конкретный IP тестовой кассы; не открывать всем сетям.
6. Проверить `/v1/health` с кассы, затем контролируемое разрешение свежего QR и ошибки; BSL-пример проверяют разработчики Cash. Этот шаг требует отдельного согласования настоящего облака и кассы.

Результат не объявляется готовым: реализация не начата из-за baseline СТОП.

## Финальное состояние Git

`git status --short`, из корня репозитория, код выхода **0**:

```text
?? C:/
?? docs/PROMPT_AGENT_POS_QR_2026-10-23.md
?? reports/AGENT_POS_QR_2026-10-23.md
```

`git diff --stat`, из корня репозитория, код выхода **0**, вывод пустой (инструмент показывает `(no output)`). Неотслеживаемый отчёт в diff не включается.

---

## Продолжение после СТОП — реализация и локальная проверка

Обновлённый промпт прочитан целиком (129 строк). Получено разрешение продолжать с **ровно 10 прежними ошибками mypy**, без их исправления. Раздел первой остановки выше сохранён как история; его утверждения «не реализовано» относятся к первому этапу, актуальный результат — ниже. Baseline тестов и ruff по прямому указанию повторно не запускался.

**Результат:** реализован опциональный POS-сервис; локальная регрессия **227 passed, 23 skipped**, ruff чистый; список 10 ошибок mypy совпал построчно, новых ошибок нет. Реальный curl на Mac проверил 200/401/400 через loopback и MockTransport. Это **не** приёмка Windows EXE, настоящей кассы и облака.

### Изменения по файлам

| Файл | Изменение |
|---|---|
| `agent/src/poscenter_loyalty_agent/config.py` | Шесть POS-настроек; по умолчанию выключено. SecretStr для POS-пароля, исключение из repr/model_dump, hide_input_in_errors для безопасных ошибок check-config. При включении проверяются пароль, IP хоста, порт и CIDR. |
| `agent/src/poscenter_loyalty_agent/pos_server.py` | Новый ThreadingHTTPServer с daemon listener/handler-потоками, два маршрута, peer-IP allowlist, compare_digest, потокобезопасный скользящий rate-limit, ограничение тела, socket timeout, синхронный httpx.Client и безопасное преобразование ошибок. Нет зависимостей от ONE/state/SQLite/HMAC. |
| `agent/src/poscenter_loyalty_agent/runtime.py` | Запуск POS только при включённой настройке, остановка listener при cleanup. Блокирующие start/stop вынесены через asyncio.to_thread. Сбой POS не прерывает sync/heartbeat. Сам алгоритм sync, курсоры, backoff и heartbeat не менялись. Windows wrapper использует этот же runtime; `windows_service.py` не изменён. |
| `agent/src/poscenter_loyalty_agent/main.py` | `status` показывает настроенное состояние POS и адрес:порт, без POS-пароля. |
| `agent/tests/test_pos_server.py` | 47 новых тестовых случаев с реальным HTTP на 127.0.0.1:0, облако исключительно MockTransport; конфиг/CLI, rate-limit, HTTP/ошибки, безопасные логи и изоляция runtime. |
| `agent/tests/pos_qr_smoke.py` | Воспроизводимый ручной smoke через настоящий curl. Синтетические значения, конфиг curl с паролем/QR через stdin, без секретов в argv, только loopback и MockTransport. |
| `docs/POS_QR_INTEGRATION.md` | Русская инструкция: схема, маршруты/коды/сообщения кассиру, настройки, безопасная передача пароля, Windows Firewall, проверка health, ограничения HTTP/тайм-аутов. |
| `docs/integrations/cash_qr_resolve.bsl` | Пример двух требуемых функций и проверки строкового barcode. Маркирован «Пример, проверить у разработчиков Cash», не запускался в 1С, без записей в ONE. |
| `agent/README.md`, `docs/AGENT_API.md` | Короткие ссылки на интеграционную инструкцию. |
| Этот отчёт | Дополнен, исходная остановка не удалялась. |

Новых зависимостей нет, `pyproject.toml`, packaging, существующие тесты и фикстуры не менялись. Тесты не ослаблялись. Рабочие секреты/конфиг не читались, Windows-служба, Firewall, ONE, облако/VPS не затрагивались. `admin/`, `backend/`, `mobile/` без правок. Commit/push не выполнялись.

### Реализованный контракт и существенные детали

- Настройки по умолчанию соответствуют промпту: POS выключен, `0.0.0.0:8765`, заданный IPv4 CIDR-список, cloud timeout 5 секунд. При выключении не создаётся listener и POS HTTP-клиент.
- При включении пароль ≥32 печатных ASCII-символов без пробелов/CRLF, хост — буквальный IPv4/IPv6 (не DNS), порт 1–65535, сети — непустые строгие CIDR через запятую. Cloud timeout — конечное число `0 < значение ≤ 5`; это уточнение документировано для бюджета ожидания Cash.
- `POST /v1/qr/resolve`: application/json, ≤1024 байт, проверка token полным совпадением `C1[A-Z2-7]{20,120}`; успех только `{"barcode":"…"}`. Строка barcode дополнительно проверяется на 6–15 ASCII-цифр; ведущие нули не теряются. Никакого card_id кассе.
- `GET /v1/health` с IP/паролем/rate-limit возвращает `{"status":"ok"}`, не вызывает облако и не доказывает его доступность.
- Реальный peer IP, без доверия X-Forwarded-For → сравнение POS-пароля через hmac.compare_digest → rate-limit с учётом результата сравнения → локальная проверка QR → облако. Для первых 10 неверных паролей — 401, дальнейших неверных за минуту — 429. Иначе ранний возврат 401 сделал бы лимит неверных паролей неработающим. Правильный пароль после 10 неверных разрешён в пределах общего лимита 60 запросов/минуту.
- Общий лимит учитывает health, неверные пароли и другие запросы разрешённого IP. Скользящее окно 60 секунд, lock на структуре счётчиков, ограничение памяти 4096 активными адресами. IP вне списка всегда 403.
- Ответы облака: 422 → QR_TOKEN_INVALID/422, 401/403 → AGENT_NOT_AUTHORIZED/502, timeout → CLOUD_TIMEOUT/504, RequestError → CLOUD_UNAVAILABLE/503, прочие HTTP/неверный JSON/схема → CLOUD_ERROR/502. Повторов и follow_redirects нет. TLS verify включён, proxy env для POS-клиента отключён.
- Для остальных ошибок определены POS_BAD_REQUEST/400, POS_LENGTH_REQUIRED/411, POS_BODY_TOO_LARGE/413, POS_UNSUPPORTED_MEDIA_TYPE/415, POS_REQUEST_TIMEOUT/408, POS_NOT_FOUND/404, POS_INTERNAL_ERROR/500. Сообщения короткие русские, без тела ошибки облака.
- Требуется Content-Length; chunked и дублированная/неверная длина отклоняются. Локальный socket timeout 2 секунды бездействия. Access-log и стандартные traceback HTTP-сервера отключены; Server=`POSCENTER-POS`, без Python. Ошибки запуска/обработки логируют максимум тип исключения, не его текст.
- В журнале приложения QR — только первые 4 символа и длина, карта — только последние 4 цифры; пароли/ключи не журналируются. Caplog проверяет сырые сообщения именно агента: тестовый внешний HTTP-клиент сам может логировать специально вредоносный URL, это не access-log сервиса.
- У каждого облачного запроса свой sync Client; нет общих ресурсов с async sync-клиентом. POS-сервис не создаёт файлов состояния. Listener закрывается вместе с runtime; уже начатые daemon-обработчики могут завершать текущий запрос с сетевыми тайм-аутами и не блокируют завершение процесса.
- `status` показывает **конфигурацию**, а не проверенную живость listener. Проверка listener — health.
- HTTPX timeout — по сетевым фазам, **не жёсткий общий wall-clock deadline**. В инструкции Cash явно требуется общий предел ожидания UI ≤7 секунд; семантику HTTPСоединение проверить разработчикам Cash. Обычный LAN HTTP не шифрует пароль/номер: только изолированная доверенная сеть, узкий Firewall и без проброса наружу.

### Сырые выводы проверок после правок

Рабочий каталог всех команд — корень репозитория. stdout/stderr проверок сохранены обёрткой subprocess в существующем разрешённом временном каталоге `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/` (`pos-qr-pytest-after.log`, `pos-qr-ruff-after.log`, `pos-qr-mypy-after.log`, `pos-qr-curl.log`). Обёртки не меняют исходники; выводы ниже настоящие. Для pytest выставлен PYTHONPATH=agent/src; новые venv и пакеты не создавались.

#### Pytest — полный набор

Команда: `PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q -ra`. Код выхода **0**, тайм-аут инструмента 360000 мс.

```text
................................ssssssssssssss.......................... [ 28%]
.............................ssss..s.................................... [ 57%]
........................................................................ [ 86%]
...........................ssss...                                       [100%]
=========================== short test summary info ============================
SKIPPED [1] agent/tests/test_installer_config.py:52: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [1] agent/tests/test_installer_config.py:113: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [5] agent/tests/test_installer_config.py:206: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [7] agent/tests/test_installer_config.py:278: ISCC compiler not found at C:\cb-build\tools\innosetup\ISCC.exe
SKIPPED [1] agent/tests/test_one_mapping.py:23: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:55: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:63: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:73: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_one_mapping.py:93: Stage 0 mapping not found at C:\cashback-stage0\stage0_mapping.json
SKIPPED [1] agent/tests/test_windows_service.py:62: Windows only test
SKIPPED [3] agent/tests/test_windows_service.py:84: Windows only test
227 passed, 23 skipped in 23.41s

EXIT_CODE=0
```

Список skip совпадает с baseline: 14 без ISCC, 5 без внешнего Stage 0 mapping, 4 Windows-only. Новых skip нет. Прирост 227−180=**47 тестов**.

#### Ruff

`backend/.venv/bin/python -m ruff check agent`, код выхода **0**:

```text
All checks passed!

EXIT_CODE=0
```

#### Mypy после — те же 10 ошибок

`PYTHONPATH=agent/src backend/.venv/bin/python -m mypy --config-file agent/pyproject.toml agent/src`, код выхода mypy **1**, разрешённый baseline-долг. Проверяется исходный пакет, **не тесты**. Новых ошибок в новом POS-модуле, config/main/runtime нет.

Сырой вывод, включая строки первоначального сравнивателя:

```text
agent/src/poscenter_loyalty_agent/stage0/data_profile.py:415: error: Dict entry 0 has incompatible type "str": "str"; expected "str": "dict[str, int]"  [dict-item]
agent/src/poscenter_loyalty_agent/stage0/data_profile.py:415: note: Error code "dict-item" not covered by "type: ignore[return-value]" comment
agent/src/poscenter_loyalty_agent/one_com_source.py:512: error: Argument 1 to "convert_one_datetime" has incompatible type "Any | None"; expected "datetime"  [arg-type]
agent/src/poscenter_loyalty_agent/dry_run.py:108: error: Unexpected keyword argument "next_check_in_seconds" for "HeartbeatResult"  [call-arg]
agent/src/poscenter_loyalty_agent/dry_run.py:108: note: "HeartbeatResult" defined in "poscenter_loyalty_agent.models"
agent/src/poscenter_loyalty_agent/dry_run.py:219: error: Incompatible types in assignment (expression has type "SourceBatch[TransactionSyncItem]", variable has type "SourceBatch[CardSyncItem]")  [assignment]
agent/src/poscenter_loyalty_agent/dry_run.py:222: error: Argument "transactions" to "TransactionsSyncPayload" has incompatible type "list[CardSyncItem]"; expected "list[TransactionSyncItem]"  [arg-type]
agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "OpenKey"  [attr-defined]
agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "HKEY_CURRENT_USER"  [attr-defined]
agent/src/poscenter_loyalty_agent/dry_run.py:273: error: Module has no attribute "QueryValueEx"  [attr-defined]
agent/src/poscenter_loyalty_agent/windows_service.py:120: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_name_"  [attr-defined]
agent/src/poscenter_loyalty_agent/windows_service.py:121: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_args_"  [attr-defined]
Found 10 errors in 4 files (checked 30 source files)

MYPY_EXIT_CODE=1
BASELINE_LINES_MATCH=False
```

**Оговорка сравнения:** обёртка завершилась кодом **1**, потому что сравнивала не только `error`, но и `note`. Добавилась поясняющая строка о месте определения HeartbeatResult; это не новая ошибка и не нарушение разрешённого порога. Mypy повторно не запускался, код после проверок не исправлялся. Списки именно ошибок из уже полученного вывода и сохранённого baseline сравнены отдельной read-only Python-командой; её код выхода **0**. Сырой результат:

```text
BASELINE_ERROR_COUNT=10
AFTER_ERROR_COUNT=10
ERROR_LINES_IDENTICAL=True
EXTRA_NOTE_ONLY: dry_run.py:108: HeartbeatResult defined in poscenter_loyalty_agent.models
1. SAME agent/src/poscenter_loyalty_agent/stage0/data_profile.py:415: error: Dict entry 0 has incompatible type "str": "str"; expected "str": "dict[str, int]"  [dict-item]
2. SAME agent/src/poscenter_loyalty_agent/one_com_source.py:512: error: Argument 1 to "convert_one_datetime" has incompatible type "Any | None"; expected "datetime"  [arg-type]
3. SAME agent/src/poscenter_loyalty_agent/dry_run.py:108: error: Unexpected keyword argument "next_check_in_seconds" for "HeartbeatResult"  [call-arg]
4. SAME agent/src/poscenter_loyalty_agent/dry_run.py:219: error: Incompatible types in assignment (expression has type "SourceBatch[TransactionSyncItem]", variable has type "SourceBatch[CardSyncItem]")  [assignment]
5. SAME agent/src/poscenter_loyalty_agent/dry_run.py:222: error: Argument "transactions" to "TransactionsSyncPayload" has incompatible type "list[CardSyncItem]"; expected "list[TransactionSyncItem]"  [arg-type]
6. SAME agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "OpenKey"  [attr-defined]
7. SAME agent/src/poscenter_loyalty_agent/dry_run.py:272: error: Module has no attribute "HKEY_CURRENT_USER"  [attr-defined]
8. SAME agent/src/poscenter_loyalty_agent/dry_run.py:273: error: Module has no attribute "QueryValueEx"  [attr-defined]
9. SAME agent/src/poscenter_loyalty_agent/windows_service.py:120: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_name_"  [attr-defined]
10. SAME agent/src/poscenter_loyalty_agent/windows_service.py:121: error: "type[POSCENTERLoyaltyAgentService]" has no attribute "_exe_args_"  [attr-defined]
```

Все 10 сообщений и их номера строк одинаковы, соответствие 1:1. Эти четыре файла не менялись. Количество проверенных исходников увеличилось 29→30 за счёт `pos_server.py`. Baseline до правок целиком приведён в первом разделе этого отчёта. Mypy **не называется полностью зелёным**.

#### Ручная проверка Mac: настоящий curl, облако подменено

Команда: `PYTHONPATH=agent/src TMPDIR=/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode backend/.venv/bin/python agent/tests/pos_qr_smoke.py`, код выхода **0**. Запуск через subprocess-обёртку; у каждого curl дополнительно `--noproxy '*'`. POS listener и данные полностью тестовые. Заголовок пароля и тело идут в curl через stdin config, не argv. Скрипт проверяет отсутствие файлов состояния и закрытие listener.

```text
LOOPBACK=http://127.0.0.1:61950; cloud=MockTransport; all credentials/data synthetic

health, correct password: curl --silent --show-error --max-time 7 --config - --write-out '\nHTTP_CODE=%{http_code}\n'
(stdin config: URL + X-Pos-Token redacted + JSON when applicable)
{"status": "ok"}
HTTP_CODE=200
CURL_EXIT_CODE=0

resolve, correct password: curl --silent --show-error --max-time 7 --config - --write-out '\nHTTP_CODE=%{http_code}\n'
(stdin config: URL + X-Pos-Token redacted + JSON when applicable)
{"barcode": "000000123456"}
HTTP_CODE=200
CURL_EXIT_CODE=0

resolve, wrong password: curl --silent --show-error --max-time 7 --config - --write-out '\nHTTP_CODE=%{http_code}\n'
(stdin config: URL + X-Pos-Token redacted + JSON when applicable)
{"error": {"code": "POS_UNAUTHORIZED", "message": "Неверный пароль кассы."}}
HTTP_CODE=401
CURL_EXIT_CODE=0

resolve, malformed QR: curl --silent --show-error --max-time 7 --config - --write-out '\nHTTP_CODE=%{http_code}\n'
(stdin config: URL + X-Pos-Token redacted + JSON when applicable)
{"error": {"code": "QR_TOKEN_MALFORMED", "message": "Некорректный формат QR."}}
HTTP_CODE=400
CURL_EXIT_CODE=0

MOCK_CLOUD_CALLS=1; STATE_FILES_CREATED=0; no retries
LISTENER_STOPPED=True

EXIT_CODE=0
```

Синтетический barcode в этом выводе — не карта клиента. Успешное разрешение вызвало только MockTransport, health/неверный пароль/кривой QR к нему не обращались. Реального облака не было.

### Не проверено (актуально)

1. Windows SCM/service-run, установленная служба, COM/ONE и LocalSystem — только кодовый lifecycle через общий runtime и локальные fake-тесты; не реальная Windows-интеграция.
2. Windows Firewall и сеть магазин → агент — правило только описано, не выполнялось; наружный LAN-порт не открывался.
3. Настоящая Cash, сканер, BSL на версии платформы Cash — не запускались; BSL требует проверки разработчиками, включая общий дедлайн ожидания и Content-Length.
4. Настоящее облако, настоящий ключ, подпись/истечение/бизнес-изоляция действительного QR — не проверялись; используются MockTransport и синтетические токены.
5. EXE/установщик, PyInstaller-комплектность и установка/обновление — не собирались и не менялись.
6. IPv6 end-to-end, нагрузочная/DoS-устойчивость, долго передаваемые по частям тела/ответы и жёсткий wall-clock дедлайн — не подтверждены. Тайм-ауты socket/HTTPX не являются общим дедлайном.
7. Mypy тестов/ручного скрипта отдельно не запускался; исходный пакет проверен относительно разрешённых 10 baseline-ошибок.

### Следующий шаг куратора

1. Независимо принять diff и локальные проверки; 10 прежних ошибок mypy оставить отдельной задачей, не смешивать с POS.
2. Выдать отдельную Windows-задачу на сборку EXE и установщика, проверить включение нового stdlib-модуля в комплект и обновление с POS **выключенным**; не изменять рабочие SQLite/HMAC и защищённые ACL.
3. По отдельному разрешению на тестовом компьютере агента: защищённая копия конфига и состояния; настроить отдельный случайный POS-пароль ≥32 символов, конкретный LAN IP и `/32` тестовой кассы; проверить check-config и штатный запуск службы. AGENT_API_KEY остаётся только у агента.
4. На Windows-компьютере агента создать согласованное входящее правило TCP 8765, только Private, remoteip — фактический IP кассы. Не копировать IP-заглушку из документа без замены.
5. Разработчики Cash проверяют BSL и обработчик сканирования; с кассы health с верным/неверным паролем. Затем отдельно согласованная проверка свежего/просроченного QR через настоящее облако и контроль бизнеса/ведущих нулей. Обычный штрихкод не изменять.
6. После этого — штатный кассовый сценарий силами кассира; никакие записи в ONE агентом или тестовыми скриптами не создавать. Это отдельная приёмка, текущие mock-тесты её не заменяют.

### Финальные Git-проверки продолжения

`git diff --check`, код выхода **0**, вывод пустой (`(no output)`). Diff изменённых tracked-файлов также прочитан командой `git diff -- agent/src/poscenter_loyalty_agent/config.py agent/src/poscenter_loyalty_agent/main.py agent/src/poscenter_loyalty_agent/runtime.py agent/README.md docs/AGENT_API.md`, код выхода **0**; изменений вне перечисленного scope не обнаружено.

`git status --short`, код выхода **0**:

```text
 M agent/README.md
 M agent/src/poscenter_loyalty_agent/config.py
 M agent/src/poscenter_loyalty_agent/main.py
 M agent/src/poscenter_loyalty_agent/runtime.py
 M docs/AGENT_API.md
?? C:/
?? agent/src/poscenter_loyalty_agent/pos_server.py
?? agent/tests/pos_qr_smoke.py
?? agent/tests/test_pos_server.py
?? docs/POS_QR_INTEGRATION.md
?? docs/PROMPT_AGENT_POS_QR_2026-10-23.md
?? docs/integrations/
?? reports/AGENT_POS_QR_2026-10-23.md
```

`git diff --stat`, код выхода **0**:

```text
 agent/README.md                              |  1 +
 agent/src/poscenter_loyalty_agent/config.py  | 37 +++++++++++++++++++++++++++-
 agent/src/poscenter_loyalty_agent/main.py    |  2 ++
 agent/src/poscenter_loyalty_agent/runtime.py | 14 +++++++++++
 docs/AGENT_API.md                            |  2 ++
 5 files changed, 55 insertions(+), 1 deletion(-)
```

Неотслеживаемые новый модуль, тесты, документы и отчёт в stat не включены. `C:/` и файл промпта существовали до продолжения и не изменялись.
