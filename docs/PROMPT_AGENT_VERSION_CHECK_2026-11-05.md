# Промпт исполнителю (Windows): почему облако видит агент 0.1.0 — только чтение, 2026-11-05

Компьютер `KONS2`, репозиторий `C:\Users\ШОУРУМ\Desktop\cashback-one`. Общайся по-русски.

**Только чтение. Ничего не менять, службу не перезапускать. Упало или неожиданно — СТОП и сырой вывод; секреты и ПДн скрыть.**

## Контекст

Обновление до 0.3.0 прошло: `reports/AGENT_UPGRADE_0_3_0_2026-11-05.md`. Куратор проверил облако в 11:27 (READ ONLY). Агент бизнеса `test`:
- `active`;
- свежий `last_seen_at`;
- `last_error` пустой;
- 1711 карт.

Но `agents.version = 0.1.0`. Сервер записывает версию из heartbeat (`version=self.settings.agent_version`). По умолчанию там `0.3.0`, но значение перекрывается переменной окружения `AGENT_VERSION`, если она есть.

## Проверить

1. **[ВЛАДЕЛЕЦ, админ-PowerShell]** В `C:\ProgramData\POSCENTER\LoyaltyAgent\config\.env.service` и в копии `C:\cashback-stage0\backup_upgrade_0_3_0_20261105_110404\ProgramData\config\.env.service` выведи **только строки, начинающиеся с `AGENT_VERSION`** (значение версии не секрет). Для остальных строк выведи только количество. Пример:
   ```powershell
   Select-String -Path <файл> -Pattern '^\s*AGENT_VERSION' | ForEach-Object Line
   ```
2. **Переменные окружения службы и системы:** есть ли `AGENT_VERSION`. Проверь `[Environment]::GetEnvironmentVariable('AGENT_VERSION','Machine')` и раздел реестра службы `HKLM\SYSTEM\CurrentControlSet\Services\POSCENTERLoyaltyAgent`, значение `Environment`, если оно есть. Выводи только имена переменных и значение `AGENT_VERSION`.
3. **[ВЛАДЕЛЕЦ]** `status` установленного агента: строка `Agent Version:` как есть. Остальные строки — только `Cards/Transactions Cursor Status`, `Last Heartbeat`, `Last Error`.
4. **Другие экземпляры:** `Get-CimInstance Win32_Process` с фильтром по `Name -like '*CashbackOneAgent*' -or CommandLine -like '*poscenter_loyalty_agent*'`. Выведи PID, путь к EXE, время запуска и командную строку **без значений после `--`, если там пути к конфигам с ключами**. Ожидается один процесс службы.
5. Строка в журнале агента после старта 0.3.0: `Starting POSCENTER Loyalty Agent v…`. Если в журнале heartbeat пишет версию, покажи её.

## Отчёт

Ответ в чате, отдельный файл не нужен:
- откуда берётся `0.1.0`;
- одна строка «это опасно/неопасно для синхронизации» с обоснованием.

Не исправлять: решение примет куратор.
