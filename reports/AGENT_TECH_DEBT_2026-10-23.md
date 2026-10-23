# Технический долг агента — 2026-10-23

## Результат

Промпт `docs/PROMPT_AGENT_TECH_DEBT_2026-10-23.md` прочитан целиком (77 строк). Исправлены все 10 ошибок mypy и добавлены безопасные агрегаты пропущенных номеров **за текущее чтение** карт/операций.

После правок: **240 passed, 23 skipped**, ruff чистый, **mypy: Success: no issues found in 30 source files**. Windows-служба, настоящий COM/ONE и EXE не проверялись. Полную производственную готовность не заявляю.

## Каждая из 10 ошибок: классификация, исправление, доказательство

Номера «до» — из baseline, «после» — текущий исходник.

| № | Место до → после | Что было и что изменено | Доказательство |
|---|---|---|---|
| 1 | `stage0/data_profile.py:415` → та же ветка | **Аннотация слишком узкая**, не ошибка поведения. Успех возвращает вложенные числовые словари, ошибка — `{"error": "строка"}`. Возвращаемый тип расширен до `dict[str, dict[str, int]] \| dict[str, str]`; старый некорректный ignore удалён. Форма отчёта и запросы не менялись. | `test_recorder_profile_error_keeps_existing_wire_shape`: до и после сохраняется тот же словарь ошибки. Существующий тест fallback профилирования остался зелёным. |
| 2 | `one_com_source.py:512` → `:553`, guard `:550–552` | **Дефект диагностики некорректного источника + проблема сужения типа.** При `Период=None` конвертер вызывал `None.replace` и выдавал AttributeError. Теперь проверяется `isinstance(raw_period, datetime)`; при нарушении — SourceProtocolError с фиксированным безопасным сообщением. Валидная дата идёт в тот же конвертер. | Характеризационный тест ДО поймал AttributeError от None.replace; курсор/ledger не сдвигались. ПОСЛЕ проверены None, строка, число: SourceProtocolError, без курсора/ledger и без completion log. Полная регрессия преобразования дат/COM-адаптера прошла. |
| 3 | `dry_run.py:108` → `:108` | **Лишний аргумент вызова, не падение и не работающий интервал.** HeartbeatResult имеет `extra="ignore"`, поэтому `next_check_in_seconds=30` молча отбрасывался. Удалён только этот аргумент; реальное возвращаемое значение остаётся `{"status":"ok"}`. | `test_dry_run_heartbeat_has_only_declared_status` до и после: status-only, атрибута интервала нет, heartbeat_count=1. Не заявляется исправление несуществовавшего runtime-падения или изменение частоты heartbeat. |
| 4 | `dry_run.py:219` → `:219` | **Статическое переиспользование имени**, не смешивание данных. Первая переменная batch выводилась как пакет карт, затем туда присваивался пакет операций. Выделены имена `cards_batch` и `tx_batch`. | `test_dry_run_keeps_card_and_transaction_batches_separate` до и после с настоящими Pydantic payload и MockCom: 2 карты и 2 операции, по странице из 1 записи, типы/идентификаторы и balance_after правильные. |
| 5 | `dry_run.py:222` → `:222` | Следствие №4: mypy видел список карт в TransactionsSyncPayload. Теперь используется `tx_batch.items`; фактический порядок вызовов и содержимое пакетов не менялись. | Тот же тест до/после и прежний полный dry-run A–D. **Бага отправки карт вместо операций не обнаружено.** |
| 6 | `dry_run.py:272`, `winreg.OpenKey` | **Платформенная типизация.** Чтение Windows registry ограничено веткой `sys.platform == "win32"`, без новых ignore/cast. На Mac раньше ImportError молча перехватывался, теперь попытки импорта нет. На Windows существующий fallback сохраняется. | Mypy на Mac теперь чистый; прежние mock dry-run тесты прошли. Настоящий registry на Windows не проверялся. |
| 7 | `dry_run.py:272`, `winreg.HKEY_CURRENT_USER` | То же платформенное сужение №6, константа и обращение к ней не изменялись. | Та же проверка; не выдаётся за настоящий Windows-тест. |
| 8 | `dry_run.py:273`, `winreg.QueryValueEx` | То же платформенное сужение №6; приоритет env → settings → Windows registry сохранён. | Та же проверка; поведение извлечения секрета не переписывалось. |
| 9 | `windows_service.py:120` → `:123`, `_exe_name_` | **Отсутствующая декларация динамического атрибута.** Добавлено `_exe_name_: ClassVar[str]` без присвоения в теле класса. Прежнее присвоение sys.executable только при frozen не менялось. | `test_frozen_service_attributes_preserved` до/после загружает свежий модуль с тестовым sys.frozen=True: значение ровно sys.executable; SCM не вызывается. |
| 10 | `windows_service.py:121` → `:124`, `_exe_args_` | Добавлено `_exe_args_: ClassVar[str]` без runtime-присвоения в теле класса. Сохраняется прежнее `service-run` в frozen-ветке. | Тот же до/после тест; настоящая pywin32-служба не запускалась. |

