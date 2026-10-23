# Промпт исполнителю (Windows): сборка агента 0.2.1 и установщика — 2026-10-23

Ты работаешь на **Windows-компьютере владельца** (`DESKTOP-VND8ELJ`). Репозиторий: `C:\Users\ШОУРУМ\Desktop\cashback-one`, PowerShell без повышения прав. Общайся и пиши отчёт по-русски. Перед каждым действием коротко пиши, на каком компьютере и в какой папке выполняешь команду.

Процедура та же, что у принятой сборки 0.2.0. Прочитай целиком **`docs/PROMPT_AGENT_EXE_0_2_0_2026-10-23.md`** и **`reports/AGENT_EXE_0_2_0_2026-10-23.md`** и повтори тот же порядок с отличиями ниже. Где этот промпт отличается от промпта 0.2.0 — прав этот.

## Что нового в 0.2.1 (относительно установленной 0.2.0)

Из `reports/AGENT_TECH_DEBT_2026-10-23.md` и `docs/AGENT_DIAGNOSTICS.md`:
- В строке лога `ONE read completed` появились агрегаты текущего цикла: `skipped_invalid_barcode=N (empty=…, non_digits=…, too_short=…, too_long=…)`. Только числа.
- В окне операций `Период` из 1С теперь обязан быть `datetime`. Иначе окно падает с `SourceProtocolError` вместо прежнего `AttributeError`.
- 10 ошибок mypy исправлены. Синхронизация, курсоры, HMAC, SQLite и POS-сервис по смыслу не менялись.
- `agent/packaging/build_installer.py` теперь **сам** кладёт копию в `C:\cashback-stage0\agent-<версия>\CashbackOneAgent-Setup-<версия>.exe` и **никогда не перезаписывает** существующий файл. Прежний перехват копирования больше не нужен — **не подменяй и не патчи скрипт**.

## Отличия от сборки 0.2.0

1. **Коммит.** `git pull --ff-only origin main`, затем `git log -1 --format=%H` должен совпасть с хешем, который владелец передаст вместе с промптом. Проверь версию: `git grep -n "0.2.1" agent/pyproject.toml agent/src/poscenter_loyalty_agent/__init__.py agent/packaging/installer.iss agent/packaging/verify_dist.py` — все четыре.
2. **Тесты на Windows** (`C:\cashback-venv`):
   - `pytest agent/tests -q` — ожидается **263 passed** (240 на Mac + 23 Windows-only), 0 failed. Если число другое, но failed = 0 — объясни расхождение. Любой failed — СТОП;
   - `ruff check agent` — чисто;
   - если в `C:\cashback-venv` есть mypy — `mypy --config-file agent/pyproject.toml agent/src` → `Success`. Если mypy нет — так и напиши, не ставь.
3. **Обязательная проверка типа даты COM.** В этом же venv, где pywin32 той же версии, что попадёт в EXE:
   ```powershell
   & 'C:\cashback-venv\Scripts\python.exe' -c "import datetime, pywintypes; print(pywintypes.TimeType, issubclass(pywintypes.TimeType, datetime.datetime))"
   ```
   И то же через `C:\cashback-build-venv\Scripts\python.exe`, где собирается EXE. Нужно `True` в обоих. **`False` — СТОП**: новая проверка в 0.2.1 остановит синхронизацию операций на реальной ONE. Сборку в этом случае не продолжать.
4. **Сборка EXE и `verify_dist.py`** — как в 0.2.0, `verify_dist` уже ждёт 0.2.1.
5. **Установщик:** `build_installer.py` как есть. Ожидается:
   - `agent\packaging\output\CashbackOneAgent-Setup.exe`;
   - строка `Copied Setup artifact to C:\cashback-stage0\agent-0.2.1\CashbackOneAgent-Setup-0.2.1.exe`.

   Перед запуском убедись, что `C:\cashback-stage0\agent-0.2.1\` нет или она пуста. Если скрипт напишет `Kept existing …` — СТОП: там уже что-то лежит.

   После сборки проверь хеши, они не должны измениться:
   - `C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe` — 14 848 085 байт, SHA-256 `fe5b799f246250dccf1d731ba3d0efdc9b3e3e03fab7617e70468afffc761ce0`;
   - `C:\cashback-stage0\CashbackOneAgent-Setup.exe` (0.1.0) — 14 796 864 байт, SHA-256 `4aa0f72eb8955aa5db8c3b845c9b45036e96d28218f19ff511eaba4eea70d56c`.
6. **Изолированная проверка собранного EXE** — как в 0.2.0, но в **новой** папке `C:\cb-pos-smoke-021\` (если существует и не пуста — СТОП). `C:\cb-pos-smoke\` от 0.2.0 не трогать.
   - `--version` → `0.2.1`;
   - `check-config` и `status`: пути только внутри `C:\cb-pos-smoke-021\`;
   - POS-сервис на `127.0.0.1:18765`: health 200, неверный пароль 401, QR при закрытом облаке 503, кривой QR 400;
   - лог без пароля, ключа и полного токена;
   - служба `POSCENTERLoyaltyAgent` (сейчас **0.2.0**) всё это время Running, `config` и `mapping` не менялись.

   Строку `ONE read completed` в режиме `stub` проверить нельзя: новый формат лога проверим при обновлении службы на реальной ONE.

## Ограничения

Те же, что в промпте 0.2.0:
- **Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**
- Не устанавливать и не обновлять службу, не запускать Setup, не читать `.env.service`, ключи и строку подключения, не трогать ONE, состояние, курсоры, ACL, Firewall.
- Не менять код и `agent/packaging/*`. Не удалять прежние Setup, бэкапы и `C:\cashback-stage0\*`, `C:\cb-pos-smoke\`, `C:\cb-keys`.
- Без публикации Release и загрузки на сайт.
- Отчёт можно отправить в GitHub **только** им самим: `git status --short` должен показывать только `reports/AGENT_EXE_0_2_1_2026-10-23.md`; затем `git add` этого файла, commit, push. Иначе — СТОП.

## Отчёт

`reports/AGENT_EXE_0_2_1_2026-10-23.md` (копия в `C:\cashback-stage0\agent-0.2.1\`) в формате отчёта 0.2.0, плюс:
- результат проверки `pywintypes.TimeType` в обоих venv;
- вывод `build_installer.py` о копировании;
- хеши прежних Setup после сборки.

Не пиши «полностью готово» без доказательств.
