# Отчёт: Установщик агента — защищённый ключ и проверка 1С (Задача E, версия 0.3.0) — 2026-11-04

Выполнены все требования промпта `docs/PROMPT_AGENT_INSTALLER_SECRETS_2026-11-04.md` на платформе macOS в репозитории `/Users/nuras/Desktop/cashback-one`.

---

## 1. Изменённые и созданные файлы

### Модули агента (Python)
- `agent/src/poscenter_loyalty_agent/__init__.py` — обновление версии до `0.3.0`.
- `agent/src/poscenter_loyalty_agent/dpapi.py` (новый) — модуль Windows DPAPI (`CryptProtectData`, `CryptUnprotectData`) через Win32 `ctypes` с областью `CRYPTPROTECT_LOCAL_MACHINE`, фиксированной солью `POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1`, освобождением памяти `LocalFree`, поддержкой мок-бэкенда для кроссплатформенного тестирования на не-Windows и полной защитой от утечек секретов в логах и исключениях.
- `agent/src/poscenter_loyalty_agent/config.py` — обновление `agent_version` до `0.3.0`, добавление полей `agent_api_key_dpapi`, `one_password`, `one_password_dpapi`, скрытие секретов из `repr`/`str` (`repr=False`), расшифровка DPAPI при загрузке, сохранение совместимости с открытыми ключами/паролями 0.2.2 с выводом предупреждения в лог без утечки значений, запрет одновременного указания открытого и зашифрованного значения.
- `agent/src/poscenter_loyalty_agent/one_check.py` (новый) — безопасная проверка подключения к файловой базе 1С (`check-one`): таймаут 30 секунд, строго только на чтение, запрет обращения к документам/регистрам, классификация кодов (`ok`, `com_not_registered`, `db_not_found`, `auth_failed`, `db_locked`, `timeout`, `unknown`) без вывода пути/логина/пароля/трассировок.
- `agent/src/poscenter_loyalty_agent/main.py` — регистрация команды `check-one` с параметрами `--db-path`, `--user`, `--password-stdin`, `--output-file`, `--timeout` (без `--password` в CLI-аргументах: пароль считывается из переменной окружения `ONE_PASSWORD` или stdin), однострочный вывод JSON `{"code": "..."}`.

### Конфигурация сборки и упаковки
- `agent/pyproject.toml` — версия `0.3.0`.
- `agent/packaging/CashbackOneAgent.spec` — добавление `poscenter_loyalty_agent.dpapi` и `poscenter_loyalty_agent.one_check` в `hiddenimports`.
- `agent/packaging/verify_dist.py` — проверка версии `0.3.0` в `--version`.
- `agent/packaging/acl_hardening.iss` — Win32 API точный DACL (`SYSTEM` и `Administrators`), разделяемый `LocalFree`.
- `agent/packaging/config_serializer.iss` — реализация функций DPAPI на Pascal Script (`ProtectSecretDPAPI`, `UnprotectSecretDPAPI`), сериализация зашифрованных значений (`SerializeConfigToFile`), процедура обновления существующего `.env.service` на месте (`UpdateExistingConfigFile`) с защищённым DACL через временный файл, парсинг и очистка connection string от `Pwd=`.
- `agent/packaging/installer.iss` — версия `0.3.0`, распаковка probe-бинарника агента во `{tmp}\agent_probe`, кнопка «Проверить подключение» на `PageOne` и при обновлении на `PageUpgrade`, передача пароля через переменную окружения `ONE_PASSWORD`, поля опциональной смены ключа агента и пароля 1С при обновлении с сохранением настроек, подтверждение продолжения при непроверенном подключении к 1С.
- `agent/packaging/harness_serializer.iss` — поддержка режимов тестирования `Mode=update` и `Mode=dpapi_test`.