`pyproject.toml` не менялся; mypy не ослаблялся, новых type-ignore нет. `runtime.py`, `models.py`, `one_time.py`, форматы состояния/курсоров/HMAC и бизнес-правила фильтрации не менялись.

### Важное о поведении при None

До: всё окно прерывалось AttributeError; не выдавался пакет и не продвигался курсор. После: всё окно прерывается SourceProtocolError; также нет пакета, продвижения курсора или успешного completion log. **Нет** молчаливого пропуска движения или подстановки текущей даты. Существующий runtime уже умеет обрабатывать SourceProtocolError: теперь ошибка классифицируется как нарушение протокола источника, а не Unexpected sync error. Это осознанное изменение диагностики ошибочных данных, не изменение расчёта/отправки валидных операций.

## Счётчики текущего чтения и лог

В `one_com_source.py` добавлены `_barcode_skip_counts` и `_log_read_completed`. Перед основным чтением сохраняются четыре накопленных счётчика, в конце берётся разница. Для карт — `cards_skipped_*`, для операций — `tx_skipped_*`. `self.counters` не сбрасывается и по-прежнему накапливается за жизнь объекта для dry-run.

Обновлены все три прежних места completion log: карты, операции с кандидатами, пустое окно операций (включая окно только с невалидными номерами). При ошибке завершение не логируется. При выдаче страницы из памяти повторного чтения/лога нет.

Настоящий вывод теста на **синтетических данных**, не из клиентской ONE:

```text
ONE read completed: type=cards_snapshot, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=1, non_digits=1, too_short=0, too_long=0), duration=0.045s
ONE read completed: type=transactions_window, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=0, non_digits=0, too_short=1, too_long=1), duration=0.145s
```

Тесты повторяют чтение на том же объекте: в обоих сообщениях 2 пропуска, не 2 и 4; накопленные счётчики при этом удваиваются. Вторая отправка валидных неизменённых/известных записей пуста. Проверено отсутствие номеров, телефонов, имён и идентификаторов из тестовых строк в сообщении.

Не утверждается, что у реальных 7 пропусков именно такая разбивка: настоящая ONE не читалась.

## Изменённые файлы и тесты

Исходники: `agent/src/poscenter_loyalty_agent/{dry_run.py,one_com_source.py,windows_service.py,stage0/data_profile.py}` — изменения описаны выше.

Новый `agent/tests/test_agent_tech_debt.py`:
- до правок исходников 5 характеризационных проверок; ПОСЛЕ 7 случаев за счёт параметризации невалидного периода;
- heartbeat, реальные типы dry-run пакетов и пагинация, отказ при невалидном периоде, прежний формат ошибки Stage 0, frozen-атрибуты без SCM.
- Характеризационная проверка периода **осознанно изменена** с ожидаемого AttributeError на SourceProtocolError; исходный результат до правок сохранён ниже. Остальные характеризационные ожидания не менялись.

В существующем `agent/tests/test_one_com_source.py` изменены **только ожидания формата** в двух старых тестах:
1. `test_diagnostics_cards_read_zero_changes_logs_completion`: точный regex дополнен четырьмя нулевыми причинами и общей суммой, прежние records_read=2 / changes_to_send=0, уровень INFO и один лог сохранены.
2. `test_diagnostics_transactions_read_with_changes_logs_completion`: оба точных regex (непустое и пустое окно) дополнены нулевыми агрегатами; прежние числа/проверки сохранены.

Также в этом файле **добавлены**, а не ослаблены прежние тесты:
- `test_card_skip_log_is_per_read_and_has_no_raw_data` ×2 пары причин: 5 карт, 2 плохих, повторный цикл, накопленные значения, отсутствие ПДн;
- `test_transaction_skip_log_is_per_read_and_has_no_raw_data` ×2: то же для операций;
- `test_all_invalid_transactions_still_log_current_read_counts`: пустые кандидаты после фильтров, повтор, дельта не накапливается в логе;
- `test_buffered_card_page_does_not_repeat_read_or_skip_log`: пагинация буфера без двойного счёта/лога.

Итого **13 новых случаев** относительно baseline: 7+6. Существующие фикстуры и setup/conftest не менялись. Все тестовые мутации — на tmp_path, сеть/ONE/служба не используются.

