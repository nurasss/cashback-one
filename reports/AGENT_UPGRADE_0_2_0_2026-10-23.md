# Отчёт по обновлению службы агента POSCENTERLoyaltyAgent 0.1.0 → 0.2.0

**Дата:** 23 октября 2026 г.  
**Компьютер:** Тестовый Windows-компьютер владельца (`DESKTOP-VND8ELJ`)  
**Рабочий каталог:** `C:\Users\ШОУРУМ\Desktop\cashback-one`  
**Исполнитель:** Gemini (exe)  

---

## 1. Проверки до обновления

1. **Состояние репозитория Git:**
   - Коммит: `d8fc1878564a70169d3dd4f2492030d097ee9b4e docs: Windows agent 0.1.0 -> 0.2.0 upgrade prompt`
   - Рабочая копия чистая (`git status --short` пуст).
2. **Проверка артефактов Setup:**
   - `Setup 0.2.0` (`C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe`):
     - Размер: **14 848 085** байт (совпадает)
     - SHA-256: `fe5b799f246250dccf1d731ba3d0efdc9b3e3e03fab7617e70468afffc761ce0` (совпадает)
   - `Setup 0.1.0` (`C:\cashback-stage0\CashbackOneAgent-Setup.exe`):
     - Размер: **14 796 864** байт (совпадает)
     - SHA-256: `4aa0f72eb8955aa5db8c3b845c9b45036e96d28218f19ff511eaba4eea70d56c` (совпадает)
3. **Состояние службы до обновления:**
   - `Get-Service POSCENTERLoyaltyAgent`: статус **`Running`**, тип запуска `Automatic`.
   - `sc.exe qc POSCENTERLoyaltyAgent`:
     - ТИП_СЛУЖБЫ: `WIN32_OWN_PROCESS`
     - ТИП_ЗАПУСКА: `AUTO_START (DELAYED)`
     - ИМЯ_ДВОИЧНОГО_ФАЙЛА: `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
     - УЧЕТНАЯ_ЗАПИСЬ: `LocalSystem`
4. **Версия установленного EXE до обновления:**
   ```text
   poscenter-loyalty-agent 0.1.0
   ```
5. **Метаданные файлов до обновления:**
   - `mapping\stage0_mapping.json`: размер **8377 байт**, `LastWriteTime` `19.10.2026 12:45:19`.
   - `config\.env.service`, `state\agent_state.db`, `state\agent_state.key`: защищены системными DACL (зафиксированы владельцем на шаге 2).
6. **Хвост лога до обновления (`logs\agent.log`):**
   - Зафиксированы стабильные регулярные циклы чтения без ошибок:
     ```text
     2026-10-23 16:14:56 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.297s
     2026-10-23 16:14:56 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.109s
     2026-10-23 16:19:58 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.109s
     2026-10-23 16:19:58 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.109s
     ```

---

## 2. Создание резервной копии (Шаг 2, администратор)

1. **Остановка службы:**
   Служба `POSCENTERLoyaltyAgent` остановлена владельцем: статус **`Stopped`**.
2. **Каталог резервной копии:**
   Создан уникальный каталог:
   `C:\cashback-stage0\backup_upgrade_0_2_0_20261023_162353`
3. **Копирование `ProgramData`:**
   Выполнено через `robocopy "C:\ProgramData\POSCENTER\LoyaltyAgent" "$backupDir\ProgramData" /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL`:
   - Скопировано: **6 файлов из 6**, СБОЙ: **0**.
   - Сохранены дескрипторы безопасности ACL (`/COPY:DATS`).
4. **Копирование `Program Files (x86)`:**
   Выполнено через `robocopy "C:\Program Files (x86)\POSCENTER\LoyaltyAgent" "$backupDir\ProgramFiles" /E /COPY:DAT /R:1 /W:1 /NFL /NDL`:
   - Скопировано: **652 файла из 652**, СБОЙ: **0**.
5. **Сверка контрольных сумм и метаданных файлов до обновления:**
   | Файл | Исходный SHA-256 | SHA-256 в копии | Размер (байт) | Дата изменения | Совпадение |
   |---|---|---|---|---|---|
   | `config\.env.service` | `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` | `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` | 325 | 10/21/2026 11:12:31 | **True** |
   | `state\agent_state.db` | `A8E27D7DF696F0C2E04A85837F83624164E92ABDCFFCBB56B02BD28B6391E109` | `A8E27D7DF696F0C2E04A85837F83624164E92ABDCFFCBB56B02BD28B6391E109` | 2 572 288 | 10/23/2026 16:23:01 | **True** |
   | `state\agent_state.key` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | 32 | 10/19/2026 18:19:44 | **True** |
   | `mapping\stage0_mapping.json` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | 8377 | 10/19/2026 12:45:19 | **True** |

---

## 3. Установка версии 0.2.0 (Шаг 3)

1. Запущен инсталлятор `C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe`.
2. В мастере установки выбран режим по умолчанию:  
   **«Сохранить существующие настройки подключения и синхронизации (Рекомендуется)»**.
3. Установщик заменил исполняемые файлы в `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\`, сохранил конфигурацию и базу состояния в `C:\ProgramData\POSCENTER\LoyaltyAgent\`, и запустил службу `POSCENTERLoyaltyAgent`.

---

## 4. Проверки после обновления (Шаг 4)

1. **Статус службы:**
   - `Get-Service POSCENTERLoyaltyAgent`: **`Running`**, `StartType: Automatic`.
   - `sc.exe qc POSCENTERLoyaltyAgent`:
     - ТИП_ЗАПУСКА: `AUTO_START (DELAYED)`
     - ИМЯ_ДВОИЧНОГО_ФАЙЛА: `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
     - УЧЕТНАЯ_ЗАПИСЬ: `LocalSystem`