### Документация и тесты
- `docs/AGENT_INSTALLATION.md` (новый) — инструкция по установке, обновлению и предупреждение об откате на 0.2.2.
- `agent/tests/test_dpapi.py` (новый) — 6 тестов шифрования/дешифрования, обработки ошибок, устойчивости к утечкам.
- `agent/tests/test_config_dpapi.py` (новый) — 8 тестов загрузки DPAPI-конфигурации, предупреждений об открытых значениях, валидации конфликтов и отсутствия секретов в `repr`/CLI.
- `agent/tests/test_check_one.py` (новый) — 10 тестов всех кодов возврата `check-one`, передачи пароля через env/stdin и JSON-вывода.

---

## 2. Сырой вывод проверок до и после правок

### До правок (Baseline на macOS)

```text
cd agent && ../.venv/bin/pytest -q
.......................................ssssssssssssss................... [ 27%]
..........................................ssss..s....................... [ 54%]
........................................................................ [ 81%]
.........................................ssss...                         [100%]
241 passed, 23 skipped in 71.50s (0:01:11)
```

```text
cd agent && ../.venv/bin/ruff check .
All checks passed!
```

```text
cd agent && ../.venv/bin/mypy src
Success: no issues found in 30 source files
```

### После правок (Regression)

```text
cd agent && ../.venv/bin/ruff check .
All checks passed!
```

```text
cd agent && ../.venv/bin/mypy src
Success: no issues found in 32 source files
```

```text
cd agent && ../.venv/bin/pytest -q
................................................................ssssssss [ 24%]
ssssss.............................................................ssss. [ 49%]
.s...................................................................... [ 74%]
..................................................................ssss.. [ 99%]
.                                                                        [100%]
266 passed, 23 skipped in 25.92s
```

*(266 passed, 23 skipped — 23 теста пропущены, так как требуют Windows Inno Setup ISCC / Win32 SCM).*

---

## 3. Выбор области DPAPI и его ограничения

### Проверка учётной записи службы
1. В `windows_service.py` служба наследуется от `win32serviceutil.ServiceFramework` с именем `POSCENTERLoyaltyAgent`.
2. В `installer.iss`:
   - Установщик компилируется с директивой `PrivilegesRequired=admin` и запускается от имени локального администратора.
   - Регистрация службы выполняется через исполняемый файл агента (`CashbackOneAgent.exe service install`), без передачи специфического пользователя.
   - По умолчанию Windows SCM регистрирует службу под системной учётной записью `LocalSystem` (`NT AUTHORITY\SYSTEM`).
   - Дополнительно в `AGENTS.md` зафиксировано: `Служба: POSCENTERLoyaltyAgent, LocalSystem, delayed-auto`.

### Область шифрования
- **Выбран флаг**: `CRYPTPROTECT_LOCAL_MACHINE` (0x00000004) в сочетании с `CRYPTPROTECT_UI_FORBIDDEN` (0x00000001).
- **Причина выбора**:
  - Текущий пользователь (`CurrentUser` DPAPI) связывает мастер-ключ с профилем администратора, запустившего установку. Служба `LocalSystem` работает в изолированном контексте и **не может** расшифровать данные, зашифрованные в профиле пользователя.
  - `CRYPTPROTECT_LOCAL_MACHINE` привязывает ключ шифрования к LSA-секрету конкретного физического компьютера, что позволяет процессу установщика (Administrator) зашифровать секрет, а службе (`LocalSystem`) — расшифровать его при старте.
- **Дополнительная энтропия**:
  - `DPAPI_ENTROPY = b"POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1"` передаётся как `pOptionalEntropy` (`DATA_BLOB`).
  - Соль **не является секретом** (репозиторий публичный, код открыт) и служит исключительно для логического отделения данных агента от других программ на машине.
- **DACL защита (основной локальный барьер)**:
  - Каталог `%ProgramData%\POSCENTER\LoyaltyAgent\config` и файл `.env.service` закрыты защищённым DACL (`acl_hardening.iss`): права полного доступа (`FILE_ALL_ACCESS`) имеют **только** `SYSTEM` (`*S-1-5-18`) и `BUILTIN\Administrators` (`*S-1-5-32-544`). Наследование от родительских папок отключено. Именно DACL защищает файл конфигурации от чтения локальными процессами.