Документация:
- новый `docs/AGENT_DIAGNOSTICS.md` — формат, значение полей, дельты/накопление, ограничения доказательств и отказ при невалидной дате;
- `docs/HANDOFF_2026-10-19.md` — добавлена явно датированная ссылка на новый формат. Старые реальные строки и исторические показатели **не переписаны**. Прочие найденные упоминания в docs не задают точный формат или являются промптами, не менялись.

## Сырые выводы проверок

Все команды из `/Users/nuras/Desktop/cashback-one`; существующий `backend/.venv/bin/python`, без установки пакетов/нового venv.

### Начальный Git status

`git status --short`, код выхода **0**:

```text
 M agent/packaging/build_installer.py
 M mobile/app.json
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/tests/cardBarcode.test.tsx
?? C:/
?? docs/PROMPT_AGENT_TECH_DEBT_2026-10-23.md
?? docs/PROMPT_APK_1_0_5_2026-10-23.md
```

**Эти изменения существовали до задачи и не изменялись мной.** Их наличие в общем diff --stat ниже не означает работу над packaging/mobile этой задачей.

### Baseline pytest

`PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q -ra`, код выхода **0**:

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
227 passed, 23 skipped in 81.15s (0:01:21)
```

### Baseline ruff

`backend/.venv/bin/python -m ruff check agent`, код выхода **0**:

```text
All checks passed!
```

### Baseline mypy — ожидаемые 10

`PYTHONPATH=agent/src backend/.venv/bin/python -m mypy --config-file agent/pyproject.toml agent/src`, код выхода **1** (ожидаемый baseline):

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
```

### Характеризация ДО изменения исходников

`PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests/test_agent_tech_debt.py -q -s`, код выхода **0**. Некорректное поведение показано явно и перехвачено ожидаемым pytest.raises, поэтому намеренного падающего прогона не было:

```text
HEARTBEAT_CONTRACT=status_only; no next_check_in_seconds at runtime
.DRY_RUN_BATCHES=2 cards + 2 transactions; types separate, pagination intact
.MISSING_PERIOD_BEFORE=AttributeError from None.replace; no cursor/ledger advancement
.RECORDER_PROFILE_ERROR=string value in error dict; annotation was too narrow
.FROZEN_SERVICE_ATTRIBUTES=existing executable + service-run; SCM not called
.
5 passed in 4.15s
```

### После правок — полный pytest

`PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q -ra`, код выхода **0**, тайм-аут инструмента 360000 мс. Запущено subprocess-обёрткой с сохранением stdout/stderr в `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/tech-debt-pytest-after.log`:

```text
.......................................ssssssssssssss................... [ 27%]
..........................................ssss..s....................... [ 54%]
........................................................................ [ 82%]
........................................ssss...                          [100%]
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
240 passed, 23 skipped in 117.53s (0:01:57)

EXIT_CODE=0
```

Skip-список тот же: 14 проверок без ISCC, 5 без внешнего Stage 0 mapping, 4 Windows-only проверки службы. Новых skip нет; они не чинились и не выдаются за passed.

### После правок — ruff и mypy

`backend/.venv/bin/python -m ruff check agent`, код выхода **0**; лог `tech-debt-ruff-after.log` в том же временном каталоге:

```text
All checks passed!

EXIT_CODE=0
```

`PYTHONPATH=agent/src backend/.venv/bin/python -m mypy --config-file agent/pyproject.toml agent/src`, код выхода **0**; лог `tech-debt-mypy-after.log`:

```text
Success: no issues found in 30 source files

EXIT_CODE=0
```

### После правок — показ поведения и примеров логов

Команда, код выхода **0**:

```sh
PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests/test_agent_tech_debt.py agent/tests/test_one_com_source.py::test_card_skip_log_is_per_read_and_has_no_raw_data agent/tests/test_one_com_source.py::test_transaction_skip_log_is_per_read_and_has_no_raw_data -q -s
```

```text
HEARTBEAT_CONTRACT=status_only; no next_check_in_seconds at runtime
.DRY_RUN_BATCHES=2 cards + 2 transactions; types separate, pagination intact
.INVALID_PERIOD_AFTER=SourceProtocolError; no cursor/ledger advancement or completion log
.INVALID_PERIOD_AFTER=SourceProtocolError; no cursor/ledger advancement or completion log
.INVALID_PERIOD_AFTER=SourceProtocolError; no cursor/ledger advancement or completion log
.RECORDER_PROFILE_ERROR=string value in error dict; annotation was too narrow
.FROZEN_SERVICE_ATTRIBUTES=existing executable + service-run; SCM not called
.ONE read completed: type=cards_snapshot, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=1, non_digits=1, too_short=0, too_long=0), duration=0.045s
.ONE read completed: type=cards_snapshot, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=0, non_digits=0, too_short=1, too_long=1), duration=0.569s
.ONE read completed: type=transactions_window, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=1, non_digits=1, too_short=0, too_long=0), duration=0.255s
.ONE read completed: type=transactions_window, records_read=5, changes_to_send=3, skipped_invalid_barcode=2 (empty=0, non_digits=0, too_short=1, too_long=1), duration=0.145s
.
11 passed in 12.73s
```

