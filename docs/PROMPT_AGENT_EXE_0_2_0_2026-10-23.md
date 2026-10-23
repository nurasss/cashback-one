# Промпт исполнителю (Windows): сборка агента 0.2.0 и установщика — 2026-10-23

Ты работаешь на **Windows-компьютере владельца**. Репозиторий: `C:\Users\ШОУРУМ\Desktop\cashback-one`, PowerShell, консоль обычно без повышения прав. Общайся и пиши отчёт по-русски. Перед каждым действием коротко пиши, на каком компьютере и в какой папке выполняешь команду.

## Цель

Собрать **агент 0.2.0** (добавлен выключенный по умолчанию POS-сервис для динамического QR; см. `docs/POS_QR_INTEGRATION.md`) в PyInstaller onedir x86 и установщик Inno Setup. Проверить сборку **изолированно**. **Не устанавливать** и не обновлять службу на этом компьютере: это отдельный следующий шаг после приёмки куратора.

## Что известно (из `AGENTS.md`, `docs/HANDOFF_2026-10-21.md`)

| Что | Где |
|---|---|
| Agent Python (тесты), x86 | `C:\cashback-venv\Scripts\python.exe` |
| Build Python (PyInstaller), x86 | `C:\cashback-build-venv\Scripts\python.exe` |
| Inno Setup | `C:\cb-build\tools\innosetup\ISCC.exe` |
| Скрипты сборки | `agent/packaging/build_exe.py`, `verify_dist.py`, `build_installer.py`, `installer.iss`, `CashbackOneAgent.spec` |
| Установленная служба (НЕ трогать) | `POSCENTERLoyaltyAgent`, `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe service-run`, версия 0.1.0 |
| Данные службы (НЕ трогать, не читать секреты) | `C:\ProgramData\POSCENTER\LoyaltyAgent\` (`config\.env.service`, `state\agent_state.db`, `.key`, `.lock`, `mapping\`) |
| Прежний Setup 0.1.0 | `C:\cashback-stage0\CashbackOneAgent-Setup.exe`, SHA-256 `4aa0f72eb8955aa5db8c3b845c9b45036e96d28218f19ff511eaba4eea70d56c` |

Версия 0.2.0 уже выставлена в исходниках: `agent/pyproject.toml`, `__init__.py`, `config.py` (`agent_version`), `installer.iss` (`MyAppVersion`), `verify_dist.py`. Установщик при обновлении по умолчанию сохраняет настройки и блокирует смену подключения при наличии `agent_state.db` — это не менять.

## Шаги

1. **Код.** `git status`. Локальные изменения, кроме известной `C:/`-подобной мелочи, — СТОП. Затем `git fetch` и `git pull --ff-only origin main`. Нужен коммит куратора с версией 0.2.0: `git log -1 --format=%H` должен совпасть с хешем, который владелец передаст вместе с промптом. Проверь `git grep -n '0.2.0' agent/pyproject.toml agent/src/poscenter_loyalty_agent/__init__.py agent/packaging/installer.iss`.
2. **Место на диске.** `Get-PSDrive C`. Меньше 3 ГБ свободно — СТОП.
3. **Тесты на Windows.** Здесь пройдут и Windows-тесты, которые на Mac пропускались, и POS-тесты на настоящих Windows-сокетах.
   - `& 'C:\cashback-venv\Scripts\python.exe' -m pytest agent/tests -q`
   - `& 'C:\cashback-venv\Scripts\python.exe' -m ruff check agent`

   Нужна зависимость, которой нет в venv, — СТОП. Ничего не ставить без разрешения. Любой failed — СТОП.
4. **Сборка EXE.** `& 'C:\cashback-build-venv\Scripts\python.exe' agent/packaging/build_exe.py`, затем `verify_dist.py` тем же Python. `verify_dist` уже ждёт 0.2.0.
5. **Установщик.** `build_installer.py` с ISCC из таблицы (как он принимает путь к ISCC — посмотри в самом скрипте). Новый Setup **не** должен перезаписать прежний `C:\cashback-stage0\CashbackOneAgent-Setup.exe`. Результат скопируй в `C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe`. Перед этим проверь, что папки нет или она пуста.
6. **Изолированная проверка собранного EXE** (`agent/packaging/dist/CashbackOneAgent/CashbackOneAgent.exe`, **не** установленный в Program Files):
   - Создай `C:\cb-pos-smoke\` (если существует и не пуста — СТОП), внутри `pd\POSCENTER\LoyaltyAgent\config\.env.service` с **выдуманными** значениями:
     - `AGENT_ENV='development'`;
     - `AGENT_CLOUD_BASE_URL='http://127.0.0.1:9'` — заведомо закрытый порт;
     - `AGENT_API_KEY='synthetic-not-real-…'`;
     - `ONE_ADAPTER_MODE='stub'`;
     - `AGENT_POS_SERVER_ENABLED='true'`;
     - `AGENT_POS_LISTEN_HOST='127.0.0.1'`;
     - `AGENT_POS_LISTEN_PORT='18765'`;
     - `AGENT_POS_TOKEN=` — случайные 40 символов, сгенерируй, в отчёт не печатай;
     - `AGENT_POS_ALLOWED_NETWORKS='127.0.0.0/8'`.

     Если `development` не принимает `http://` или нужен другой ключ — ориентируйся на `config.py` и сообщи, что поменял.
   - Запускай **только** в отдельном процессе PowerShell, где `$env:ProgramData='C:\cb-pos-smoke\pd'`, рабочая папка `C:\cb-pos-smoke`, и явно `AGENT_STATE_DB_PATH`/`AGENT_LOG_DIR` внутри `C:\cb-pos-smoke\`. Перед запуском выведи, какой путь к конфигу и состоянию агент реально использует (`check-config`/`status`), и убедись, что это **не** `C:\ProgramData\…`. Иначе — СТОП, не запускать `run`.
   - `CashbackOneAgent.exe --version` → `0.2.0`; `check-config` → ок; `status` показывает «POS-сервис: включён, 127.0.0.1:18765» без пароля.
   - `CashbackOneAgent.exe run` в фоне. Затем:
     - `Invoke-WebRequest`/`curl.exe` на `GET http://127.0.0.1:18765/v1/health` с `X-Pos-Token` → 200 `{"status":"ok"}`;
     - то же с неверным паролем → 401;
     - `POST /v1/qr/resolve` с синтетическим `{"token":"C1AAAAAAAAAAAAAAAAAAAAAAAA"}` → 503 `CLOUD_UNAVAILABLE` (облако закрыто — это и проверяем);
     - кривой токен → 400.

     Пароль передавай из переменной, а не текстом в команде, которая попадёт в отчёт.
   - Останови процесс штатно (Ctrl+C или завершение по PID этого процесса — **только своего**). Проверь, что порт 18765 освобождён. Проверь логи в `C:\cb-pos-smoke\`: нет пароля, ключа и полного токена.
   - Убедись, что установленная служба `POSCENTERLoyaltyAgent` всё это время работала (`Get-Service`), и что файлы в `C:\ProgramData\POSCENTER\LoyaltyAgent\` не менялись. Сравни `LastWriteTime` `config\.env.service` и `mapping\` до и после. `state\` может меняться самой службой — это нормально, укажи.
   - Папку `C:\cb-pos-smoke\` после проверки оставь (в ней только синтетика), путь укажи в отчёте.
7. **Артефакты.** Размер и SHA-256 нового Setup, `CashbackOneAgent.exe` и итоговой папки `dist`. Разрядность x86, как раньше. Сравни размер с Setup 0.1.0 (14 796 864 байт).

## Ограничения

- **Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**
- **Не устанавливать, не обновлять, не останавливать и не перезапускать** службу `POSCENTERLoyaltyAgent`. Не запускать Setup. Не читать и не печатать `C:\ProgramData\POSCENTER\LoyaltyAgent\config\.env.service`, ключи, строку подключения. Не трогать ONE (только чтение), `agent_state.db`, HMAC-ключ, курсоры, ACL.
- Не создавать правила Windows Firewall на этом шаге.
- Не менять код и `agent/packaging/*`. Если сборка без изменений невозможна — СТОП и объясни.
- Без commit/push, без публикации Release, без загрузки на сайт.
- Не удалять прежние Setup, бэкапы и `C:\cashback-stage0\*`.
- Не трогать `C:\cb-keys`.

## Отчёт

Сохрани в репозитории `reports/AGENT_EXE_0_2_0_2026-10-23.md`, копию положи в `C:\cashback-stage0\agent-0.2.0\`. В отчёте:
- коммит;
- сырые выводы тестов, ruff, сборки и `verify_dist`;
- пути, размеры и SHA-256 артефактов;
- результаты изолированной проверки с кодами ответов;
- подтверждение, что служба и её конфиг не тронуты;
- список «не проверено»: установка/обновление поверх 0.1.0, доступ с кассы по сети, Firewall, реальная касса.

Не пиши «полностью готово» без доказательств.