### Что защищает и от чего не защищает:
- **Защищает от**:
  - Чтения открытых ключей и паролей при обычном копировании каталога, бэкапов или случайной публикации файлов на другой компьютер (DPAPI привязан к физической машине).
  - Непривилегированных пользователей и стандартных процессов на данном компьютере (доступ к файлу блокирует строгий DACL).
  - Случайного чтения незашифрованных секретов из резервных копий вне операционной системы.
- **Не защищает от**:
  - Локального администратора и любых процессов, работающих с правами `SYSTEM` или `Administrator` на **этом же** локальном компьютере, которые имеют доступ к файлу через DACL (machine-scope DPAPI расшифровывается в контексте этой машины, а соль публична).

---

## 4. Формат `.env.service` до и после

### До (версия 0.2.2 — открытые секреты):
```dotenv
AGENT_ENV='production'
AGENT_CLOUD_BASE_URL='https://api.cashback-qr.poscenter.kz'
AGENT_API_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
ONE_ADAPTER_MODE='com'
ONE_CONNECTION_STRING='File="C:\1C_data\int";Usr="loyalty_ro";Pwd="secret_password";'
AGENT_POLL_INTERVAL_SECONDS='300'
AGENT_CLAMP_NEGATIVE_BALANCE='false'
```

### После (версия 0.3.0 — зашифрованные секреты DPAPI):
```dotenv
AGENT_ENV='production'
AGENT_CLOUD_BASE_URL='https://api.cashback-qr.poscenter.kz'
AGENT_API_KEY_DPAPI='AQAAANCMnd8BFdERjHoAwE/Cl+sBAAAA...=='
ONE_ADAPTER_MODE='com'
ONE_CONNECTION_STRING='File="C:\1C_data\int";Usr="loyalty_ro";'
ONE_PASSWORD_DPAPI='AQAAANCMnd8BFdERjHoAwE/Cl+sBAAAA...=='
AGENT_POLL_INTERVAL_SECONDS='300'
AGENT_CLAMP_NEGATIVE_BALANCE='false'
```

*Примечание:* Строка `ONE_CONNECTION_STRING` содержит только несекретные параметры (`File` и `Usr`). Пароль 1С вынесен в `ONE_PASSWORD_DPAPI` и подставляется динамически при загрузке агента.

---

## 5. Предупреждение об откате на версию 0.2.2

> **ВНИМАНИЕ:**
> Агент версии 0.2.2 **не умеет** читать `AGENT_API_KEY_DPAPI` и `ONE_PASSWORD_DPAPI`.
> При откате с 0.3.0 на 0.2.2 (через `CashbackOneAgent-Setup-0.2.2.exe`) выбор режима «Сохранить существующие настройки» приведёт к ошибке запуска службы 0.2.2 из-за отсутствия открытого `AGENT_API_KEY`.
> Для отката потребуется либо восстановить резервную копию `.env.service` из бэкапа перед установкой, либо заново ввести открытый ключ и пароль 1С.
> Предупреждение зафиксировано в `docs/AGENT_INSTALLATION.md`.

---

## 6. Что проверить на Windows при сборке 0.3.0