2. **Версия установленного EXE:**
   ```text
   poscenter-loyalty-agent 0.2.0
   ```
3. **Сверка контрольных сумм после обновления:**
   - `config\.env.service`: `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.key`: `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` — **совпадает побайтно (Match: True)**;
   - `mapping\stage0_mapping.json`: `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.db`: размер **2 572 288 байт** (идентичен бэкапу, файл удерживается блокировкой SQLite запущенной службы).
4. **Статус агента (`CashbackOneAgent.exe status`):**
   ```text
   === POSCENTER Loyalty Agent Operational Status ===
   State DB Path:                 C:\ProgramData\POSCENTER\LoyaltyAgent\state\agent_state.db
   Cards Cursor Status:           set
   Transactions Cursor Status:    set
   Last Successful Sync:          2026-10-19 15:42:09.959806+00:00
   Last Heartbeat:                2026-10-23 11:36:32.576054+00:00
   Last Error:                    (none)
   POS-сервис: выключен, 0.0.0.0:8765
   ```
   - Курсоры карт и транзакций сохранены: **`set`**.
   - Ошибок нет: `Last Error: (none)`.
   - `POS-сервис: выключен`.
5. **Проверка портов:**
   - Порт 8765: **не слушается** (`Get-NetTCPConnection` вернул пустоту).
   - Порт 18765: **не слушается**.
6. **Наблюдение за работой службы (не менее 12 минут):**
   - Время старта версии 0.2.0: **`2026-10-23 16:27:29`**.
   - Лог старта:
     ```text
     2026-10-23 16:27:29 [INFO] [poscenter_loyalty_agent.windows_service] Starting POSCENTERLoyaltyAgent via Windows Service Manager...
     2026-10-23 16:27:29 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'balance_after' is CANDIDATE: enabled via sequential calculation
     2026-10-23 16:27:29 [INFO] [poscenter_loyalty_agent.runtime] Starting POSCENTER Loyalty Agent v0.2.0 (adapter_mode=com, interval=300s)
     ```
   - Строка `POS service started` **отсутствует** (POS-сервис корректно выключен по умолчанию).
   - **Цикл 1 (16:27:55 - 16:27:56):**
     - `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=24.938s`
     - `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.688s`
   - **Цикл 2 (16:32:58):**
     - `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.907s`
     - `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.313s`
   - **Цикл 3 (16:38:00):**
     - `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.484s`
     - `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.125s`
   - **Ошибки и Traceback отсутствуют.**

---

## 5. План отката (на случай необходимости)

В случае выявления сбоев откат выполняется следующими действиями в админ-PowerShell:
1. Запустить инсталлятор версии 0.1.0:
   `Start-Process -FilePath "C:\cashback-stage0\CashbackOneAgent-Setup.exe"`
   Выбрать пункт **«Сохранить существующие настройки подключения и синхронизации»**.
2. Если повреждена база состояния:
   ```powershell
   Stop-Service POSCENTERLoyaltyAgent
   robocopy "C:\cashback-stage0\backup_upgrade_0_2_0_20261023_162353\ProgramData" "C:\ProgramData\POSCENTER\LoyaltyAgent" /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL
   Start-Service POSCENTERLoyaltyAgent
   ```

---

## 6. Список «не проверено»

1. **Облачная сторона (VPS):**
   - Отображение версии агента `0.2.0` в heartbeat на сервере;
   - Фиксация свежего `last_seen_at` и сохранение количества карт/операций (1704/9747).  
   *(Проверяется куратором через SQL READ ONLY на `kz-vps`, так как агент к серверу напрямую доступ не имеет)*.
2. **Перезагрузка операционной системы Windows:**
   - Автоматический отложенный запуск службы после перезагрузки ОС (ранее был подтверждён для 0.1.0, для 0.2.0 не выполнялся во избежание прерывания работы).
3. **Кассовый сценарий:**
   - Закрытие смены на кассе POSCENTER Cash и поступление реальных новых движений в ONE.
4. **Сетевой доступ к POS-серверу:**
   - Взаимодействие с внешними кассами по локальной сети при включённом POS-сервисе (сервис в данной версии штатно выключен).