`git diff --check`, код выхода **0**, вывод пустой (`(no output)`). Diff четырёх изменённых исходников прочитан; команда `git diff -- agent/src/poscenter_loyalty_agent/dry_run.py agent/src/poscenter_loyalty_agent/one_com_source.py agent/src/poscenter_loyalty_agent/stage0/data_profile.py agent/src/poscenter_loyalty_agent/windows_service.py` завершилась кодом **0**.

## Для куратора: что попадёт в следующую EXE 0.2.1

**Меняет наблюдаемое поведение:**
- новые агрегатные поля completion log и понятная классификация некорректного периода как SourceProtocolError;
- на не-Windows dry-run больше не пытается импортировать winreg (раньше ошибка импорта перехватывалась); на Windows путь чтения registry прежний.

**Не меняет бизнес-поведение:**
- фильтр номеров карт, чтение/запросы ONE, конвертация валидных дат, расчёт балансов, отрицательные остатки;
- состав/ACK/пагинация пакетов, runtime, poll/heartbeat и backoff;
- SQLite-схема/формат, курсоры, HMAC/ACL;
- статусный heartbeat dry-run и frozen-параметры запуска службы; их ошибки были статическими/лишним игнорируемым аргументом.

Версия не повышалась и EXE не собирался. Новую сборку/установку/приёмку выполняет отдельная Windows-задача. Не переносить этот локальный результат на уже установленную службу.

## Не проверено

- Windows-only тесты и Inno Setup, реальные winreg/pywin32/SCM/LocalSystem, настоящая Windows-служба.
- Настоящий COM VT_DATE на Windows (новый guard ожидает datetime/его подкласс), реальные строки ONE и распределение 7 невалидных номеров.
- Реальное облако и полный кассовый сценарий.
- EXE 0.2.1, подпись, установщик, установка/обновление/откат.
- Mypy тестов отдельно: проверен настроенный исходный пакет `agent/src`.

Windows-служба не управлялась, ONE/облако не вызывались, конфиги/ключи/рабочие базы не изменялись, сборок/commit/push не было. Чужие изменения packaging/mobile и папка `C:/` сохранены.

## Финальное состояние Git

`git status --short`, код выхода **0**:

```text
 M agent/packaging/build_installer.py
 M agent/src/poscenter_loyalty_agent/dry_run.py
 M agent/src/poscenter_loyalty_agent/one_com_source.py
 M agent/src/poscenter_loyalty_agent/stage0/data_profile.py
 M agent/src/poscenter_loyalty_agent/windows_service.py
 M agent/tests/test_one_com_source.py
 M docs/HANDOFF_2026-10-19.md
 M mobile/app.json
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/tests/cardBarcode.test.tsx
?? C:/
?? agent/tests/test_agent_tech_debt.py
?? docs/AGENT_DIAGNOSTICS.md
?? docs/PROMPT_AGENT_TECH_DEBT_2026-10-23.md
?? docs/PROMPT_APK_1_0_5_2026-10-23.md
?? reports/AGENT_TECH_DEBT_2026-10-23.md
```

`git diff --stat`, код выхода **0**:

```text
 agent/packaging/build_installer.py                 |  25 +++-
 agent/src/poscenter_loyalty_agent/dry_run.py       |  28 ++--
 .../src/poscenter_loyalty_agent/one_com_source.py  |  67 ++++++++--
 .../poscenter_loyalty_agent/stage0/data_profile.py |   4 +-
 .../src/poscenter_loyalty_agent/windows_service.py |   6 +-
 agent/tests/test_one_com_source.py                 | 141 ++++++++++++++++++++-
 docs/HANDOFF_2026-10-19.md                         |   1 +
 mobile/app.json                                    |   4 +-
 mobile/src/i18n/kz.ts                              |   2 +-
 mobile/src/i18n/ru.ts                              |   2 +-
 mobile/tests/cardBarcode.test.tsx                  |   5 +-
 11 files changed, 238 insertions(+), 47 deletions(-)
```

Статистика общая: включает **чужие исходные изменения** packaging/mobile и не включает новые неотслеживаемые тесты/документ/отчёт. Их не добавляли в индекс.