1. **Сборка бинарников**:
   - `python packaging/build_exe.py` (создаёт `dist\CashbackOneAgent\`).
   - `python packaging/build_installer.py` (компилирует `installer.iss` через ISCC в `CashbackOneAgent-Setup.exe` и копирует в `C:\cashback-stage0\agent-0.3.0\CashbackOneAgent-Setup-0.3.0.exe`).
2. **Проверка версии**:
   - `CashbackOneAgent.exe --version` выводит `poscenter-loyalty-agent 0.3.0`.
3. **Новая установка (чистый стенд без .env.service)**:
   - Ввод URL, ключа агента, параметров 1С.
   - Проверка кнопки **«Проверить подключение»**:
     - с неверным паролем 1С → сообщение об ошибке авторизации;
     - с верным паролем 1С → `Подключение к 1С успешно установлено.`;
     - при нажатии «Далее» без проверки → модальный диалог с вопросом «Подключение к 1С не проверено. Продолжить установку?».
   - Успешная установка: файл `.env.service` содержит `AGENT_API_KEY_DPAPI` и `ONE_PASSWORD_DPAPI`, в строке `ONE_CONNECTION_STRING` нет `Pwd=`.
4. **Обновление с 0.2.2 с сохранением настроек**:
   - На компьютере с установленным агентом 0.2.2 запустить `CashbackOneAgent-Setup-0.3.0.exe`.
   - Выбрать «Сохранить существующие настройки».
   - Оставить поля «Новый ключ агента» и «Новый пароль 1С» пустыми.
   - Проверить, что файл `.env.service` обновился на месте: открытые `AGENT_API_KEY` и `Pwd=` зашифрованы в DPAPI, а остальные строки и комментарии остались прежними.
   - Проверить, что база `agent_state.db` и ключ `agent_state.key` не затронуты.
5. **Замена ключа и пароля при обновлении**:
   - При обновлении ввести в поле «Новый ключ агента» новый ключ. Проверить, что обновилась только строка `AGENT_API_KEY_DPAPI`.
   - При вводе нового пароля 1С протестировать кнопку «Проверить подключение».
6. **Работа службы Windows**:
   - Служба `POSCENTERLoyaltyAgent` запускается от `LocalSystem`.
   - В журнале `logs\agent.log` агент стартует с версией `0.3.0`, успешно расшифровывает ключи и выполняет циклы чтения без ошибок.
   - В журнале **отсутствует** предупреждение «ключ хранится открытым текстом» при наличии DPAPI-ключей.

---

## 7. Всё непроверенное

- Сборка исполняемых файлов PyInstaller (`build_exe.py`) и Inno Setup (`ISCC.exe`) не выполнялась, так как работа велась на macOS (нет Windows и ISCC).
- Реальное подключение через `V83.COMConnector` к базе `1Cv8.1CD` не проверялось на практике (COM-коннектор доступен только на Windows). Все тесты выполнены с использованием мок-коннекторов и изолированных файловых фикстур.
- Полномочия службы `LocalSystem` по дешифрованию реального LSA-секрета будут проверены при тестовой установке на Windows.
- Изменения production не производились, git commit и push не выполнялись.

---

## 8. Исправления по приёмке (2026-11-04)

Выполнены три замечания куратора из `docs/PROMPT_AGENT_INSTALLER_SECRETS_FIXES_2026-11-04.md`.

### 1. Изменённые файлы
- `agent/src/poscenter_loyalty_agent/one_check.py`:
  - Добавлены функции инициализации STA-апартамента COM: `_sta_init()` вызывает `pythoncom.CoInitialize()` до любых операций с COM/Dispatch, `_sta_uninit()` вызывает `pythoncom.CoUninitialize()` в блоке `finally`.
  - Заменён `ThreadPoolExecutor` на выделенный фоновый поток-демон `threading.Thread(name="OneCheckWorkerThread", daemon=True)`: при зависании 1С рабочий поток больше не блокирует завершение процесса Python.
  - Добавлен тестовый шов `_ONE_CHECK_TEST_MOCK` для проверки поведения при зависании в отдельном подпроцессе.
- `agent/src/poscenter_loyalty_agent/main.py`:
  - В `cmd_check_one` добавлен гарантированный сброс буферов: `print(result_json, flush=True)`, `f.flush()`, `os.fsync(f.fileno())` для файла вывода, `sys.stdout.flush()`, `sys.stderr.flush()`.
  - В `cli()`: при запуске команды `check-one` в качестве корневого CLI-процесса (`argv is None`) вызывается `os._exit(exit_code)` для немедленного возврата управления установщику даже при наличии заблокированных COM RPC-потоков на уровне ОС.
- `agent/src/poscenter_loyalty_agent/dpapi.py`:
  - Исправлены формулировки в docstring: удалено неверное утверждение о том, что соль защищает от других процессов. Зафиксировано: DPAPI с областью машины защищает при переносе на другой компьютер и в бэкапах; от локального администратора защищает строгий DACL; соль не является секретом и служит только для разделения пространств приложений.
- `docs/AGENT_INSTALLATION.md`:
  - Добавлен раздел «4. Модель безопасности DPAPI» с точным описанием границ защиты (DACL как локальный барьер, machine-scope DPAPI как защита от копирования, открытая соль).
- `agent/tests/test_check_one.py`:
  - Добавлены 4 новых теста:
    1. `test_sta_thread_initialization_order`: проверка вызова `pythoncom.CoInitialize()` строго до создания коннектора и `pythoncom.CoUninitialize()` после.
    2. `test_sta_thread_uninitialization_on_error`: проверка вызова `pythoncom.CoUninitialize()` в блоке `finally` при возникновении ошибки авторизации.
    3. `test_check_one_timeout_returns_promptly`: проверка возврата кода `timeout` за время, близкое к таймауту (0.2 с при задержке фабрики 5 с).
    4. `test_check_one_subprocess_hung_connector_terminates_promptly`: запуск отдельного подпроцесса CLI (`sys.executable -m poscenter_loyalty_agent.main check-one ...`) с имитацией зависания коннектора на 15 секунд и таймаутом 0.3 секунды. Проверено, что подпроцесс завершается за < 1.5 секунды, возвращает код 1, а в stdout и `--output-file` записан `{"code": "timeout"}`.

### 2. Сырой вывод проверок до и после

#### До правок (Baseline перед исправлениями замечаний):
```text
cd agent && ../.venv/bin/ruff check .
All checks passed!
```

```text
cd agent && ../.venv/bin/mypy src
Success: no issues found in 32 source files
```

```text
cd agent && ../.venv/bin/pytest -q
................................................................ssssssss [ 24%]
ssssss.............................................................ssss. [ 49%]
.s...................................................................... [ 74%]
..................................................................ssss.. [ 99%]
.                                                                        [100%]
266 passed, 23 skipped in 29.23s
```

#### После правок:
```text
cd agent && ../.venv/bin/ruff check .
All checks passed!
```

```text
cd agent && ../.venv/bin/mypy src
Success: no issues found in 32 source files
```

```text
cd agent && ../.venv/bin/pytest -q
....................................................................ssss [ 24%]
ssssssssss.............................................................s [ 49%]
sss..s.................................................................. [ 73%]
......................................................................ss [ 98%]
ss...                                                                    [100%]
270 passed, 23 skipped in 25.40s
```

### 3. Как проверено завершение процесса при зависании
1. **На уровне потоков**: В `one_check.py` рабочий поток запускается как демон (`daemon=True`). В отличие от `ThreadPoolExecutor`, Python не вызывает `join()` для потоков-демонов при выходе из интерпретатора. При наступлении таймаута очередь `result_queue.get(timeout=...)` немедленно генерирует `queue.Empty`, и функция возвращает код `timeout`.
2. **На уровне ввода-вывода**: До завершения процесса stdout и файл `--output-file` сбрасываются на диск через `flush()` и системный вызов `os.fsync(fileno)`.
3. **На уровне процесса**: В `main.py` при вызове `check-one` в качестве корневого CLI-процесса (`argv is None`) вызывается `os._exit(exit_code)`, что гарантирует завершение процесса на уровне ОС даже в случае, если сторонний native COM-компонент удерживает внутренние системные потоки.
4. **Тест подпроцесса**: В тесте `test_check_one_subprocess_hung_connector_terminates_promptly` отдельный процесс запускается через `subprocess.run` с таймаутом CLI `--timeout 0.3` и искусственным зависанием коннектора на 15 секунд. Процесс завершается за 1.5 секунды с кодом выхода 1, валидным JSON `{"code": "timeout"}` в stdout и файле результата, не зависая и не дожидаясь окончания 15-секундного ожидания.
